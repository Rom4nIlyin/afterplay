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
    def __init__(self,device,destination,gain=100,voice_cleanup=True):
        import av
        import numpy as np
        import pyaudiowpatch as pa
        self.error='';self.closed=False;self.peak=0;self.manager=None;self.stream=None
        self.device=device;self.destination=destination
        self.processor=None;self.epoch=None;self.input_frames=0;self.output_frames=0
        if voice_cleanup:
            from voice_processing import VoiceProcessor
            self.processor=VoiceProcessor(gain)
        self.resampler=av.AudioResampler(format='flt',layout='stereo',rate=48000)
        self.manager=pa.PyAudio()
        def callback(data,frames,clock,status):
            if self.closed:return None,pa.paComplete
            try:
                timestamp=clock.get('input_buffer_adc_time',0)
                if abs(timestamp-time.perf_counter())>30:timestamp=time.perf_counter()-frames/device['rate']
                if self.epoch is None:self.epoch=timestamp
                expected=self.epoch+self.input_frames/device['rate']
                if abs(timestamp-expected)>.1:
                    # Preserve a real device gap instead of joining unrelated samples.
                    if self.processor:
                        for block in self.processor.flush():self._deliver(block,self.epoch+block.pts/48000)
                        self.processor=VoiceProcessor(gain)
                    self.resampler=av.AudioResampler(format='flt',layout='stereo',rate=48000)
                    self.epoch=timestamp;self.input_frames=0;self.output_frames=0
                self.input_frames+=frames
                samples=np.frombuffer(data,dtype='<f4').copy()
                np.nan_to_num(samples,copy=False,nan=0,posinf=0,neginf=0)
                if not self.processor:samples*=gain/100
                frame=av.AudioFrame.from_ndarray(samples.reshape(1,-1),format='flt',layout='stereo' if device['channels']==2 else 'mono')
                frame.sample_rate=device['rate']
                for block in self.resampler.resample(frame):
                    if self.processor:
                        for clean in self.processor.process(block):self._deliver(clean,self.epoch+clean.pts/48000)
                    else:self._deliver(block,self.epoch+self.output_frames/48000)
                    self.output_frames+=block.samples
            except Exception as error:self.error=str(error);return None,pa.paAbort
            return None,pa.paContinue
        try:
            self.stream=self.manager.open(format=pa.paFloat32,channels=device['channels'],rate=device['rate'],
                                          input=True,input_device_index=int(device['id']),frames_per_buffer=1024,stream_callback=callback)
        except Exception:
            self.close();raise

    def _deliver(self,block,timestamp):
        import numpy as np
        samples=block.to_ndarray()
        self.peak=float(np.max(np.abs(samples))) if samples.size else 0
        value=(timestamp,samples.astype('<f4').tobytes())
        try:self.destination.put_nowait(value)
        except queue.Full:
            try:self.destination.get_nowait()
            except queue.Empty:pass
            try:self.destination.put_nowait(value)
            except queue.Full:pass

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
        if self.processor and self.epoch is not None:
            try:
                for block in self.resampler.resample(None):
                    for clean in self.processor.process(block):self._deliver(clean,self.epoch+clean.pts/48000)
                for block in self.processor.flush():self._deliver(block,self.epoch+block.pts/48000)
            except Exception as error:self.error=str(error)
        self.processor=None
