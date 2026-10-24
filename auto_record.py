"""Opt-in window-based recording for an explicit executable allowlist."""
import copy
import ntpath
from pathlib import Path
import threading
import time
import uuid
import process_audio

DEFAULTS = {'enabled': False, 'save_on_exit': True, 'apps': []}


def path_key(path):
    return ntpath.normcase(ntpath.normpath(str(path)))


def validate(values):
    result = copy.deepcopy(DEFAULTS)
    for key in ('enabled', 'save_on_exit'):
        value = values.get(key, result[key])
        if not isinstance(value, bool): raise ValueError('Ожидался переключатель: ' + key)
        result[key] = value
    apps = values.get('apps', [])
    if not isinstance(apps, list) or len(apps) > 100:
        raise ValueError('В списке может быть до 100 приложений')
    seen = set()
    for app in apps:
        path = str(app.get('path', '')).strip().strip('"')
        if not ntpath.isabs(path) or ntpath.splitext(path)[1].lower() != '.exe':
            raise ValueError('Выберите полный путь к исполняемому файлу .exe')
        key = path_key(path)
        if key in seen: raise ValueError('Приложение уже есть в списке')
        seen.add(key)
        enabled = app.get('enabled', True)
        if not isinstance(enabled, bool): raise ValueError('Некорректное состояние приложения')
        result['apps'].append({'id': str(app.get('id') or uuid.uuid4().hex),
                               'name': str(app.get('name') or ntpath.basename(path))[:100],
                               'path': path, 'enabled': enabled})
    return result


