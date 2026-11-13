"""Optional, reconnecting output-device capture isolated from the recorder."""
import queue
import time
from microphone import OptionalInput


def devices():
    import pyaudiowpatch as pa
    manager=pa.PyAudio()
    try:
        try:default=manager.get_default_wasapi_loopback()['index']
        except Exception:default=None
        return [{'id':int(d['index']),'name':d['name'],'rate':int(d['defaultSampleRate']),
                 'channels':min(2,int(d['maxInputChannels'])),'default':d['index']==default}
                for d in manager.get_loopback_device_info_generator()]
    finally:manager.terminate()


class OptionalOutput(OptionalInput):
    SOURCE_NAME='output audio'
    WORKER='loopback_worker.py'

    def _configuration(self,settings):
        return {'audio':str(settings.get('audio','default'))}


class Capture:
    def __init__(self,device,destination):
        import av
        import numpy as np
        import pyaudiowpatch as pa
        from audio_clock import SampleClock
        self.error='';self.closed=False;self.manager=None;self.stream=None
        self.resampler=av.AudioResampler(format='flt',layout='stereo',rate=48000)
        self.clock=SampleClock(device['rate']);self.output_frames=0
        def callback(data,frames,info,status):
            if self.closed:return None,pa.paComplete
            try:
                timestamp,gap=self.clock.stamp(frames,info,time.perf_counter(),bool(status&pa.paInputOverflow))
                if gap:
                    self.resampler=av.AudioResampler(format='flt',layout='stereo',rate=48000)
                    self.output_frames=0
                samples=np.frombuffer(data,dtype='<f4').copy() if data else np.zeros(frames*device['channels'],dtype='<f4')
                np.nan_to_num(samples,copy=False,nan=0,posinf=0,neginf=0)
                frame=av.AudioFrame.from_ndarray(samples.reshape(1,-1),format='flt',layout='stereo' if device['channels']==2 else 'mono')
                frame.sample_rate=device['rate']
                for block in self.resampler.resample(frame):
                    packet=(self.clock.epoch+self.output_frames/48000,block.to_ndarray().astype('<f4').tobytes())
                    self.output_frames+=block.samples
                    try:destination.put_nowait(packet)
                    except queue.Full:
                        try:destination.get_nowait()
                        except queue.Empty:pass
                        try:destination.put_nowait(packet)
                        except queue.Full:pass
            except Exception as error:
                self.error=str(error);return None,pa.paAbort
            return None,pa.paContinue
        try:
            self.manager=pa.PyAudio()
            self.stream=self.manager.open(format=pa.paFloat32,channels=device['channels'],rate=device['rate'],
                input=True,input_device_index=int(device['id']),frames_per_buffer=1024,stream_callback=callback)
        except Exception:
            self.close();raise

    def is_active(self):
        try:return not self.closed and not self.error and self.stream is not None and self.stream.is_active()
        except Exception:return False

    def close(self):
        self.closed=True
        if self.stream:
            try:self.stream.stop_stream();self.stream.close()
            except Exception:pass
            self.stream=None
        if self.manager:
            try:self.manager.terminate()
            except Exception:pass
            self.manager=None
