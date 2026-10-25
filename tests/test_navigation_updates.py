from pathlib import Path
import io,json,tempfile,unittest
from unittest.mock import patch
from app import Suite
import app_update


class NavigationAndUpdateTests(unittest.TestCase):
    def test_open_in_folder_passes_exact_unicode_path_as_one_argument(self):
        with tempfile.TemporaryDirectory() as tmp:
            suite=Suite(tmp);path=Path(tmp)/'Имя с пробелами.mp4';path.write_bytes(b'fixture')
            with patch.object(suite,'clip',return_value={'path':str(path)}),patch('app.subprocess.Popen') as opened:
                self.assertEqual(suite.dispatch('open',{'target':'clip-folder','id':'clip'}),{'ok':True})
                self.assertEqual(opened.call_args.args[0],['explorer.exe','/select,',str(path)])
            path.unlink()
            with patch.object(suite,'clip',return_value={'path':str(path)}),patch('app.subprocess.Popen') as opened:
                with self.assertRaises(ValueError):suite.dispatch('open',{'target':'clip-folder','id':'clip'})
                opened.assert_not_called()

    def test_check_contacts_metadata_only_without_preparing_or_installing(self):
        with tempfile.TemporaryDirectory() as tmp:
            updater=app_update.AppUpdater(tmp,Path(tmp)/'data')
            metadata={'tag_name':'v99.0.0','draft':False,'prerelease':False,'assets':[{
                'name':'AFTERPLAY-99.0.0-Portable-Win64.zip','size':1000000,'state':'uploaded',
                'browser_download_url':'https://github.com/'+app_update.REPOSITORY+'/releases/download/v99.0.0/AFTERPLAY-99.0.0-Portable-Win64.zip','digest':'sha256:'+'a'*64}]}
            with patch.object(app_update,'open_url',return_value=io.BytesIO(json.dumps(metadata).encode())) as network:
                result=updater.check()
            network.assert_called_once_with(app_update.LATEST_URL)
            self.assertTrue(result['latest']['available']);self.assertIsNone(updater.prepared)
            self.assertFalse(list(Path(tmp).iterdir()))

    def test_filmstrip_rejects_invalid_viewport_without_invoking_ffmpeg(self):
        with tempfile.TemporaryDirectory() as tmp:
            suite=Suite(tmp);source=Path(tmp)/'video.mp4';source.write_bytes(b'fixture')
            with patch.object(suite,'clip',return_value={'path':str(source),'duration':300}),patch.object(suite,'ff') as ff:
                for start,end in ((-1,3),(4,3),(0,301),(float('nan'),3),(0,float('inf'))):
                    with self.assertRaises(ValueError):suite.filmstrip('id',start,end)
                ff.assert_not_called()
                for frames in (0,65,'invalid'):
                    with self.assertRaises(ValueError):suite.filmstrip('id',0,10,frames)
                ff.assert_not_called()
