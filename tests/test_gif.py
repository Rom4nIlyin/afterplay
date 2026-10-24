from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
import gif_media
from app import Suite, run
from replay import Replay


class GifTests(unittest.TestCase):
    def test_duration_boundaries(self):
        for value in (2, 5, 15):self.assertEqual(gif_media.validate_duration(value), value)
        for value in (0, 1.99, 15.01, float('nan'), float('inf')):
            with self.assertRaises(ValueError):gif_media.validate_duration(value)

    def test_real_video_section_and_rolling_buffer_gifs(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);suite=Suite(root/'data')
            source=root/'source.mp4'
            proc=run([suite.ff(),'-v','error','-f','lavfi','-i','testsrc2=size=320x180:rate=30:duration=18',
                      '-f','lavfi','-i','sine=frequency=440:duration=18','-c:v','libx264','-preset','ultrafast',
                      '-g','30','-c:a','aac','-y',source],timeout=60)
            self.assertEqual(proc.returncode,0,proc.stderr)
            cid=suite.index_video(source)
            for duration in (2,15):
                result=suite.export({'id':cid,'start':1,'end':1+duration,'format':'gif','name':'section'}, {})
                self.assertEqual(result['format'],'gif');self.assertEqual(result['audio'],0)
                self.assertAlmostEqual(result['duration'],duration,delta=.15)
                from PIL import Image
                with Image.open(result['path']) as image:
                    self.assertEqual(image.format,'GIF');self.assertGreaterEqual(image.n_frames,29)
                    self.assertEqual(image.info['loop'],0)
                decoded=run([suite.ff(),'-v','error','-ignore_loop','1','-i',result['path'],'-f','null','-'],timeout=40)
                self.assertEqual(decoded.returncode,0,decoded.stderr)
            with self.assertRaises(ValueError):suite.export({'id':cid,'start':0,'end':16,'format':'gif'}, {})
            for duration in (2,15):
                replay=Replay(suite);suite.replay=replay
                session=root/('buffer-'+str(duration));session.mkdir()
                segments=run([suite.ff(),'-v','error','-i',source,'-c','copy','-f','segment','-segment_time','1',
                              '-segment_list',session/'segments.csv','-y',session/'seg-%07d.ts'],timeout=40)
                self.assertEqual(segments.returncode,0,segments.stderr)
                replay.session=session;replay.media_time=17
                replay.settings.update(save_format='gif',gif_seconds=duration)
                result=replay.save({},allow_stopped=True)
                self.assertAlmostEqual(result['duration'],duration,delta=.15)
                self.assertEqual(result['audio'],0);self.assertFalse(replay.saving)
            exported=suite.dispatch('exports',{})
            self.assertEqual(len(exported),4)
            self.assertTrue(all(row['name'].endswith('.gif') for row in exported))


class AutomaticUpdateTests(unittest.TestCase):
    def test_opt_in_persistence_and_disabled_means_no_network(self):
        with tempfile.TemporaryDirectory() as temp:
            suite=Suite(temp);suite.updater=Mock();suite.desktop=Mock()
            suite.automatic_update_tick();suite.updater.check.assert_not_called()
            suite.dispatch('updates_config',{'auto_enabled':True})
            self.assertTrue(Suite(temp).cfg['updates']['auto_enabled'])
            suite.dispatch('updates_config',{'auto_enabled':False})
            self.assertFalse(Suite(temp).cfg['updates']['auto_enabled'])
            with self.assertRaises(ValueError):suite.dispatch('updates_config',{'auto_enabled':'yes'})

    def test_updates_only_when_idle_and_rechecks_opt_out_after_download(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as temp:
            suite=Suite(temp);suite.cfg['updates']['auto_enabled']=True
            suite.desktop=Mock();suite.updater=Mock()
            suite.updater.state.return_value={'supported':True}
            suite.updater.check.return_value={'latest':{'available':True}}
            suite.replay=SimpleNamespace(phase='recording',saving=False)
            suite.automatic_update_tick();suite.updater.check.assert_not_called()
            suite.replay.phase='off'
            suite.updater.prepare.side_effect=lambda job:suite.cfg['updates'].update(auto_enabled=False)
            suite.automatic_update_tick();suite.updater.launch.assert_not_called()
            suite.cfg['updates']['auto_enabled']=True;suite.updater.prepare.side_effect=None
            suite.automatic_update_tick();suite.updater.launch.assert_called_once();suite.desktop.exit.assert_called_once()
