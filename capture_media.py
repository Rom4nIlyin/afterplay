"""Windows Graphics Capture + timestamped NUT transport on a single clock."""
from collections import deque
from fractions import Fraction
import threading
import time

VIDEO_TIME_BASE=Fraction(1,1000000)

class AudioTimeline:
    """Place packets at their captured sample position, never append clocked gaps."""
    def __init__(self,rate,channels,epoch,offset_ms=0):
        self.rate=rate;self.align=channels*4;self.epoch=epoch;self.offset=offset_ms/1000
        self.cursor=0;self.blocks=deque();self.late_frames=0

    def add(self,timestamp,data):
        start=round((timestamp-self.epoch+self.offset)*self.rate)
        end=start+len(data)//self.align
        if end<=self.cursor:
            self.late_frames+=len(data)//self.align;return
        if start<self.cursor:
            skip=self.cursor-start;data=data[skip*self.align:];start=self.cursor
            self.late_frames+=skip
        self.blocks.append((start,data))

    def read(self,frames):
        start=self.cursor;end=start+frames;output=bytearray(frames*self.align)
        keep=deque()
        for pos,data in self.blocks:
            packet_end=pos+len(data)//self.align
            left=max(start,pos);right=min(end,packet_end)
            if right>left:
                output[(left-start)*self.align:(right-start)*self.align]=data[(left-pos)*self.align:(right-pos)*self.align]
            if packet_end>end:keep.append((pos,data))
        self.blocks=keep;self.cursor=end
        return start,bytes(output)

class VideoSource:
    def __init__(self,*,hwnd=None,monitor_index=None,fps=60,cursor=True,capture_border=False):
        from windows_capture import WindowsCapture
        self.ready=threading.Event();self.lock=threading.Lock()
        self.first=None;self.latest=None;self.serial=0;self.error='';self.closed=False
        self.received=0;self.dropped=0;self.last_read=0;self.clock_fallback=False
        self.capture=WindowsCapture(window_hwnd=hwnd,monitor_index=monitor_index,
                                    cursor_capture=cursor,draw_border=capture_border,
                                    minimum_update_interval=max(1,int(1000/fps)))
        @self.capture.event
        def on_frame_arrived(frame,capture_control):
            if self.closed:capture_control.stop();return
            try:
                now=time.perf_counter();timestamp=frame.timespan/10000000
                if abs(timestamp-now)>60:timestamp=now;self.clock_fallback=True
                # The package owns the native mapped frame behind this ndarray.
                # Copy once here so resizing/reusing the capture surface is safe.
                pixels=frame.frame_buffer.copy()
                with self.lock:
                    self.serial+=1;self.received+=1
                    value=(timestamp,pixels,self.serial)
                    if self.first is None:self.first=value
                    if self.latest and self.last_read<self.latest[2]:self.dropped+=1
                    self.latest=value
                self.ready.set()
            except Exception as error:
                self.error=str(error);self.ready.set();capture_control.stop()
        @self.capture.event
        def on_closed():
            if not self.closed:self.error='Источник захвата закрыт. Включите запись заново.'
            self.ready.set()
        self.control=self.capture.start_free_threaded()
        if not self.ready.wait(10):
            self.stop();raise RuntimeError('Окно не выдаёт кадры. Разверните его и используйте оконный режим без рамки.')
        if self.error or self.first is None:
            self.stop();raise RuntimeError(self.error or 'Не удалось получить изображение окна')
        self.height,self.width=self.first[1].shape[:2]

    def get(self):
        with self.lock:
            value=self.latest
            if value:self.last_read=value[2]
            return value

    def stop(self):
        self.closed=True
        try:self.control.stop()
        except Exception:pass

