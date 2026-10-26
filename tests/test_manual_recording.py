"""Manual recordings retain the whole session and survive a failed final save."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

from app import Suite, run
from replay import Replay, closed_segments, validate_export


class ManualRecordingTests(unittest.TestCase):
    def make_session(self, rec):
        session=rec.root/('b'*32);session.mkdir()
        (session/'.afterplay-buffer').touch()
        rec.session=session;rec.continuous=True
        return session

    def test_hour_recording_ignores_replay_and_gif_limits_and_keeps_markers(self):
        with tempfile.TemporaryDirectory() as temp:
            suite=Suite(Path(temp)/'data');rec=Replay(suite)
            session=self.make_session(rec)
            result=run([suite.ff(),'-v','error','-f','lavfi','-i',
                        'testsrc2=size=64x36:rate=2:duration=3665',
                        '-c:v','libx264','-preset','ultrafast','-g','2','-bf','0','-an',
                        '-f','segment','-segment_time','60','-reset_timestamps','0',
                        '-segment_format','mpegts','-segment_list',session/'segments.csv',
                        '-segment_list_type','csv','-y',session/'seg-%07d.ts'],timeout=90)
            self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
            rec.settings.update(seconds=60,fps=2,audio_mode='none',save_format='gif')
            rec.interval_start=3600;rec.session_marks=[10,1800,3650]
            self.assertEqual(rec.state()['recording_seconds'],3665)
            self.assertEqual(rec._prune_markers(),[10,1800,3650])
            saved=rec.finish_recording({})
            self.assertTrue(saved['path'].endswith('.mp4'))
            self.assertAlmostEqual(saved['duration'],3665,delta=.02)
            self.assertEqual(saved['capture_start'],0)
            validate_export(saved['path'],3665,2,False)
            self.assertFalse(session.exists());self.assertIsNone(rec.session)
            self.assertFalse(rec.finishing);self.assertFalse(rec.saving)

    def test_failed_save_keeps_all_segments_and_can_be_retried(self):
        with tempfile.TemporaryDirectory() as temp:
            suite=Suite(Path(temp)/'data');rec=Replay(suite)
            session=self.make_session(rec)
            result=run([suite.ff(),'-v','error','-f','lavfi','-i',
                        'testsrc2=size=160x90:rate=30:duration=4',
                        '-c:v','libx264','-preset','ultrafast','-g','30','-bf','0','-an',
                        '-f','segment','-segment_time','1','-segment_format','mpegts',
                        '-segment_list',session/'segments.csv','-y',session/'seg-%07d.ts'],timeout=30)
            self.assertEqual(result.returncode,0)
            rec.settings.update(audio_mode='none',fps=30)
            original={r['path']:r['path'].read_bytes() for r in closed_segments(session)}
            with patch.object(suite,'probe',side_effect=OSError('disk unavailable')):
                with self.assertRaisesRegex(OSError,'disk unavailable'):rec.finish_recording({})
            self.assertEqual(rec.phase,'error');self.assertEqual(rec.session,session)
            self.assertTrue(rec.state()['pending_recording'])
            self.assertEqual({p:p.read_bytes() for p in original},original)
            self.assertFalse(rec.finishing);self.assertFalse(rec.saving)
            with self.assertRaisesRegex(ValueError,'предыдущую запись'):rec.start(continuous=True)
            saved=rec.finish_recording({})
            self.assertAlmostEqual(saved['duration'],4,delta=.04)
            self.assertIsNone(rec.session)

    def test_maintenance_does_not_delete_early_manual_segments(self):
        with tempfile.TemporaryDirectory() as temp:
            suite=Suite(temp);rec=Replay(suite);session=self.make_session(rec)
            for i in range(3):(session/f'seg-{i:07d}.ts').write_bytes(b'keep')
            (session/'segments.csv').write_text('\n'.join(f'seg-{i:07d}.ts,{i*3600},{(i+1)*3600}' for i in range(3)))
            rec.phase='recording';rec.capture_epoch=0;rec.audio_error=''
            rec.proc=Mock();rec.proc.poll.return_value=None
            rec.stop_event=Mock();rec.stop_event.wait.side_effect=[False,True]
            rec._maintain(None)
            self.assertEqual(len(closed_segments(session)),3)

    def test_shutdown_finalizes_manual_recording(self):
        with tempfile.TemporaryDirectory() as temp:
            rec=Replay(Suite(temp));rec.continuous=True
            with patch.object(rec,'finish_recording') as finish:
                rec.shutdown()
                finish.assert_called_once_with()

    def test_brief_manual_recording_is_not_rejected_by_replay_minimum(self):
        from replay import select_segments
        rows=[{'start':0,'end':.2,'path':Path('short.ts')}]
        with self.assertRaises(ValueError):select_segments(rows,.2,60)
        selected,skip,duration=select_segments(rows,.2,.2,minimum=.001)
        self.assertEqual(selected,rows);self.assertEqual(skip,0);self.assertEqual(duration,.2)

    def test_replay_save_does_not_cut_manual_recording_or_stop_either_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            suite=Suite(Path(temp)/'data');rec=Replay(suite)
            session=self.make_session(rec)
            result=run([suite.ff(),'-v','error','-f','lavfi','-i',
                        'testsrc2=size=160x90:rate=30:duration=150',
                        '-c:v','libx264','-preset','ultrafast','-g','30','-bf','0','-an',
                        '-f','segment','-segment_time','1','-segment_format','mpegts',
                        '-segment_list',session/'segments.csv','-y',session/'seg-%07d.ts'],timeout=40)
            self.assertEqual(result.returncode,0)
            rec.continuous=False;rec.replay_enabled=True;rec.phase='recording';rec.capture_epoch=100
            rec.settings.update(seconds=60,fps=30,audio_mode='none')
            with patch('replay.time.perf_counter',return_value=180):rec.begin_recording()
            self.assertEqual(rec.recording_start,80)
            with patch('replay.time.perf_counter',return_value=200):moment=rec.save({})
            self.assertAlmostEqual(moment['capture_start'],40);self.assertAlmostEqual(moment['duration'],60,delta=.04)
            self.assertTrue(rec.continuous);self.assertTrue(rec.replay_enabled);self.assertEqual(rec.phase,'recording')
            with patch('replay.time.perf_counter',return_value=240):full=rec.finish_recording({})
            self.assertAlmostEqual(full['capture_start'],80);self.assertAlmostEqual(full['duration'],60,delta=.04)
            self.assertEqual(rec.phase,'recording');self.assertTrue(rec.replay_enabled);self.assertFalse(rec.continuous)
            self.assertEqual(rec.interval_start,100)
            validate_export(moment['path'],60,30,False);validate_export(full['path'],60,30,False)

    def test_switching_replay_does_not_stop_an_existing_manual_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            rec=Replay(Suite(temp));self.make_session(rec);rec.phase='recording';rec.capture_epoch=0
            with patch.object(rec,'start') as start,patch.object(rec,'stop') as stop:
                rec.begin_replay()
                self.assertTrue(rec.replay_enabled);self.assertTrue(rec.continuous)
                rec.end_replay()
                self.assertFalse(rec.replay_enabled);self.assertTrue(rec.continuous)
                self.assertEqual(rec.phase,'recording');start.assert_not_called();stop.assert_not_called()
