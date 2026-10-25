"""Exercise real segmented H.264/AAC exports, including consecutive saves."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import av
from app import Suite,run
from replay import DEFAULTS,Replay,closed_segments,validate_export


class ReplayExportTests(unittest.TestCase):
    def test_successful_save_starts_next_interval_at_click_without_av_lead(self):
        with tempfile.TemporaryDirectory() as temp:
            suite=Suite(Path(temp)/'data');rec=Replay(suite)
            session=rec.root/('a'*32);session.mkdir()
            (session/'.afterplay-buffer').touch()
            result=run([suite.ff(),'-v','error','-f','lavfi','-i',
                        'testsrc2=size=160x90:rate=30:duration=370',
                        '-f','lavfi','-i','sine=frequency=880:sample_rate=48000:duration=370',
                        '-c:v','libx264','-preset','ultrafast','-g','30','-bf','0',
                        '-c:a','aac','-f','segment','-segment_time','2','-reset_timestamps','0',
                        '-segment_format','mpegts','-segment_list',session/'segments.csv',
                        '-segment_list_type','csv','-y',session/'seg-%07d.ts'],timeout=60)
            self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
            rec.session=session;rec.phase='recording';rec.capture_epoch=100
            rec.encoder='libx264';rec.media_time=4 # deliberately stale encoder progress
            rec.settings.update(seconds=300,fps=30,audio_mode='system')
            original=[(r['path'],r['path'].stat().st_size) for r in closed_segments(session)]
            saves=[]
            for cutoff in (340.73,355.61):
                expected=min(300,cutoff-rec.interval_start)
                if saves:
                    previous_start=rec.interval_start
                    with patch('replay.time.perf_counter',return_value=100+cutoff),patch.object(suite,'probe',side_effect=ValueError('probe failed')):
                        with self.assertRaisesRegex(ValueError,'probe failed'):rec.save({})
                    self.assertEqual(rec.interval_start,previous_start)
                    self.assertFalse(rec.saving)
                with patch('replay.time.perf_counter',return_value=100+cutoff):
                    saved=rec.save({})
                self.assertAlmostEqual(saved['capture_end'],cutoff)
                self.assertAlmostEqual(saved['duration'],expected,delta=.07)
                self.assertAlmostEqual(rec.interval_start,cutoff)
                validate_export(saved['path'],expected,30,True)
                decoded=run([suite.ff(),'-v','error','-i',saved['path'],'-f','null','-'],timeout=30)
                self.assertEqual(decoded.returncode,0,decoded.stderr.decode(errors='replace'))
                with av.open(saved['path']) as media:
                    keys=[float(p.pts*p.time_base) for p in media.demux(video=0) if p.pts is not None and p.is_keyframe]
                gaps=[b-a for a,b in zip(keys,keys[1:])]+[expected-keys[-1]]
                self.assertGreaterEqual(len(keys),int(expected))
                self.assertLessEqual(max(gaps),1.04)
                with av.open(saved['path']) as media:
                    frames=media.decode(video=0)
                    first=next(frames)
                    self.assertLess(abs(first.time),1/30)
                    for frame in frames:
                        if frame.time>=.2:break
                    # A zero timestamp must not merely hide an initial freeze.
                    import numpy as np
                    difference=np.abs(frame.to_ndarray(format='gray').astype(float)-first.to_ndarray(format='gray'))
                    self.assertGreater(float(difference.mean()),1)
                self.assertEqual(rec.phase,'recording');self.assertFalse(rec.saving)
                self.assertEqual([(p,p.stat().st_size) for p,_ in original],original)
                saves.append(saved)
            # Reproduce the former stream-copy export and ensure the boundary
            # validator detects its missing leading video instead of accepting
            # the apparently correct container duration.
            joined=Path(temp)/'joined.ts'
            with joined.open('wb') as out:
                for row in closed_segments(session)[1:5]:out.write(row['path'].read_bytes())
            broken=Path(temp)/'old.mp4'
            result=run([suite.ff(),'-v','error','-ss','0.73','-i',joined,'-t','5',
                        '-map','0:v','-map','0:a','-c','copy','-avoid_negative_ts','make_zero',broken],timeout=30)
            self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
            with self.assertRaises(ValueError):validate_export(broken,5,30,True)
            self.assertAlmostEqual(saves[1]['capture_start'],saves[0]['capture_end'])
            self.assertAlmostEqual(saves[1]['duration'],14.88,delta=.07)
            self.assertAlmostEqual(rec.state()['buffer_seconds'],14.4,delta=.1)

    def test_destination_failure_releases_save_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            suite=Suite(Path(temp)/'data');rec=Replay(suite)
            rec.phase='recording';rec.capture_epoch=0;rec.session=rec.root
            rec.interval_start=12
            with patch.object(suite,'recordings_dir',side_effect=OSError('disk unavailable')):
                with self.assertRaises(OSError):rec.save({})
            self.assertFalse(rec.saving)
            self.assertEqual(rec.interval_start,12)

    def test_all_capture_profiles_use_short_non_reordered_gops_for_fast_copy(self):
        from video_quality import encoder_options
        for preset in ('performance','balanced','quality'):
            for encoder in ('h264_nvenc','libx264'):
                cfg={**DEFAULTS,'preset':preset,'fps':60}
                options=encoder_options(cfg,encoder,2560,1440)
                self.assertEqual(options[options.index('-bf')+1],'0')
                self.assertEqual(options[options.index('-g')+1],'60')
                self.assertEqual(options[options.index('-force_key_frames')+1],'expr:gte(t,n_forced)')

    def test_stale_capture_is_not_silently_exported(self):
        with tempfile.TemporaryDirectory() as temp:
            suite=Suite(Path(temp)/'data');rec=Replay(suite)
            rec.phase='recording';rec.capture_epoch=0;rec.session=rec.root
            with patch('replay.time.perf_counter',return_value=300),patch('replay.time.monotonic',side_effect=[0,11]):
                with self.assertRaisesRegex(ValueError,'отстаёт'):rec.save({})
            self.assertFalse(rec.saving)
            self.assertEqual(list(suite.recordings_dir().iterdir()),[])


if __name__=='__main__':unittest.main()
