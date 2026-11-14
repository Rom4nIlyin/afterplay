"""Readable export names with per-process reservations and no silent replacement."""
from contextlib import contextmanager
import re
import threading
from pathlib import Path

_lock=threading.RLock()
_reserved=set()


def clean_name(value,extension,default='clip'):
    name=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',str(value or default)).strip(' .')
    if name.casefold().endswith(extension.casefold()):name=name[:-len(extension)].strip(' .')
    name=name or default
    # Leave space for a numbered duplicate and the extension on Windows.
    while len(name.encode('utf-16-le'))//2>180:name=name[:-1]
    if re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?',name,re.I):
        raise ValueError('Недопустимое имя файла Windows')
    return name


@contextmanager
def reserve_output(folder,name,extension,default='clip'):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    base=clean_name(name,extension,default);number=1
    with _lock:
        while True:
            candidate=folder/(base+('' if number==1 else f' ({number})')+extension)
            key=str(candidate.resolve()).casefold()
            if key not in _reserved and not candidate.exists():break
            number+=1
        _reserved.add(key)
    try:yield candidate
    finally:
        with _lock:_reserved.discard(key)


def commit_output(partial,target):
    target=Path(target)
    if target.exists():raise FileExistsError('Файл с таким именем уже существует: '+target.name)
    # Windows rename refuses an existing target, including a file created after
    # the preceding check. Internal encode files may still use random names.
    Path(partial).rename(target)
