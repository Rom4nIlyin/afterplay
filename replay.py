"""Visible, opt-in desktop replay with NVENC and WASAPI output loopback.

No microphone or game injection; optional allowlist automation lives in auto_record.
"""
import array
import csv
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import threading
import time
import uuid
import process_audio
import storage
import video_quality
from capture_media import VideoSource,MediaMux

NO_WINDOW = 0x08000000
MINUTES = (1,3,5,10,15,20,30)
DEFAULTS = {'seconds':300, 'fps':60, 'mbps':20, 'monitor':'primary', 'audio':'default',
            'audio_mode':'system', 'game_pid':0, 'game_path':'',**video_quality.DEFAULTS}

def monitors():
    class Info(ctypes.Structure):
        _fields_=[('cbSize',wintypes.DWORD),('rcMonitor',wintypes.RECT),('rcWork',wintypes.RECT),
                  ('dwFlags',wintypes.DWORD),('szDevice',wintypes.WCHAR*32)]
    result=[]
    callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HMONITOR,wintypes.HDC,ctypes.POINTER(wintypes.RECT),wintypes.LPARAM)
    def visit(handle,dc,rect,arg):
        info=Info();info.cbSize=ctypes.sizeof(info)
        ctypes.windll.user32.GetMonitorInfoW(wintypes.HMONITOR(handle),ctypes.byref(info))
        r=info.rcMonitor
        result.append({'id':info.szDevice,'x':r.left,'y':r.top,'width':r.right-r.left,'height':r.bottom-r.top,
                       'primary':bool(info.dwFlags&1),'wgc_index':len(result)+1})
        return True
    ctypes.windll.user32.EnumDisplayMonitors(None,None,callback(visit),0)
    return sorted(result,key=lambda m:not m['primary'])

def audio_devices():
    import pyaudiowpatch as pa
    p=pa.PyAudio()
    try:
        try: default=p.get_default_wasapi_loopback()['index']
        except Exception: default=None
        return [{'id':int(d['index']),'name':d['name'],'rate':int(d['defaultSampleRate']),
                 'channels':min(2,int(d['maxInputChannels'])),'default':d['index']==default}
                for d in p.get_loopback_device_info_generator()]
    finally:p.terminate()

def closed_segments(session):
    session=Path(session)
    path=session/'segments.csv'
    if not path.is_file():return []
    result=[]
    try:
        for row in csv.reader(path.read_text('utf-8',errors='replace').splitlines()):
            if len(row)!=3:continue
            name=Path(row[0]).name
            if not re.fullmatch(r'seg-\d{7}\.ts',name):continue
            try:
                start,end=float(row[1]),float(row[2])
                f=session/name
                if f.is_file() and end>start:result.append({'path':f,'start':start,'end':end})
            except (ValueError,OSError):pass
    except OSError:pass
    return result

def select_segments(rows,cutoff,seconds):
    start=max(0,float(cutoff)-float(seconds))
    selected=[r for r in rows if r['end']>start+.001 and r['start']<cutoff-.001]
    if not selected:raise ValueError('Буфер ещё пуст. Подожди несколько секунд.')
    actual_start=max(start,selected[0]['start'])
    actual_end=min(cutoff,selected[-1]['end'])
    if actual_end-actual_start<.5:raise ValueError('Слишком мало кадров в буфере')
    return selected,actual_start-selected[0]['start'],actual_end-actual_start

