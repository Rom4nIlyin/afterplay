"""Live lookahead must be drained when capture closes, including silent inputs."""
import io,queue,unittest
from types import SimpleNamespace
from unittest.mock import patch
import av
import numpy as np
from capture_media import MediaMux
from gpu_capture import AudioMux

class Buffer(io.BytesIO):
    def close(self):pass

class ClockStop:
    def __init__(self):self.now=100.
    def is_set(self):return self.now>=100.22
    def wait(self,_):self.now+=.02;return self.is_set()

class AudioShutdownTests(unittest.TestCase):
    def test_video_bridge_drains_audio_lookahead_to_final_frame(self):
        stop=ClockStop();pixels=np.zeros((36,64,4),dtype=np.uint8)
        source=SimpleNamespace(first=(100.,pixels,1),width=64,height=36,error='')
        source.get=lambda:(stop.now,pixels,round((stop.now-100)*1000))
        output=Buffer();mux=MediaMux(source,queue.Queue(),{'rate':48000,'channels':2},30,stop)
        with patch('capture_media.time.perf_counter',side_effect=lambda:stop.now):mux.write(output)
        self.assertFalse(mux.error,mux.error)
        with av.open(io.BytesIO(output.getvalue())) as media:video=list(media.decode(video=0))
        with av.open(io.BytesIO(output.getvalue())) as media:sound=list(media.decode(audio=0))
        self.assertTrue(video);self.assertTrue(sound)
        self.assertAlmostEqual(sum(f.samples for f in sound)/48000,video[-1].time+1/30,delta=.001)
    def test_gpu_audio_bridge_drains_to_stop_time(self):
        stop=ClockStop();output=Buffer();mux=AudioMux(queue.Queue(),{'rate':48000,'channels':2},100,stop)
        with patch('gpu_capture.time.perf_counter',side_effect=lambda:stop.now):mux.write(output)
        self.assertFalse(mux.error,mux.error)
        with av.open(io.BytesIO(output.getvalue())) as media:sound=list(media.decode(audio=0))
        self.assertAlmostEqual(sum(f.samples for f in sound)/48000,stop.now-100,delta=.001)

if __name__=='__main__':unittest.main()
