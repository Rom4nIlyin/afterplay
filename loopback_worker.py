"""Output-device hotplug worker; absent devices yield silence in the parent."""
import json,queue,struct,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import loopback,microphone
from microphone_worker import parent_watcher


def run(config,closed,send,*,clock=time.monotonic,pause=time.sleep):
    packets=queue.Queue(maxsize=256)
    capture=None;device=None;remembered='';last_check=-10.;last_status=-10.
    state='waiting';error=''
    try:
        while not closed():
            now=clock()
            if now-last_check>=2:
                last_check=now
                try:
                    rows=loopback.devices()
                    if config.get('audio','default')=='default':chosen=next((d for d in rows if d['default']),None)
                    elif remembered:chosen=next((d for d in rows if d['name']==remembered),None)
                    else:chosen=next((d for d in rows if str(d['id'])==str(config['audio'])),None)
                    if capture and (not chosen or chosen!=device or not capture.is_active()):
                        capture.close();capture=None;device=None
                    if not capture and chosen:
                        candidate=loopback.Capture(chosen,packets)
                        if closed():candidate.close();break
                        capture=candidate;device=chosen;remembered=chosen['name']
                    state='connected' if capture else 'waiting';error=''
                except Exception as exception:
                    if capture:
                        capture.close();capture=None;device=None
                    state='waiting';error=str(exception)
            if now-last_status>=.5:
                send(microphone.STATE_PACKET,json.dumps({'state':state,'error':error}).encode('utf-8'));last_status=now
            sent=0
            while not packets.empty() and sent<64:
                timestamp,data=packets.get_nowait()
                send(microphone.AUDIO_PACKET,struct.pack('<d',timestamp)+data);sent+=1
            pause(.005)
    finally:
        if capture:capture.close()


def main():
    config=json.loads(sys.stdin.buffer.readline());closed=parent_watcher()
    def send(kind,body):
        sys.stdout.buffer.write(microphone.PACKET_HEADER.pack(kind,len(body)))
        sys.stdout.buffer.write(body);sys.stdout.buffer.flush()
    run(config,closed,send)


if __name__=='__main__':
    try:main()
    except (BrokenPipeError,EOFError):pass
