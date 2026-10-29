"""Sequential, bounded-memory montage export with uniform video and audio."""
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import uuid
import input_capture
import input_overlay


def segments(suite, values):
    if not isinstance(values, list) or not 1 <= len(values) <= 50:
        raise ValueError('В подборке должно быть от 1 до 50 отрезков')
    result = [];cursor=0.
    for value in values:
        if not isinstance(value, dict): raise ValueError('Некорректный отрезок подборки')
        clip = suite.clip(value.get('id'))
        path = Path(clip['path'])
        if not path.is_file(): raise ValueError('Не найден исходник: ' + clip['name'])
        start, end = value.get('start', 0), value.get('end', clip['duration'])
        if any(type(t) not in (int, float) or not math.isfinite(t) for t in (start,end)):
            raise ValueError('Укажи время начала и конца отрезка')
        info = suite.probe(path)
        if not 0 <= start < end <= info['duration'] + .05:
            raise ValueError('Проверь границы отрезка: ' + clip['name'])
        show = value.get('show_inputs', False)
        if type(show) is not bool: raise ValueError('Ожидался переключатель нажатий')
        inputs = input_capture.read(path)
        if show and inputs is None: raise ValueError('В отрезке не записаны нажатия: ' + clip['name'])
        at=value.get('at',cursor)
        if type(at) not in (int,float) or not math.isfinite(at) or not 0<=at<=86400:raise ValueError('Некорректная позиция фрагмента')
        timer=value.get('timer',False)
        if type(timer) is not bool:raise ValueError('Ожидался переключатель таймера')
        audio=value.get('audio',{'audio_mode':'mix'})
        if not isinstance(audio,dict):raise ValueError('Некорректный звук фрагмента')
        from audio_tracks import export_audio
        audio={**audio,'audio_mode':'mix' if audio.get('audio_mode')=='all' else audio.get('audio_mode','mix')}
        audio_filters,audio_maps,audio_count,_=export_audio(info,audio)
        result.append({'id':clip['id'], 'path':path, 'start':float(start), 'duration':float(end-start),'at':float(at),'timer':timer,
                       'audio_filters':audio_filters,'audio_maps':audio_maps,'audio_count':audio_count,
                       'show_inputs':show, 'inputs':inputs, 'overlay':input_overlay.settings(value.get('input_overlay')),
                       'info':info, 'marks':__import__('json').loads(clip.get('marks') or '[]')})
        cursor=at+end-start
    result.sort(key=lambda row:row['at']);cursor=0.
    for row in result:
        if row['at']<cursor-.001:raise ValueError('Фрагменты перекрываются на одной видеодорожке')
        cursor=row['at']+row['duration']
    if cursor > 86400:
        raise ValueError('Подборка не должна превышать 24 часа')
    return result


def process(suite, command, job, total, offset, log):
    proc = None
    control=suite.export_controls.get(job.get('id'))
    if control:control.check()
    try:
        with Path(log).open('wb') as errors:
            spawn=control.start if control else subprocess.Popen
            proc = spawn([str(x) for x in command], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=errors, creationflags=0x08000000 if os.name=='nt' else 0)
            with suite.lock: suite.children.add(proc)
            for line in iter(proc.stdout.readline,b''):
                if control:control.check()
                if line.startswith(b'out_time_us='):
                    try:
                        elapsed=max(0,int(line.split(b'=')[1])/1000000)
                        job.update(progress=min(96,int((offset+elapsed)/max(.001,total)*94)))
                    except ValueError: pass
            proc.wait()
        if control:control.check()
        if proc.returncode:
            raise ValueError('Не удалось собрать подборку. Подробности в data/logs. ' + Path(log).read_text('utf-8',errors='replace')[-500:])
    finally:
        if proc:
            if proc.poll() is None: proc.kill();proc.wait()
            if proc.stdout: proc.stdout.close()
            with suite.lock: suite.children.discard(proc)
            if control:control.release(proc)


def export(suite, arg, job):
    from output_names import reserve_output
    extension='.gif' if arg.get('format')=='gif' else '.mp4'
    with reserve_output(suite.recordings_dir(),arg.get('name') or 'Подборка',extension,'Подборка') as target:
        return _export_to(suite,arg,job,target)


