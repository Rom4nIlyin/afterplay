"""Regenerate a verified portable archive after signing only our own PE files."""
from pathlib import Path
import argparse,hashlib,json,os,re,zipfile

SIGNABLE={'AFTERPLAY.exe','Updater.exe','ProcessAudio.dll','ReplayNotification.dll'}
SIGNABLE |= {'app/'+name for name in SIGNABLE if name != 'AFTERPLAY.exe'}

def repackage(bundle,output,version):
    bundle=Path(bundle).resolve();output=Path(output).resolve()
    if not re.fullmatch(r'\d+\.\d+\.\d+',version):raise ValueError('Invalid version')
    prefix='app/' if (bundle/'app/app.py').is_file() else ''
    catalog=prefix+'SHA256SUMS.json'
    if (bundle/(prefix+'version.py')).read_text('utf-8').strip()!=f"VERSION = '{version}'":raise ValueError('Version mismatch')
    previous=json.loads((bundle/catalog).read_text('utf-8'));sums={}
    for name,checksum in previous.items():
        if '\\' in name or ':' in name or '..' in Path(name).parts or Path(name).is_absolute():raise ValueError('Unsafe catalog entry')
        path=(bundle/name).resolve()
        if not path.is_relative_to(bundle) or name.split('/')[0].lower() in {'data','backups'}:raise ValueError('Unsafe catalog entry')
        with path.open('rb') as source:actual=hashlib.file_digest(source,'sha256').hexdigest()
        if actual!=checksum and name not in SIGNABLE:raise ValueError('Unexpected signing modification: '+name)
        sums[name]=actual
    (bundle/catalog).write_text(json.dumps(sums,indent=2),encoding='utf-8')
    output.mkdir(parents=True,exist_ok=True);archive=output/f'AFTERPLAY-{version}-Portable-Win64.zip'
    temporary=archive.with_suffix('.partial.zip')
    try:
        with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for name in sorted([*sums,catalog]):z.write(bundle/name,'AFTERPLAY Portable/'+name)
        with zipfile.ZipFile(temporary) as z:
            if z.testzip():raise ValueError('Archive CRC failed')
            for name,checksum in sums.items():
                if hashlib.sha256(z.read('AFTERPLAY Portable/'+name)).hexdigest()!=checksum:raise ValueError('Archive SHA-256 failed')
        os.replace(temporary,archive)
    finally:temporary.unlink(missing_ok=True)
    with archive.open('rb') as source:checksum=hashlib.file_digest(source,'sha256').hexdigest()
    archive.with_suffix('.zip.sha256').write_text(checksum+'  '+archive.name+'\n',encoding='utf-8')
    return archive

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',required=True);p.add_argument('--output',required=True);p.add_argument('--version',required=True)
    a=p.parse_args();print(repackage(a.bundle,a.output,a.version))
