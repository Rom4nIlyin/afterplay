"""Synthetic hotplug endpoints; no Windows audio configuration is changed."""
import sys,threading,time,queue,json,struct
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import numpy as np
import loopback,microphone,loopback_worker,microphone_worker
phase=Path(sys.argv[2]);kind=sys.argv[3]
frequency=440 if kind=='output' else 880

def devices():
    if phase.read_text().strip()!='on':return []
    return [{'id':1,'name':'Synthetic endpoint','rate':48000,'channels':2,'default':True}]

class Tone:
    def __init__(self,device,destination,*args):
        self.stop=threading.Event();self.thread=threading.Thread(target=self.write,args=(destination,),daemon=True);self.thread.start()
    def write(self,destination):
        epoch=time.perf_counter();n=0
        while not self.stop.is_set():
            stamp=epoch+n/48000
            values=(np.sin(2*np.pi*frequency*np.arange(n,n+1024)/48000)*.1).astype('<f4')
            destination.put((stamp,np.repeat(values,2).tobytes()));n+=1024
            self.stop.wait(max(0,epoch+n/48000-time.perf_counter()))
    def is_active(self):return self.thread.is_alive()
    def close(self):self.stop.set();self.thread.join(1)

if kind=='output':
    loopback.devices=devices;loopback.Capture=Tone;loopback_worker.main()
else:
    microphone.devices=devices;microphone.Capture=Tone;microphone_worker.run()
