from pathlib import Path
import json,tempfile,unittest,sys,types
from contextlib import contextmanager
from unittest.mock import patch,Mock
from app import Suite
import storage

@contextmanager
def recycle_stub(side_effect=None):
    mocked=Mock(side_effect=side_effect)
    modules={name:types.ModuleType(name) for name in ('send2trash','send2trash.win','send2trash.win.modern')}
    modules['send2trash.win.modern'].send2trash=mocked
    with patch.dict(sys.modules,modules):yield mocked


class VideoDeleteTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.suite=Suite(self.root/'data')
        self.video=self.root/'selected.mp4';self.video.write_bytes(b'selected fixture')
        self.neighbor=self.root/'keep.mp4';self.neighbor.write_bytes(b'keep fixture')
        self.add('selected',self.video);self.add('neighbor',self.neighbor)

    def add(self,identifier,path):
        with self.suite.db() as db:db.execute('INSERT INTO clips(id,path,name) VALUES(?,?,?)',(identifier,str(path),path.name))

    def test_default_recycles_only_selected_video_and_preserves_metadata(self):
        recycled=self.root/'mock-recycle-bin.mp4'
        with recycle_stub(side_effect=lambda name:Path(name).rename(recycled)) as trash:
            result=self.suite.dispatch('clip_delete',{'id':'selected'})
        trash.assert_called_once_with(str(self.video.resolve()));self.assertTrue(result['recycled'])
        self.assertEqual(recycled.read_bytes(),b'selected fixture');self.assertEqual(self.neighbor.read_bytes(),b'keep fixture')
        with self.suite.db() as db:
            row=db.execute('SELECT * FROM deleted_clips WHERE id=?',('selected',)).fetchone()
            self.assertEqual(row['action'],'recycle');self.assertEqual(json.loads(row['metadata'])['path'],str(self.video))

    def test_explicit_permanent_deletes_fixture_without_calling_recycle_bin(self):
        with recycle_stub() as trash:
            result=self.suite.dispatch('clip_delete',{'id':'selected','delete_mode':'permanent','path':str(self.neighbor)})
        trash.assert_not_called();self.assertFalse(result['recycled']);self.assertFalse(self.video.exists())
        self.assertEqual(self.neighbor.read_bytes(),b'keep fixture')
        with self.suite.db() as db:
            self.assertIsNone(db.execute('SELECT * FROM clips WHERE id=?',('selected',)).fetchone())
            self.assertEqual(db.execute('SELECT action FROM deleted_clips WHERE id=?',('selected',)).fetchone()[0],'permanent')
        self.video.write_bytes(b'new file at same path')
        with self.assertRaises(ValueError):self.suite.dispatch('clip_delete',{'id':'selected','delete_mode':'permanent'})
        self.assertEqual(self.video.read_bytes(),b'new file at same path')

    def test_invalid_modes_and_unknown_identifiers_never_delete_files(self):
        for mode in ('unknown','PERMANENT','true',True,None,{},[]):
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.suite.dispatch('clip_delete',{'id':'selected','delete_mode':mode})
        with self.assertRaises(ValueError):self.suite.dispatch('clip_delete',{'id':'missing','delete_mode':'permanent'})
        self.assertTrue(self.video.exists());self.assertTrue(self.neighbor.exists())

    def test_failed_unlink_or_recycle_keeps_library_entry_and_other_video(self):
        with patch.object(Path,'unlink',side_effect=PermissionError('fixture is open')):
            with self.assertRaises(PermissionError):self.suite.dispatch('clip_delete',{'id':'selected','delete_mode':'permanent'})
        with recycle_stub():
            with self.assertRaises(ValueError):self.suite.dispatch('clip_delete',{'id':'selected','delete_mode':'recycle'})
        self.assertEqual(self.suite.clip('selected')['path'],str(self.video));self.assertTrue(self.video.exists())
        with self.suite.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM deleted_clips').fetchone()[0],0)

    def test_internal_buffers_directories_and_symlinks_are_rejected(self):
        folder=self.root/'.afterplay-buffer';folder.mkdir();internal=folder/'segment.ts';internal.write_bytes(b'buffer');self.add('buffer',internal)
        directory=self.root/'directory.mp4';directory.mkdir();keep=directory/'keep.txt';keep.write_text('keep');self.add('directory',directory)
        for identifier in ('buffer','directory'):
            with self.assertRaises(ValueError):self.suite.dispatch('clip_delete',{'id':identifier,'delete_mode':'permanent'})
        with patch.object(Path,'is_symlink',return_value=True):
            with self.assertRaises(ValueError):self.suite.dispatch('clip_delete',{'id':'selected','delete_mode':'permanent'})
        self.assertTrue(internal.exists());self.assertEqual(keep.read_text(),'keep');self.assertTrue(self.video.exists())

    def test_opaque_export_key_distinguishes_equal_names_and_rejects_traversal(self):
        first=self.suite.data/'exports/same.mp4';first.write_bytes(b'first')
        other=self.root/'other';storage.configure(self.suite,str(other));second=other/'same.mp4';second.write_bytes(b'second')
        chosen=next(row for row in storage.exports(self.suite) if Path(row['path']).resolve()==second.resolve())
        self.suite.dispatch('clip_delete',{'export_key':chosen['key'],'delete_mode':'permanent'})
        self.assertFalse(second.exists());self.assertEqual(first.read_bytes(),b'first')
        for args in ({'export_key':'../../selected.mp4'},{'export_name':'../selected.mp4'}):
            with self.assertRaises(ValueError):self.suite.dispatch('clip_delete',{**args,'delete_mode':'permanent'})
        self.assertTrue(self.video.exists())

if __name__=='__main__':unittest.main()
