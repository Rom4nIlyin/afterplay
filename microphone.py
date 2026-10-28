"""Opt-in WASAPI microphone capture, resampled onto the shared QPC timeline."""
import queue
import time

def devices():
    import pyaudiowpatch as pa
    manager=pa.PyAudio()
    try:
        host=manager.get_host_api_info_by_type(pa.paWASAPI)
        default=int(host.get('defaultInputDevice',-1))
        result=[]
        for index in range(manager.get_device_count()):
            item=manager.get_device_info_by_index(index)
            if item['hostApi']!=host['index'] or item.get('isLoopbackDevice') or not item['maxInputChannels']:continue
            result.append({'id':str(index),'name':item['name'],'rate':int(item['defaultSampleRate']),
                           'channels':min(2,int(item['maxInputChannels'])),'default':index==default})
        return result
    finally:manager.terminate()

class Capture:
    def __init__(self,device,destination,gain=100):
        import av
        import numpy as np
        import pyaudiowpatch as pa
        self.error='';self.closed=False;self.peak=0;self.manager=None;self.stream=None
        self.device=device;self.destination=destination
        self.resampler=av.AudioResampler(format='flt',layout='stereo',rate=48000)
        self.manager=pa.PyAudio()
        def callback(data,frames,clock,status):
            if self.closed:return None,pa.paComplete
            try:
                timestamp=clock.get('input_buffer_adc_time',0)
                if abs(timestamp-time.perf_counter())>30:timestamp=time.perf_counter()-frames/device['rate']
                samples=np.frombuffer(data,dtype='<f4').copy()
                samples*=gain/100
                self.peak=float(np.max(np.abs(samples))) if samples.size else 0
                frame=av.AudioFrame.from_ndarray(samples.reshape(1,-1),format='flt',layout='stereo' if device['channels']==2 else 'mono')
                frame.sample_rate=device['rate']
                for block in self.resampler.resample(frame):
                    value=(timestamp,block.to_ndarray().astype('<f4').tobytes())
                    try:destination.put_nowait(value)
                    except queue.Full:
                        try:destination.get_nowait()
                        except queue.Empty:pass
                        try:destination.put_nowait(value)
                        except queue.Full:pass
                    timestamp+=block.samples/48000
            except Exception as error:self.error=str(error);return None,pa.paAbort
            return None,pa.paContinue
        try:
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
            self.manager.terminate();self.manager=None
