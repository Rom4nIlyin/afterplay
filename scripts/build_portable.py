"""Build a self-contained Windows x64 release. Run with Python 3.13 x64."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ('app.py', 'replay.py', 'capture_media.py', 'video_quality.py', 'desktop.py', 'process_audio.py', 'runtime_trust.py', 'ProcessAudio.cs',
         'Launcher.cs', 'ReplayNotification.cs', 'Install-Shortcuts.ps1', 'README.md',
         'THIRD-PARTY.md', 'FFmpeg-COPYING.GPLv3.txt', 'CHANGELOG.md')
PYTHON_URL = 'https://www.python.org/ftp/python/3.13.0/python-3.13.0-embed-amd64.zip'
WEBVIEW_URL = 'https://go.microsoft.com/fwlink/p/?LinkId=2124701'

def run(args):
    subprocess.run([str(a) for a in args], check=True)

def download(url, path):
    if path.exists():
        print('Cached:', path.name, flush=True)
        return
    print('Downloading:', path.name, flush=True)
    temp = path.with_suffix(path.suffix + '.partial')
    try:
        with urllib.request.urlopen(url, timeout=120) as response, temp.open('wb') as output:
            shutil.copyfileobj(response, output)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)

def compile_components(target):
    compiler = Path(os.environ['WINDIR']) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    if not compiler.exists():
        raise RuntimeError('.NET Framework x64 compiler is missing: ' + str(compiler))
    for name in ('ProcessAudio', 'ReplayNotification'):
        args = [compiler, '/nologo', '/target:library', '/platform:x64',
                '/out:' + str(target / (name + '.dll'))]
        if name == 'ReplayNotification':
            args += ['/r:System.Windows.Forms.dll', '/r:System.Drawing.dll']
        run(args + [ROOT / (name + '.cs')])
    run([compiler, '/nologo', '/target:winexe', '/platform:x64',
         '/r:System.Windows.Forms.dll', '/r:System.Drawing.dll',
         '/win32icon:' + str(ROOT / 'ui/clips.ico'),
         '/out:' + str(target / 'Game Clips.exe'), ROOT / 'Launcher.cs'])

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', default='1.2.0')
    args = parser.parse_args()
    if os.name != 'nt' or sys.version_info[:2] != (3, 13) or struct.calcsize('P') != 8:
        parser.error('Use Windows x64 and 64-bit Python 3.13.')
    if not args.version or any(c not in '0123456789.-' for c in args.version):
        parser.error('Version must contain only digits, dots and hyphens.')
    cache = ROOT / 'build/downloads'
    cache.mkdir(parents=True, exist_ok=True)
    target = ROOT / 'build' / ('portable-' + args.version) / 'Game Clips Portable'
    # Do not delete or overwrite an earlier build or user data.
    target.mkdir(parents=True, exist_ok=False)
    for name in FILES:
        shutil.copy2(ROOT / name, target / name)
    shutil.copytree(ROOT / 'ui', target / 'ui')
    shutil.copytree(ROOT / 'docs', target / 'docs')
    compile_components(target)
    runtime = target / 'runtime'
    runtime.mkdir()
    embedded = cache / 'python-3.13.0-embed-amd64.zip'
    download(PYTHON_URL, embedded)
    with zipfile.ZipFile(embedded) as z:
        z.extractall(runtime)
    site = runtime / 'Lib/site-packages'
    run([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
         '--only-binary=:all:', '--no-binary=proxy_tools', '--target', site,
         '-r', ROOT / 'requirements-lock.txt'])
    for dll in (site / 'pywin32_system32').glob('*.dll'):
        shutil.copy2(dll, runtime / dll.name)
    (runtime / 'python313._pth').write_text(
        'python313.zip\n.\n..\nLib/site-packages\nLib/site-packages/win32\n'
        'Lib/site-packages/win32/lib\nLib/site-packages/pythonwin\nimport site\n', encoding='utf-8')
    prerequisites = target / 'prerequisites'
    prerequisites.mkdir()
    installer = cache / 'MicrosoftEdgeWebView2RuntimeInstallerX64.exe'
    download(WEBVIEW_URL, installer)
    # Verify the downloaded Microsoft installer before putting it into a release.
    script = "Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Security/Microsoft.PowerShell.Security.psd1') -ErrorAction Stop; $s=Get-AuthenticodeSignature -LiteralPath $env:GAME_CLIPS_WEBVIEW_INSTALLER; if ($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') { throw 'Invalid Microsoft signature' }"
    signature_env = {**os.environ, 'GAME_CLIPS_WEBVIEW_INSTALLER': str(installer)}
    signature_env.pop('PSModulePath', None)  # Do not pass PowerShell 7 modules to Windows PowerShell.
    subprocess.run(['powershell.exe', '-NoProfile', '-Command', script], check=True,
                   env=signature_env)
    shutil.copy2(installer, prerequisites / installer.name)
    files = sorted(p for p in target.rglob('*') if p.is_file()
                   and '__pycache__' not in p.parts and p.suffix != '.pyc')
    sums = {p.relative_to(target).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    manifest = target / 'SHA256SUMS.json'
    manifest.write_text(json.dumps(sums, indent=2), encoding='utf-8')
    files.append(manifest)
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    archive = dist / ('Game-Clips-' + args.version + '-Portable-Win64.zip')
    if archive.exists():
        raise FileExistsError(archive)
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in files:
            z.write(p, Path('Game Clips Portable') / p.relative_to(target))
    with zipfile.ZipFile(archive) as z:
        corrupt = z.testzip()
        if corrupt:
            raise RuntimeError('Archive verification failed: ' + corrupt)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(digest + '  ' + archive.name + '\n', encoding='utf-8')
    print('Ready:', archive)
    print('SHA-256:', digest)

if __name__ == '__main__':
    main()
