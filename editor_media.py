"""Bounded waveform analysis, exact decoded frame steps and isolated audio preview."""
import base64
import hashlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
import threading

_analysis_lock=threading.Lock()
_preview_lock=threading.Lock()


def source(suite,cid):
    clip=suite.clip(cid);path=Path(clip['path'])
    if not path.is_file():raise ValueError('Видео недоступно')
    return clip,path


def info(suite,cid):
    import av
    clip,path=source(suite,cid)
    with av.open(str(path)) as media:
        video=media.streams.video[0]
        rate=video.average_rate or video.base_rate
        def title(stream,index):
            value=stream.metadata.get('title') or stream.metadata.get('handler_name')
            if value and value not in {'SoundHandler','Core Media Audio','AudioHandler'}:return value
            from audio_tracks import TITLES
            return TITLES[index] if len(media.streams.audio)==3 and index<3 else 'Общий звук' if index==0 else f'Дорожка {index+1}'
        return {'fps':float(rate) if rate else 30,'rate':str(rate or 30),
                'duration':clip['duration'],
                'audio':[{'index':i,'title':title(stream,i),'codec':stream.codec_context.name,
                          'start':float((stream.start_time or 0)*stream.time_base),
                          'channels':stream.codec_context.channels} for i,stream in enumerate(media.streams.audio)]}


def frame_step(suite,cid,at,direction):
    import av
    clip,path=source(suite,cid);at=float(at)
    if not math.isfinite(at) or not 0<=at<=clip['duration']+.1 or direction not in (-1,1):raise ValueError('Недопустимый шаг кадра')
    with av.open(str(path)) as media:
        video=media.streams.video[0];video.thread_type='AUTO'
        media.seek(int(max(0,at-1.5)*av.time_base),backward=True,any_frame=False)
        chosen=None;last=None
        for frame in media.decode(video):
            if frame.time is None or frame.time<-.000001:continue
            position=max(0,float(frame.time))
            if direction>0 and position>at+1e-6:chosen=frame;break
            if direction<0 and position>=at-1e-6:chosen=last or frame;break
            last=frame
        chosen=chosen or last
        if chosen is None:raise ValueError('Не удалось декодировать кадр')
        buffer=io.BytesIO()
        picture=chosen.to_image();picture.thumbnail((1600,1000));picture.save(buffer,format='JPEG',quality=88)
        return {'time':max(0,float(chosen.time)),'image':'data:image/jpeg;base64,'+base64.b64encode(buffer.getvalue()).decode('ascii')}


def _cache(suite,cid,path,kind,*values):
    st=path.stat();signature=hashlib.sha256(repr((st.st_size,st.st_mtime_ns,*values)).encode()).hexdigest()[:20]
    return suite.data/'thumbs'/f'{cid}-{kind}-{signature}'


def waveform(suite,cid,start=0,end=None,track=0):
    import numpy as np
    clip,path=source(suite,cid)
    start=float(start);end=float(clip['duration'] if end is None else end);track=int(track)
    if not math.isfinite(start) or not math.isfinite(end) or not 0<=start<end<=clip['duration']+.1 or not 0<=track<32:raise ValueError('Недопустимый диапазон звуковой волны')
    target=_cache(suite,cid,path,'wave',round(start,3),round(end,3),track).with_suffix('.json')
    with _analysis_lock:
        if target.is_file():return json.loads(target.read_text('utf-8'))
        metadata=info(suite,cid)
        if not metadata['audio']:return {'start':start,'end':end,'peaks':[],'silent':True,'track':track}
        if track>=len(metadata['audio']):raise ValueError('Аудиодорожка не найдена')
        points=1000;rate=8000;expected=max(1,math.ceil((end-start)*rate));peaks=np.zeros(points,dtype=np.float32)
        command=[suite.ff(),'-v','error','-ss',str(start),'-i',str(path),'-t',str(end-start),
                 '-map',f'0:a:{track}','-vn','-ac','1','-ar',str(rate),'-f','f32le','pipe:1']
        proc=None
        try:
            with (suite.data/'logs'/'waveform.log').open('wb') as errors:
                proc=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=errors,creationflags=0x08000000 if os.name=='nt' else 0)
                with suite.lock:suite.children.add(proc)
                offset=0
                while block:=proc.stdout.read(65536):
                    values=np.abs(np.frombuffer(block,dtype='<f4'))
                    indices=np.minimum(points-1,(np.arange(len(values),dtype=np.int64)+offset)*points//expected)
                    np.maximum.at(peaks,indices,values);offset+=len(values)
                if proc.wait(timeout=10):raise ValueError('Не удалось построить звуковую волну')
            result={'start':start,'end':end,'peaks':[round(float(value),5) for value in peaks],
                    'silent':bool(peaks.max()<.00003),'track':track}
            target.write_text(json.dumps(result),encoding='utf-8')
            return result
        finally:
            if proc:
                if proc.poll() is None:proc.kill();proc.wait()
                if proc.stdout:proc.stdout.close()
                with suite.lock:suite.children.discard(proc)


def audio_preview(suite,cid,track):
    clip,path=source(suite,cid);track=int(track)
    metadata=info(suite,cid)
    if not 0<=track<len(metadata['audio']):raise ValueError('Аудиодорожка не найдена')
    targets={item['index']:_cache(suite,cid,path,'audio2',item['index']).with_suffix('.m4a') for item in metadata['audio']}
    target=targets[track]
    with _preview_lock:
        if target.is_file():return target
        # All sources are prepared in one pass. Native AAC needs no re-encoding.
        pending=[item for item in metadata['audio'] if not targets[item['index']].is_file()]
        temporary={item['index']:targets[item['index']].with_suffix('.partial.m4a') for item in pending}
        command=[suite.ff(),'-v','error','-i',str(path)]
        for item in pending:
            command+=['-map',f'0:a:{item["index"]}','-vn']
            if item['codec']=='aac' and abs(item['start'])<.04:command+=['-c:a','copy']
            else:command+=['-af','aresample=async=1000:first_pts=0','-c:a','aac','-b:a','192k']
            command+=['-movflags','+faststart','-y',str(temporary[item['index']])]
        proc=None
        try:
            with (suite.data/'logs'/'audio-preview.log').open('wb') as errors:
                proc=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=errors,creationflags=0x08000000 if os.name=='nt' else 0)
                with suite.lock:suite.children.add(proc)
                if proc.wait(timeout=max(60,clip['duration']*.5)) or any(not p.is_file() or not p.stat().st_size for p in temporary.values()):raise ValueError('Не удалось подготовить прослушивание дорожки')
            for index,path in temporary.items():path.replace(targets[index])
            return target
        finally:
            if proc:
                if proc.poll() is None:proc.kill();proc.wait()
                with suite.lock:suite.children.discard(proc)
            for path in temporary.values():path.unlink(missing_ok=True)
