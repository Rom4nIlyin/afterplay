"""Concurrent requests retain click times, audio, source files and FIFO order."""
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import av
from app import Suite,run
from replay import Replay,validate_export


class ReplayQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.suite=Suite(Path(self.temp.name)/'data');self.rec=Replay(self.suite)
        self.session=self.rec.root/('c'*32);self.session.mkdir()
        (self.session/'.afterplay-buffer').touch()
        result=run([self.suite.ff(),'-v','error','-f','lavfi','-i',
                    'testsrc2=size=160x90:rate=30:duration=16',
                    '-f','lavfi','-i','sine=frequency=880:sample_rate=48000:duration=16',
                    '-map','0:v',*sum((['-map','1:a'] for _ in range(4)),[]),
                    '-c:v','libx264','-preset','ultrafast','-g','30','-bf','0','-c:a','aac',
                    '-f','segment','-segment_time','1','-reset_timestamps','0',
                    '-segment_format','mpegts','-segment_list',self.session/'segments.csv',
                    '-segment_list_type','csv','-y',self.session/'seg-%07d.ts'],timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.rec.session=self.session;self.rec.phase='recording';self.rec.capture_epoch=0
        self.rec.settings.update(fps=30,audio_mode='multitrack',seconds=60)
        self.rec.audio_titles=['Mixed','Game','Chat','Mic'];self.rec.session_marks=[3,9,11]

    def wait_jobs(self,ids):
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            if all(self.suite.jobs[i]['status']!='running' for i in ids):return
            time.sleep(.01)
        self.fail('Save jobs did not finish')

    def check_video(self,saved,duration):
        validate_export(saved['path'],duration,30,True)
        with av.open(saved['path']) as media:
            self.assertEqual(len(media.streams.audio),4)
            frames=list(media.decode(video=0))
        self.assertAlmostEqual(len(frames)/30,duration,delta=.04)
        self.assertLessEqual(max(b.time-a.time for a,b in zip(frames,frames[1:])),.034)
        self.assertGreater(len({f.to_ndarray(format='gray').tobytes() for f in frames}),len(frames)*.95)
        # The index is already at the front; finalization must not shift mdat.
        data=Path(saved['path']).read_bytes()
        self.assertLess(data.index(b'moov'),data.index(b'mdat'))

    def test_overlapping_clicks_keep_their_times_and_survive_stop(self):
        entered=threading.Event();release=threading.Event();original=self.suite.probe
        first=True
        def blocked(path):
            nonlocal first
            if first:
                first=False;entered.set()
                if not release.wait(10):raise TimeoutError('test gate')
            return original(path)
        with patch.object(self.suite,'probe',side_effect=blocked):
            self.rec.session_marks=[3]
            with patch('replay.time.perf_counter',return_value=8):a=self.rec.save_job()['job']
            self.assertTrue(entered.wait(5))
            self.rec.session_marks.extend([9,11])
            with patch('replay.time.perf_counter',return_value=12):b=self.rec.save_job()['job']
            self.assertEqual(self.rec.state()['save_queue'],2)
            self.rec.stop(preserve=False)
            self.assertTrue(self.session.exists())
            release.set();self.wait_jobs([a,b])
        for i in (a,b):self.assertEqual(self.suite.jobs[i]['status'],'done',self.suite.jobs[i])
        first=self.suite.jobs[a]['result'];second=self.suite.jobs[b]['result']
        self.assertEqual((first['capture_start'],first['capture_end']),(0,8))
        self.assertEqual((second['capture_start'],second['capture_end']),(8,12))
        self.assertEqual(first['marks'],[3]);self.assertEqual(second['marks'],[1,3])
        self.check_video(first,8);self.check_video(second,4)
        self.assertFalse(self.rec.saving);self.assertIsNone(self.rec.session)
        self.assertFalse(self.session.exists())

    def test_failed_first_export_does_not_discard_queued_material(self):
        calls=[]
        def deferred(label,callback):calls.append(callback);return {'job':len(calls)}
        with patch.object(self.suite,'job',side_effect=deferred):
            with patch('replay.time.perf_counter',return_value=8):self.rec.save_job()
            with patch('replay.time.perf_counter',return_value=12):self.rec.save_job()
        with patch.object(self.suite,'probe',side_effect=OSError('disk unavailable')):
            with self.assertRaisesRegex(OSError,'disk unavailable'):calls[0]({})
        self.assertTrue(self.rec.saving);self.assertEqual(self.rec.interval_start,0)
        self.assertTrue(self.session.exists())
        saved=calls[1]({})
        self.assertEqual((saved['capture_start'],saved['capture_end']),(0,12))
        self.check_video(saved,12);self.assertFalse(self.rec.saving)

    def test_worker_scheduling_cannot_reorder_clicks(self):
        callbacks=[];results=[]
        def deferred(label,callback):callbacks.append(callback);return {'job':len(callbacks)}
        with patch.object(self.suite,'job',side_effect=deferred):
            with patch('replay.time.perf_counter',return_value=8):self.rec.save_job()
            with patch('replay.time.perf_counter',return_value=12):self.rec.save_job(5)
        thread=threading.Thread(target=lambda:results.append(callbacks[1]({})))
        thread.start()
        try:first=callbacks[0]({})
        finally:thread.join(10)
        self.assertFalse(thread.is_alive());self.assertEqual(len(results),1)
        self.assertEqual(first['capture_end'],8)
        self.assertEqual((results[0]['capture_start'],results[0]['capture_end']),(7,12))
        self.assertEqual(self.rec.interval_start,8) # Quick clips never reset the normal interval.
        self.check_video(results[0],5)

    def test_invalid_or_unscheduled_request_never_pins_buffer(self):
        with self.assertRaises(ValueError):self.rec.save_job(4)
        self.assertFalse(self.rec.saving)
        with patch.object(self.suite,'job',side_effect=RuntimeError('scheduler failed')):
            with self.assertRaises(RuntimeError):self.rec.save_job()
        self.assertFalse(self.rec.saving);self.assertEqual(self.rec._save_requests,[])

    def test_shutdown_waits_for_every_reserved_save(self):
        callbacks=[];closed=threading.Event()
        def deferred(label,callback):callbacks.append(callback);return {'job':len(callbacks)}
        with patch.object(self.suite,'job',side_effect=deferred):
            with patch('replay.time.perf_counter',return_value=8):self.rec.save_job()
            with patch('replay.time.perf_counter',return_value=12):self.rec.save_job()
        thread=threading.Thread(target=lambda:(self.rec.shutdown(),closed.set()))
        thread.start()
        try:
            self.assertFalse(closed.wait(.05))
            callbacks[0]({})
            self.assertTrue(self.session.exists());self.assertFalse(closed.is_set())
            callbacks[1]({})
        finally:thread.join(10)
        self.assertTrue(closed.is_set());self.assertFalse(self.session.exists())


if __name__=='__main__':unittest.main()
