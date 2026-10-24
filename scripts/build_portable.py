"""Build a self-contained Windows x64 release. Run with Python 3.13 x64."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ('app.py', 'app_update.py', 'version.py', 'Updater.cs', 'shortcuts.py', 'replay.py', 'capture_media.py', 'gpu_capture.py', 'video_quality.py', 'desktop.py', 'storage.py', 'auto_record.py', 'hotkeys.py', 'gif_media.py', 'timer_overlay.py', 'single_instance.py', 'process_audio.py', 'runtime_trust.py', 'ProcessAudio.cs',
         'Launcher.cs', 'RuntimeExit.cs', 'app.manifest', 'ReplayNotification.cs', 'Install-Shortcuts.ps1', 'Update-Existing.ps1', 'README.md',
         'LICENSE', 'THIRD-PARTY.md', 'FFmpeg-COPYING.GPLv3.txt', 'CHANGELOG.md')
PYTHON_URL = 'https://www.python.org/ftp/python/3.13.0/python-3.13.0-embed-amd64.zip'
WEBVIEW_URL = 'https://go.microsoft.com/fwlink/p/?LinkId=2124701'
FFMPEG_URL = 'https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-9.0.2-essentials_build.zip'
FFMPEG_SHA256 = '60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba'


def install_ffmpeg(cache,runtime):
    archive=Path(cache)/'ffmpeg-9.0.2-essentials_build.zip'
    download(FFMPEG_URL,archive)
    with archive.open('rb') as source:actual=hashlib.file_digest(source,'sha256').hexdigest()
    if actual!=FFMPEG_SHA256:raise ValueError('FFmpeg download SHA-256 mismatch')
    with zipfile.ZipFile(archive) as z:
        with z.open('ffmpeg-9.0.2-essentials_build/bin/ffmpeg.exe') as source,open(Path(runtime)/'ffmpeg.exe','wb') as out:
            shutil.copyfileobj(source,out)

def run(args):
    subprocess.run([str(a) for a in args], check=True)

def download(url, path):
    if path.exists():
        print('Cached:', path.name, flush=True)
        return
    print('Downloading:', path.name, flush=True)
    temp = path.with_suffix(path.suffix + '.partial')
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=120) as response, temp.open('wb') as output:
                shutil.copyfileobj(response, output)
            temp.replace(path)
            return
        except (urllib.error.HTTPError,urllib.error.URLError) as error:
            if isinstance(error,urllib.error.HTTPError) and error.code not in (408,429,500,502,503,504):raise
            if attempt==4:raise
            print('Temporary download error; retrying:',type(error).__name__,flush=True)
            time.sleep(2**attempt)
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
         '/r:System.Windows.Forms.dll', '/r:System.Drawing.dll', '/r:System.Web.Extensions.dll',
         '/win32icon:' + str(ROOT / 'ui/afterplay.ico'), '/win32manifest:'+str(ROOT/'app.manifest'),
         '/out:' + str(target / 'AFTERPLAY.exe'), ROOT / 'Launcher.cs', ROOT / 'RuntimeExit.cs'])
    run([compiler, '/nologo', '/target:winexe', '/platform:x64', '/r:System.Web.Extensions.dll',
         '/r:System.Windows.Forms.dll', '/out:' + str(target / 'Updater.exe'), ROOT / 'Updater.cs'])
    sign_components(target)


def sign_components(target):
    """Use an existing publisher certificate; never create or trust a certificate."""
    thumbprint=os.environ.get('AFTERPLAY_SIGN_THUMBPRINT','').strip()
    if not thumbprint:return
    if not re.fullmatch('[0-9a-fA-F]{40}',thumbprint):raise ValueError('Invalid signing certificate thumbprint')
    script=r'''
$ErrorActionPreference='Stop'
$cert=Get-Item -LiteralPath ('Cert:\CurrentUser\My\'+$env:AFTERPLAY_SIGN_THUMBPRINT)
if (-not $cert.HasPrivateKey -or $cert.NotAfter -lt (Get-Date)) { throw 'Signing certificate is expired or lacks its private key' }
foreach ($name in @('AFTERPLAY.exe','Updater.exe','ProcessAudio.dll','ReplayNotification.dll')) {
 $result=Set-AuthenticodeSignature -LiteralPath (Join-Path $env:AFTERPLAY_SIGN_FOLDER $name) -Certificate $cert -HashAlgorithm SHA256 -TimestampServer 'https://timestamp.digicert.com'
 if ($result.Status -ne 'Valid') { throw ('Authenticode signature validation failed: '+$name+' '+$result.StatusMessage) }
}
'''
    environment={**os.environ,'AFTERPLAY_SIGN_THUMBPRINT':thumbprint,'AFTERPLAY_SIGN_FOLDER':str(Path(target).resolve())}
    environment.pop('PSModulePath',None)
    subprocess.run(['powershell.exe','-NoProfile','-Command',script],env=environment,check=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', default='1.8.1')
    args = parser.parse_args()
    if os.name != 'nt' or sys.version_info[:2] != (3, 13) or struct.calcsize('P') != 8:
        parser.error('Use Windows x64 and 64-bit Python 3.13.')
    if not args.version or any(c not in '0123456789.-' for c in args.version):
        parser.error('Version must contain only digits, dots and hyphens.')
    cache = ROOT / 'build/downloads'
    cache.mkdir(parents=True, exist_ok=True)
    target = ROOT / 'build' / ('portable-' + args.version) / 'AFTERPLAY Portable'
    # Do not delete or overwrite an earlier build or user data.
    target.mkdir(parents=True, exist_ok=False)
    for name in FILES:
        shutil.copy2(ROOT / name, target / name)
    (target / 'version.py').write_text(f"VERSION = '{args.version}'\n", encoding='utf-8')
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
    install_ffmpeg(cache,runtime)
    prerequisites = target / 'prerequisites'
    prerequisites.mkdir()
    installer = cache / 'MicrosoftEdgeWebView2RuntimeInstallerX64.exe'
    download(WEBVIEW_URL, installer)
    # Verify the downloaded Microsoft installer before putting it into a release.
    script = "Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Security/Microsoft.PowerShell.Security.psd1') -ErrorAction Stop; $s=Get-AuthenticodeSignature -LiteralPath $env:AFTERPLAY_WEBVIEW_INSTALLER; if ($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') { throw 'Invalid Microsoft signature' }"
    signature_env = {**os.environ, 'AFTERPLAY_WEBVIEW_INSTALLER': str(installer)}
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
    archive = dist / ('AFTERPLAY-' + args.version + '-Portable-Win64.zip')
    if archive.exists():
        raise FileExistsError(archive)
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in files:
            z.write(p, Path('AFTERPLAY Portable') / p.relative_to(target))
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
