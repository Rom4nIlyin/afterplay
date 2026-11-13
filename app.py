"""AFTERPLAY: local video library and instant replay."""
import argparse
from contextlib import contextmanager
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
import uuid
import io
import storage
from export_control import ExportControl, ExportCancelled
from portable_paths import install_root
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

BASE = Path(__file__).resolve().parent
ROOT = install_root(BASE)
NO_WINDOW = 0x08000000 if os.name == 'nt' else 0
VIDEO_EXT = {'.mp4', '.mkv', '.mov', '.avi', '.webm', '.m4v', '.ts', '.gif'}


def atomic_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp-' + uuid.uuid4().hex)
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(tmp, path)

def run(args, **kw):
    # Desktop launches can have invalid inherited console handles after FreeConsole.
    # Supply stdin explicitly, just as we do stdout/stderr, for every child process.
    if 'input' not in kw:
        kw.setdefault('stdin', subprocess.DEVNULL)
    return subprocess.run([str(x) for x in args], capture_output=True, creationflags=NO_WINDOW, **kw)

def safe_child(root, rel):
    root = Path(root).resolve()
    p = root / rel
    if Path(rel).is_absolute() or '..' in Path(rel).parts or ':' in str(rel):
        raise ValueError('Недопустимый относительный путь')
    if not p.resolve().is_relative_to(root):
        raise ValueError('Путь выходит за пределы выбранной папки')
    for x in [p, *p.parents]:
        if x == root.parent:
            break
        if x.is_symlink() or (hasattr(x, 'is_junction') and x.is_junction()):
            raise ValueError('Ссылки и junction не поддерживаются')
    return p


def verify_interface_bundle(root):
    """Catch partial extraction before opening an unstyled, unusable WebView."""
    root=Path(root);catalog=root/'app/SHA256SUMS.json'
    if not catalog.is_file():return
    ui=root/'app/ui';index=ui/'index.html'
    if not index.is_file():raise RuntimeError('Не найден app/ui/index.html. Распакуйте AFTERPLAY целиком в новую папку.')
    sums=json.loads(catalog.read_text('utf-8'))
    names={'index.html'}
    names.update(urlparse(name).path for name in re.findall(r'(?:src|href)="([^"]+)"',index.read_text('utf-8')) if not urlparse(name).scheme)
    broken=[]
    for name in sorted(names):
        path=safe_child(ui,name);key='app/ui/'+name
        if not path.is_file() or key not in sums or hashlib.sha256(path.read_bytes()).hexdigest()!=sums[key]:broken.append(name)
    if broken:raise RuntimeError('Файлы интерфейса отсутствуют или повреждены: '+', '.join(broken)+'. Распакуйте полный ZIP AFTERPLAY в новую папку; подробности в data/logs/host.log.')


def monitor_interface(suite,url,pause=time.sleep,polls=24):
    """Retry one failed first load and retain a bounded, local startup report."""
    if not suite.window.events.loaded.wait(30):
        report={'ready':False,'error':'WebView2 load event timed out'}
        atomic_json(suite.data/'logs/ui-startup.json',report);suite.log('ui_startup_failed',report=report)
        return False
    expression="({ready:typeof state!=='undefined'&&!!state.replay&&typeof render==='function',documentState:document.readyState,errors:window.afterplayErrors||[],customErrors:window.customErrors||[],resources:performance.getEntriesByType('resource').filter(r=>['script','link'].includes(r.initiatorType)).map(r=>({name:r.name.split('/').at(-1),status:r.responseStatus,bytes:r.decodedBodySize}))})"
    for attempt in range(2):
        report={}
        for _ in range(polls):
            if suite.desktop and suite.desktop.exiting:return False
            try:report=suite.window.evaluate_js(expression) or {}
            except Exception as error:report={'ready':False,'error':str(error)}
            report['attempt']=attempt+1
            if report.get('ready'):
                atomic_json(suite.data/'logs/ui-startup.json',report)
                return True
            pause(.25)
        atomic_json(suite.data/'logs/ui-startup.json',report)
        suite.log('ui_startup_retry' if attempt==0 else 'ui_startup_failed',report=report)
        if attempt==0:suite.window.load_url(url)
    if suite.desktop:
        suite.desktop.notify('AFTERPLAY','Не удалось загрузить интерфейс. Подробности: data/logs/ui-startup.json.','error',feedback=False)
    return False

