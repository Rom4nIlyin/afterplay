"""D3D11 textures go straight from Windows capture to NVENC.

Only timestamped audio crosses the Python pipe. Video is never mapped to CPU
memory, converted by PyAV/OpenCV, or uploaded back to the GPU on this path.
"""
from fractions import Fraction
from functools import lru_cache
import ctypes
from ctypes import wintypes
import queue
import subprocess
import time
import uuid
from capture_media import AudioTimeline

NO_WINDOW = 0x08000000


@lru_cache(maxsize=4)
def available(ffmpeg):
    result=subprocess.run([str(ffmpeg),'-hide_banner','-filters'],
                          stdin=subprocess.DEVNULL,capture_output=True,
                          creationflags=NO_WINDOW,timeout=15)
    return result.returncode==0 and b' gfxcapture ' in result.stdout


@lru_cache(maxsize=4)
def repeats_idle_frames(ffmpeg):
    """Older gfxcapture stalls both inputs when an open window stops changing."""
    result=subprocess.run([str(ffmpeg),'-hide_banner','-h','filter=gfxcapture'],
                          stdin=subprocess.DEVNULL,capture_output=True,
                          creationflags=NO_WINDOW,timeout=15)
    return result.returncode==0 and b'dup_frames ' in result.stdout


def source_size(window,monitor):
    if not window:return monitor['width'],monitor['height']
    # Get physical client dimensions even when hosted by a DPI-unaware process.
    user=ctypes.windll.user32
    set_dpi=getattr(user,'SetThreadDpiAwarenessContext',None)
    if set_dpi:
        set_dpi.restype=ctypes.c_void_p;set_dpi.argtypes=[ctypes.c_void_p]
    previous=set_dpi(ctypes.c_void_p(-4)) if set_dpi else None
    try:
        rect=wintypes.RECT()
        if not user.GetClientRect(wintypes.HWND(window['hwnd']),ctypes.byref(rect)):
            raise ValueError('Не удалось получить размеры выбранного окна')
        if rect.right<2 or rect.bottom<2:raise ValueError('Окно не готово к записи')
        return rect.right,rect.bottom
    finally:
        if previous:set_dpi(previous)


def source_filter(cfg,window,monitor,size,*,idle_frames=False):
    if not window and size==(monitor['width'],monitor['height']):
        adapter,output=desktop_output(monitor['id'])
        if adapter==0:
            # DDA repeats an unchanged desktop on its own clock. WGC emits only
            # compositor updates and can otherwise stall on a static desktop.
            return f'ddagrab=output_idx={output}:framerate={cfg["fps"]}:draw_mouse={int(cfg["cursor"])}:dup_frames=1'
    target=f"hwnd={int(window['hwnd'])}" if window else f"monitor_idx={int(monitor['wgc_index'])-1}"
    w,h=size
    return (f'gfxcapture={target}:max_framerate={cfg["fps"]}'
            f':capture_cursor={int(cfg["cursor"])}:display_border=0'
            f':width={w}:height={h}:resize_mode=scale_aspect:scale_mode=bilinear'
            +(':dup_frames=1' if idle_frames else ''))


def desktop_output(device_name):
    """Match the Win32 display name to DXGI; never assume monitor index order."""
    class Desc(ctypes.Structure):
        _fields_=[('name',wintypes.WCHAR*32),('rect',wintypes.RECT),
                  ('attached',wintypes.BOOL),('rotation',wintypes.UINT),('monitor',wintypes.HMONITOR)]
    def method(obj,index,result,*args):
        address=ctypes.cast(obj,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents[index]
        return ctypes.WINFUNCTYPE(result,ctypes.c_void_p,*args)(address)
    def release(obj):
        if obj:method(obj,2,wintypes.ULONG)(obj)
    factory=ctypes.c_void_p()
    iid=(ctypes.c_ubyte*16).from_buffer_copy(uuid.UUID('770aae78-f26f-4dba-a829-253c83d1b387').bytes_le)
    create=ctypes.windll.dxgi.CreateDXGIFactory1
    create.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p)];create.restype=ctypes.c_long
    if create(ctypes.byref(iid),ctypes.byref(factory))<0:return -1,-1
    try:
        for adapter_index in range(32):
            adapter=ctypes.c_void_p()
            if method(factory,12,ctypes.c_long,wintypes.UINT,ctypes.POINTER(ctypes.c_void_p))(factory,adapter_index,ctypes.byref(adapter))<0:break
            try:
                for output_index in range(32):
                    output=ctypes.c_void_p()
                    if method(adapter,7,ctypes.c_long,wintypes.UINT,ctypes.POINTER(ctypes.c_void_p))(adapter,output_index,ctypes.byref(output))<0:break
                    try:
                        desc=Desc()
                        if method(output,7,ctypes.c_long,ctypes.POINTER(Desc))(output,ctypes.byref(desc))>=0 and desc.name==device_name:
                            return adapter_index,output_index
                    finally:release(output)
            finally:release(adapter)
    finally:release(factory)
    return -1,-1


def input_options(graph,epoch,audio):
    # Preserve the capture clock instead of stamping frames when the demuxer
    # happens to read them. Anchor only the FIRST frame to the recording epoch,
    # inside the source graph before input queues and audio probing can delay it.
    # Later frames retain WGC/DXGI monotonic intervals, including a stalled pipe.
    origin_us=round(epoch*1000000)
    clock=(f'setpts=PTS-STARTPTS+if(eq(N\\,0)\\,st(0\\,(RTCTIME-{origin_us})/1000000)\\,ld(0))/TB')
    args=['-copyts','-f','lavfi','-i',graph+','+clock]
    if audio:
        args+=['-probesize','32768','-analyzeduration','0',
               '-f','nut','-i','pipe:0']
    args+=['-map','0:v:0']
    return args


class AudioMux:
    """Small PCM-only pipe; timeline preserves silence, packet gaps and offsets."""
    def __init__(self,audio_queue,audio,epoch,stop_event,offset_ms=0):
        self.queue=audio_queue;self.audio=audio;self.epoch=epoch
        self.stop_event=stop_event;self.offset_ms=offset_ms
        self.error='';self.late_audio_frames=0

    def write(self,handle):
        import av
        from audio_tracks import AudioPackets
        mux=None
        try:
            rate=self.audio['rate'];channels=self.audio['channels']
            mux=av.open(handle,'w',format='nut',options={'flush_packets':'1'})
            audio=AudioPackets(mux,self.audio,self.queue,self.epoch,self.offset_ms)
            mux.start_encoding()
            while not self.stop_event.is_set():
                audio.drain()
                hold=.1+max(0,-self.offset_ms)/1000
                due=max(0,int((time.perf_counter()-self.epoch-hold)*rate))
                for _ in range(32):
                    if audio.cursor+1024>due:break
                    audio.mux(mux)
                self.late_audio_frames=audio.late_frames
                self.stop_event.wait(.005)
            audio.finish(mux,max(0,round((time.perf_counter()-self.epoch)*rate)))
        except Exception as error:
            if not self.stop_event.is_set():self.error=str(error)
        finally:
            try:
                if mux:mux.close()
            except Exception:pass
            try:handle.close()
            except Exception:pass
