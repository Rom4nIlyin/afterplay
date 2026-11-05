import json,math,queue,tempfile,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import numpy as np
import loopback,loopback_worker,microphone
from audio_clock import SampleClock
from capture_media import AudioTimeline
from replay import Replay
from app import Suite


class AudioClockTests(unittest.TestCase):
    def test_adc_jitter_never_removes_or_repeats_samples(self):
        rate=48000;clock=SampleClock(rate);line=AudioTimeline(rate,1,100)
        blocks=[]
        for i in range(200):
            adc=100+i*1024/rate+(.001*math.sin(i) if i else 0)
            timestamp,gap=clock.stamp(1024,{'input_buffer_adc_time':adc,'current_time':adc+.01},adc+.01)
            self.assertFalse(gap)
            block=np.sin(np.arange(i*1024,(i+1)*1024)*.1).astype('<f4').tobytes()
            blocks.append(block);line.add(timestamp,block)
        self.assertEqual(line.read(200*1024)[1],b''.join(blocks))

    def test_callback_arrival_jitter_is_not_mistaken_for_device_gaps(self):
        clock=SampleClock(48000)
        for i in range(100):
            stamp,gap=clock.stamp(1024,{},100+(i+1)*1024/48000+.02*math.sin(i))
            self.assertFalse(gap);self.assertAlmostEqual(stamp,100+i*1024/48000)
        stamp,gap=clock.stamp(1024,{},110)
        self.assertTrue(gap);self.assertGreater(stamp,109)

    def test_output_resampling_keeps_mono_44100_contiguous(self):
        manager=Mock();manager.open.return_value=Mock()
        packets=queue.Queue();device={'id':3,'rate':44100,'channels':1}
        with patch('pyaudiowpatch.PyAudio',return_value=manager):capture=loopback.Capture(device,packets)
        self.addCleanup(capture.close)
        callback=manager.open.call_args.kwargs['stream_callback']
        for i in range(100):
            adc=100+i*.01+.001*math.sin(i)
            data=np.sin(2*np.pi*440*np.arange(i*441,(i+1)*441)/44100).astype('<f4').tobytes()
            with patch('loopback.time.perf_counter',return_value=adc+.01):
                callback(data,441,{'input_buffer_adc_time':adc,'current_time':adc+.01},0)
        self.assertFalse(capture.error,capture.error)
        previous=None;count=0
        while not packets.empty():
            stamp,data=packets.get_nowait();frames=len(data)//8
            if previous is not None:self.assertAlmostEqual(stamp,previous,places=8)
            previous=stamp+frames/48000;count+=frames
        self.assertAlmostEqual(count/48000,1,delta=.001)


class HotplugTests(unittest.TestCase):
    def test_start_with_both_devices_absent_does_not_enumerate_on_recorder(self):
        with tempfile.TemporaryDirectory() as temp:
            rec=Replay(Suite(Path(temp)/'data'));rec.settings.update(audio_mode='system',microphone_enabled=True)
            with patch('replay.audio_devices',side_effect=AssertionError('driver on recorder')),patch('microphone.devices',side_effect=AssertionError('driver on recorder')):
                device=rec._audio_device()
            self.assertEqual(device['titles'],['Общий звук','Звук устройства','Микрофон'])
            output=Mock(is_active=Mock(return_value=True));mic=Mock(is_active=Mock(return_value=True))
            with patch('loopback.OptionalOutput',return_value=output),patch('microphone.OptionalInput',return_value=mic):
                rec._open_audio(device);rec._refresh_optional_audio()
            self.assertEqual(len(rec._optional_audio),2);self.assertFalse(rec.stop_event.is_set())
            for source in rec._optional_audio:rec._close_optional_audio(source)
            output.close.assert_called_once();mic.close.assert_called_once()

    def test_worker_missing_attach_unplug_default_change_and_driver_error(self):
        a={'id':2,'name':'A','rate':48000,'channels':2,'default':True}
        b={'id':9,'name':'B','rate':44100,'channels':1,'default':True}
        now=[0.];events=[];opened=[];closed=[]
        def pause(_):now[0]+=1
        def devices():
            stage=int(now[0])//2
            if stage in (0,2):return []
            if stage==4:raise OSError('device removed')
            return [a if stage in (1,5) else b]
        class Capture:
            def __init__(self,device,packets):
                self.device=device;opened.append(device['name']);packets.put((100+now[0],bytes(8192)))
            def is_active(self):return True
            def close(self):closed.append(self.device['name'])
        with patch('loopback.devices',side_effect=devices),patch('loopback.Capture',Capture):
            loopback_worker.run({'audio':'default'},lambda:now[0]>=12,
                lambda kind,body:events.append((kind,body)),clock=lambda:now[0],pause=pause)
        self.assertEqual(opened,['A','B','A']);self.assertEqual(closed,['A','B','A'])
        states=[json.loads(body)['state'] for kind,body in events if kind==microphone.STATE_PACKET]
        self.assertIn('waiting',states);self.assertIn('connected',states)
        self.assertEqual(sum(kind==microphone.AUDIO_PACKET for kind,_ in events),3)

    def test_explicit_device_reconnects_by_name_after_index_changes(self):
        now=[0.];opened=[]
        def devices():
            index=3 if now[0]<2 else 8
            return [{'id':index,'name':'Chosen','rate':48000,'channels':2,'default':False}]
        class Capture:
            def __init__(self,device,packets):opened.append(device['id'])
            def is_active(self):return True
            def close(self):pass
        with patch('loopback.devices',side_effect=devices),patch('loopback.Capture',Capture):
            loopback_worker.run({'audio':'3'},lambda:now[0]>=4,lambda *_:None,
                clock=lambda:now[0],pause=lambda _:now.__setitem__(0,now[0]+1))
        self.assertEqual(opened,[3,8])

    def test_output_worker_restarts_after_driver_hang(self):
        fixture=Path(__file__).with_name('MicrophoneWorkerFixture.py')
        import sys
        with tempfile.TemporaryDirectory() as temp:
            phase=Path(temp)/'phase';phase.write_text('voice');output=queue.Queue()
            with patch.object(loopback.OptionalOutput,'_command',return_value=[sys.executable,'-u',str(fixture),str(phase)]),patch.object(loopback.OptionalOutput,'HEARTBEAT_TIMEOUT',.5),patch.object(loopback.OptionalOutput,'RETRY_SECONDS',.05):
                worker=loopback.OptionalOutput({'audio':'default'},output)
                try:
                    output.get(timeout=5);pid=worker.process.pid
                    phase.write_text('hang');deadline=time.monotonic()+4
                    while time.monotonic()<deadline:
                        if worker.process and worker.process.pid!=pid:break
                        time.sleep(.02)
                    self.assertTrue(worker.is_active());self.assertNotEqual(worker.process.pid,pid)
                finally:worker.close()
            self.assertFalse(worker.thread.is_alive())


if __name__=='__main__':unittest.main()