class Replay:
    def __init__(self,suite):
        self.suite=suite
        self.root=storage.buffer_dir(suite)
        self.root.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock()
        self.stop_event=threading.Event()
        self.proc=None;self.session=None;self.started=None
        self.phase='off';self.error='';self.audio_name='';self.engine=''
        self.media_time=0.;self.audio_peak=0.;self.last_signal=0.;self.saving=False
        self.last_saved=None;self.hotkey_ok=False;self.hotkey_thread=None;self.hotkey_tid=None
        self.tray=None;self.auto_owned=False;self.hotkeys=None
        self.settings={**DEFAULTS,**suite.cfg.get('replay',{})}
        if 'audio_mode' not in suite.cfg.get('replay',{}) and self.settings['audio']=='none':
            self.settings['audio_mode']='none'
            self.settings['audio']='default'
        self.encoder='h264_nvenc'
        self.video_source=None;self.muxer=None;self.mux_thread=None
        self.duplicate_frames=0;self.dropped_frames=0
        self._audio_queue=queue.Queue(maxsize=64)

    def devices(self):
        try: devices=audio_devices()
        except Exception: devices=[]
        return {'monitors':monitors(),'audio':devices,'applications':process_audio.applications(),
                'process_audio_supported':process_audio.supported(),'settings':self.settings}

    def configure(self,args):
        if self.phase in {'starting','recording','stopping'} or self.saving:
            raise ValueError('Сначала останови повтор и дождись сохранения')
        cfg={**self.settings}
        if 'fps' in args:
            cfg['fps']=int(args['fps'])
        if 'mbps' in args:
            cfg['mbps']=int(args['mbps'])
        for key in ('max_mbps','cq','height','audio_bitrate','audio_offset_ms'):
            if key in args:cfg[key]=int(args[key])
        for key in ('capture_mode','quality_mode','preset','encoder'):
            if key in args:cfg[key]=str(args[key])
        for key in ('audio_follow_window','cursor','capture_border'):
            if key in args:
                if not isinstance(args[key],bool):raise ValueError('Ожидался переключатель: '+key)
                cfg[key]=args[key]
        if 'window_hwnd' in args and int(args['window_hwnd']):
            window=next((a for a in process_audio.applications() if a['hwnd']==int(args['window_hwnd'])),None)
            if not window:raise ValueError('Окно закрыто. Обновите список приложений.')
            cfg.update(window_hwnd=window['hwnd'],window_pid=window['pid'],window_path=window['path'],window_title=window['title'])
        video_quality.validate(cfg)
        if 'monitor' in args:cfg['monitor']=str(args['monitor'])
        if 'audio' in args:cfg['audio']=str(args['audio'])
        if 'audio_mode' in args:
            if args['audio_mode'] not in {'system','game','exclude','none'}:raise ValueError('Неизвестный режим звука')
            cfg['audio_mode']=args['audio_mode']
        if 'seconds' in args:
            cfg['seconds']=int(args['seconds'])
            if cfg['seconds'] not in {n*60 for n in MINUTES}:raise ValueError('Недопустимая длительность буфера')
        if 'game_pid' in args:
            pid=int(args['game_pid'])
            if pid:
                target=next((a for a in process_audio.applications() if a['pid']==pid),None)
                if not target:raise ValueError('Выбранное окно закрыто. Обнови список приложений.')
                cfg['game_pid']=pid;cfg['game_path']=target['path']
        if cfg['capture_mode']=='window' and not cfg['window_path']:raise ValueError('Выберите окно для записи')
        if cfg['capture_mode']=='window' and cfg['audio_follow_window'] and cfg['audio_mode']=='game':
            cfg['game_pid']=cfg['window_pid'];cfg['game_path']=cfg['window_path']
        if cfg['audio_mode'] in {'game','exclude'}:
            if not process_audio.supported():raise ValueError('Звук отдельного приложения требует Windows 11 или build 20348+')
            if not cfg['game_path']:raise ValueError('Выбери игру или приложение для записи звука')
        self.settings=cfg
        self.suite.cfg['replay']=cfg
        self.suite.save_cfg()
        return self.state()

    def state(self):
        with self.lock:
            rows=closed_segments(self.session) if self.session else []
            length=min(self.settings['seconds'],max(0,rows[-1]['end']-rows[0]['start'])) if rows else 0
            return {'phase':self.phase,'error':self.error,'buffer_seconds':round(length,1),
                    'elapsed':round(time.monotonic()-self.started,1) if self.started else 0,
                    'audio_name':self.audio_name,'audio_peak':round(self.audio_peak,4),
                    'audio_recent':time.monotonic()-self.last_signal<3,'engine':self.engine,
                    'encoder':self.encoder,
                    'duplicate_frames':self.duplicate_frames,'dropped_frames':self.dropped_frames,
                    'late_audio_ms':round(self.muxer.late_audio_frames/(self._audio_rate or 48000)*1000,1) if self.muxer else 0,
                    'output_size':getattr(self,'output_size',None),
                    'settings':self.settings,'hotkey_ok':bool(self.hotkeys and self.hotkeys.ok),'hotkey_error':self.hotkeys.error if self.hotkeys else '', 'saving':self.saving,
                    'last_saved':self.last_saved,'disk_bytes':sum(r['path'].stat().st_size for r in rows if r['path'].exists())}

    def _capture_command(self,monitor,audio,backend):
        cfg=self.settings
        cmd=[self.suite.ff(),'-hide_banner','-loglevel','warning','-thread_queue_size','512',
             '-probesize','32768','-analyzeduration','0','-f','nut','-colorspace','bt709','-color_range','tv','-i','pipe:0','-map','0:v:0']
        if audio:
            cmd+=['-map','0:a:0','-af','aresample=async=1000:first_pts=0','-c:a','aac','-b:a',f'{cfg["audio_bitrate"]}k']
        else:cmd+=['-an']
        cmd+=video_quality.encoder_options(cfg,self.encoder,monitor['width'],monitor['height'])
        cmd+=[
              '-f','segment','-segment_time','2','-reset_timestamps','0','-segment_format','mpegts',
              '-segment_list',str(self.session/'segments.csv'),'-segment_list_type','csv',
              '-progress','pipe:1','-nostats','-y',str(self.session/'seg-%07d.ts')]
        return cmd

    def start(self):
        with self.lock:
            if self.phase in {'starting','recording','stopping'}:raise ValueError('Повтор уже включён')
            if self.saving:raise ValueError('Дождись сохранения клипа')
            self.phase='starting';self.error='';self.stop_event=threading.Event()
            self.media_time=0.;self.audio_peak=0.;self.last_signal=0.
            self.duplicate_frames=0;self.dropped_frames=0
        try:
            bitrate=self.settings['mbps'] if self.settings['quality_mode']=='cbr' else self.settings['max_mbps']
            needed=max(2*1024**3,int(bitrate*1000000/8*(self.settings['seconds']+10)*3.2)+512*1024**2)
            if shutil.disk_usage(self.root).free<needed:
                raise ValueError(f'Для буфера и сохранения нужно минимум {needed/1024**3:.1f} ГБ свободного места')
            screens=monitors()
            monitor=next((m for m in screens if m['id']==self.settings['monitor']),None)
            if self.settings['monitor']=='primary':monitor=next((m for m in screens if m['primary']),None)
            if self.settings['capture_mode']=='monitor' and not monitor:raise ValueError('Выбранный экран недоступен')
            window=None
            if self.settings['capture_mode']=='window':
                candidates=[a for a in process_audio.applications() if a['path'].lower()==self.settings['window_path'].lower()]
                window=next((a for a in candidates if a['hwnd']==self.settings['window_hwnd'] and a['pid']==self.settings['window_pid']),None)
                if not window and len(candidates)==1:window=candidates[0]
                if not window:raise ValueError('Выбранное окно недоступно. Запустите приложение и обновите список.')
                if window['minimized']:raise ValueError('Разверните окно перед включением записи')
            audio=None
            mode=self.settings['audio_mode']
            if mode=='system':
                devices=audio_devices()
                audio=next((d for d in devices if str(d['id'])==self.settings['audio']),None)
                if self.settings['audio']=='default':audio=next((d for d in devices if d['default']),None)
                if not audio:raise ValueError('Устройство системного звука недоступно. Выбери его заново.')
            elif mode in {'game','exclude'}:
                target=window if window and self.settings['audio_follow_window'] and mode=='game' else process_audio.resolve_target(self.settings)
                audio={'name':('Только ' if mode=='game' else 'Всё кроме ')+target['name'],
                       'pid':target['pid'],'rate':48000,'channels':2,'process':True,'exclude':mode=='exclude'}
            self.audio_name=audio['name'] if audio else 'Без звука'
            check=subprocess.run([self.suite.ff(),'-v','error','-f','lavfi','-i','color=s=640x360:r=30',
                                  '-frames:v','1','-c:v','h264_nvenc','-f','null','-'],
                                 stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                 creationflags=NO_WINDOW,timeout=15)
            choice=self.settings['encoder']
            if choice=='h264_nvenc' and check.returncode:raise ValueError('NVENC недоступен. Выберите автоматический кодировщик или CPU.')
            self.encoder=('h264_nvenc' if check.returncode==0 else 'libx264') if choice=='auto' else choice
            self.session=self.root/uuid.uuid4().hex;self.session.mkdir()
            (self.session/'.game-clips-buffer').write_text('Owned rolling buffer; no original media.',encoding='utf-8')
            self.engine='Windows Graphics Capture · '+('окно' if window else 'экран')
            self._audio_queue=queue.Queue(maxsize=256)
            self._audio_stream=None;self._audio_manager=None;self._process_capture=None
            self._process_reader=None;self.audio_error=''
            self.video_source=VideoSource(hwnd=window['hwnd'] if window else None,
                                          monitor_index=None if window else monitor['wgc_index'],
                                          fps=self.settings['fps'],cursor=self.settings['cursor'],
                                          capture_border=self.settings['capture_border'])
            self.window_hwnd=window['hwnd'] if window else None
            monitor={'width':self.video_source.width,'height':self.video_source.height}
            self.output_size=video_quality.output_size(self.settings,monitor['width'],monitor['height'])
            self._audio_rate=audio['rate'] if audio else 0
            if audio:self._open_audio(audio)
            log=self.suite.data/'logs'/f'replay-{self.session.name}.log'
            self.logfile=open(log,'wb')
            cmd=self._capture_command(monitor,audio,self.engine)
            self.proc=subprocess.Popen([str(x) for x in cmd],stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE,stderr=self.logfile,creationflags=NO_WINDOW)
            self.muxer=MediaMux(self.video_source,self._audio_queue,audio,self.settings['fps'],self.stop_event,self.settings['audio_offset_ms'],self.output_size)
            self.mux_thread=threading.Thread(target=self.muxer.write,args=(self.proc.stdin,),daemon=True)
            self.mux_thread.start()
            threading.Thread(target=self._progress_reader,args=(self.proc,),daemon=True).start()
            self.started=time.monotonic()
            self.phase='recording'
            self.suite.log('replay_start',monitor=monitor,system_audio=self.audio_name,microphone=False,
                           encoder=self.encoder,output_size=self.output_size,settings=self.settings)
            threading.Thread(target=self._maintain,args=(audio,),daemon=True).start()
            return self.state()
        except Exception as e:
            self.stop()
            self.phase='error';self.error=str(e)
            raise

    def _open_audio(self,device):
        if device.get('process'):
            capture=process_audio.open_capture(device['pid'],device['exclude'])
            self._process_capture=capture
            self._process_reader=threading.Thread(target=self._process_audio_reader,args=(capture,),daemon=True)
            self._process_reader.start()
            return
        import pyaudiowpatch as pa
        self._audio_manager=pa.PyAudio()
        def callback(data,frames,clock,status):
            if self.stop_event.is_set():return (None,pa.paComplete)
            if data:
                samples=array.array('f');samples.frombytes(data)
                peak=max((abs(x) for x in samples[::16]),default=0.)
                self.audio_peak=peak
                if peak>.00003:self.last_signal=time.monotonic()
                timestamp=clock.get('input_buffer_adc_time',0)
                if abs(timestamp-time.perf_counter())>30:timestamp=time.perf_counter()-frames/device['rate']
                packet=(timestamp,data)
                try:self._audio_queue.put_nowait(packet)
                except queue.Full:
                    try:self._audio_queue.get_nowait()
                    except queue.Empty:pass
                    try:self._audio_queue.put_nowait(packet)
                    except queue.Full:pass
            return (None,pa.paContinue)
        self._audio_stream=self._audio_manager.open(format=pa.paFloat32,channels=device['channels'],rate=device['rate'],
                         input=True,input_device_index=device['id'],frames_per_buffer=1024,stream_callback=callback)

    def _process_audio_reader(self,capture):
        try:
            while not self.stop_event.is_set():
                if capture.Error:raise RuntimeError(str(capture.Error))
                block=capture.ReadPacket()
                if block is None:self.stop_event.wait(.005);continue
                data=bytes(block.Data)
                timestamp=int(block.Qpc100ns)/10000000
                if int(block.Flags)&4 or abs(timestamp-time.perf_counter())>30:
                    timestamp=time.perf_counter()-len(data)/(48000*2*4)
                samples=array.array('f');samples.frombytes(data)
                peak=max((abs(x) for x in samples[::16]),default=0.)
                self.audio_peak=peak
                if peak>.00003:self.last_signal=time.monotonic()
                packet=(timestamp,data)
                try:self._audio_queue.put_nowait(packet)
                except queue.Full:
                    try:self._audio_queue.get_nowait()
                    except queue.Empty:pass
                    try:self._audio_queue.put_nowait(packet)
                    except queue.Full:pass
        except Exception as e:self.audio_error=str(e)

    def _progress_reader(self,proc):
        for line in iter(proc.stdout.readline,b''):
            if line.startswith(b'out_time_us='):
                try:self.media_time=max(self.media_time,int(line.strip().split(b'=')[1])/1000000)
                except ValueError:pass
            for key,attr in ((b'dup_frames=', 'duplicate_frames'),(b'drop_frames=','dropped_frames')):
                if line.startswith(key):
                    try:setattr(self,attr,int(line.strip().split(b'=')[1]))
                    except ValueError:pass

    def _maintain(self,audio):
        last_device_check=0
        while not self.stop_event.wait(.5):
            if getattr(self,'window_hwnd',None) and ctypes.windll.user32.IsIconic(wintypes.HWND(self.window_hwnd)):
                self.error='Окно свёрнуто. Разверните его и включите повтор заново.'
                self.stop();self.phase='error';break
            media_error=self.muxer.error if self.muxer else ''
            if media_error:
                self.error='Ошибка захвата: '+media_error
                self.stop();self.phase='error';break
            if self.audio_error:
                self.error='Ошибка захвата звука приложения: '+self.audio_error
                self.stop();self.phase='error';break
            if self.proc.poll() is not None:
                code=self.proc.returncode
                self.error=f'Запись завершилась с кодом {code}. Подробности: data/logs/replay-{self.session.name}.log'
                self.stop();self.phase='error';break
            if self.started and time.monotonic()-self.started>15 and self.media_time<1:
                self.error='Нет кадров от захвата. Останови повтор и проверь журнал в data/logs.'
                self.stop();self.phase='error';break
            with self.lock:
                rows=closed_segments(self.session)
                if rows and not self.saving:
                    threshold=rows[-1]['end']-self.settings['seconds']-6
                    for row in rows:
                        if row['end']<threshold:row['path'].unlink(missing_ok=True)
            if shutil.disk_usage(self.root).free<512*1024**2:
                self.error='Запись остановлена: осталось меньше 512 МБ свободного места'
                self.stop();self.phase='error';break
            if audio and time.monotonic()-last_device_check>8:
                last_device_check=time.monotonic()
                if audio.get('process') and not process_audio.is_alive(audio['pid']):
                    self.error='Выбранная игра или приложение закрыто. Запусти его и включи повтор заново.'
                    self.stop();self.phase='error';break
                try:
                    if self.settings['audio_mode']=='system' and self.settings['audio']=='default':
                        current=next((d for d in audio_devices() if d['default']),None)
                        if not current or current['name']!=audio['name']:
                            self.error='Устройство системного звука изменилось. Включи повтор заново.'
                            self.stop();self.phase='error';break
                except Exception:pass

    def _cleanup_session(self,session):
        if not session:return
        session=Path(session)
        if session.resolve().parent!=self.root.resolve() or not re.fullmatch(r'[a-f0-9]{32}',session.name):return
        if (session/'.game-clips-buffer').is_file():shutil.rmtree(session,ignore_errors=True)

    def stop(self,preserve=None):
        if preserve is None:preserve=self.auto_owned
        with self.lock:
            if self.phase=='stopping':return self.state()
            if self.phase=='off' and self.proc is None:return self.state()
            self.phase='stopping';self.stop_event.set();proc=self.proc
        source=getattr(self,'video_source',None)
        if source:
            source.stop();self.video_source=None
        writer=getattr(self,'mux_thread',None)
        if writer and writer is not threading.current_thread():writer.join(timeout=3)
        if proc and proc.poll() is None:
            try:proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:proc.wait(timeout=3)
                except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=3)
        reader=getattr(self,'_process_reader',None)
        if reader and reader is not threading.current_thread():reader.join(timeout=2)
        capture=getattr(self,'_process_capture',None)
        if capture:
            capture.Dispose();self._process_capture=None
        stream=getattr(self,'_audio_stream',None)
        if stream:
            try:stream.stop_stream();stream.close()
            except Exception:pass
            self._audio_stream=None
        manager=getattr(self,'_audio_manager',None)
        if manager:
            try:manager.terminate()
            except Exception:pass
            self._audio_manager=None
        try:self.logfile.close()
        except Exception:pass
        with self.lock:
            self.proc=None;self.phase='off';self.started=None
            if not self.saving and not preserve:self._cleanup_session(self.session);self.session=None
        self.suite.log('replay_stop')
        return self.state()

    def save(self,job,allow_stopped=False):
        with self.lock:
            if self.phase!='recording' and not (allow_stopped and self.session):raise ValueError('Сначала включи повтор')
            if self.saving:raise ValueError('Предыдущий повтор ещё сохраняется')
            self.saving=True;session=self.session
            rows=closed_segments(session)
            cutoff=max(self.media_time,rows[-1]['end'] if rows else 0)
        destination=self.suite.recordings_dir()
        stage=destination/('.replay-stage-'+uuid.uuid4().hex)
        stage.mkdir()
        partial=None
        try:
            # Close the segment containing the hotkey moment; trim away future frames.
            deadline=time.monotonic()+6
            while time.monotonic()<deadline:
                rows=closed_segments(session)
                if rows and rows[-1]['end']>=cutoff-.02:break
                if self.phase!='recording':break
                time.sleep(.1)
            selected,skip,duration=select_segments(rows,cutoff,self.settings['seconds'])
            job.update(message='Сохранение последних '+str(round(duration))+' секунд',progress=10)
            # MPEG-TS timestamps remain continuous across the rolling segments.
            # Joining their bytes preserves the original A/V clock without the
            # concat demuxer's per-file duration rounding.
            listing=stage/'capture.ts'
            with listing.open('wb') as output:
                for row in selected:
                    with row['path'].open('rb') as source:shutil.copyfileobj(source,output,1024*1024)
            name='Повтор-'+time.strftime('%Y-%m-%d_%H-%M-%S')+'-'+uuid.uuid4().hex[:4]+'.mp4'
            target=destination/name
            partial=target.with_suffix('.partial.mp4')
            cmd=[self.suite.ff(),'-hide_banner','-loglevel','error','-ss',f'{max(0,skip):.6f}',
                 '-i',str(listing),'-t',f'{duration:.6f}','-map','0:v:0','-map','0:a?',
                 '-c','copy','-video_track_timescale','90000','-avoid_negative_ts','make_zero','-movflags','+faststart','-y',str(partial)]
            proc=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=NO_WINDOW)
            with self.suite.lock:self.suite.children.add(proc)
            try:
                try:stdout,stderr=proc.communicate(timeout=120)
                except subprocess.TimeoutExpired:
                    proc.kill();proc.communicate()
                    raise ValueError('Превышено время сохранения повтора')
            finally:
                with self.suite.lock:self.suite.children.discard(proc)
            if proc.returncode:raise ValueError('Не удалось сохранить повтор: '+stderr.decode('utf-8','replace')[-500:])
            job.update(progress=80,message='Проверка видео и звука')
            info=self.suite.probe(partial)
            if abs(info['duration']-duration)>2.2:raise ValueError('Длительность сохранённого повтора не прошла проверку')
            if self.settings['audio_mode']!='none' and info['audio']<1:raise ValueError('В сохранённом повторе нет аудиодорожки')
            if partial.stat().st_size<1000:raise ValueError('Пустой повтор')
            os.replace(partial,target)
            self.last_saved={'path':str(target),'bytes':target.stat().st_size,**info}
            self.suite.index_video(target)
            self.suite.log('replay_save',**self.last_saved)
            return self.last_saved
        finally:
            if partial:partial.unlink(missing_ok=True)
            if stage.resolve().parent==destination.resolve() and stage.name.startswith('.replay-stage-'):
                shutil.rmtree(stage,ignore_errors=True)
            with self.lock:
                self.saving=False
                if self.phase!='recording':self._cleanup_session(session);self.session=None

    def save_job(self):
        def notice(title,message,kind):
            try:
                if self.suite.desktop:self.suite.desktop.notify(title,message,kind)
            except Exception as e:self.suite.log('notification_failed',error=str(e))
        def save_with_notice(job):
            notice('Сохраняю повтор…','AFTERPLAY · подготовка видео','saving')
            try:
                result=self.save(job)
            except Exception as e:
                notice('Не удалось сохранить повтор',str(e),'error')
                raise
            seconds=max(0,round(result['duration']))
            duration=f'{seconds//60:02d}:{seconds%60:02d}'
            notice('Повтор сохранён',duration+' · видео в разделе «Экспорт»','success')
            return result
        return self.suite.job('Сохранение повтора',save_with_notice)

    def attach_desktop(self):
        from hotkeys import GlobalHotkeys,DEFAULTS,validate
        if os.name!='nt':return
        self.hotkeys=GlobalHotkeys({'save':self.save_job,'auto':self.suite.auto.toggle},self.suite.log)
        try:self.hotkeys.configure(validate(self.suite.cfg.get('hotkeys',DEFAULTS)))
        except ValueError as error:self.suite.log('hotkey_registration_error',error=str(error))
        self.hotkey_ok=self.hotkeys.ok;self.hotkey_tid=self.hotkeys.tid

    def shutdown(self):
        self.stop()
        if self.hotkeys:self.hotkeys.shutdown()
        if self.tray:
            icon=self.tray;self.tray=None
            try:icon.stop()
            except Exception:pass