class Suite:
    def __init__(self, data=None):
        self.data = Path(data or ROOT / 'data')
        self.data.mkdir(parents=True, exist_ok=True)
        for name in ['thumbs', 'exports', 'logs']:
            (self.data / name).mkdir(exist_ok=True)
        self.lock = threading.RLock()
        self.filmstrip_lock = threading.Lock()
        self.jobs = {}
        self.export_controls = {}
        self.children = set()
        self.window = None
        self.chrome = None
        self.cfg_path = self.data / 'settings.json'
        self._saved_cfg = {}
        self.cfg = json.loads(self.cfg_path.read_text('utf-8')) if self.cfg_path.exists() else {
            'video_roots': [],
        }
        self.cfg.setdefault('updates', {'auto_enabled': False})
        self.cfg.setdefault('desktop',{}).setdefault('clips',{}).setdefault('close_action','tray')
        self.cfg.get('hotkeys',{}).pop('auto',None)
        from quick_clips import migrate as migrate_quick_clips
        migrate_quick_clips(self.cfg)
        from customization import migrate_palettes
        migrate_palettes(self.cfg)
        self.save_cfg()
        self.update_stop = threading.Event()
        with self.db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS clips
                (id TEXT PRIMARY KEY, path TEXT UNIQUE, name TEXT, size INTEGER, mtime REAL,
                 duration REAL DEFAULT 0, width INTEGER DEFAULT 0, height INTEGER DEFAULT 0,
                 audio INTEGER DEFAULT 0, tags TEXT DEFAULT '', note TEXT DEFAULT '',
                 favorite INTEGER DEFAULT 0, marks TEXT DEFAULT '[]', error TEXT DEFAULT '')''')
            db.execute('CREATE TABLE IF NOT EXISTS deleted_clips (id TEXT PRIMARY KEY, metadata TEXT, deleted_at TEXT, action TEXT)')
        self.ffmpeg = None
        self.replay = None
        self.desktop = None
        self.auto = None
        self.app_mode = 'clips'
        self.test_control = False
        from app_update import AppUpdater
        self.updater = AppUpdater(ROOT,self.data)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.data / 'library.sqlite3', timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def save_cfg(self):
        # Merge changed settings under the file lock.
        with self.lock:
            lockpath = self.data / 'settings.lock'
            with open(lockpath, 'a+b') as handle:
                if os.name == 'nt':
                    import msvcrt
                    handle.seek(0)
                    if handle.read(1) == b'':
                        handle.write(b'0'); handle.flush()
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    current = json.loads(self.cfg_path.read_text('utf-8')) if self.cfg_path.exists() else {}
                    for key, val in self.cfg.items():
                        if key not in self._saved_cfg or val != self._saved_cfg[key]:
                            current[key] = val
                    for key in set(self._saved_cfg) - set(self.cfg):
                        current.pop(key, None)
                    atomic_json(self.cfg_path, current)
                    self.cfg = current
                    self._saved_cfg = json.loads(json.dumps(current))
                    try:
                        stat=self.cfg_path.stat();self._cfg_signature=(stat.st_mtime_ns,stat.st_size)
                    except OSError:self._cfg_signature=None
                finally:
                    if os.name == 'nt':
                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

    def log(self, event, **detail):
        with self.lock:
            path = self.data / 'journal.jsonl'
            with open(path, 'a', encoding='utf-8') as f:
                f.write(json.dumps({'at': time.strftime('%Y-%m-%d %H:%M:%S'), 'event': event, **detail}, ensure_ascii=False, default=str) + '\n')
                size = f.tell()
            # The journal used to grow forever; keep the current and one previous file.
            if size > 16 * 1024 ** 2:
                try:os.replace(path, self.data / 'journal.previous.jsonl')
                except OSError:pass

    CACHE_MARKERS = ((('thumbs',), ('-strip-', '-wave-', '-audio2-')),
                     (('logs',), ('replay-', 'export-', 'gif-', 'input-', 'montage-')))

    def cache_bytes(self):
        total = 0
        for (folder,), markers in self.CACHE_MARKERS:
            try:
                for entry in os.scandir(self.data / folder):
                    if any(marker in entry.name for marker in markers) and entry.is_file(follow_symlinks=False):
                        total += entry.stat().st_size
            except OSError:
                continue
        return total

    def cleanup_caches(self, max_age_days=30):
        """Drop regenerable caches and old logs so data/ does not grow without bound.

        Filmstrips, waveforms and audio previews are cached per trim range and
        were never removed. Clip thumbnails ({id}.jpg) are kept.
        """
        cutoff = time.time() - max_age_days * 86400
        removed = 0
        patterns = ((self.data / 'thumbs', ('-strip-', '-wave-', '-audio2-')),
                    (self.data / 'logs', ('replay-', 'export-', 'gif-', 'input-', 'montage-')))
        for folder, markers in patterns:
            try:entries = list(os.scandir(folder))
            except OSError:continue
            for entry in entries:
                if not any(marker in entry.name for marker in markers):continue
                try:
                    if entry.is_file(follow_symlinks=False) and entry.stat().st_mtime < cutoff:
                        os.unlink(entry.path);removed += 1
                except OSError:pass
        if removed:self.log('cache_cleanup', removed=removed)
        return removed

    def job(self, label, fn, cancellable=False):
        jid = uuid.uuid4().hex
        with self.lock:
            # Finished jobs were never removed: a long session kept every result
            # in memory and every running-job check scanned all of them.
            finished=[key for key,value in self.jobs.items() if value.get('status')!='running']
            for key in finished[:max(0,len(finished)-60)]:self.jobs.pop(key,None)
            self.jobs[jid] = {'id': jid, 'label': label, 'status': 'running', 'progress': 0, 'message': 'Подготовка…'}
        control = ExportControl(self.jobs[jid]) if cancellable else None
        if control:
            with self.lock:
                self.export_controls[jid] = control
        def worker():
            try:
                if control:control.check()
                result = fn(self.jobs[jid])
                self.jobs[jid].update(status='done', progress=100, result=result, message='Готово')
                if label=='Экспорт видео':
                    import customization
                    customization.sound(self,'success')
            except ExportCancelled:
                self.jobs[jid].update(status='cancelled', cancellable=False, message='Экспорт отменён')
                self.log('export_cancelled', job_id=jid)
            except Exception as e:
                if control and control.cancelled.is_set():
                    self.jobs[jid].update(status='cancelled', cancellable=False, message='Экспорт отменён')
                    self.log('export_cancelled', job_id=jid)
                else:
                    self.jobs[jid].update(status='error', cancellable=False, message=str(e))
                    self.log('error', job=label, error=str(e), trace=traceback.format_exc())
                    if label=='Экспорт видео':
                        import customization
                        customization.sound(self,'error')
            finally:
                if control:
                    with self.lock:
                        self.export_controls.pop(jid, None)
        threading.Thread(target=worker, daemon=True).start()
        return {'job': jid}

    def cancel_export(self, identifier):
        with self.lock:
            job = self.jobs.get(str(identifier))
            control = self.export_controls.get(str(identifier))
        if not job:raise ValueError('Задача не найдена')
        if job['status'] != 'running':
            return {'accepted':False, 'status':job['status']}
        if control is None:raise ValueError('Эту операцию нельзя отменить')
        accepted = control.cancel()
        return {'accepted':accepted, 'status':job['status']}













    def ff(self):
        if not self.ffmpeg:
            import imageio_ffmpeg
            from imageio_ffmpeg._definitions import FNAME_PER_PLATFORM, get_platform
            # Use our bundled executable directly. The package's auto-discovery
            # launches a probe with inherited stdin, which can fail in a GUI process.
            binary = BASE / 'runtime' / 'ffmpeg.exe'
            if not binary.is_file():
                binary = Path(imageio_ffmpeg.__file__).resolve().parent / 'binaries' / FNAME_PER_PLATFORM[get_platform()]
            if not binary.is_file():
                raise ValueError('Встроенный FFmpeg отсутствует: ' + str(binary))
            try:
                check = run([binary, '-version'], timeout=15)
            except OSError as e:
                raise ValueError('Не удалось запустить встроенный FFmpeg: ' + str(e)) from e
            if check.returncode:
                detail = check.stderr.decode('utf-8', 'replace').strip()[:500]
                raise ValueError('Ошибка запуска FFmpeg: ' + (detail or str(check.returncode)))
            self.ffmpeg = str(binary)
        return self.ffmpeg

    @staticmethod
    def _probe_av(path):
        """In-process probe: avoids launching the 100 MB FFmpeg for every file."""
        try:
            import av
            with av.open(str(path)) as media:
                if not media.streams.video:return None
                video=media.streams.video[0]
                width,height=int(video.codec_context.width or 0),int(video.codec_context.height or 0)
                duration=float(media.duration)/1000000 if media.duration else 0.
                if not (duration>0 and width>=10 and height>=10):return None
                audio=list(media.streams.audio)
                return {'duration':duration,'width':width,'height':height,'audio':len(audio),
                        'audio_titles':[s.metadata.get('title') or s.metadata.get('handler_name','') for s in audio],
                        'fps':float(video.average_rate or 60)}
        except Exception:
            return None

    def probe(self, path):
        fast=self._probe_av(path)
        if fast:return fast
        p = run([self.ff(), '-hide_banner', '-i', path], timeout=25)
        text = p.stderr.decode('utf-8', 'replace')
        d = re.search(r'Duration: (\d+):(\d+):(\d+(?:\.\d+)?)', text)
        wh = re.search(r'Video:.*?\b(\d{2,5})x(\d{2,5})\b', text)
        if not d or not wh:
            raise ValueError('Не удалось прочитать видео')
        result={'duration': int(d[1])*3600+int(d[2])*60+float(d[3]),
                'width': int(wh[1]), 'height': int(wh[2]), 'audio': len(re.findall(r'Stream #.*Audio:', text))}
        try:
            import av
            with av.open(str(path)) as media:
                result['audio_titles']=[s.metadata.get('title') or s.metadata.get('handler_name','') for s in media.streams.audio]
                result['fps']=float(media.streams.video[0].average_rate or 60)
        except Exception:pass
        return result

    @staticmethod
    def _path_key(path):
        # Case-normalized (Windows rules), separator-normalized key with a trailing separator,
        # so prefix tests never match "D:\\Video2" against "D:\\Video".
        return os.path.normcase(os.path.abspath(str(path))).rstrip('\\/')+os.sep

    def _resolved_key(self, path):
        cache=self.__dict__.setdefault('_resolved_keys',{})
        text=str(path);key=cache.get(text)
        if key is None:
            try:key=self._path_key(Path(text).resolve())
            except (OSError,ValueError):key=self._path_key(text)
            if len(cache)>256:cache.clear()
            cache[text]=key
        return key

    @staticmethod
    def _internal_name(path):
        text=str(path).casefold()
        # Fast path for ordinary library rows: no marker text, no parsing.
        if not any(marker in text for marker in ('.afterplay-buffer','.afterpaly-buffer','.replay-stage-','.partial.')):
            return False
        parts=Path(path).parts
        if any(part.casefold() in {'.afterplay-buffer','.afterpaly-buffer'} or part.casefold().startswith('.replay-stage-') for part in parts):
            return True
        return bool(parts) and '.partial.' in parts[-1].casefold()

    def internal_media(self, path):
        if self._internal_name(path):return True
        return Path(path).resolve().is_relative_to((self.data/'replay-buffer').resolve())

    def _visibility(self):
        """Build a fast filter once per listing instead of resolving every row.

        Root folders are resolved once (cached); clip paths are compared by
        normalized absolute text. Resolving each of thousands of rows on every
        1.8 s UI poll was the main cause of library/UI slowdowns on Windows.
        """
        buffer=self._resolved_key(self.data/'replay-buffer')
        inactive=tuple(self._resolved_key(root) for root in self.cfg.get('disconnected_roots',[]))
        active=tuple(self._resolved_key(root) for root in [*self.cfg.get('video_roots',[]),str(self.recordings_dir()),*self.cfg.get('storage',{}).get('previous_dirs',[])])
        internal=self._internal_name;path_key=self._path_key
        def visible(path):
            if internal(path):return False
            key=path_key(path)
            if key.startswith(buffer):return False
            if not inactive or not key.startswith(inactive):return True
            # Keep notes for disconnected sources, and reveal them on reconnection.
            return key.startswith(active)
        return visible

    def library_visible(self, path):
        return self._visibility()(path)

    def scan_videos(self, job):
        paths = []
        buffer = self._resolved_key(self.data/'replay-buffer')
        def internal(path):
            # Same rules as internal_media() without resolving every file.
            return self._internal_name(path) or self._path_key(path).startswith(buffer)
        for root in self.cfg['video_roots']:
            root = Path(root)
            if not root.is_dir() or self.internal_media(root):
                continue
            for folder, dirs, files in os.walk(root, followlinks=False):
                dirs[:] = [d for d in dirs if not internal(Path(folder)/d) and not (Path(folder)/d).is_symlink()
                           and not (hasattr(Path(folder)/d,'is_junction') and (Path(folder)/d).is_junction())]
                for name in files:
                    p = Path(folder)/name
                    if p.suffix.lower() in VIDEO_EXT and not internal(p) and not p.is_symlink():
                        paths.append(p)
                if len(paths) > 5000:
                    raise ValueError('Более 5000 видео. Выбери папку поменьше.')
        entries = []
        for p in set(paths):
            try:entries.append((p, p.stat()))
            except OSError:continue  # Removed while scanning.
        entries.sort(key=lambda item: item[1].st_mtime, reverse=True)
        pending = []
        with self.db() as db:
            # One query instead of a connection + SELECT per file.
            existing = {row['path']: row for row in db.execute('SELECT id,path,size,mtime FROM clips')}
            for p, st in entries:
                old = existing.get(str(p))
                # Thumbnails and metadata belong to the stored row id.
                cid = old['id'] if old else hashlib.sha256(str(p.resolve()).lower().encode()).hexdigest()[:24]
                changed = not old or old['size'] != st.st_size or old['mtime'] != st.st_mtime
                if changed:
                    try:
                        db.execute('''INSERT INTO clips(id,path,name,size,mtime) VALUES(?,?,?,?,?)
                                      ON CONFLICT(path) DO UPDATE SET size=excluded.size,mtime=excluded.mtime''',
                                   (cid, str(p), p.name, st.st_size, st.st_mtime))
                    except sqlite3.IntegrityError:
                        continue  # The same file is already indexed under another spelling.
                if changed or not (self.data/'thumbs'/f'{cid}.jpg').exists():
                    pending.append((p, cid))
        total = len(pending)
        job.update(message=f'Видео 0/{total}', progress=0)
        if pending:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            # Probing and thumbnails are independent FFmpeg runs; a few in
            # parallel make a large rescan several times faster.
            workers = max(1, min(4, (os.cpu_count() or 2) // 2, total))
            self.ff()  # Locate/verify FFmpeg once, before the workers start.
            db = sqlite3.connect(self.data / 'library.sqlite3', timeout=30)
            try:
                with ThreadPoolExecutor(max_workers=workers, thread_name_prefix='afterplay-scan') as pool:
                    futures = {pool.submit(self._index_thumbnail, p, cid): (p, cid) for p, cid in pending}
                    for done, future in enumerate(as_completed(futures), 1):
                        p, cid = futures[future]
                        job.update(message=f'Видео {done}/{total} · {p.name}', progress=int(done/total*100))
                        try:
                            info = future.result()
                            db.execute('UPDATE clips SET duration=?,width=?,height=?,audio=?,error=? WHERE id=?',
                                       (info['duration'],info['width'],info['height'],info['audio'],'',cid))
                        except Exception as e:
                            db.execute('UPDATE clips SET error=? WHERE id=?', (str(e),cid))
                        db.commit()
            finally:
                db.close()
        self.prune_missing()
        self.log('video_scan', count=len(entries))
        return {'count': len(entries)}

    def _index_thumbnail(self, path, cid):
        info = self.probe(path)
        thumb = self.data/'thumbs'/f'{cid}.jpg'
        proc = run([self.ff(), '-hide_banner', '-loglevel', 'error', '-ss', str(min(3, info['duration']/3)),
                    '-i', path, '-frames:v', '1', '-vf', 'scale=480:-2', '-threads', '2', '-y', thumb], timeout=30)
        if proc.returncode:
            raise ValueError('Не удалось создать превью')
        return info

    def prune_missing(self):
        """Drop library rows whose file was deleted or moved outside AFTERPLAY.

        Only rows on a reachable source are removed: a disconnected drive or
        network share keeps its rows (and notes) until it returns.
        """
        roots=sorted({self._resolved_key(root):root for root in [*self.cfg.get('video_roots',[]),str(self.recordings_dir()),
                      *self.cfg.get('storage',{}).get('previous_dirs',[])]}.items(),key=lambda item:len(item[0]),reverse=True)
        reachable={}
        def source_present(path):
            key=self._path_key(path)
            root=next((folder for prefix,folder in roots if key.startswith(prefix)),None)
            target=Path(root) if root else Path(Path(path).anchor or path)
            if target not in reachable:
                try:reachable[target]=target.is_dir()
                except OSError:reachable[target]=False
            return reachable[target]
        with self.db() as db:
            rows=list(db.execute('SELECT id,path FROM clips'))
        missing=[]
        for row in rows:
            path=Path(row['path'])
            try:
                if path.exists():continue
            except OSError:continue
            if source_present(path):missing.append((row['id'],row['path']))
        if not missing:return 0
        with self.db() as db:
            db.executemany('DELETE FROM clips WHERE id=? AND path=?',missing)
        for cid,_ in missing:
            (self.data/'thumbs'/f'{cid}.jpg').unlink(missing_ok=True)
        self.log('library_pruned',count=len(missing),paths=[path for _,path in missing[:20]])
        return len(missing)

    def prune_missing_soon(self,interval=10):
        """Throttled background prune for the UI poll; never blocks a request."""
        now=time.monotonic()
        with self.lock:
            if self.__dict__.get('_pruning') or now-self.__dict__.get('_pruned_at',-interval)<interval:return
            self._pruning=True;self._pruned_at=now
        def run():
            try:self.prune_missing()
            except Exception as error:self.log('library_prune_failed',error=str(error))
            finally:self._pruning=False
        threading.Thread(target=run,name='afterplay-prune',daemon=True).start()

    def clips(self):
        visible=self._visibility()
        with self.db() as db:
            return [dict(r) for r in db.execute('SELECT * FROM clips ORDER BY mtime DESC') if visible(r['path'])]

    def latest_clip_id(self):
        """Newest visible clip without materializing the whole library."""
        visible=self._visibility()
        with self.db() as db:
            for row in db.execute('SELECT id,path FROM clips ORDER BY mtime DESC'):
                if visible(row['path']):return row['id']
        return None

    def index_video(self,path):
        path=Path(path)
        info=self.probe(path)
        st=path.stat()
        cid=hashlib.sha256(str(path.resolve()).lower().encode()).hexdigest()[:24]
        with self.db() as db:
            db.execute('''INSERT INTO clips(id,path,name,size,mtime,duration,width,height,audio,tags)
                          VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET
                          size=excluded.size,mtime=excluded.mtime,duration=excluded.duration,
                          width=excluded.width,height=excluded.height,audio=excluded.audio''',
                       (cid,str(path),path.name,st.st_size,st.st_mtime,info['duration'],info['width'],info['height'],info['audio'],'повтор'))
        thumb=self.data/'thumbs'/f'{cid}.jpg'
        p=run([self.ff(),'-hide_banner','-loglevel','error','-ss',str(min(1,info['duration']/3)),
               '-i',path,'-frames:v','1','-vf','scale=480:-2','-y',thumb],timeout=30)
        if p.returncode:self.log('thumbnail_failed',path=str(path))
        if self.replay and self.replay.active_profile:
            with self.lock:
                self.cfg.setdefault('clip_games',{})[cid]=self.replay.active_profile;self.save_cfg()
        return cid

    def recycle_video(self,arg):
        mode=arg.get('delete_mode','recycle')
        if mode not in ('recycle','permanent'):raise ValueError('Неизвестный способ удаления')
        if arg.get('export_key'):
            record=next((row for row in storage.exports(self) if row['key']==str(arg['export_key'])),None)
            if not record:raise ValueError('Запись в папках экспорта не найдена')
            path=Path(record['path'])
            with self.db() as db:row=db.execute('SELECT * FROM clips WHERE path=?',(str(path),)).fetchone()
            info=dict(row) if row else {'id':record['key'],'path':str(path),'name':path.name}
        elif arg.get('export_name'):
            name=str(arg['export_name'])
            if Path(name).name!=name or Path(name).suffix.lower() not in {'.mp4','.gif'} or '.partial.' in name:
                raise ValueError('Некорректное имя экспорта')
            path=safe_child(self.data/'exports',name)
            with self.db() as db:
                row=db.execute('SELECT * FROM clips WHERE path=?',(str(path),)).fetchone()
            info=dict(row) if row else {'id':hashlib.sha256(str(path.resolve()).lower().encode()).hexdigest()[:24],
                                      'path':str(path),'name':name}
        else:
            info=self.clip(arg['id']);path=Path(info['path'])
        if path.suffix.lower() not in VIDEO_EXT or path.is_symlink() or path.is_dir() or self.internal_media(path):
            raise ValueError('Можно удалять только обычные видеофайлы из библиотеки')
        if not path.exists() and not path.is_symlink():
            # Deleted or moved outside AFTERPLAY: there is nothing to recycle,
            # only the stale library entry to remove.
            with self.db() as db:db.execute('DELETE FROM clips WHERE path=?',(str(path),))
            if info.get('id'):(self.data/'thumbs'/f"{info['id']}.jpg").unlink(missing_ok=True)
            self.log('video_entry_removed',path=str(path),metadata=info)
            return {'ok':True,'name':info['name'],'path':str(path),'recycled':False,'delete_mode':mode,'missing':True}
        if not path.is_file():raise ValueError('Можно удалять только обычные видеофайлы из библиотеки')
        if mode=='permanent':
            path.unlink()
        else:
            from send2trash.win.modern import send2trash
            send2trash(str(path.resolve()))
        if path.exists():raise ValueError('Windows не удалила видеофайл')
        with self.db() as db:
            db.execute('INSERT OR REPLACE INTO deleted_clips VALUES(?,?,?,?)',
                       (info['id'],json.dumps(info,ensure_ascii=False),time.strftime('%Y-%m-%d %H:%M:%S'),mode))
            db.execute('DELETE FROM clips WHERE path=?',(str(path),))
        self.log('video_recycled' if mode=='recycle' else 'video_deleted_permanently',path=str(path),metadata=info)
        return {'ok':True,'name':info['name'],'path':str(path),'recycled':mode=='recycle','delete_mode':mode}

    def clip(self, cid):
        with self.db() as db:
            r = db.execute('SELECT * FROM clips WHERE id=?', (str(cid),)).fetchone()
        if not r:
            raise ValueError('Видео не найдено')
        return dict(r)

    def save_clip(self, arg):
        self.clip(arg['id'])
        marks = arg.get('marks', [])
        if not isinstance(marks, list) or len(marks)>1000:
            raise ValueError('Некорректные метки')
        duration = self.clip(arg['id'])['duration']
        if any(not isinstance(m, (int,float)) or not 0 <= m <= duration for m in marks):
            raise ValueError('Метки должны находиться внутри видео')
        with self.db() as db:
            db.execute('UPDATE clips SET tags=?,note=?,favorite=?,marks=? WHERE id=?',
                       (str(arg.get('tags',''))[:1000],str(arg.get('note',''))[:10000],int(bool(arg.get('favorite'))),
                        json.dumps(sorted(set(marks))),arg['id']))
        return {'ok': True}

    def export(self, arg, job):
        from output_names import reserve_output
        source=Path(self.clip(arg['id'])['path'])
        extension='.gif' if arg.get('format')=='gif' else '.mp4'
        with reserve_output(self.recordings_dir(),arg.get('name') or source.stem,extension) as destination:
            return self._export_to(arg,job,destination)

    def _export_to(self, arg, job, dest):
        control = self.export_controls.get(job.get('id'))
        if control:control.check()
        c = self.clip(arg['id'])
        src = Path(c['path'])
        info = self.probe(src)
        if control:control.check()
        start, end = float(arg['start']), float(arg['end'])
        if not 0 <= start < end <= info['duration']+0.05:
            raise ValueError('Проверь начало и конец отрезка')
        if arg.get('format') not in (None, 'original', 'vertical', 'gif'):
            raise ValueError('Неизвестный формат экспорта')
        quality = arg.get('quality') or 'standard'
        if quality not in ('standard', 'discord', 'high'):
            raise ValueError('Неизвестное качество экспорта')
        timer = arg.get('timer', False)
        if not isinstance(timer, bool):
            raise ValueError('Ожидался переключатель таймера')
        import input_capture,input_overlay
        show_inputs=arg.get('show_inputs',False)
        if type(show_inputs) is not bool:raise ValueError('Ожидался переключатель нажатий')
        input_data=input_capture.read(src) if show_inputs else None
        if show_inputs and input_data is None:raise ValueError('В этой записи нет дорожки нажатий')
        overlay_cfg=input_overlay.settings(arg.get('input_overlay'))
        if arg.get('format') == 'gif':
            import gif_media
            gif_media.validate_duration(end-start)
            width=int(arg.get('gif_width',720));ass=None;extra=''
            try:
                if show_inputs:
                    ass=self.data/'logs'/('input-'+uuid.uuid4().hex+'.ass')
                    ow=min(width,info['width']);oh=max(2,round(info['height']*ow/info['width']/2)*2)
                    extra=input_overlay.render_ass(ass,input_data,start,end-start,ow,oh,overlay_cfg)
                result = gif_media.encode(self, src, dest, start, end-start, job, width, timer=timer,control=control,extra_filter=extra)
            finally:
                if ass:ass.unlink(missing_ok=True)
            if not show_inputs:input_capture.copy_trim(src,dest,start,result['duration'])
            self.index_video(dest)
            self.log('gif_export', source=str(src), start=start, end=end, **result)
            return result
        vertical = arg.get('format') == 'vertical'
        partial = dest.with_suffix('.partial.mp4')
        vf = 'scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1' if vertical else 'scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1'
        if quality == 'discord' and not vertical:
            # Fit Discord's 10 MB limit: 720p, 30 fps and a bitrate from the length.
            vf = "fps=30,scale='min(1280,iw)':-2:flags=lanczos,setsar=1"
        if timer:
            from timer_overlay import video_filter
            vf += ',' + video_filter(self.cfg.get('customization'),info.get('fps',60),self.cfg.get('language','ru'))
        ass=None
        if show_inputs:
            ass=self.data/'logs'/('input-'+uuid.uuid4().hex+'.ass')
            ow,oh=(720,1280) if vertical else (info['width']//2*2,info['height']//2*2)
            vf+=',setpts=PTS-STARTPTS,'+input_overlay.render_ass(ass,input_data,start,end-start,ow,oh,overlay_cfg)
        from audio_tracks import export_audio
        audio_filters,audio_maps,expected_audio,titles=export_audio(info,arg)
        video_rate = ['-preset', 'fast', '-crf', '20']
        audio_rate = '192k'
        if quality == 'high':
            video_rate = ['-preset', 'medium', '-crf', '17']
        elif quality == 'discord':
            audio_rate = '96k'
            budget = 9.4 * 1000 * 1000 * 8 / max(end - start, .1)  # bits per second for 9.4 MB
            kbps = int((budget - 96000 * expected_audio - 60000) / 1000)
            if kbps < 250:
                raise ValueError('Для Discord до 10 МБ отрезок слишком длинный. Укоротите его или выберите Discord Nitro.')
            kbps = min(kbps, 8000)
            video_rate = ['-preset', 'fast', '-b:v', f'{kbps}k', '-maxrate', f'{int(kbps*1.3)}k', '-bufsize', f'{kbps*2}k']
        cmd = [self.ff(), '-hide_banner', '-loglevel', 'error', '-ss', str(start), '-i', src,
               '-t', str(end-start), *audio_filters, '-map', '0:v:0', *audio_maps, '-vf', vf,
               '-c:v', 'libx264', *video_rate, '-pix_fmt', 'yuv420p',
               '-c:a', 'aac', '-b:a', audio_rate, '-movflags', '+faststart', '-progress', 'pipe:1', '-nostats', '-y', partial]
        for index,title in enumerate(titles):cmd[-2:-2]=[f'-metadata:s:a:{index}','title='+title,f'-metadata:s:a:{index}','handler_name='+title,f'-disposition:a:{index}','default' if index==0 else '0']
        log_path = self.data/'logs'/f'export-{uuid.uuid4().hex[:12]}.log'
        proc = None
        try:
            with open(log_path,'wb') as err:
                spawn = control.start if control else subprocess.Popen
                proc = spawn([str(x) for x in cmd], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=err, creationflags=NO_WINDOW)
                with self.lock:
                    self.children.add(proc)
                for line in iter(proc.stdout.readline, b''):
                    if control:control.check()
                    if line.startswith(b'out_time_us='):
                        try:
                            elapsed = int(line.strip().split(b'=')[1])/1000000
                            job.update(progress=min(96,int(elapsed/(end-start)*96)),message=f'Экспорт · {elapsed:.0f} / {end-start:.0f} с')
                        except ValueError:
                            pass
                proc.wait()
            if control:control.check()
            if proc.returncode or not partial.is_file() or partial.stat().st_size < 1000:
                raise ValueError('FFmpeg не завершил экспорт. Подробности в data/logs.')
            result = self.probe(partial)
            if control:control.check()
            if abs(result['duration']-(end-start)) > max(.6, (end-start)*.02):
                raise ValueError('Длительность экспорта не прошла проверку')
            if result['audio']!=expected_audio:
                raise ValueError('Экспорт потерял аудиодорожку')
            if vertical and (result['width'],result['height']) != (720,1280):
                raise ValueError('Размер вертикального видео не прошёл проверку')
            if control:control.commit()
            from output_names import commit_output
            commit_output(partial,dest)
            if not show_inputs:input_capture.copy_trim(src,dest,start,result['duration'])
            self.index_video(dest)
            self.log('export', source=str(src), output=str(dest), start=start, end=end, **result)
            return {'path': str(dest), **result, 'bytes':dest.stat().st_size}
        finally:
            if proc:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
                if proc.stdout:proc.stdout.close()
                with self.lock:
                    self.children.discard(proc)
                if control:control.release(proc)
            partial.unlink(missing_ok=True)
            if ass:ass.unlink(missing_ok=True)

    def recordings_dir(self):
        return storage.recording_dir(self)

    def filmstrip(self,cid,start=0,end=None,frames=12):
        import math
        clip=self.clip(cid);source=Path(clip['path']);st=source.stat()
        start=float(start);end=float(clip['duration'] if end is None else end)
        frames=int(frames)
        if not 1<=frames<=64:raise ValueError('Недопустимое число кадров')
        if not math.isfinite(start) or not math.isfinite(end) or not 0<=start<end<=float(clip['duration'])+.1:
            raise ValueError('Недопустимый диапазон кадров')
        signature=hashlib.sha256(f"v2:{st.st_size}:{st.st_mtime_ns}:{start:.3f}:{end:.3f}:{frames}".encode()).hexdigest()[:12]
        target=self.data/'thumbs'/f'{cid}-strip-{signature}.jpg'
        with self.filmstrip_lock:
            if target.is_file():return target
            from PIL import Image
            sheet=Image.new('RGB',(160*frames,90),(20,26,30))
            available=0
            def grab(index):
                position=max(0,start+(end-start)*(index+.5)/frames)
                try:
                    return run([self.ff(),'-hide_banner','-loglevel','error','-ss',f'{position:.3f}',
                                '-i',source,'-frames:v','1','-vf','scale=160:90:force_original_aspect_ratio=decrease,pad=160:90:(ow-iw)/2:(oh-ih)/2',
                                '-threads','1','-f','image2pipe','-vcodec','mjpeg','pipe:1'],timeout=20)
                except subprocess.TimeoutExpired:return None
            # Independent seeks: decode several frames at once instead of
            # launching up to 64 FFmpeg processes one after another.
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=max(1,min(6,os.cpu_count() or 2,frames))) as pool:
                results=list(pool.map(grab,range(frames)))
            for index,frame in enumerate(results):
                if frame is not None and frame.returncode==0 and frame.stdout:
                    try:
                        with Image.open(io.BytesIO(frame.stdout)) as image:sheet.paste(image.convert('RGB'),(160*index,0))
                        available+=1
                    except OSError:pass
            if not available:raise ValueError('Не удалось получить кадры видео')
            temporary=target.with_suffix('.tmp.jpg');sheet.save(temporary,quality=80);os.replace(temporary,target)
        return target

    def automatic_update_tick(self):
        # Opt-in only. Recheck immediately before replacement, including after download.
        def idle():
            return (self.cfg.get('updates',{}).get('auto_enabled',False)
                    and self.desktop and self.updater.state()['supported']
                    and not (self.replay and (self.replay.phase in {'starting','recording','stopping'} or self.replay.saving))
                    and not any(j['status']=='running' for j in list(self.jobs.values()))
                    and not self.update_stop.is_set())
        if not idle():return
        if not self.updater.check()['latest']['available'] or not idle():return
        self.updater.prepare({})
        if idle():
            self.updater.launch()
            self.desktop.exit()

    def automatic_updates(self):
        if self.update_stop.wait(30):return
        while not self.update_stop.is_set():
            try:self.automatic_update_tick()
            except Exception as error:self.log('automatic_update_error',error=str(error))
            if self.update_stop.wait(3600):return

    def shutdown(self):
        self.update_stop.set()
        if self.auto:self.auto.shutdown()
        if self.replay:self.replay.shutdown()
        if self.desktop:self.desktop.shutdown()
        with self.lock:
            for proc in list(self.children):
                if proc.poll() is None:
                    proc.terminate()
            self.children.clear()

    def browse(self, purpose):
        if not self.window:
            raise ValueError('Введи путь вручную')
        import webview
        selected = self.window.create_file_dialog(webview.FileDialog.OPEN, file_types=('Приложения (*.exe)',)) if purpose in {'auto-app','profile-app'} else self.window.create_file_dialog(webview.FileDialog.FOLDER)
        return {'path': selected[0] if selected else None}


    def _reload_cfg(self):
        """Pick up settings changed by another writer, but skip unchanged files.

        Every UI poll used to read, parse and deep-copy settings.json.
        """
        with self.lock:
            try:stat=self.cfg_path.stat()
            except FileNotFoundError:return
            signature=(stat.st_mtime_ns,stat.st_size)
            if signature==getattr(self,'_cfg_signature',None):return
            self.cfg = json.loads(self.cfg_path.read_text('utf-8'))
            self._saved_cfg = json.loads(json.dumps(self.cfg))
            self._cfg_signature=signature

    def dispatch(self, action, arg):
        self._reload_cfg()
        try:return self._dispatch(action, arg)
        except BaseException:
            # A failed command may have left partial edits in self.cfg. Reload
            # the saved file on the next request, exactly as before caching.
            self._cfg_signature=None
            raise

    def _dispatch(self, action, arg):
        if action=='inputs_config':
            if not self.replay:raise ValueError('Запись нажатий доступна в окне AFTERPLAY')
            return self.replay.configure_inputs(arg.get('enabled'))
        if action=='clip_inputs':
            import input_overlay
            return input_overlay.metadata(self,str(arg['id']))
        if action=='clip_inputs_config':
            import input_overlay
            return input_overlay.configure(self,str(arg['id']),arg.get('settings'))
        if action=='montage_export':
            import montage
            # Validate source paths and trims before creating a background job.
            montage.segments(self,arg.get('segments'))
            return self.job('Сборка подборки',lambda job:montage.export(self,arg,job),cancellable=True)
        if action=='montage_project':
            path=self.data/'projects/montage.json'
            return {'project':json.loads(path.read_text('utf-8')) if path.is_file() else None}
        if action=='montage_project_save':
            project=arg.get('project')
            if not isinstance(project,dict) or not isinstance(project.get('segments'),list) or len(project['segments'])>50:raise ValueError('Некорректный проект монтажа')
            import math
            for row in project['segments']:
                if not isinstance(row,dict):raise ValueError('Некорректный фрагмент')
                clip=self.clip(row.get('id'))
                start,end,at=row.get('start'),row.get('end'),row.get('at',0)
                if any(type(t) not in (int,float) or not math.isfinite(t) for t in (start,end,at)) or not 0<=start<end<=clip['duration']+.05 or not 0<=at<=86400:raise ValueError('Проверь границы фрагмента')
            with self.lock:atomic_json(self.data/'projects/montage.json',project)
            return {'ok':True}
        if action.startswith('customize_'):
            import customization
            return customization.dispatch(self,action,arg)
        if action=='language_config':
            import localization
            return localization.configure(self,arg.get('language'))
        if action.startswith('profile_'):
            import capture_profiles
            if not self.replay:raise ValueError('Профили доступны в окне AFTERPLAY')
            if action=='profile_list':return capture_profiles.state(self)
            if action=='profile_save':return capture_profiles.save(self,arg)
            if action=='profile_remove':return capture_profiles.remove(self,arg.get('path',''))
            if action=='profile_apply':return capture_profiles.apply(self,arg.get('path',''))
            if action=='profile_configure':return capture_profiles.configure(self,arg)
            if action=='profile_new':return capture_profiles.create(self)
        if action in {'clip_media_info','clip_frame_step','clip_waveform'}:
            import editor_media
            if action=='clip_media_info':return editor_media.info(self,str(arg['id']))
            if action=='clip_frame_step':return editor_media.frame_step(self,str(arg['id']),arg.get('time',0),arg.get('direction',1))
            return editor_media.waveform(self,str(arg['id']),arg.get('start',0),arg.get('end'),arg.get('track',0))
        if action=='replay_mark':
            if not self.replay:raise ValueError('Запись недоступна')
            return self.replay.add_marker()
        if action == 'state':
            self.prune_missing_soon()
            return {'settings': self.cfg, 'jobs':list(self.jobs.values())[-15:], 'clips':self.clips(),
                    'storage':storage.state(self),'updates':self.updater.state(), 'auto_record':self.auto.state() if self.auto else None,
                    'replay':self.replay.state() if self.replay else None}
        if action=='storage_config':
            active=self.replay and (self.replay.phase in {'starting','recording','stopping'} or self.replay.saving)
            if active or any(job['status']=='running' for job in list(self.jobs.values())):
                raise ValueError('Остановите запись и дождитесь завершения текущих операций')
            return storage.configure(self,arg.get('recordings_dir'))
        if action=='auto_config':
            if not self.auto:raise ValueError('Автозапись недоступна')
            return self.auto.configure(arg)
        if action=='auto_toggle':
            if not self.auto:raise ValueError('Автозапись недоступна')
            return self.auto.toggle()
        if action=='hotkeys_edit':
            if not self.replay or not self.replay.hotkeys:raise ValueError('Горячие клавиши доступны в окне AFTERPLAY')
            self.replay.hotkeys.editing(bool(arg.get('enabled')))
            return {'ok':True}
        if action=='updates_config':
            value=arg.get('auto_enabled')
            if not isinstance(value,bool):raise ValueError('Ожидался переключатель автообновления')
            self.cfg['updates']={'auto_enabled':value};self.save_cfg()
            return self.cfg['updates']
        if action=='hotkeys_config':
            from hotkeys import validate
            from quick_clips import durations
            values=validate(arg)
            clips=durations(arg.get('quick_clips',self.cfg.get('quick_clips')))
            if not self.replay or not self.replay.hotkeys:raise ValueError('Настройка клавиш доступна в окне AFTERPLAY')
            self.replay.hotkeys.configure(values)
            self.cfg['hotkeys']=values;self.cfg['quick_clips']=clips;self.save_cfg()
            return values
        if action=='appearance_config':
            appearance=self.cfg.setdefault('appearance',{})
            if 'theme' in arg:
                from customization import THEMES,THEME_PALETTES,THEME_ALIASES
                arg={**arg,'theme':THEME_ALIASES.get(arg['theme'],arg['theme'])}
                if arg['theme'] not in THEMES:raise ValueError('Неизвестная тема')
                appearance['theme']=arg['theme']
                self.cfg.setdefault('customization',{})['theme']=arg['theme']
                if arg['theme'] in THEME_PALETTES:
                    background,accent=THEME_PALETTES[arg['theme']]
                    self.cfg['customization'].update(background='color',background_color=background,
                                                     accent=accent,colors_custom=False,panel_opacity=94)
            if 'library_view' in arg:
                if arg['library_view'] not in {'gallery','list'}:raise ValueError('Неизвестный вид библиотеки')
                appearance['library_view']=arg['library_view']
            self.save_cfg()
            return self.cfg['appearance']
        if action=='shortcut_desktop':
            from shortcuts import create_shortcut
            return {'path':str(create_shortcut(ROOT))}
        if action=='shortcut_taskbar':
            from shortcuts import taskbar_shortcut
            return taskbar_shortcut(ROOT)
        if action=='autostart_config':
            from shortcuts import set_autostart
            result=set_autostart(ROOT,arg.get('enabled'))
            self.cfg.setdefault('desktop',{}).setdefault(self.app_mode,{})['autostart']=result['enabled']
            self.save_cfg()
            return result
        if action=='update_check':
            if self.updater.busy or any(j['status']=='running' and j['label']=='Проверка обновлений' for j in list(self.jobs.values())):raise ValueError('Дождитесь завершения проверки или загрузки')
            return self.job('Проверка обновлений',lambda j:self.updater.check())
        if action in {'update_prepare','update_install'}:
            if self.replay and (self.replay.phase in {'starting','recording','stopping'} or self.replay.saving):
                raise ValueError('Перед обновлением остановите запись и дождитесь сохранения клипа')
            if any(j['status']=='running' for j in list(self.jobs.values())):raise ValueError('Дождитесь завершения текущих операций')
            if not self.desktop:raise ValueError('Установка обновления доступна в окне портативной программы')
            if action=='update_prepare':return self.job('Обновление AFTERPLAY',self.updater.prepare)
            result=self.updater.launch()
            threading.Timer(.5,self.desktop.exit).start()
            return result
        if action=='pet_config':
            cfg={'enabled':False,'sound':True,**self.cfg.get('pet',{})}
            for key in ('enabled','sound'):
                if key in arg:
                    if not isinstance(arg[key],bool):raise ValueError('Некорректная настройка питомца')
                    cfg[key]=arg[key]
            self.cfg['pet']={key:cfg[key] for key in ('enabled','sound')}
            self.save_cfg()
            return self.cfg['pet']
        if action=='onboarding_offer':
            # Claim the first offer on disk before displaying it, including if
            # the user quits without explicitly skipping or finishing the tour.
            with self.lock:
                current=json.loads(self.cfg_path.read_text('utf-8')).get('onboarding',{})
                if current.get('status'):return {'show':False,'onboarding':current}
                self.cfg['onboarding']={'version':1,'status':'offered'}
                self.save_cfg()
                return {'show':True,'onboarding':self.cfg['onboarding']}
        if action=='editor_layout_config':
            height=arg.get('timeline_height')
            if type(height) not in (int,float) or not 110<=height<=1200:raise ValueError('Некорректная высота дорожки')
            self.cfg['editor_layout']={'timeline_height':round(height)}
            self.save_cfg()
            return self.cfg['editor_layout']
        if action=='onboarding_config':
            status=arg.get('status')
            if status not in {'skipped','completed'}:raise ValueError('Некорректный статус обучения')
            self.cfg['onboarding']={'version':1,'status':status}
            self.save_cfg()
            return self.cfg['onboarding']
        if action=='window_state':
            return self.chrome.state() if self.chrome else {'native':False,'styled':False,'maximized':False}
        if action=='window_chrome_config':
            return self.chrome.configure(arg.get('colors')) if self.chrome else {'native':False,'styled':False,'maximized':False}
        if action=='window_control':
            if not self.chrome:raise ValueError('Управление окном доступно в AFTERPLAY')
            return self.chrome.control(arg.get('command'),arg.get('edge'))
        if action=='desktop_config':
            choice=arg.get('close_action')
            if choice not in {'close','tray'}:raise ValueError('Некорректное действие крестика')
            settings=self.cfg.setdefault('desktop',{})
            settings.setdefault(self.app_mode,{})['close_action']=choice
            self.save_cfg()
            return {'ok':True,'close_action':choice}
        if action=='desktop_exit':
            if not self.desktop:raise ValueError('Полный выход доступен в окне приложения')
            threading.Timer(.2,self.desktop.exit).start()
            return {'ok':True}
        if action=='desktop_test' and self.test_control:
            op=arg.get('op','info')
            if op=='boot_info':
                return self.window.evaluate_js("({href:location.href,ready:document.readyState,render:typeof render,state:typeof state,errors:window.afterplayErrors||[],customErrors:window.customErrors||[],scripts:[...document.scripts].map(s=>s.src),resources:performance.getEntriesByType('resource').map(r=>({name:r.name.split('/').at(-1),status:r.responseStatus,duration:r.duration,bytes:r.decodedBodySize}))})")
            if op=='moments_info':
                return self.window.evaluate_js("({errors:window.afterplayErrors||[],selection:[...montageSelection],quick:quickClipValues(),quickFields:[0,1,2].map(i=>!!$('#quickClipKey'+i)),inputTab:!!$('[data-review-pane=inputs]'),inputAvailable:!!$('#previewInputs'),overlayVisible:!!inputEditor?.preview&&!inputEditor.preview.node.hidden,overlayKeys:inputEditor?.preview?.node.querySelectorAll('.pressed').length||0,montage:montageDraft,rows:document.querySelectorAll('[data-montage-row]').length,overflow:$('#dialog').open?$('#dialog').scrollWidth>$('#dialog').clientWidth:document.documentElement.scrollWidth>innerWidth,dialog:$('#dialog').open?$('#dialog').innerText.slice(0,5000):null})")
            if op=='ui_tab':
                choice=arg.get('tab','library')
                if choice not in {'library','settings','replay','favorites','exports','customize'}:raise ValueError('Неизвестный экран')
                self.window.evaluate_js('tab='+json.dumps(choice)+';render()')
                return {'ok':True}
            if op=='ui_check':
                return self.window.evaluate_js("({title:document.title,theme:document.documentElement.dataset.theme,auto:!!document.querySelector('#autoEnabled'),hotkeys:!!document.querySelector('#saveHotkey'),logo:document.querySelector('#brandMark img')?.naturalWidth,overflow:document.documentElement.scrollWidth>window.innerWidth,cards:document.querySelectorAll('.settings-card').length})")
            if op=='pet_info':
                return self.window.evaluate_js("({...window.afterplayPet?.info(),settings:!!document.querySelector('#petSettings'),errors:window.afterplayErrors||[]})")
            if op=='custom_info':
                return self.window.evaluate_js("({debug:window.customDebug?.(),tab,pane:typeof customPane!=='undefined'?customPane:null,themeCount:document.querySelectorAll('.custom-theme').length,mic:!!$('#microphoneEnabled'),micOptions:$('#microphoneDevice')?.options.length,errors:window.afterplayErrors||[],text:document.querySelector('main').innerText.slice(0,3500),dialog:$('#dialog').open?$('#dialog').innerText:null,presetButtons:[...document.querySelectorAll('.custom-preset-item')].map(e=>({name:e.querySelector('[data-action=custom-preset-load]').textContent,deleteLabel:e.querySelector('[data-action=custom-preset-delete]').getAttribute('aria-label')}))})")
            if op=='localization_info':
                return self.window.evaluate_js("({language:window.afterplayI18n?.language,documentLanguage:document.documentElement.lang,missing:window.afterplayI18n?.untranslated(),errors:window.afterplayErrors||[],debug:window.customDebug?.(),languageSelect:$('#interfaceLanguage')?.value,review:window.reviewDebug?.(),frame:$('#player')?{width:$('#player').clientWidth,height:$('#player').clientHeight,videoWidth:$('#player').videoWidth,videoHeight:$('#player').videoHeight,layout:['#dialog','.dialog-head','.review-viewer','.review-transport'].map(s=>{const e=$(s);return e?{selector:s,width:e.clientWidth,height:e.clientHeight,style:e.getAttribute('style'),rows:getComputedStyle(e).gridTemplateRows}:null})}:null})")
            if op=='language_select':
                value=arg.get('language')
                if value not in {'ru','en'}:raise ValueError('Unsupported language')
                self.window.evaluate_js("$('#interfaceLanguage').value="+json.dumps(value)+";$('#interfaceLanguage').dispatchEvent(new Event('change',{bubbles:true}))")
                return {'ok':True}
            if op=='custom_hover':
                cid=self.clip(str(arg['id']))['id']
                self.window.evaluate_js("document.querySelector('[data-clip=\""+cid+"\"]')?.dispatchEvent(new PointerEvent('pointerover',{bubbles:true}))")
                return {'ok':True}
            if op=='custom_hover_stop':self.window.evaluate_js('customStopHover()');return {'ok':True}
            if op=='custom_resize':
                from System.Drawing import Size
                from System import Action
                width=max(1050,min(2000,int(arg.get('width',1600))));height=max(700,min(1200,int(arg.get('height',1000))))
                self.window.native.Invoke(Action(lambda:setattr(self.window.native,'Size',Size(width,height))))
                return {'ok':True}
            if op=='custom_action':
                action=arg.get('action','')
                if action not in {'custom-theme','custom-pane','custom-scene','custom-background','custom-save','custom-cancel','custom-reset','custom-sound','custom-notice','custom-workspace','custom-cover','custom-preset-save','custom-preset-load','custom-preset-delete','custom-preset-delete-confirm','custom-preset-export','custom-preset-import'}:raise ValueError('Unsupported custom test action')
                self.window.evaluate_js('window.customTestError="";action('+json.dumps(action)+',{dataset:'+json.dumps(arg.get('dataset',{}))+'}).catch(e=>window.customTestError=String(e))')
                return {'ok':True}
            if op=='custom_fields':
                import customization
                values=arg.get('values',{})
                if not set(values)<=set(customization.DEFAULTS):raise ValueError('Unknown custom test setting')
                customization.validate(values)
                self.window.evaluate_js('Object.assign(customDraft,'+json.dumps(values)+');customChanged();render()')
                return {'ok':True}
            if op=='ui_diagnostics':
                return self.window.evaluate_js("({tab,auto:typeof autoSettings,hotkeys:typeof hotkeySettings,errors:window.afterplayErrors||[],text:document.querySelector('main').innerText.slice(0,2500),render:window.renderDesktopExtras?.toString().slice(0,450)})")
            if op=='ui_features':
                return self.window.evaluate_js("(()=>{const d=document.querySelector('#dialog'),p=document.querySelector('.player'),r=p?.getBoundingClientRect();return {save:document.querySelector('#saveHotkey')?.value,auto:document.querySelector('#autoHotkey')?.value,autoUpdate:document.querySelector('#autoUpdateEnabled')?.checked,gif:!!document.querySelector('#replaySaveFormat'),gifSeconds:document.querySelector('#replayGifSeconds')?.value,format:document.querySelector('#clipFormat')?.value,exportDisabled:document.querySelector('[data-action=export]')?.disabled,dialogOpen:d.open,dialogWidth:d.clientWidth,player:r?{width:r.width,height:r.height,center:r.x+r.width/2,viewport:innerWidth}:null,image:document.querySelector('.editor-preview img')?.naturalWidth}})()")
            if op=='ui_clip':
                cid=self.clip(str(arg['id']))['id']
                self.window.evaluate_js('state='+json.dumps(self._dispatch('state',{}))+';openClip('+json.dumps(cid)+')')
                return {'ok':True}
            if op=='ui_playback':
                return self.window.evaluate_js("({rate:$('#player')?.playbackRate,time:$('#player')?.currentTime,paused:$('#player')?.paused,fullscreen:document.fullscreenElement?.className||null,exactTime:studioEditor?.exactTime,frameHidden:$('#preciseFrame')?.hidden,frameReady:$('#preciseFrame')?.complete,timer:$('#previewTimer')?.checked,exportTimer:$('#exportTimer')?.checked,label:$('#videoTimer')?.textContent,speed:$('#playbackSpeed')?.value,windowHotkey:$('#windowHotkey')?.value,overflow:$('#dialog').scrollWidth>$('#dialog').clientWidth})")
            if op=='window_hotkey':
                identifier=next(i for i,a in self.replay.hotkeys.actions.items() if a=='window')
                ctypes.windll.user32.PostThreadMessageW(self.replay.hotkey_tid,0x0312,identifier,0)
                return {'ok':True}
            if op=='ui_trim':
                start,end=float(arg['start']),float(arg['end'])
                if not 0<=start<end:raise ValueError('Invalid test range')
                self.window.evaluate_js(f'setTrim({start},{end},{{seek:true}})')
                return self.window.evaluate_js("({start:parse($('#clipIn').value),end:parse($('#clipOut').value),selected:$('#trimSelection').style.width,frames:$('#trimFilmstrip').naturalWidth,valid:trimFromFields(),overflow:$('#dialog').scrollWidth>$('#dialog').clientWidth})")
            if op=='close':threading.Timer(.1,self.window.destroy).start();return {'ok':True}
            if op=='show':self.desktop.show();return {'ok':True}
            if op=='hotkey':
                if not self.replay or not (self.replay.hotkeys and self.replay.hotkeys.ok):raise ValueError('Горячая клавиша не зарегистрирована')
                binding=arg.get('action','save')
                if binding not in {'save','clip_1','clip_2','inputs'}:raise ValueError('Unsupported shortcut')
                identifier=next(i for i,a in self.replay.hotkeys.actions.items() if a==binding)
                ctypes.windll.user32.PostThreadMessageW(self.replay.hotkey_tid,0x0312,identifier,0)
                return {'ok':True}
            if op=='marker_hotkey':
                identifier=next(i for i,a in self.replay.hotkeys.actions.items() if a=='mark')
                ctypes.windll.user32.PostThreadMessageW(self.replay.hotkey_tid,0x0312,identifier,0)
                return {'ok':True}
            if op=='review_info':
                return self.window.evaluate_js('({layout:window.reviewDebug?.(),errors:window.afterplayErrors||[]})')
            if op=='review_mode':
                pane=arg.get('pane','trim')
                if pane not in {'trim','sound','export','notes','inputs'}:raise ValueError('Unsupported pane')
                self.window.evaluate_js('reviewSetMode('+json.dumps(bool(arg.get('editing')))+','+json.dumps(pane)+')')
                return {'ok':True}
            if op=='studio_info':
                return self.window.evaluate_js("({profiles:!!$('#captureProfile'),mark:!!$('#markHotkey'),wave:!!$('#audioWaveform'),waveReady:!!studioEditor?.wave?.peaks?.length,waveTrack:studioEditor?.wave?.track,waveStatus:$('#waveStatus')?.textContent,exactTime:studioEditor?.exactTime,preciseFrame:!!$('#preciseFrame')?.naturalWidth,position:$('#framePosition')?.textContent,audioOptions:[...($('#exportAudioMode')?.options||[])].map(x=>x.value),previewOptions:[...($('#previewAudioTrack')?.options||[])].map(x=>x.value),previewStatus:$('#previewAudioStatus')?.textContent,previewReady:studioEditor?.audio?.readyState,fps:$('#sourceFps')?.textContent,overflow:$('#dialog').scrollWidth>$('#dialog').clientWidth,errors:window.studioTestError||'',profileForm:!!$('#profilePath')})")
            if op=='studio_action':
                choice=arg.get('action')
                if choice not in {'frame-next','frame-prev','set-in','set-out','profile-new','profile-save','profile-cancel','profile-apply','profile-edit','export','close'}:raise ValueError('Unsupported studio test action')
                self.window.evaluate_js('window.studioTestError="";action('+json.dumps(choice)+',{dataset:{}}).catch(e=>window.studioTestError=String(e))')
                return {'ok':True}
            if op=='studio_fields':
                fields=arg.get('fields',{})
                allowed={'profileName','profilePath','profileSeconds','profileFps','profileCq','profileAudio','captureProfile','exportAudioMode','exportGameGain','exportChatGain','previewAudioTrack','waveTrack','markHotkey','clipIn','clipOut','clipName','playbackSpeed'}
                if not set(fields).issubset(allowed):raise ValueError('Unsupported studio test field')
                self.window.evaluate_js('for(const [id,value] of Object.entries('+json.dumps(fields)+')){const el=document.getElementById(id);if(el){el.value=String(value);el.dispatchEvent(new Event("change",{bubbles:true}))}}')
                return {'ok':True}
            return {'console_window':bool(ctypes.windll.kernel32.GetConsoleWindow()),
                    'native_fullscreen':bool(self.window.native.is_fullscreen),
                    'native_visible':bool(self.window.native.Visible),
                    'taskbar_visible':bool(self.window.native.ShowInTaskbar),
                    'window_icon_handle':int(self.window.native.Icon.Handle.ToInt64()),
                    'tray_visible':bool(self.desktop.icon.visible),'mode':self.app_mode,
                    'icon_name':getattr(self.desktop,'current_icon_name',None),
                    'icon_error':getattr(self.desktop,'icon_error','')}
        if action in {'recording_start','recording_stop'}:
            if not self.replay or not self.auto:raise ValueError('Запись доступна только в AFTERPLAY')
            operation='start_recording' if action=='recording_start' else 'stop_recording'
            return self.job('Включение записи' if action=='recording_start' else 'Сохранение записи',lambda job:self.auto.manual(operation,job))
        if action.startswith('replay_'):
            if not self.replay:raise ValueError('Повтор доступен только в AFTERPLAY')
            if action=='replay_devices':return self.replay.devices()
            if action=='replay_applications':
                import process_audio
                return {'applications':process_audio.applications(),'audio_applications':process_audio.audio_applications()}
            if action=='replay_config':return self.auto.manual('configure',arg)
            if action=='replay_start':return self.job('Включение повтора',lambda j:self.auto.manual('start_replay'))
            if action=='replay_stop':return self.job('Остановка повтора',lambda j:self.auto.manual('stop_replay'))
            if action=='replay_save':return self.replay.save_job(arg.get('seconds'))
        if action == 'browse': return self.browse(arg.get('purpose'))
        if action == 'settings':
            if 'remove_video_root' in arg:
                value=arg['remove_video_root']
                if not isinstance(value,str) or not value:raise ValueError('Выберите подключённую папку')
                key=str(Path(value).resolve()).casefold()
                removed=[p for p in self.cfg['video_roots'] if str(Path(p).resolve()).casefold()==key]
                if not removed:raise ValueError('Папка уже отключена')
                self.cfg['video_roots']=[p for p in self.cfg['video_roots'] if p not in removed]
                self.cfg['disconnected_roots']=list(dict.fromkeys([*self.cfg.get('disconnected_roots',[]),*removed]))
            if 'video_root' in arg:
                p = Path(arg['video_root'])
                if not p.is_dir(): raise ValueError('Папка видео не найдена')
                if self.internal_media(p):raise ValueError('Служебный буфер не добавляется в библиотеку')
                self.cfg['video_roots'] = list(dict.fromkeys([*self.cfg['video_roots'],str(p.resolve())]))
                self.cfg['disconnected_roots']=[v for v in self.cfg.get('disconnected_roots',[]) if str(Path(v).resolve()).casefold()!=str(p.resolve()).casefold()]
            self.save_cfg()
            return self.cfg
        if action=='scan':
            if any(j['status']=='running' and j['label']=='Индексация видео' for j in list(self.jobs.values())):
                raise ValueError('Индексация уже выполняется')
            return self.job('Индексация видео',self.scan_videos)
        if action=='clip_save': return self.save_clip(arg)
        if action=='copy_file':
            path=Path(self.clip(str(arg.get('id','')))['path'])
            if not path.is_file():raise ValueError('Файл не найден')
            if os.name!='nt':raise ValueError('Копирование файла доступно в Windows')
            # Put the file itself on the clipboard (paste into Discord or Explorer).
            env={**os.environ,'AFTERPLAY_COPY':str(path)}
            result=run(['powershell.exe','-NoProfile','-NonInteractive','-Command','Set-Clipboard -LiteralPath $env:AFTERPLAY_COPY'],env=env,timeout=20)
            if result.returncode:raise ValueError('Не удалось скопировать файл: '+result.stderr.decode('utf-8','replace')[-300:])
            return {'ok':True}
        if action=='cache_info':
            return {'bytes':self.cache_bytes()}
        if action=='cache_clear':
            before=self.cache_bytes();self.cleanup_caches(max_age_days=0)
            return {'bytes':max(0,before-self.cache_bytes())}
        if action=='clip_delete':return self.recycle_video(arg)
        if action=='exports':
            return [{**row,'at':time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(row['mtime']))} for row in storage.exports(self)[:200]]
        if action=='export':
            # Each export is a full x264 encode. Parallel ones (repeated clicks)
            # exhausted RAM on long high-resolution replays.
            with self.lock:running=any(job.get('label')=='Экспорт видео' and job.get('status')=='running' for job in self.jobs.values())
            if running:raise ValueError('Экспорт уже идёт. Дождитесь его завершения или отмените.')
            return self.job('Экспорт видео',lambda j:self.export(arg,j),cancellable=True)
        if action=='job_cancel': return self.cancel_export(arg.get('id'))
        if action=='open':
            target = arg.get('target')
            if target=='github':
                from app_update import REPOSITORY
                os.startfile('https://github.com/'+REPOSITORY)
                return {'ok':True}
            if target=='exports': p=self.recordings_dir()
            elif target=='data': p=self.data
            elif target in {'clip','clip-folder'}:
                p=Path(self.clip(arg['id'])['path'])
                if not p.is_file():raise ValueError('Файл записи не найден')
                if target=='clip-folder':
                    subprocess.Popen(['explorer.exe','/select,',str(p)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=NO_WINDOW)
                    return {'ok':True}
            else: raise ValueError('Неизвестная цель')
            os.startfile(str(p))
            return {'ok':True}
        raise ValueError('Неизвестная команда')

def server_for(suite, token=None, port=0):
    token = token or secrets.token_urlsafe(32)
    content_types={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8',
                   '.js':'text/javascript; charset=utf-8','.json':'application/json; charset=utf-8',
                   '.svg':'image/svg+xml','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg',
                   '.ico':'image/x-icon','.ttf':'font/ttf','.mp4':'video/mp4','.m4a':'audio/mp4',
                   '.m4v':'video/mp4','.mov':'video/quicktime','.mkv':'video/x-matroska',
                   '.avi':'video/x-msvideo','.ts':'video/mp2t',
                   '.webm':'video/webm','.gif':'image/gif','.wav':'audio/wav'}
    # Thumbnails keep their URL when regenerated, so they are reused for a few
    # minutes and then revalidated by ETag (cheap 304 responses).
    cache_control={'static':'private, max-age=86400','short':'private, max-age=300'}
    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'
        def log_message(self, *args): pass
        def send_json(self, obj, status=200):
            b=json.dumps(obj,ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(b)))
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            self.wfile.write(b)
        def route(self):
            p=urlparse(self.path).path
            prefix='/'+token+'/'
            return p[len(prefix):] if p.startswith(prefix) else None
        def do_POST(self):
            if self.route()!='api' or self.headers.get('X-App-Token')!=token:
                return self.send_json({'error':'Forbidden'},403)
            origin=self.headers.get('Origin')
            if origin and origin != f'http://127.0.0.1:{self.server.server_port}':
                return self.send_json({'error':'Origin rejected'},403)
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<1024*1024: raise ValueError('Некорректный размер запроса')
                req=json.loads(self.rfile.read(size))
                result=suite.dispatch(req['action'],req.get('args',{}))
                self.send_json(result)
            except (BrokenPipeError,ConnectionAbortedError,ConnectionResetError):pass
            except Exception as e:
                import localization
                suite.log('http_request_failed',route='api',error=str(e))
                self.send_json({'error':localization.translate(suite,str(e))},400)
        def do_GET(self):
            route=self.route()
            if route is None: return self.send_json({'error':'Forbidden'},403)
            # Interface files never change while the app runs (the token in the
            # URL changes every launch). Generated images are revalidated with
            # an ETag, so re-rendering the library no longer re-downloads every
            # thumbnail. Video streams stay uncached.
            cache='no-store'
            try:
                if route in {'','window-chrome.js','index.html','style.css','themes.css','ui.js','recording-size.js','replay-ui.js','preferences-ui.js','afterplay-ui.js','trim-ui.js','filmstrip-ui.js','typography.css','fonts/Inter-Regular.ttf','fonts/Inter-Medium.ttf','fonts/Inter-SemiBold.ttf','trim-viewport.js','navigation-ui.js','playback-ui.js','library-ui.js','studio-ui.js','studio.css','review-ui.js','profiles-ui.js','audio-mixer-ui.js','review.css','button-effects.css','button-effects.js','dropdowns.css','dropdowns.js','afterplay.css','afterplay.png','afterplay.ico','afterplay-recording.ico'}:
                    p=BASE/'ui'/('index.html' if route=='' else route)
                    # The page itself is tiny and names versioned assets: never cache it.
                    cache='no-store' if route in {'','index.html'} else 'static'
                elif route in {'settings-layout.js','scrollbars.css','sequence-viewport.js','sequence-model.js','sequence-ui.js','sequence.css','input-timeline.js','moments-ui.js','moments.css','pet-ui.js','pet.css','pets/rysya.png','pets/rysya-groom.png','pets/purr.wav','comfort.css','onboarding.js','onboarding.css','customization-ui.js','customization.css','i18n.js','en-catalog.js','en.json','afterglow.css','afterglow.js','ag-app.css','ag-app.js'}:
                    p=BASE/'ui'/route
                    cache='static'
                elif route.startswith('backgrounds/'):
                    p=safe_child(BASE/'ui',route)
                    cache='static'
                elif route.startswith('custom-assets/'):
                    import customization
                    p=customization.asset_path(suite,route.split('/')[-1])
                    cache='short'
                elif route.startswith('filmstrip/'):
                    query=parse_qs(urlparse(self.path).query)
                    p=suite.filmstrip(route.split('/')[-1],query.get('start',[0])[0],query.get('end',[None])[0],query.get('frames',[12])[0])
                    cache='short'
                elif route.startswith('thumb/'):
                    cid=route.split('/')[-1]
                    suite.clip(cid)
                    p=suite.data/'thumbs'/f'{cid}.jpg'
                    cache='short'
                elif route.startswith('media/'):
                    p=Path(suite.clip(route.split('/')[-1])['path'])
                elif route.startswith('audio-preview/'):
                    import editor_media
                    query=parse_qs(urlparse(self.path).query)
                    p=editor_media.audio_preview(suite,route.split('/')[-1],query.get('track',[0])[0])
                else: return self.send_json({'error':'Not found'},404)
                try:info=p.stat()
                except OSError:info=None
                if info is None or not p.is_file(): return self.send_json({'error':'Not found'},404)
                size=info.st_size
                start,end=0,size-1
                ranged=self.headers.get('Range')
                etag=f'"{size:x}-{info.st_mtime_ns:x}"'
                if cache!='no-store' and not ranged and self.headers.get('If-None-Match')==etag:
                    self.send_response(304)
                    self.send_header('ETag',etag)
                    self.send_header('Cache-Control',cache_control[cache])
                    self.end_headers()
                    return
                if ranged:
                    m=re.fullmatch(r'bytes=(\d*)-(\d*)',ranged)
                    if not m: return self.send_json({'error':'Range'},416)
                    if m[1]: start=int(m[1]); end=int(m[2]) if m[2] else end
                    elif m[2]: start=max(0,size-int(m[2]))
                    if start>=size or start>end:
                        self.send_response(416); self.send_header('Content-Range',f'bytes */{size}'); self.send_header('Content-Length','0'); self.end_headers(); return
                    end=min(end,size-1)
                self.send_response(206 if ranged else 200)
                self.send_header('Content-Type',content_types.get(p.suffix.lower(),'application/octet-stream'))
                if cache=='no-store':self.send_header('Cache-Control','no-store')
                else:
                    self.send_header('Cache-Control',cache_control[cache])
                    self.send_header('ETag',etag)
                self.send_header('Content-Length',str(end-start+1))
                self.send_header('Accept-Ranges','bytes')
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Referrer-Policy','no-referrer')
                self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self'; connect-src 'self'; frame-ancestors 'none'")
                if ranged: self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
                self.end_headers()
                with open(p,'rb') as f:
                    f.seek(start)
                    remaining=end-start+1
                    while remaining:
                        b=f.read(min(1024*1024,remaining))
                        if not b: break
                        self.wfile.write(b); remaining-=len(b)
            except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError): pass
            except Exception as e:
                suite.log('http_request_failed',route=route,error=str(e))
                self.send_json({'error':str(e)},400)
    class LocalHTTPServer(ThreadingHTTPServer):
        request_queue_size=128
        daemon_threads=True
    server=LocalHTTPServer(('127.0.0.1',port),Handler)
    server.daemon_threads=True
    return server,token

def main():
    from runtime_trust import prepare_runtime
    prepared_components = prepare_runtime(ROOT)
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=['clips'],default='clips')
    parser.add_argument('--serve',action='store_true')
    parser.add_argument('--autostart',action='store_true')
    parser.add_argument('--data')
    parser.add_argument('--smoke',action='store_true')
    parser.add_argument('--report-url',action='store_true')
    parser.add_argument('--tab',choices=['library','replay','customize'],default='library')
    args=parser.parse_args()
    instance = None
    if os.name=='nt' and not args.serve:
        from single_instance import DesktopInstance
        instance = DesktopInstance(Path(args.data or ROOT/'data'))
        if not instance.primary:
            instance.close()
            return
    verify_interface_bundle(ROOT)
    suite=Suite(args.data)
    if prepared_components:suite.log('portable_components_prepared',components=prepared_components)
    suite.app_mode=args.mode
    suite.test_control=args.report_url
    # Only a real installed launch creates the default Windows startup shortcut.
    if os.name=='nt' and not (args.serve or args.smoke or args.data or args.report_url):
        from shortcuts import initialize_autostart
        initialize_autostart(suite,ROOT)
    if os.name=='nt' and not args.serve:
        ctypes.windll.kernel32.FreeConsole()
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('AFTERPLAY.Desktop')
    if args.mode=='clips':
        from replay import Replay
        suite.replay=Replay(suite)
        from capture_profiles import ensure_defaults
        ensure_defaults(suite)
        from auto_record import AutoRecorder
        suite.auto=AutoRecorder(suite)
    server,token=server_for(suite)
    url=f'http://127.0.0.1:{server.server_port}/{token}/index.html?mode={args.mode}&tab={args.tab}'
    if args.report_url:print(url,flush=True)
    if args.serve:
        print(url,flush=True)
        server.serve_forever()
    else:
        import webview
        threading.Thread(target=server.serve_forever,daemon=True).start()
        suite.window=webview.create_window('AFTERPLAY',url,
                                          width=1600,height=1000,min_size=(1050,700),background_color='#101314',hidden=args.smoke or args.autostart,
                                          frameless=True,easy_drag=False,shadow=True)
        from window_chrome import WindowChrome
        suite.chrome=WindowChrome(suite)
        if suite.replay and not args.smoke:suite.replay.attach_desktop()
        if not args.smoke:
            from desktop import Desktop
            suite.desktop=Desktop(suite,args.mode)
            if instance:instance.listen(suite.desktop)
        def smoke():
            if not args.smoke: return
            report={}
            try:
                for _ in range(100):
                    report=suite.window.evaluate_js("({title:document.title,ready:typeof state!=='undefined' && !!state.replay,body:document.body.innerText.slice(0,400)})")
                    if report and report.get('ready'): break
                    time.sleep(.2)
                suite.window.evaluate_js("tab='replay';render()")
                time.sleep(1)
                report['controls']=suite.window.evaluate_js("({minutes:[...document.querySelector('#replaySeconds').options].map(o=>Number(o.value)/60),audio:[...document.querySelector('#replayAudioMode').options].map(o=>o.value),hasApp:!!document.querySelector('#replayApplication'),hasSave:!!document.querySelector('#replaySave'),body:document.body.innerText.slice(0,2500)})")
                report['capture']=suite.window.evaluate_js("({modes:[...document.querySelector('#replayCaptureMode').options].map(o=>o.value),fps:[...document.querySelector('#replayFPS').options].map(o=>Number(o.value)),quality:[...document.querySelector('#replayQuality').options].map(o=>o.value),hasOffset:!!document.querySelector('#replayOffset'),hasResolution:!!document.querySelector('#replayHeight')})")
                report['ok']=bool(report.get('ready') and report['controls']['minutes']==[1,3,5,10,15,20,30] and len(report['controls']['audio'])==5 and report['capture']['modes']==['monitor','window'] and report['capture']['fps']==[24,30,60,90,120] and len(report['capture']['quality'])==3 and report['capture']['hasOffset'] and report['capture']['hasResolution'])
                suite.window.evaluate_js("tab='settings';render()")
                report['preferences']=suite.window.evaluate_js("({cinema:document.body.classList.contains('onyx-cinema'),profile:!!document.querySelector('#cinemaProfile b')?.textContent,themes:[...(document.querySelector('#interfaceTheme')?.options||[])].map(o=>o.value),autostart:!!document.querySelector('#launchAtLogin'),desktop:!!document.querySelector('[data-action=shortcut-desktop]'),taskbar:!!document.querySelector('[data-action=shortcut-taskbar]'),updates:!!document.querySelector('[data-action=update-check]'),noBorderToggle:!document.querySelector('#captureBorder')})")
                preferences=report['preferences']
                design_ok=(preferences['profile'] and not preferences['themes']) if preferences['cinema'] else preferences['themes']==['obsidian','glass','aurora','ember','mist','paper']
                report['ok']=bool(report['ok'] and design_ok and all(preferences[key] for key in ('autostart','desktop','taskbar','updates','noBorderToggle')))
                report['engine']='Microsoft Edge WebView2 / pywebview'
                atomic_json(suite.data/f'verification-native-{args.mode}.json',report)
            finally:
                suite.window.destroy()
        try:
            def ready():
                suite.chrome.attach()
                if args.smoke:smoke()
                else:
                    if suite.desktop:suite.desktop.attach_navigation()
                    if suite.auto:suite.auto.start()
                    threading.Thread(target=monitor_interface,args=(suite,url),daemon=True).start()
                    threading.Thread(target=suite.automatic_updates,daemon=True).start()
                    threading.Thread(target=suite.cleanup_caches,daemon=True).start()
            webview.start(ready,gui='edgechromium',private_mode=True,
                          storage_path=str(suite.data/'webview'/args.mode),
                          icon=str(BASE/'ui'/'afterplay.ico'))
        finally:
            suite.shutdown()
            server.shutdown()
            if instance:instance.close()

if __name__=='__main__':
    try: main()
    except Exception:
        log=ROOT/'data/logs/startup-error.log'
        log.parent.mkdir(parents=True,exist_ok=True)
        log.write_text(traceback.format_exc(),encoding='utf-8')
        if os.name=='nt': ctypes.windll.user32.MessageBoxW(None,'Не удалось открыть приложение. См. data/logs/startup-error.log.', 'AFTERPLAY',16)
        raise
