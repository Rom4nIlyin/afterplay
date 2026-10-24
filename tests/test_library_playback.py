from pathlib import Path
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from app import Suite, run
from gpu_capture import input_options


class LibraryTests(unittest.TestCase):
    def test_buffer_tree_is_never_scanned_or_returned_from_old_index(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);suite=Suite(root/'data');videos=root/'videos';videos.mkdir()
            suite.cfg['video_roots']=[str(videos)]
            for name in ('.afterplay-buffer','.afterpaly-buffer','.replay-stage-old'):
                folder=videos/name/'session';folder.mkdir(parents=True)
                media=folder/'segment.ts';media.write_bytes(b'buffer')
                with suite.db() as db:
                    db.execute('INSERT INTO clips(id,path,name) VALUES(?,?,?)',(name,str(media),'segment.ts'))
            partial=videos/'unfinished.partial.mp4';partial.write_bytes(b'incomplete')
            self.assertEqual(suite.scan_videos({})['count'],0)
            self.assertEqual(suite.clips(),[])
            self.assertTrue(partial.exists())
            with self.assertRaises(ValueError):suite.dispatch('settings',{'video_root':str(videos/'.afterplay-buffer')})

    def test_disconnect_preserves_files_and_notes_and_reconnect_restores_them(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);videos=root/'videos';videos.mkdir();file=videos/'keep.mp4';file.write_bytes(b'original')
            suite=Suite(root/'data');suite.dispatch('settings',{'video_root':str(videos)})
            with suite.db() as db:
                db.execute('INSERT INTO clips(id,path,name,note) VALUES(?,?,?,?)',('saved',str(file),'keep.mp4','My note'))
            suite.dispatch('settings',{'remove_video_root':str(videos)})
            self.assertEqual(suite.cfg['video_roots'],[]);self.assertEqual(suite.clips(),[])
            self.assertEqual(file.read_bytes(),b'original')
            suite.dispatch('settings',{'video_root':str(videos)})
            self.assertEqual(suite.clips()[0]['note'],'My note')

    def test_disconnecting_parent_keeps_nested_connected_source_visible(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);parent=root/'videos';child=parent/'child';child.mkdir(parents=True)
            suite=Suite(root/'data')
            for folder in (parent,child):suite.dispatch('settings',{'video_root':str(folder)})
            suite.dispatch('settings',{'remove_video_root':str(parent)})
            self.assertTrue(suite.library_visible(child/'keep.mp4'))
            self.assertFalse(suite.library_visible(parent/'hidden.mp4'))


class CaptureClockTests(unittest.TestCase):
    def test_slow_frame_delivery_does_not_stretch_the_capture_clock(self):
        # Delay source delivery to model an input/encoder queue stall. The source
        # still contains exactly 2 s of capture timestamps, not 4 s of arrival time.
        import av
        with tempfile.TemporaryDirectory() as temp:
            suite=Suite(Path(temp)/'data');output=Path(temp)/'clock.mp4'
            args=input_options('testsrc2=size=128x72:rate=30:duration=2,realtime=speed=0.5',time.time(),False)
            result=run([suite.ff(),'-v','error',*args,'-c:v','libx264','-preset','ultrafast','-fps_mode','passthrough','-y',output],timeout=20)
            self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
            with av.open(str(output)) as container:times=[float(frame.time) for frame in container.decode(video=0)]
            self.assertEqual(len(times),60)
            self.assertAlmostEqual(times[-1]-times[0],59/30,delta=.01)


if __name__=='__main__':unittest.main()
