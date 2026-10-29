"""Controlled local PCM source; never opens audio hardware."""
import json
from pathlib import Path
import struct
import sys
import threading
import time

json.loads(sys.stdin.buffer.readline())
phase=Path(sys.argv[1]);stop=threading.Event()
def control():
    sys.stdin.buffer.read();stop.set()
threading.Thread(target=control,daemon=True).start()
def send(kind,body):
    sys.stdout.buffer.write(struct.pack('<BI',kind,len(body))+body);sys.stdout.buffer.flush()
def audio(value):
    send(1,struct.pack('<d',time.perf_counter()-1024/48000)+struct.pack('<f',value)*2048)
while not stop.is_set():
    mode=phase.read_text('utf-8')
    if mode=='hang':time.sleep(10);continue
    if mode=='crash':raise SystemExit(23)
    send(2,json.dumps({'state':'waiting' if mode=='unavailable' else 'connected','error':'device missing' if mode=='unavailable' else ''}).encode())
    if mode=='voice':audio(.125)
    elif mode=='mute':audio(0.)
    stop.wait(.02)
audio(.75)  # Distinctive DSP tail emitted on a graceful stop.
