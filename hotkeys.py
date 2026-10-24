"""Global shortcuts with atomic rebinding on a dedicated Win32 message thread."""
import ctypes
from ctypes import wintypes
import queue
import threading
import time

DEFAULTS = {'save': 'Ctrl+Alt+F10', 'auto': 'Ctrl+Alt+F9'}
SPECIAL = {'Space': 0x20, 'Insert': 0x2D, 'Delete': 0x2E, 'Home': 0x24,
           'End': 0x23, 'PageUp': 0x21, 'PageDown': 0x22, 'Up': 0x26,
           'Down': 0x28, 'Left': 0x25, 'Right': 0x27, 'Pause': 0x13}


def parse(value):
    if not isinstance(value, str):
        raise ValueError('Ожидалась комбинация клавиш')
    parts = value.replace(' ', '').split('+')
    aliases = {'control': 'Ctrl', 'ctrl': 'Ctrl', 'alt': 'Alt', 'shift': 'Shift'}
    mods = []
    for part in parts[:-1]:
        mod = aliases.get(part.lower())
        if not mod or mod in mods:
            raise ValueError('Используйте Ctrl, Alt, Shift и одну клавишу')
        mods.append(mod)
    key = parts[-1]
    if key.upper().startswith('F') and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        key = 'F' + str(int(key[1:])); vk = 0x6F + int(key[1:])
    elif len(key) == 1 and key.upper() in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789':
        key = key.upper(); vk = ord(key)
    else:
        key = next((k for k in SPECIAL if k.lower() == key.lower()), '')
        if not key:
            raise ValueError('Выберите букву, цифру, F1–F24 или служебную клавишу')
        vk = SPECIAL[key]
    if not mods and not (key.startswith('F') and key[1:].isdigit()):
        raise ValueError('Для этой клавиши добавьте Ctrl, Alt или Shift')
    if key == 'F12':
        raise ValueError('F12 зарезервирована Windows; выберите другую клавишу')
    mask = sum({'Alt': 1, 'Ctrl': 2, 'Shift': 4}[m] for m in mods)
    canonical = '+'.join([m for m in ('Ctrl', 'Alt', 'Shift') if m in mods] + [key])
    return canonical, mask, vk


def validate(settings):
    result = {k: parse(settings.get(k, v))[0] for k, v in DEFAULTS.items()}
    if len(set(result.values())) != len(result):
        raise ValueError('Для двух действий нужны разные комбинации')
    return result


class GlobalHotkeys:
    def __init__(self, callbacks, logger):
        self.callbacks = callbacks; self.log = logger
        self.commands = queue.Queue(); self.ready = threading.Event()
        self.registered = {}; self.actions = {}; self.next_id = 100
        self.tid = None; self.error = ''; self.ok = False
        self.desired = {}; self.edit_until = 0
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        if not self.ready.wait(5):
            raise ValueError('Поток горячих клавиш не отвечает')

    def configure(self, values):
        values = validate(values)
        return self._request('configure', values)

    def editing(self, enabled):
        return self._request('editing', bool(enabled))

    def _request(self, command, values):
        done = threading.Event(); result = {}
        self.commands.put((command, values, done, result))
        if not ctypes.windll.user32.PostThreadMessageW(self.tid, 0x8001, 0, 0):
            raise ValueError('Не удалось обновить горячие клавиши')
        if not done.wait(5):
            raise ValueError('Горячие клавиши не ответили вовремя')
        if result.get('error'):
            raise ValueError(result['error'])
        return values

    def _bind(self, values):
        user = ctypes.windll.user32
        additions = {}
        try:
            for key in values.values():
                if key in self.registered or key in additions:
                    continue
                _, mods, vk = parse(key); self.next_id += 1
                if not user.RegisterHotKey(None, self.next_id, mods | 0x4000, vk):
                    raise ValueError(key + ' уже занята другой программой. Выберите другую комбинацию.')
                additions[key] = self.next_id
        except Exception:
            for identifier in additions.values():
                user.UnregisterHotKey(None, identifier)
            raise
        keep = set(values.values())
        for key, identifier in self.registered.items():
            if key not in keep:
                user.UnregisterHotKey(None, identifier)
        self.registered = {k: v for k, v in self.registered.items() if k in keep}
        self.registered.update(additions)
        self.actions = {self.registered[key]: action for action, key in values.items()}
        self.ok = True; self.error = ''

    def _run(self):
        self.tid = ctypes.windll.kernel32.GetCurrentThreadId()
        user = ctypes.windll.user32
        msg = wintypes.MSG()
        user.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
        self.ready.set()
        # A short lease restores shortcuts even if the WebView loses focus/crashes.
        user.SetTimer(None, 1, 1000, None)
        try:
            while user.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == 0x8001:
                    while not self.commands.empty():
                        command, values, done, result = self.commands.get()
                        try:
                            if command == 'configure':
                                self._bind(values)
                                self.edit_until = 0
                                self.desired = values
                            elif values:
                                if not self.edit_until:self._bind({})
                                self.edit_until = time.monotonic()+15
                            else:
                                self.edit_until = 0
                                self._bind(self.desired)
                        except Exception as error:
                            result['error'] = str(error); self.error = str(error)
                        finally:
                            done.set()
                elif msg.message == 0x0113 and self.edit_until and time.monotonic() >= self.edit_until:
                    self.edit_until = 0
                    try:self._bind(self.desired)
                    except ValueError as error:self.error = str(error);self.ok = False
                elif msg.message == 0x0312 and not self.edit_until:
                    action = self.actions.get(int(msg.wParam))
                    if action:
                        def invoke(action=action):
                            try: self.callbacks[action]()
                            except Exception as error: self.log('hotkey_error', action=action, error=str(error))
                        threading.Thread(target=invoke, daemon=True).start()
        finally:
            for identifier in self.registered.values():
                user.UnregisterHotKey(None, identifier)
            self.ok = False

    def shutdown(self):
        if self.tid:
            ctypes.windll.user32.PostThreadMessageW(self.tid, 0x0012, 0, 0)
            self.thread.join(timeout=3)
