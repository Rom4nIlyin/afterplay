"""Exercise the production worker's native imports without audio hardware."""
from pathlib import Path
import runpy
import sys
import time

sys.path.insert(0,sys.argv[1])
import microphone
microphone.devices=lambda:[{'id':'test','name':'test','default':True,'rate':48000,'channels':1}]
class Input:
    def __init__(self,device,destination,*args):
        import numpy as np
        destination.put((time.perf_counter(),np.zeros(2048,dtype='<f4').tobytes()))
    def is_active(self):return True
    def close(self):pass
microphone.Capture=Input
runpy.run_path(str(Path(microphone.__file__).with_name('microphone_worker.py')),run_name='__main__')
