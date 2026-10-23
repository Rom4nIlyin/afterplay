"""Explicit portable updates from this project's public GitHub Releases."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from version import VERSION

REPOSITORY = 'Rom4nIlyin/game-clips'
LATEST_URL = f'https://api.github.com/repos/{REPOSITORY}/releases/latest'
MAX_DOWNLOAD = 1024**3
MAX_EXTRACT = 3*1024**3

def version_tuple(value):
    if not re.fullmatch(r'v?\d+\.\d+\.\d+', value):
        raise ValueError('Некорректный номер версии GitHub')
    return tuple(map(int, value.lstrip('v').split('.')))

def allowed_url(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None,443):
        raise ValueError('Некорректный адрес обновления')
    if parsed.hostname not in {'api.github.com','github.com','release-assets.githubusercontent.com','objects.githubusercontent.com'}:
        raise ValueError('Обновление должно загружаться с GitHub')
    return url

class GitHubRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return super().redirect_request(req,fp,code,msg,headers,allowed_url(newurl))

def open_url(url):
    req=urllib.request.Request(allowed_url(url),headers={'User-Agent':f'Game-Clips/{VERSION}', 'Accept':'application/vnd.github+json'})
    return urllib.request.build_opener(GitHubRedirect()).open(req,timeout=30)

def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def safe_name(name):
    p=PurePosixPath(name)
    if (not name or '\\' in name or ':' in name or p.is_absolute() or
        any(part in ('','.', '..') or part.endswith((' ','.')) for part in name.split('/')) or
        p.parts[0].lower() in {'data','backups'} or
        any(re.fullmatch(r'(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?',part,re.I) for part in p.parts)):
        raise ValueError('Небезопасный путь в обновлении: '+name)
    return p

def release_info(release, current=VERSION):
    if release.get('draft') or release.get('prerelease'):raise ValueError('Ожидался стабильный релиз')
    tag=release.get('tag_name','');version=tag.lstrip('v');new=version_tuple(tag)
    name=f'Game-Clips-{version}-Portable-Win64.zip'
    assets={a['name']:a for a in release.get('assets',[])}
    asset=assets.get(name)
    if not asset or asset.get('state')!='uploaded':raise ValueError('В релизе пока нет готового портативного архива')
    expected=f'https://github.com/{REPOSITORY}/releases/download/{tag}/{name}'
    if asset.get('browser_download_url')!=expected:raise ValueError('Архив принадлежит другому репозиторию')
    size=int(asset.get('size',0))
    if not 1000<size<=MAX_DOWNLOAD:raise ValueError('Недопустимый размер обновления')
    checksum=asset.get('digest','') or ''
    if not re.fullmatch(r'sha256:[0-9a-fA-F]{64}',checksum):
        sidecar=assets.get(name+'.sha256',{})
        if sidecar.get('browser_download_url')!=expected+'.sha256':raise ValueError('Нет контрольной суммы обновления')
        with open_url(expected+'.sha256') as response:line=response.read(4097).decode('utf-8').strip()
        match=re.fullmatch(r'([0-9a-fA-F]{64})\s+\*?'+re.escape(name),line)
        if not match:raise ValueError('Некорректная контрольная сумма')
        checksum='sha256:'+match[1]
    return {'version':version,'available':new>version_tuple(current),'url':expected,'sha256':checksum[7:].lower(),
            'bytes':size,'release_url':f'https://github.com/{REPOSITORY}/releases/tag/{tag}',
            'notes':str(release.get('body',''))[:16000]}

def unpack_verified(archive, destination, expected_version):
    """Validate all member names before extracting any; allow only catalogued files."""
    destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(archive) as z:
        names=set();members=[];total=0
        for info in z.infolist():
            if info.is_dir():continue
            prefix='Game Clips Portable/'
            if not info.filename.startswith(prefix):raise ValueError('Некорректная структура архива')
            name=info.filename[len(prefix):];safe_name(name)
            if name.casefold() in names:raise ValueError('Повторяющийся путь в архиве')
            names.add(name.casefold())
            if stat.S_ISLNK(info.external_attr>>16):raise ValueError('Ссылки в обновлении запрещены')
            total+=info.file_size
            if total>MAX_EXTRACT or len(names)>15000:raise ValueError('Слишком большой распакованный архив')
            members.append((info,name))
        if shutil.disk_usage(destination).free<total*2+256*1024**2:raise ValueError('Не хватает места для обновления и резервной копии')
        for info,name in members:
            target=destination/name;target.parent.mkdir(parents=True,exist_ok=True)
            with z.open(info) as source,target.open('wb') as out:shutil.copyfileobj(source,out,1024*1024)
    manifest=json.loads((destination/'SHA256SUMS.json').read_text('utf-8'))
    if not isinstance(manifest,dict):raise ValueError('Некорректный каталог обновления')
    required={'app.py','version.py','Updater.exe','Game Clips.exe','runtime/pythonw.exe'}
    if not required.issubset(manifest):raise ValueError('Неполный комплект обновления')
    if {name for _,name in members}!=set(manifest)|{'SHA256SUMS.json'}:raise ValueError('Архив не соответствует каталогу файлов')
    for name,checksum in manifest.items():
        safe_name(name)
        if not isinstance(checksum,str) or not re.fullmatch('[0-9a-f]{64}',checksum) or digest(destination/name)!=checksum:
            raise ValueError('Проверка SHA-256 не пройдена: '+name)
    version_text=(destination/'version.py').read_text('utf-8').strip()
    if version_text!=f"VERSION = '{expected_version}'":raise ValueError('Версия внутри архива не совпадает с релизом')
    return [{'path':name,'sha256':digest(destination/name)} for name in sorted([*manifest,'SHA256SUMS.json'])]

class AppUpdater:
    def __init__(self, root, data):
        self.root=Path(root).resolve();self.data=Path(data).resolve()
        self.lock=threading.Lock();self.busy=False;self.latest=None;self.prepared=None;self.error=''
        self._cleanup_completed_cache()

    def _cleanup_completed_cache(self):
        try:
            status=json.loads((self.data/'update-status.json').read_text('utf-8'))
            cache=Path(status['stage']).resolve().parent
            expected=(Path(os.environ.get('LOCALAPPDATA',tempfile.gettempdir()))/'GameClips/updates').resolve()
            if (status.get('success') and status.get('version')==VERSION and cache.parent==expected
                and re.fullmatch('[0-9a-f]{32}',cache.name) and (cache/'.game-clips-update').is_file()):
                shutil.rmtree(cache)
        except (OSError,ValueError,KeyError,TypeError):pass

    def state(self):
        result=None
        try:result=json.loads((self.data/'update-status.json').read_text('utf-8'))
        except (OSError,ValueError):pass
        return {'version':VERSION,'latest':self.latest,'busy':self.busy,'prepared':bool(self.prepared),
                'error':self.error,'last_result':result,
                'supported':(self.root/'Updater.exe').is_file() and (self.root/'runtime/pythonw.exe').is_file()}

    def check(self):
        try:
            with open_url(LATEST_URL) as response:
                raw=response.read(2*1024*1024+1)
                if len(raw)>2*1024*1024:raise ValueError('Слишком большой ответ GitHub')
                self.latest=release_info(json.loads(raw))
            self.error='';return self.state()
        except Exception as error:
            self.error='Не удалось проверить GitHub. Проверьте интернет и попробуйте ещё раз. '+str(error)
            raise ValueError(self.error) from error

    def prepare(self,job):
        if not self.lock.acquire(blocking=False):raise ValueError('Обновление уже загружается')
        cache=None
        try:
            self.busy=True;self.error='';self.prepared=None
            self.check();latest=self.latest
            if not latest['available']:raise ValueError('Уже установлена последняя версия')
            if not self.state()['supported']:raise ValueError('Автообновление доступно в портативной сборке')
            if shutil.disk_usage(self.root).free<latest['bytes']*6+512*1024**2:raise ValueError('Недостаточно места для обновления и резервной копии')
            with tempfile.NamedTemporaryFile(dir=self.root,prefix='.update-write-',delete=True):pass
            cache_root=Path(os.environ.get('LOCALAPPDATA',tempfile.gettempdir()))/'GameClips'/'updates'
            cache_root.mkdir(parents=True,exist_ok=True)
            cache=cache_root/uuid.uuid4().hex;cache.mkdir()
            (cache/'.game-clips-update').write_text('Owned Game Clips update cache','utf-8')
            archive=cache/'release.zip';received=0;hasher=hashlib.sha256()
            with open_url(latest['url']) as response,archive.open('wb') as out:
                while True:
                    chunk=response.read(1024*1024)
                    if not chunk:break
                    received+=len(chunk)
                    if received>latest['bytes']:raise ValueError('Размер архива не совпадает с релизом')
                    hasher.update(chunk);out.write(chunk)
                    job.update(progress=round(received/latest['bytes']*80),message=f'Загрузка {received/1024**2:.0f} / {latest["bytes"]/1024**2:.0f} МБ')
            if received!=latest['bytes'] or hasher.hexdigest()!=latest['sha256']:raise ValueError('Проверка скачанного архива не пройдена')
            job.update(progress=85,message='Проверка и распаковка обновления')
            files=unpack_verified(archive,cache/'bundle',latest['version'])
            # Run an independent helper so no runtime file being replaced is loaded.
            helper=cache/'Updater.exe';shutil.copy2(cache/'bundle/Updater.exe',helper)
            self.prepared={'target':str(self.root),'stage':str(cache/'bundle'),'version':latest['version'],
                           'files':files,'status':str(self.data/'update-status.json'),'restart':True,'quiet':False}
            archive.unlink();job.update(progress=100,message='Готово к перезапуску');self.busy=False
            return self.state()
        except Exception as error:
            self.error=str(error)
            if cache and cache.parent.name=='updates':shutil.rmtree(cache,ignore_errors=True)
            raise
        finally:self.busy=False;self.lock.release()

    def launch(self):
        if not self.prepared:raise ValueError('Сначала скачайте обновление')
        plan={**self.prepared,'parent_pid':os.getpid()}
        stage=Path(plan['stage']);helper=stage.parent/'Updater.exe'
        if digest(helper)!=next(f['sha256'] for f in plan['files'] if f['path']=='Updater.exe'):
            raise ValueError('Компонент обновления повреждён')
        path=stage.parent/'plan.json';path.write_text(json.dumps(plan,ensure_ascii=False),'utf-8')
        subprocess.Popen([str(helper),str(path)],cwd=stage.parent,stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=0x08000000)
        return {'restarting':True,'version':plan['version']}