class AutoRecorder:
    def __init__(self, suite, applications=None, clock=None):
        self.suite = suite; self.replay = suite.replay
        self.applications = applications or process_audio.applications
        self.clock = clock or time.monotonic
        self.lock = threading.RLock(); self.stopped = threading.Event()
        self.settings = validate(suite.cfg.get('auto_record', DEFAULTS))
        self.owner = None; self.previous = None; self.blocked = set()
        self.pending = None; self.pending_at = 0; self.error = ''; self.thread = None

    def state(self):
        return {'settings': copy.deepcopy(self.settings),
                'active': self.owner['name'] if self.owner else None,
                'error': self.error,
                'watching': bool(self.thread and self.thread.is_alive())}

    def configure(self, values):
        settings = validate(values)
        with self.lock:
            self.settings = settings; self.error = ''; self.pending = None
            self.suite.cfg['auto_record'] = copy.deepcopy(settings); self.suite.save_cfg()
            if not settings['enabled'] and self.owner:
                self._finish()
            self.suite.log('auto_record_config', enabled=settings['enabled'], apps=len(settings['apps']))
        return self.state()

    def toggle(self):
        result = self.configure({**self.settings, 'enabled': not self.settings['enabled']})
        self.notice('Автозапись включена' if self.settings['enabled'] else 'Автозапись выключена',
                    'Приложений в списке: ' + str(len(self.settings['apps'])))
        return result

    def notice(self, title, text, kind='success'):
        try:
            if self.suite.desktop: self.suite.desktop.notify(title, text, kind)
        except Exception as error: self.suite.log('auto_record_notification_error', error=str(error))

    def manual(self, operation, args=None):
        with self.lock:
            if operation == 'stop':
                self.blocked.update((path_key(a['path']), a['pid']) for a in self.applications())
                self.replay.auto_owned = False
                result = self.replay.stop()
                self._restore()
                self.owner = None
                return result
            if operation == 'start':
                return self.replay.start()
            if operation == 'configure':
                return self.replay.configure(args)

    def _restore(self):
        if self.previous is not None:
            self.replay.settings = self.previous
            self.suite.cfg['replay'] = copy.deepcopy(self.previous)
            self.suite.save_cfg(); self.previous = None
        self.replay.auto_owned = False

    def _finish(self):
        owner = self.owner; self.owner = None
        try:
            self.replay.stop(preserve=True)
            if self.settings['save_on_exit'] and self.replay.session:
                if not self.replay.saving:
                    self.replay.save({'progress': 0}, allow_stopped=True)
                    self.notice('Момент сохранён', (owner or {}).get('name', 'AFTERPLAY'))
                else:
                    # An in-flight save owns the session until its finally block.
                    deadline = self.clock() + max(120,self.replay.settings['seconds']*2) + 30
                    while self.replay.saving and self.clock() < deadline:
                        time.sleep(.1)
            elif not self.replay.saving:
                self.replay._cleanup_session(self.replay.session); self.replay.session = None
        except Exception as error:
            self.error = 'Сохранение при остановке: ' + str(error)
            self.notice('Не удалось сохранить последний момент', str(error), 'error')
            self.suite.log('auto_record_save_error', error=str(error))
            if not self.replay.saving:
                self.replay._cleanup_session(self.replay.session); self.replay.session = None
        finally:
            self._restore()
            self.suite.log('auto_record_stopped', app=(owner or {}).get('name'))

    def tick(self):
        with self.lock:
            if not self.settings['enabled']: return
            apps = self.applications()
            live = {(path_key(a['path']), a['pid']) for a in apps}
            self.blocked.intersection_update(live)
            allowed = {path_key(a['path']): a for a in self.settings['apps'] if a['enabled']}
            if self.owner:
                identity = self.owner['key']
                present = next((a for a in apps if (path_key(a['path']), a['pid']) == identity and not a['minimized']), None)
                if not present or identity[0] not in allowed or self.replay.phase in {'off', 'error'}:
                    if present and self.replay.phase == 'error': self.blocked.add(identity)
                    self._finish()
                return
            if self.replay.phase in {'starting', 'recording', 'stopping'} or self.replay.saving:
                return  # Never replace a manually started recording.
            candidates = [a for a in apps if path_key(a['path']) in allowed
                          and (path_key(a['path']), a['pid']) not in self.blocked
                          and not a['minimized'] and a['width'] > 0 and a['height'] > 0]
            if not candidates:
                self.pending = None; return
            # Allowlist order is the stable priority when several windows are open.
            order = list(allowed)
            candidates.sort(key=lambda a: (order.index(path_key(a['path'])), a['pid']))
            app = candidates[0]; identity = (path_key(app['path']), app['pid'])
            if identity != self.pending:
                self.pending = identity; self.pending_at = self.clock(); return
            if self.clock() - self.pending_at < 2: return
            self.pending = None
            self.previous = copy.deepcopy(self.replay.settings)
            try:
                self.replay.configure({'capture_mode': 'window', 'window_hwnd': app['hwnd'],
                                       'audio_follow_window': True, 'game_pid': app['pid']})
                self.replay.auto_owned = True
                self.owner = {'key': identity, 'name': allowed[identity[0]]['name']}
                self.replay.start(); self.error = ''
                self.suite.log('auto_record_started', app=self.owner['name'], path=app['path'], pid=app['pid'])
                self.notice('Автозапись началась', self.owner['name'] + ' · сохранить: ' +
                            self.suite.cfg.get('hotkeys', {}).get('save', 'Ctrl+Alt+F10'))
            except Exception as error:
                self.blocked.add(identity); self.owner = None; self.error = str(error)
                self.replay.auto_owned = False
                self.replay.stop(preserve=False)
                self._restore()
                self.notice('Не удалось включить автозапись', str(error), 'error')
                self.suite.log('auto_record_start_error', path=app['path'], error=str(error))

    def start(self):
        def watch():
            while not self.stopped.wait(1):
                if not self.settings['enabled']: continue
                try: self.tick()
                except Exception as error:
                    self.error = str(error); self.suite.log('auto_record_error', error=str(error))
        self.thread = threading.Thread(target=watch, daemon=True); self.thread.start()

    def shutdown(self):
        self.stopped.set()
        if self.thread: self.thread.join(timeout=3)
        with self.lock:
            if self.owner: self._finish()
