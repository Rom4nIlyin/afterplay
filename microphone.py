"""Opt-in WASAPI microphone capture, resampled onto the shared QPC timeline."""
import queue
import time
import json
from pathlib import Path
import struct
import subprocess
import sys
import threading

PACKET_HEADER=struct.Struct('<BI')
AUDIO_PACKET=1
STATE_PACKET=2


def _child_job(process):
    """Windows also terminates the mic worker if its recorder crashes/exits."""
    if sys.platform!='win32':return None
    import ctypes
    from ctypes import wintypes
    class Basic(ctypes.Structure):
        _fields_=[('process_time',ctypes.c_int64),('job_time',ctypes.c_int64),('flags',wintypes.DWORD),
                  ('minimum',ctypes.c_size_t),('maximum',ctypes.c_size_t),('active',wintypes.DWORD),
                  ('affinity',ctypes.c_size_t),('priority',wintypes.DWORD),('scheduling',wintypes.DWORD)]
    class Extended(ctypes.Structure):
        _fields_=[('basic',Basic),('io',ctypes.c_uint64*6),('process_memory',ctypes.c_size_t),
                  ('job_memory',ctypes.c_size_t),('peak_process',ctypes.c_size_t),('peak_job',ctypes.c_size_t)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR];kernel.CreateJobObjectW.restype=wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    job=kernel.CreateJobObjectW(None,None)
    if not job:raise ctypes.WinError(ctypes.get_last_error())
    limits=Extended();limits.basic.flags=0x2000
    if not kernel.SetInformationJobObject(job,9,ctypes.byref(limits),ctypes.sizeof(limits)) or not kernel.AssignProcessToJobObject(job,int(process._handle)):
        error=ctypes.WinError(ctypes.get_last_error());kernel.CloseHandle(job);raise error
    return job


def _close_job(job):
    if job is not None:
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32');kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle(job)


class OptionalInput:
    """Keep microphone driver/DSP failures outside the video recorder process."""
    HEARTBEAT_TIMEOUT=8.
    RETRY_SECONDS=2.

    def __init__(self,settings,destination,on_state=None):
        self.config={name:settings.get(name,default) for name,default in (
            ('microphone_device','default'),('microphone_name',''),
            ('microphone_gain',100),('microphone_voice_cleanup',True))}
        self.destination=destination;self.on_state=on_state
        self.closed=False;self.error='';self.peak=0.;self.process=None
        self.stop_event=threading.Event();self.last_message=0.;self.last_state=None
        self.thread=threading.Thread(target=self._run,name='AFTERPLAY microphone',daemon=True)
        self.thread.start()

    def _command(self):
        runtime=Path(__file__).parent/'runtime/python.exe'
        python=runtime if runtime.is_file() else Path(sys.executable)
        return [str(python),'-u',str(Path(__file__).with_name('microphone_worker.py'))]

    def _state(self,event,error=''):
        self.error=error
        if (event,error)==self.last_state:return
        self.last_state=(event,error)
        if self.on_state and not self.closed:
            try:self.on_state(event,error)
            except Exception:pass

    def _read(self,process):
        try:
            while True:
                header=process.stdout.read(PACKET_HEADER.size)
                if len(header)!=PACKET_HEADER.size:break
                kind,length=PACKET_HEADER.unpack(header)
                if length>2*1024*1024:raise ValueError('Invalid microphone packet size')
                body=process.stdout.read(length)
                if len(body)!=length:break
                self.last_message=time.monotonic()
                if kind==AUDIO_PACKET:
                    if length<8 or (length-8)%8:raise ValueError('Invalid microphone PCM')
                    value=(struct.unpack_from('<d',body)[0],body[8:])
                    try:self.destination.put_nowait(value)
                    except queue.Full:
                        try:self.destination.get_nowait()
                        except queue.Empty:pass
                        try:self.destination.put_nowait(value)
                        except queue.Full:pass
                elif kind==STATE_PACKET and not self.closed:
                    state=json.loads(body)
                    self._state(state['state'],state.get('error',''))
        except Exception as error:
            if not self.closed:self._state('waiting',str(error))

    def _run(self):
        while not self.stop_event.is_set():
            process=None;reader=None;job=None
            try:
                process=subprocess.Popen(self._command(),stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                         stderr=subprocess.DEVNULL,creationflags=0x08000000 if sys.platform=='win32' else 0)
                job=_child_job(process)
                self.process=process;self.last_message=time.monotonic()
                process.stdin.write(json.dumps(self.config).encode('utf-8')+b'\n');process.stdin.flush()
                reader=threading.Thread(target=self._read,args=(process,),daemon=True);reader.start()
                while not self.stop_event.wait(.1):
                    if process.poll() is not None:raise RuntimeError('Microphone worker exited')
                    if time.monotonic()-self.last_message>self.HEARTBEAT_TIMEOUT:
                        raise TimeoutError('Microphone driver stopped responding')
            except Exception as error:
                if not self.closed:self._state('waiting',str(error))
            finally:
                if process:
                    try:process.stdin.close()
                    except Exception:pass
                    try:process.wait(timeout=.6)
                    except subprocess.TimeoutExpired:
                        try:process.kill()
                        except OSError:pass
                        try:process.wait(timeout=2)
                        except (subprocess.TimeoutExpired,OSError):pass
                _close_job(job)
                if reader:reader.join(timeout=.5)
                if process and process.stdout and (not reader or not reader.is_alive()):process.stdout.close()
                self.process=None
            if self.stop_event.wait(self.RETRY_SECONDS):break

    def is_active(self):
        # A live supervisor includes silence while the physical source is muted,
        # absent, still opening or recovering. It is never a video failure.
        return not self.closed and self.thread.is_alive()

    def close(self):
        self.closed=True;self.stop_event.set()
        if self.thread is not threading.current_thread():self.thread.join(timeout=3.5)

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
                # Some physical mute switches suspend callbacks; others send
                # an empty input buffer. Both mean silence, not capture failure.
                samples=np.frombuffer(data,dtype='<f4').copy() if data else np.zeros(frames*device['channels'],dtype='<f4')
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
