from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from app import Suite
import process_audio
import storage

class StorageTests(unittest.TestCase):
    def test_destination_persists_and_keeps_previous_exports_visible(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);suite=Suite(root/'data')
            old=suite.data/'exports'/'old.mp4';old.write_bytes(b'old media')
            chosen=root/'Новые записи';suite.dispatch('storage_config',{'recordings_dir':str(chosen)})
            self.assertTrue(old.is_file());self.assertEqual(old.read_bytes(),b'old media')
            self.assertEqual(Suite(suite.data).recordings_dir(),chosen.resolve())
            new=chosen/'new.mp4';new.write_bytes(b'new media')
            (chosen/'incomplete.partial.mp4').write_bytes(b'partial')
            names={row['name'] for row in suite.dispatch('exports',{})}
            self.assertEqual(names,{'old.mp4','new.mp4'})
            suite.dispatch('storage_config',{'recordings_dir':str(root/'Другие записи')})
            self.assertEqual({row['name'] for row in suite.dispatch('exports',{})},{'old.mp4','new.mp4'})
            self.assertFalse(list(chosen.glob('.afterplay-check-*')))
    def test_duplicate_filenames_have_distinct_opaque_export_keys(self):
        with tempfile.TemporaryDirectory() as temp:
            suite=Suite(Path(temp)/'data');(suite.data/'exports'/'same.mp4').write_bytes(b'one')
            folder=Path(temp)/'other';suite.dispatch('storage_config',{'recordings_dir':str(folder)})
            (folder/'same.mp4').write_bytes(b'two')
            rows=suite.dispatch('exports',{});self.assertEqual(len(rows),2)
            self.assertNotEqual(rows[0]['key'],rows[1]['key'])
            with self.assertRaises(ValueError):suite.recycle_video({'export_key':'../../outside.mp4'})
    def test_changes_are_blocked_while_recording_and_invalid_paths_do_not_persist(self):
        with tempfile.TemporaryDirectory() as temp:
            suite=Suite(Path(temp)/'data');before=dict(suite.cfg)
            with self.assertRaises(ValueError):suite.dispatch('storage_config',{'recordings_dir':'relative/folder'})
            self.assertEqual(before,suite.cfg)
            suite.replay=SimpleNamespace(phase='recording',saving=False)
            with self.assertRaises(ValueError):suite.dispatch('storage_config',{'recordings_dir':str(Path(temp)/'new')})
            self.assertEqual(before,suite.cfg)
    def test_buffer_follows_custom_destination_and_default_remains_portable(self):
        with tempfile.TemporaryDirectory() as temp:
            suite=Suite(Path(temp)/'data');self.assertEqual(storage.buffer_dir(suite),suite.data/'replay-buffer')
            folder=Path(temp)/'recordings';suite.dispatch('storage_config',{'recordings_dir':str(folder)})
            self.assertEqual(storage.buffer_dir(suite),folder.resolve()/'.afterplay-buffer')
    def test_library_view_persists_without_changing_theme(self):
        with tempfile.TemporaryDirectory() as temp:
            suite=Suite(temp);suite.dispatch('appearance_config',{'theme':'obsidian'})
            suite.dispatch('appearance_config',{'library_view':'list'})
            self.assertEqual(Suite(temp).cfg['appearance'],{'theme':'obsidian','library_view':'list'})
            with self.assertRaises(ValueError):suite.dispatch('appearance_config',{'library_view':'unknown'})

class PlatformTests(unittest.TestCase):
    @unittest.skipUnless(__import__('os').name=='nt','Windows version check')
    def test_old_manifest_version_does_not_disable_modern_process_audio(self):
        if process_audio.windows_version()[2]<20348:self.skipTest('Process audio not supported by the host OS')
        with patch.object(process_audio.sys,'getwindowsversion',return_value=SimpleNamespace(build=9200)):
            self.assertTrue(process_audio.supported())

if __name__=='__main__':unittest.main()
