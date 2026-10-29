"""Exercise native speech DSP, clock continuity, mute and profile persistence."""
import queue
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import av
import numpy as np
from voice_processing import VoiceProcessor, RATE


def frame(samples, channels=2, rate=RATE):
    data=np.asarray(samples,dtype='float32').reshape(1,-1)
    result=av.AudioFrame.from_ndarray(data,format='flt',layout='stereo' if channels==2 else 'mono')
    result.sample_rate=rate
    return result


def run(samples, gain=100):
    processor=VoiceProcessor(gain);result=[]
    for start in range(0,len(samples),1024):
        result+=processor.process(frame(np.repeat(samples[start:start+1024],2)))
    result+=processor.flush()
    return processor,result,np.concatenate([f.to_ndarray().ravel() for f in result]).reshape(-1,2)


class VoiceProcessingTests(unittest.TestCase):
    def test_silence_stays_silent_including_non_aligned_eof(self):
        for count in (1,479,480,1024,10240):
            with self.subTest(count=count):
                processor,blocks,samples=run(np.zeros(count))
                self.assertEqual(samples.shape,(count,2))
                self.assertEqual(float(np.max(abs(samples))),0)
                self.assertEqual(processor.flush(),[])

    def test_noise_and_hum_are_reduced_without_hard_clipping(self):
        rng=np.random.default_rng(71);t=np.arange(RATE*3)/RATE
        noise=rng.normal(0,.01,len(t))+.03*np.sin(2*np.pi*50*t)
        _,_,out=run(noise)
        before=np.sqrt(np.mean(noise[RATE:]**2));after=np.sqrt(np.mean(out[RATE:,0]**2))
        # At least 6 dB for the combined hum + broadband noise, after makeup gain.
        self.assertLess(after,before/2)
        self.assertTrue(np.isfinite(out).all())
        self.assertLessEqual(float(np.max(abs(out))),.89)

    def test_output_is_clocked_and_has_exact_input_duration(self):
        _,blocks,samples=run(np.random.default_rng(2).normal(0,.01,98765))
        self.assertEqual(blocks[0].pts,0)
        self.assertEqual(blocks[-1].pts+blocks[-1].samples,98765)
        self.assertTrue(all(b.pts==a.pts+a.samples for a,b in zip(blocks,blocks[1:])))
        np.testing.assert_array_equal(samples[:,0],samples[:,1])

    def test_manual_gain_is_after_agc_and_zero_is_a_real_mute(self):
        source=np.random.default_rng(8).normal(0,.2,RATE)
        _,_,full=run(source);_,_,half=run(source,50);_,_,muted=run(source,0)
        np.testing.assert_allclose(half,full*.5,atol=1e-7)
        self.assertFalse(np.any(muted))

    def test_leveler_reduces_voice_volume_difference_and_freezes_in_pauses(self):
        levels=[]
        for amplitude in (.015,.15):
            processor=VoiceProcessor()
            for i in range(600):
                tone=amplitude*np.sin(2*np.pi*180*(np.arange(480)+i*480)/RATE)
                block=frame(tone,channels=1);block.pts=i*480
                out=processor._level(block)
            levels.append(float(np.sqrt(np.mean(out.to_ndarray()**2))))
            previous=processor.level
            for _ in range(50):processor._level(frame(np.zeros(480),channels=1))
            self.assertAlmostEqual(processor.level,previous)
        self.assertLess(levels[1]/levels[0],3)

    def test_missing_model_is_reported(self):
        with self.assertRaisesRegex(RuntimeError,'Модель очистки'):
            VoiceProcessor(model=Path('missing-speech-model.rnnn'))

    def test_capture_resamples_44100_and_flushes_on_same_clock(self):
        import microphone
        manager=Mock();callbacks={}
        def open_stream(**args):callbacks.update(args);return Mock()
        manager.open.side_effect=open_stream
        device={'id':'1','rate':44100,'channels':1}
        destination=queue.Queue(maxsize=1000)
        with patch('pyaudiowpatch.PyAudio',return_value=manager),patch('microphone.time.perf_counter',return_value=100.):
            capture=microphone.Capture(device,destination)
            cursor=0
            while cursor<44100:
                count=min(1024,44100-cursor)
                callbacks['stream_callback'](np.zeros(count,dtype='float32').tobytes(),count,{'input_buffer_adc_time':100+cursor/44100},0)
                cursor+=count
            capture.close()
        self.assertFalse(capture.error,capture.error)
        rows=[]
        while not destination.empty():rows.append(destination.get_nowait())
        self.assertEqual(sum(len(data)//8 for _,data in rows),RATE)
        cursor=0
        for stamp,data in rows:
            self.assertAlmostEqual(stamp,100+cursor/RATE,places=7);cursor+=len(data)//8

    def test_disabled_cleanup_bypasses_model(self):
        import microphone
        manager=Mock();callbacks={}
        manager.open.side_effect=lambda **args:(callbacks.update(args) or Mock())
        destination=queue.Queue()
        with patch('pyaudiowpatch.PyAudio',return_value=manager),patch('voice_processing.VoiceProcessor',side_effect=AssertionError('bypass failed')):
            capture=microphone.Capture({'id':'1','rate':RATE,'channels':1},destination,50,False)
            callbacks['stream_callback'](np.full(1024,.2,dtype='float32').tobytes(),1024,{'input_buffer_adc_time':0},0)
            capture.close()
        self.assertFalse(capture.error,capture.error)
        # FFmpeg's standard mono -> stereo matrix applies -3 dB per channel.
        np.testing.assert_allclose(np.frombuffer(destination.get_nowait()[1],dtype='float32'),.1/np.sqrt(2),atol=1e-7)

    def test_microphone_tail_is_drained_before_mux_stop(self):
        from app import Suite
        from replay import Replay
        with tempfile.TemporaryDirectory() as temp:
            suite=Suite(Path(temp)/'data');rec=Replay(suite)
            capture=Mock()
            capture.close.side_effect=lambda:self.assertFalse(rec.stop_event.is_set())
            rec._optional_audio=[{'optional':'microphone','_capture':capture}]
            rec.phase='recording'
            rec.stop(preserve=False)
            capture.close.assert_called_once()
            self.assertTrue(rec.stop_event.is_set())

    def test_old_profiles_default_on_and_explicit_off_is_validated(self):
        from app import Suite
        from replay import Replay
        import capture_profiles
        with tempfile.TemporaryDirectory() as temp:
            suite=Suite(Path(temp)/'data');suite.replay=rec=Replay(suite)
            self.assertTrue(rec.settings['microphone_voice_cleanup'])
            rec.configure({'microphone_voice_cleanup':False})
            self.assertFalse(suite.cfg['replay']['microphone_voice_cleanup'])
            self.assertEqual(capture_profiles.validated({'microphone_voice_cleanup':False}),{'microphone_voice_cleanup':False})
            for value in (0,1,'yes',None):
                with self.assertRaises(ValueError):rec.configure({'microphone_voice_cleanup':value})
                with self.assertRaises(ValueError):capture_profiles.validated({'microphone_voice_cleanup':value})


if __name__=='__main__':unittest.main()
