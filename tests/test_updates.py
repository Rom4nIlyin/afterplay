import ctypes
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import app_update as update
from shortcuts import create_shortcut,set_autostart,APP_ID

def sample_files(version='1.3.1'):
    return {'app.py':b'new application\n','version.py':f"VERSION = '{version}'\n".encode(),
            'Updater.exe':b'updater fixture','AFTERPLAY.exe':b'launcher fixture','runtime/pythonw.exe':b'python fixture'}

def make_archive(path,files=None):
    files=files or sample_files()
    sums={name:hashlib.sha256(data).hexdigest() for name,data in files.items()}
    with zipfile.ZipFile(path,'w') as z:
        for name,data in files.items():z.writestr('AFTERPLAY Portable/'+name,data)
        z.writestr('AFTERPLAY Portable/SHA256SUMS.json',json.dumps(sums))

def release(archive,version='1.3.1'):
    name=f'AFTERPLAY-{version}-Portable-Win64.zip'
    return {'tag_name':'v'+version,'draft':False,'prerelease':False,'assets':[{
        'name':name,'state':'uploaded','size':Path(archive).stat().st_size,
        'browser_download_url':f'https://github.com/{update.REPOSITORY}/releases/download/v{version}/{name}',
        'digest':'sha256:'+update.digest(archive)}]}

class UpdateValidationTests(unittest.TestCase):
    def test_theme_preference_persists_and_rejects_unknown_theme(self):
        from app import Suite
        with tempfile.TemporaryDirectory() as tmp:
            suite=Suite(tmp)
            for theme in ('standard','dark','light'):
                suite.dispatch('appearance_config',{'theme':theme})
                self.assertEqual(json.loads(suite.cfg_path.read_text('utf-8'))['appearance']['theme'],theme)
            with self.assertRaises(ValueError):suite.dispatch('appearance_config',{'theme':'other'})

    def test_semantic_version_and_stable_release_selection(self):
        self.assertGreater(update.version_tuple('v1.10.0'),update.version_tuple('1.9.9'))
        with tempfile.TemporaryDirectory() as tmp:
            archive=Path(tmp)/'release.zip';make_archive(archive);info=release(archive)
            self.assertTrue(update.release_info(info,current='1.2.0')['available'])
            self.assertFalse(update.release_info(info,current='1.3.1')['available'])
            with self.assertRaises(ValueError):update.release_info({**info,'prerelease':True})
            info['assets'][0]['browser_download_url']='https://example.com/other.zip'
            with self.assertRaises(ValueError):update.release_info(info)

    def test_rejects_traversal_user_data_and_unsafe_redirects(self):
        for name in ('../app.py','data/settings.json','backups/old.exe','runtime/../app.py','a:Zone.Identifier','CON.txt','a\\b.py'):
            with self.assertRaises(ValueError,msg=name):update.safe_name(name)
        for url in ('http://github.com/a','https://evil.example/a','https://github.com@evil.example/a'):
            with self.assertRaises(ValueError):update.allowed_url(url)
        with tempfile.TemporaryDirectory() as tmp:
            archive=Path(tmp)/'bad.zip'
            with zipfile.ZipFile(archive,'w') as z:z.writestr('AFTERPLAY Portable/../escape.txt','bad')
            with self.assertRaises(ValueError):update.unpack_verified(archive,Path(tmp)/'bundle','1.3.1')
            self.assertFalse((Path(tmp)/'escape.txt').exists())

    def test_hash_and_version_mismatch_prevent_installation(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);archive=tmp/'good.zip';make_archive(archive)
            files=update.unpack_verified(archive,tmp/'good','1.3.1')
            self.assertIn('SHA256SUMS.json',{f['path'] for f in files})
            with self.assertRaises(ValueError):update.unpack_verified(archive,tmp/'wrong-version','9.9.9')
            with zipfile.ZipFile(archive) as original,zipfile.ZipFile(tmp/'bad.zip','w') as broken:
                for f in original.infolist():broken.writestr(f,b'changed' if f.filename.endswith('/app.py') else original.read(f))
            with self.assertRaises(ValueError):update.unpack_verified(tmp/'bad.zip',tmp/'damaged','1.3.1')

    def test_download_prepare_verifies_actual_bytes_and_writes_no_user_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);target=tmp/'installed';target.mkdir();(target/'runtime').mkdir()
            (target/'Updater.exe').write_bytes(b'old');(target/'runtime/pythonw.exe').write_bytes(b'old')
            archive=tmp/'release.zip';make_archive(archive);metadata=json.dumps(release(archive)).encode()
            updater=update.AppUpdater(target,target/'data')
            def network(url):return io.BytesIO(metadata if url==update.LATEST_URL else archive.read_bytes())
            release_info=update.release_info
            with patch.object(update,'open_url',side_effect=network),patch.object(update,'release_info',side_effect=lambda info:release_info(info,current='1.2.0')),patch.dict(os.environ,{'LOCALAPPDATA':str(tmp/'cache')}):
                state=updater.prepare({})
            self.assertTrue(state['prepared']);self.assertFalse(state['busy'])
            self.assertEqual((target/'Updater.exe').read_bytes(),b'old')
            self.assertFalse((target/'data').exists())
            self.assertTrue(Path(updater.prepared['stage']).is_dir())

