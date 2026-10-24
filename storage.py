"""User-selected recording destinations; existing media is never moved."""
import hashlib
import os
from pathlib import Path
import tempfile


def recording_dir(suite):
    value=suite.cfg.get('storage',{}).get('recordings_dir')
    return Path(value) if value else suite.data/'exports'


def buffer_dir(suite):
    folder=recording_dir(suite)
    if folder.resolve()==(suite.data/'exports').resolve():return suite.data/'replay-buffer'
    return folder/'.afterplay-buffer'


def configure(suite,value):
    if not isinstance(value,str):raise ValueError('Укажите папку для записей')
    folder=Path(os.path.expandvars(os.path.expanduser(value.strip().strip('"')))) if value.strip() else suite.data/'exports'
    if not folder.is_absolute():raise ValueError('Укажите полный путь к папке')
    folder=folder.resolve()
    try:
        folder.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix='.afterplay-check-',dir=folder):pass
    except OSError as error:raise ValueError('В эту папку нельзя сохранять записи: '+str(error)) from error
    previous=[str(recording_dir(suite)),*suite.cfg.get('storage',{}).get('previous_dirs',[])]
    unique={str((suite.data/'exports').resolve()).casefold():str((suite.data/'exports').resolve())}
    for path in previous:
        if Path(path).is_absolute():unique[str(Path(path).resolve()).casefold()]=str(Path(path).resolve())
    suite.cfg['storage']={'recordings_dir':str(folder),'previous_dirs':list(unique.values())[-64:]}
    suite.save_cfg()
    if suite.replay:
        suite.replay.root=buffer_dir(suite);suite.replay.root.mkdir(parents=True,exist_ok=True)
    return state(suite)


def state(suite):
    return {'recordings_dir':str(recording_dir(suite)), 'buffer_dir':str(buffer_dir(suite))}


def exports(suite):
    candidates=[suite.data/'exports',recording_dir(suite),*[Path(p) for p in suite.cfg.get('storage',{}).get('previous_dirs',[])]]
    folders={str(p.resolve()).casefold():p for p in candidates if p.is_absolute()}
    result=[]
    for folder in folders.values():
        try:
            for path in folder.iterdir():
                if path.suffix.lower() not in {'.mp4','.gif'}:continue
                if ('.partial.' in path.name) or path.is_symlink() or not path.is_file():continue
                try:stat=path.stat()
                except OSError:continue
                key=hashlib.sha256(str(path.resolve()).casefold().encode()).hexdigest()[:24]
                result.append({'key':key,'name':path.name,'path':str(path),'size':stat.st_size,'mtime':stat.st_mtime})
        except OSError:continue
    return sorted(result,key=lambda row:row['mtime'],reverse=True)