class MediaMux:
    """Both streams carry timestamps from Windows QPC, including silent gaps."""
    def __init__(self,source,audio_queue,audio,fps,stop_event,offset_ms=0,output_size=None):
        self.source=source;self.queue=audio_queue;self.audio=audio;self.fps=fps
        self.stop_event=stop_event;self.epoch=source.first[0];self.offset_ms=offset_ms
        self.error='';self.frames=0;self.late_audio_frames=0
        self.width,self.height=output_size or (source.width//2*2,source.height//2*2)

    def write(self,handle):
        import av
        import cv2
        import queue
        mux=None
        try:
            mux=av.open(handle,'w',format='nut',options={'flush_packets':'1','max_interleave_delta':'100000'})
            video=mux.add_stream('rawvideo',rate=self.fps)
            # Convert once before transport. YUV420 uses 3/8 of BGRA's pipe
            # bandwidth; downscaling here also avoids transporting discarded pixels.
            video.width=self.width;video.height=self.height;video.pix_fmt='yuv420p'
            converter=av.video.reformatter.VideoReformatter()
            video.time_base=VIDEO_TIME_BASE;video.codec_context.time_base=VIDEO_TIME_BASE
            sound=None;timeline=None
            if self.audio:
                rate=self.audio['rate'];channels=self.audio['channels']
                sound=mux.add_stream('pcm_f32le',rate=rate)
                sound.codec_context.layout='stereo' if channels==2 else 'mono'
                sound.codec_context.format='flt';sound.time_base=Fraction(1,rate)
                sound.codec_context.time_base=Fraction(1,rate)
                timeline=AudioTimeline(rate,channels,self.epoch,self.offset_ms)
            mux.start_encoding()
            last_serial=0;last_pts=-1;next_video=self.epoch;first=True
            while not self.stop_event.is_set():
                now=time.perf_counter()
                if self.source.error:raise RuntimeError(self.source.error)
                if timeline:
                    while True:
                        try:timestamp,data=self.queue.get_nowait();timeline.add(timestamp,data)
                        except queue.Empty:break
                    # Advancing audio needs extra lookahead: a packet cannot be
                    # placed earlier until it has actually arrived from WASAPI.
                    hold=.1+max(0,-self.offset_ms)/1000
                    due=max(0,int((now-self.epoch-hold)*rate))
                    for _ in range(32):
                        if timeline.cursor+1024>due:break
                        pos,data=timeline.read(1024)
                        packet=av.Packet(data);packet.stream=sound
                        packet.pts=packet.dts=pos;packet.duration=1024;packet.time_base=sound.time_base
                        mux.mux(packet)
                    self.late_audio_frames=timeline.late_frames
                if now>=next_video:
                    value=self.source.first if first else self.source.get()
                    timestamp,pixels,serial=value
                    if first or serial!=last_serial:
                        pts=max(0,round((timestamp-self.epoch)*1000000))
                    else:
                        pts=max(0,round((now-self.epoch)*1000000))
                    if pts>last_pts:
                        if pixels.shape[:2]!=(self.source.height,self.source.width):
                            # A resized window keeps its proportions inside the
                            # dimensions fixed by this recording's video stream.
                            import numpy as np
                            scale=min(self.source.width/pixels.shape[1],self.source.height/pixels.shape[0])
                            w=max(1,round(pixels.shape[1]*scale));h=max(1,round(pixels.shape[0]*scale))
                            resized=cv2.resize(pixels,(w,h),interpolation=cv2.INTER_AREA)
                            pixels=np.zeros((self.source.height,self.source.width,4),dtype=np.uint8)
                            x=(self.source.width-w)//2;y=(self.source.height-h)//2
                            pixels[y:y+h,x:x+w]=resized
                        frame=av.VideoFrame.from_ndarray(pixels,format='bgra')
                        frame=converter.reformat(frame,width=self.width,height=self.height,format='yuv420p',
                                                  dst_colorspace='ITU709',src_color_range='JPEG',dst_color_range='MPEG',
                                                  interpolation='LANCZOS',threads=2)
                        packet=av.Packet(frame.to_ndarray().tobytes());packet.stream=video
                        packet.pts=packet.dts=pts;packet.time_base=VIDEO_TIME_BASE
                        packet.duration=max(1,round(1000000/self.fps));mux.mux(packet)
                        last_pts=pts;self.frames+=1
                    first=False;last_serial=serial
                    next_video+=1/self.fps
                    if next_video<now-1/self.fps:next_video=now+1/self.fps
                self.stop_event.wait(.002)
        except (OSError,ValueError) as error:
            if not self.stop_event.is_set():self.error=str(error)
        except Exception as error:
            self.error=str(error)
        finally:
            try:
                if mux:mux.close()
            except Exception:pass
            try:handle.close()
            except Exception:pass