@unittest.skipUnless(os.name=='nt','Windows Shell integration')
class ShortcutTests(unittest.TestCase):
    def test_desktop_and_autostart_use_launcher_and_preserve_other_shortcuts(self):
        import pythoncom,win32com.client
        from win32com.propsys import propsys,pscon
        pythoncom.CoInitialize()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp=Path(tmp);root=tmp/'app';root.mkdir();exe=root/'AFTERPLAY.exe';exe.write_bytes(b'fixture')
                desktop=tmp/'desktop';link=create_shortcut(root,folder=desktop)
                shell=win32com.client.Dispatch('WScript.Shell');saved=shell.CreateShortcut(str(link))
                self.assertTrue(os.path.samefile(saved.TargetPath,exe))
                self.assertTrue(os.path.samefile(saved.WorkingDirectory,root))
                store=propsys.SHGetPropertyStoreFromParsingName(str(link))
                self.assertEqual(store.GetValue(pscon.PKEY_AppUserModel_ID).GetValue(),APP_ID)
                # A different install keeps its own shortcut and startup entry.
                other=tmp/'other';other.mkdir();(other/'AFTERPLAY.exe').write_bytes(b'other')
                other_link=create_shortcut(other,folder=desktop)
                self.assertNotEqual(link,other_link);self.assertTrue(link.exists())
                startup=tmp/'startup';first=set_autostart(root,True,startup)
                set_autostart(other,True,startup);set_autostart(root,False,startup)
                self.assertFalse(Path(first['path']).exists());self.assertEqual(len(list(startup.glob('*.lnk'))),1)
                del saved,store,shell
        finally:pythoncom.CoUninitialize()

@unittest.skipUnless(os.name=='nt','Windows update transaction')
class NativeUpdaterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace=tempfile.TemporaryDirectory();cls.home=Path(cls.workspace.name)
        cls.helper=cls.home/'Updater.exe'
        compiler=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        source=Path(__file__).resolve().parents[1]/'Updater.cs'
        subprocess.run([str(compiler),'/nologo','/target:winexe','/platform:x64','/r:System.Web.Extensions.dll','/r:System.Windows.Forms.dll',
                        '/out:'+str(cls.helper),str(source)],check=True,capture_output=True)

    @classmethod
    def tearDownClass(cls):cls.workspace.cleanup()

    def fixture(self,name):
        home=self.home/name;home.mkdir();target=home/'installed';stage=home/'stage';target.mkdir();stage.mkdir()
        files=sample_files()
        files['SHA256SUMS.json']=json.dumps({k:hashlib.sha256(v).hexdigest() for k,v in files.items()}).encode()
        entries=[]
        for path,data in files.items():
            for root,content in ((stage,data),(target,b'old '+data)):
                p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(content)
            entries.append({'path':path,'sha256':hashlib.sha256(data).hexdigest()})
        (target/'data').mkdir();(target/'data/settings.json').write_text('user settings','utf-8')
        (target/'data/clip.mp4').write_bytes(b'user video')
        plan={'target':str(target),'stage':str(stage),'version':'1.3.1','parent_pid':0,'files':entries,
              'status':str(target/'data/update-status.json'),'restart':False,'quiet':True}
        path=home/'plan.json';path.write_text(json.dumps(plan),'utf-8')
        return target,stage,path

    def test_installs_with_backup_and_preserves_clips_and_settings(self):
        target,stage,plan=self.fixture('success')
        result=subprocess.run([str(self.helper),str(plan)],timeout=30)
        self.assertEqual(result.returncode,0)
        self.assertEqual((target/'app.py').read_bytes(),(stage/'app.py').read_bytes())
        status=json.loads((target/'data/update-status.json').read_text('utf-8'));self.assertTrue(status['success'])
        self.assertEqual((Path(status['backup'])/'app.py').read_bytes(),b'old '+(stage/'app.py').read_bytes())
        self.assertEqual((target/'data/settings.json').read_text('utf-8'),'user settings')
        self.assertEqual((target/'data/clip.mp4').read_bytes(),b'user video')

    def test_locked_file_rolls_back_already_replaced_files(self):
        target,stage,plan=self.fixture('rollback');original=(target/'app.py').read_bytes()
        kernel=ctypes.windll.kernel32;kernel.CreateFileW.restype=ctypes.c_void_p
        kernel.CloseHandle.argtypes=[ctypes.c_void_p]
        handle=kernel.CreateFileW(str(target/'version.py'),0x80000000,1,None,3,0,None)
        self.assertNotEqual(handle,ctypes.c_void_p(-1).value)
        try:result=subprocess.run([str(self.helper),str(plan)],timeout=30)
        finally:kernel.CloseHandle(handle)
        self.assertEqual(result.returncode,1);self.assertEqual((target/'app.py').read_bytes(),original)
        status=json.loads((target/'data/update-status.json').read_text('utf-8'));self.assertFalse(status['success'])
        self.assertIn('восстановлены',status['message'])
        self.assertEqual((target/'data/clip.mp4').read_bytes(),b'user video')

    def test_retires_only_unchanged_catalogued_program_files_and_backs_them_up(self):
        target,stage,plan=self.fixture('retired')
        (target/'obsolete.exe').write_bytes(b'obsolete launcher')
        (target/'modified.txt').write_bytes(b'local changes')
        previous={'obsolete.exe':hashlib.sha256(b'obsolete launcher').hexdigest(),
                  'modified.txt':hashlib.sha256(b'original').hexdigest()}
        (target/'SHA256SUMS.json').write_text(json.dumps(previous),'utf-8')
        result=subprocess.run([str(self.helper),str(plan)],timeout=30)
        self.assertEqual(result.returncode,0)
        self.assertFalse((target/'obsolete.exe').exists())
        self.assertEqual((target/'modified.txt').read_bytes(),b'local changes')
        status=json.loads((target/'data/update-status.json').read_text('utf-8'))
        self.assertEqual((Path(status['backup'])/'obsolete.exe').read_bytes(),b'obsolete launcher')
        self.assertEqual(status['retired'],['obsolete.exe'])

if __name__=='__main__':unittest.main()
