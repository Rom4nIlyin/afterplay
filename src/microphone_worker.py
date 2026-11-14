"""Isolated microphone capture. PCM travels over stdout, never through files."""
import json
import queue
import struct
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import microphone


def parent_watcher():
    # Do not hold a blocking BufferedReader/CRT stdin lock on another thread
    # while NumPy/PortAudio native extensions initialize in the main thread.
    if sys.platform=='win32':
        import ctypes
        from ctypes import wintypes
        import msvcrt
        handle=msvcrt.get_osfhandle(sys.stdin.fileno())
        peek=ctypes.WinDLL('kernel32',use_last_error=True).PeekNamedPipe
        peek.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD,
                       ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p]
        peek.restype=wintypes.BOOL
        return lambda:not peek(handle,None,0,None,None,None)
    import select
    return lambda:bool(select.select([sys.stdin],[],[],0)[0])


def run():
    config=json.loads(sys.stdin.buffer.readline())
    closed=parent_watcher();packets=queue.Queue(maxsize=256)
    capture=None;device=None;state='waiting';error='';last_check=-10.;last_status=-10.
    def send(kind,body):
        sys.stdout.buffer.write(microphone.PACKET_HEADER.pack(kind,len(body)))
        sys.stdout.buffer.write(body);sys.stdout.buffer.flush()
    try:
        while not closed():
            now=time.monotonic()
            if now-last_check>=2:
                last_check=now
                try:
                    rows=microphone.devices();name=config.get('microphone_name','')
                    if config.get('microphone_device','default')=='default':chosen=next((d for d in rows if d['default']),None)
                    else:chosen=next((d for d in rows if d['name']==name),None) if name else next((d for d in rows if d['id']==config['microphone_device']),None)
                    if capture and (not chosen or chosen!=device or not capture.is_active()):
                        capture.close();capture=None;device=None
                    if not capture and chosen:
                        candidate=microphone.Capture(chosen,packets,config.get('microphone_gain',100),config.get('microphone_voice_cleanup',True))
                        if closed():candidate.close();break
                        capture=candidate;device=chosen
                    state='connected' if capture else 'waiting';error=''
                except Exception as exception:
                    state='waiting';error=str(exception)
            # Status is independent of PCM: hardware mute may stop callbacks.
            # A stuck driver cannot freeze video; the parent restarts this worker.
            if now-last_status>=.5:
                send(microphone.STATE_PACKET,json.dumps({'state':state,'error':error}).encode('utf-8'))
                last_status=now
            try:
                timestamp,data=packets.get(timeout=.02)
                send(microphone.AUDIO_PACKET,struct.pack('<d',timestamp)+data)
            except queue.Empty:pass
    finally:
        if capture:
            capture.close()
            while not packets.empty():
                timestamp,data=packets.get_nowait()
                send(microphone.AUDIO_PACKET,struct.pack('<d',timestamp)+data)


if __name__=='__main__':
    try:run()
    except (BrokenPipeError,EOFError):pass