def _export_to(suite, arg, job, target):
    control=suite.export_controls.get(job.get('id'))
    if control:control.check()
    rows=segments(suite,arg.get('segments'))
    audio_mode=arg.get('audio_mode','mix')
    if audio_mode not in ('mix','none'): raise ValueError('Неизвестный режим звука подборки')
    resolution=arg.get('resolution','source')
    if resolution not in ('source','1080p','720p'): raise ValueError('Неизвестный размер подборки')
    export_format=arg.get('format','original')
    if export_format not in ('original','vertical','gif'):raise ValueError('Неизвестный формат монтажа')
    width,height=rows[0]['info']['width'],rows[0]['info']['height']
    if resolution!='source':
        maximum=1920 if resolution=='1080p' else 1280
        scale=min(1,maximum/max(width,height));width=round(width*scale);height=round(height*scale)
    width=max(2,width//2*2);height=max(2,height//2*2)
    if export_format=='vertical':width,height=720,1280
    if max(width,height)>7680: raise ValueError('Слишком большое разрешение исходника')
    fps=min(60,max(15,round(rows[0]['info'].get('fps',30))))
    sound=audio_mode!='none' and any(row['audio_count'] for row in rows)
    total=max(row['at']+row['duration'] for row in rows)
    if export_format=='gif':
        from gif_media import validate_duration
        validate_duration(total)
    destination=suite.recordings_dir();destination.mkdir(parents=True,exist_ok=True)
    # The estimate covers temporary encodes plus the final copy.
    if shutil.disk_usage(destination).free < max(512*1024**2,width*height*fps*total*.04):
        raise ValueError('Недостаточно свободного места для сборки подборки')
    partial=target.with_suffix('.partial.mp4')
    stage=destination/('.replay-stage-montage-'+uuid.uuid4().hex);stage.mkdir()
    log=suite.data/'logs'/('montage-'+uuid.uuid4().hex[:12]+'.log')
    offset=0.;events=[];marks=[];sources=[];part_durations=[]
    try:
        def encode_part(row,duration,gap=False):
            nonlocal offset
            frames=max(1,round(duration*fps));duration=frames/fps
            index=len(sources);segment=stage/f'part-{index:03d}.mp4'
            vf=f'setpts=PTS-STARTPTS,scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=fps={fps}:start_time=0,tpad=stop_mode=clone:stop_duration=1,trim=end_frame={frames}'
            if not gap and row['timer']:
                from timer_overlay import video_filter
                vf+=','+video_filter(suite.cfg.get('customization'),fps,suite.cfg.get('language','ru'))
            if not gap and row['show_inputs']:
                vf+=','+input_overlay.render_ass(stage/f'input-{index:03d}.ass',row['inputs'],row['start'],row['duration'],width,height,row['overlay'])
            command=[suite.ff(),'-v','error']
            if gap:command+=['-f','lavfi','-i',f'color=c=black:s={width}x{height}:r={fps}:d={duration:.6f}']
            else:command+=['-ss',row['start'],'-i',row['path']]
            source_audio=not gap and row['audio_count']>0
            if sound and not source_audio:
                command+=['-f','lavfi','-i','anullsrc=r=48000:cl=stereo']
            command+=['-t',duration,'-map','0:v:0','-vf',vf,'-frames:v',frames,'-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p',
                      '-video_track_timescale','90000']
            if sound:
                if source_audio and row['audio_filters']:
                    graph=row['audio_filters'][1]+';'+row['audio_maps'][1]+'aresample=48000:async=1:first_pts=0,apad[seq_audio]'
                    command+=['-filter_complex',graph,'-map','[seq_audio]']
                else:command+=(row['audio_maps'] if source_audio else ['-map','1:a:0'])+['-af','aresample=48000:async=1:first_pts=0,apad']
                command+=['-c:a','aac','-ar','48000','-ac','2','-b:a','192k']
            else: command+=['-an']
            command+=['-movflags','+faststart','-progress','pipe:1','-nostats','-y',segment]
            process(suite,command,job,total,offset,log)
            actual=suite.probe(segment)
            if abs(actual['duration']-duration)>max(.15,2/fps):raise ValueError('Отрезок подборки не прошёл проверку длительности')
            import av
            with av.open(str(segment)) as media:
                video=media.streams.video[0];part_duration=frames/fps
                if video.frames!=frames:raise ValueError('Количество кадров фрагмента не совпало с таймлайном')
            if not gap and row['inputs']:
                events.extend([round(offset+t,6),code,down] for t,code,down in input_capture.cut(row['inputs']['events'],row['start'],part_duration))
            if not gap:marks.extend(round(offset+t-row['start'],6) for t in row['marks'] if row['start']<=t<row['start']+row['duration'])
            sources.append(segment)
            part_durations.append(part_duration);offset+=part_duration
        for index,row in enumerate(rows):
            job.update(message=f'Монтаж · фрагмент {index+1} из {len(rows)}')
            if row['at']-offset>=.5/fps:encode_part(None,row['at']-offset,gap=True)
            encode_part(row,row['duration'])
        listing=stage/'concat.txt'
        listing.write_text('\n'.join("file '"+p.name+"'\nduration "+f'{d:.6f}' for p,d in zip(sources,part_durations)),encoding='utf-8')
        job.update(message='Соединение и проверка подборки',progress=96)
        command=[suite.ff(),'-v','error','-f','concat','-safe','1','-i',listing,'-map','0','-c','copy','-movflags','+faststart',
                 '-progress','pipe:1','-nostats','-y',partial]
        process(suite,command,job,total,total,log)
        info=suite.probe(partial)
        if ((info['width'],info['height'])!=(width,height) or info['audio']!=int(sound)
                or abs(info['duration']-offset)>max(.25,len(rows)*.04)):
            raise ValueError('Подборка не прошла проверку видео, звука или длительности')
        if export_format=='gif':
            import gif_media
            info=gif_media.encode(suite,partial,target,0,offset,job,control=control)
        else:
            if control:control.commit()
            from output_names import commit_output
            commit_output(partial,target)
        cid=suite.index_video(target)
        if not any(row['show_inputs'] for row in rows) and any(row['inputs'] is not None for row in rows):
            input_capture.write(target,events,info['duration'])
        with suite.db() as db:
            db.execute('UPDATE clips SET marks=?,tags=? WHERE id=?',(__import__('json').dumps(marks),'подборка',cid))
        result={'path':str(target),'bytes':target.stat().st_size,'segments':len(rows),**info}
        suite.log('montage_export',**result)
        return result
    finally:
        partial.unlink(missing_ok=True)
        if stage.parent.resolve()==destination.resolve() and stage.name.startswith('.replay-stage-montage-'):
            shutil.rmtree(stage,ignore_errors=True)
