"""Visible, opt-in desktop replay with NVENC and WASAPI output loopback.

No microphone, game injection, keyboard logger, or autostart.
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

NO_WINDOW = 0x08000000
MINUTES = (1,3,5,10,15,20,30)
DEFAULTS = {'seconds':300, 'fps':60, 'mbps':20, 'monitor':'primary', 'audio':'default',
            'audio_mode':'system', 'game_pid':0, 'game_path':''}

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
                       'primary':bool(info.dwFlags&1)})
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
        self.root=suite.data/'replay-buffer'
        self.root.mkdir(exist_ok=True)
        self.lock=threading.RLock()
        self.stop_event=threading.Event()
        self.proc=None;self.session=None;self.started=None
        self.phase='off';self.error='';self.audio_name='';self.engine=''
        self.media_time=0.;self.audio_peak=0.;self.last_signal=0.;self.saving=False
        self.last_saved=None;self.hotkey_ok=False;self.hotkey_thread=None;self.hotkey_tid=None
        self.tray=None
        self.settings={**DEFAULTS,**suite.cfg.get('replay',{})}
        if 'audio_mode' not in suite.cfg.get('replay',{}) and self.settings['audio']=='none':
            self.settings['audio_mode']='none'
            self.settings['audio']='default'
        self.encoder='h264_nvenc'
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
            if cfg['fps'] not in {30,60}:raise ValueError('FPS должен быть 30 или 60')
        if 'mbps' in args:
            cfg['mbps']=int(args['mbps'])
            if cfg['mbps'] not in {10,20,35,50}:raise ValueError('Неподдерживаемый битрейт')
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
                    'settings':self.settings,'hotkey_ok':self.hotkey_ok,'saving':self.saving,
                    'last_saved':self.last_saved,'disk_bytes':sum(r['path'].stat().st_size for r in rows if r['path'].exists())}

    def _capture_command(self,monitor,audio,backend):
        cfg=self.settings;fps=cfg['fps']
        cmd=[self.suite.ff(),'-hide_banner','-loglevel','warning','-thread_queue_size','256']
        if backend=='Desktop Duplication':
            cmd+=['-f','lavfi','-i',f'ddagrab=output_idx=0:framerate={fps}:draw_mouse=1:dup_frames=1']
        else:
            cmd+=['-f','gdigrab','-framerate',str(fps),'-draw_mouse','1','-offset_x',str(monitor['x']),
                  '-offset_y',str(monitor['y']),'-video_size',f'{monitor["width"]}x{monitor["height"]}','-i','desktop']
        if audio:
            cmd+=['-thread_queue_size','256','-f','f32le','-ar',str(audio['rate']),'-ac',str(audio['channels']),
                  '-probesize','32','-analyzeduration','0','-i','pipe:0','-map','0:v:0','-map','1:a:0',
                  '-af','aresample=async=1000:first_pts=0','-c:a','aac','-b:a','192k']
        else:cmd+=['-map','0:v:0','-an']
        if self.encoder=='h264_nvenc':
            cmd+=['-c:v','h264_nvenc','-preset','p4','-tune','ll','-rc','cbr','-forced-idr','1']
        else:
            if backend=='Desktop Duplication':cmd+=['-vf','hwdownload,format=bgra,format=yuv420p']
            else:cmd+=['-pix_fmt','yuv420p']
            cmd+=['-c:v','libx264','-preset','ultrafast','-tune','zerolatency']
        cmd+=['-b:v',f'{cfg["mbps"]}M',
              '-maxrate',f'{cfg["mbps"]}M','-bufsize',f'{cfg["mbps"]*2}M','-bf','0','-g',str(fps*2),
              '-force_key_frames','expr:gte(t,n_forced*2)','-fps_mode','cfr','-r',str(fps),
              '-f','segment','-segment_time','2','-reset_timestamps','1','-segment_format','mpegts',
              '-segment_list',str(self.session/'segments.csv'),'-segment_list_type','csv',
              '-progress','pipe:1','-nostats','-y',str(self.session/'seg-%07d.ts')]
        if audio:cmd.insert(len(cmd)-1,'-shortest')
        return cmd

    def start(self):
        with self.lock:
            if self.phase in {'starting','recording','stopping'}:raise ValueError('Повтор уже включён')
            if self.saving:raise ValueError('Дождись сохранения клипа')
            self.phase='starting';self.error='';self.stop_event=threading.Event()
            self.media_time=0.;self.audio_peak=0.;self.last_signal=0.
        try:
            needed=max(2*1024**3,int(self.settings['mbps']*1000000/8*(self.settings['seconds']+10)*3.2)+512*1024**2)
            if shutil.disk_usage(self.root).free<needed:
                raise ValueError(f'Для буфера и сохранения нужно минимум {needed/1024**3:.1f} ГБ свободного места')
            screens=monitors()
            monitor=next((m for m in screens if m['id']==self.settings['monitor']),None)
            if self.settings['monitor']=='primary':monitor=next((m for m in screens if m['primary']),None)
            if not monitor:raise ValueError('Выбранный экран недоступен')
            audio=None
            mode=self.settings['audio_mode']
            if mode=='system':
                devices=audio_devices()
                audio=next((d for d in devices if str(d['id'])==self.settings['audio']),None)
                if self.settings['audio']=='default':audio=next((d for d in devices if d['default']),None)
                if not audio:raise ValueError('Устройство системного звука недоступно. Выбери его заново.')
            elif mode in {'game','exclude'}:
                target=process_audio.resolve_target(self.settings)
                audio={'name':('Только ' if mode=='game' else 'Всё кроме ')+target['name'],
                       'pid':target['pid'],'rate':48000,'channels':2,'process':True,'exclude':mode=='exclude'}
            self.audio_name=audio['name'] if audio else 'Без звука'
            check=subprocess.run([self.suite.ff(),'-v','error','-f','lavfi','-i','color=s=128x128:r=1',
                                  '-frames:v','1','-c:v','h264_nvenc','-f','null','-'],
                                 stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                 creationflags=NO_WINDOW,timeout=15)
            self.encoder='h264_nvenc' if check.returncode==0 else 'libx264'
            self.session=self.root/uuid.uuid4().hex;self.session.mkdir()
            (self.session/'.game-clips-buffer').write_text('Owned rolling buffer; no original media.',encoding='utf-8')
            # Primary output is DXGI index 0. Other screens use their exact GDI rectangle.
            self.engine='Desktop Duplication' if monitor['primary'] else 'GDI'
            self._audio_queue=queue.Queue(maxsize=64)
            self._audio_stream=None;self._audio_manager=None;self._process_capture=None
            self._process_reader=None;self.audio_error=''
            if audio:self._open_audio(audio)
            log=self.suite.data/'logs'/f'replay-{self.session.name}.log'
            self.logfile=open(log,'wb')
            cmd=self._capture_command(monitor,audio,self.engine)
            self.proc=subprocess.Popen([str(x) for x in cmd],stdin=subprocess.PIPE if audio else subprocess.DEVNULL,
                                       stdout=subprocess.PIPE,stderr=self.logfile,creationflags=NO_WINDOW)
            if audio:
                threading.Thread(target=self._audio_writer,args=(audio,self.proc),daemon=True).start()
            threading.Thread(target=self._progress_reader,args=(self.proc,),daemon=True).start()
            self.started=time.monotonic()
            self.phase='recording'
            self.suite.log('replay_start',monitor=monitor,system_audio=self.audio_name,microphone=False,
                           encoder=self.encoder,settings=self.settings)
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
                try:self._audio_queue.put_nowait(data)
                except queue.Full:
                    try:self._audio_queue.get_nowait()
                    except queue.Empty:pass
                    try:self._audio_queue.put_nowait(data)
                    except queue.Full:pass
            return (None,pa.paContinue)
        self._audio_stream=self._audio_manager.open(format=pa.paFloat32,channels=device['channels'],rate=device['rate'],
                         input=True,input_device_index=device['id'],frames_per_buffer=1024,stream_callback=callback)

    def _process_audio_reader(self,capture):
        try:
            while not self.stop_event.is_set():
                if capture.Error:raise RuntimeError(str(capture.Error))
                block=capture.Read()
                if block is None:self.stop_event.wait(.005);continue
                data=bytes(block)
                samples=array.array('f');samples.frombytes(data)
                peak=max((abs(x) for x in samples[::16]),default=0.)
                self.audio_peak=peak
                if peak>.00003:self.last_signal=time.monotonic()
                try:self._audio_queue.put_nowait(data)
                except queue.Full:
                    try:self._audio_queue.get_nowait()
                    except queue.Empty:pass
                    try:self._audio_queue.put_nowait(data)
                    except queue.Full:pass
        except Exception as e:self.audio_error=str(e)

    def _audio_writer(self,device,proc):
        # Supply clocked silence when no application is playing audio. WASAPI loopback
        # otherwise produces no packets and can prevent the video muxer from starting.
        frames=1024;nbytes=frames*device['channels']*4;period=frames/device['rate']
        silence=bytes(nbytes);pending=bytearray();deadline=time.monotonic()
        try:
            while not self.stop_event.is_set() and proc.poll() is None:
                while len(pending)<nbytes:
                    try:pending.extend(self._audio_queue.get_nowait())
                    except queue.Empty:break
                if len(pending)>=nbytes:
                    block=bytes(pending[:nbytes]);del pending[:nbytes]
                else:block=silence
                proc.stdin.write(block);proc.stdin.flush()
                deadline+=period
                delay=deadline-time.monotonic()
                if delay>0:self.stop_event.wait(delay)
                elif delay<-.5:deadline=time.monotonic()
        except (OSError,ValueError):pass
        finally:
            try:proc.stdin.close()
            except (OSError,ValueError):pass

    def _progress_reader(self,proc):
        for line in iter(proc.stdout.readline,b''):
            if line.startswith(b'out_time_us='):
                try:self.media_time=max(self.media_time,int(line.strip().split(b'=')[1])/1000000)
                except ValueError:pass

    def _maintain(self,audio):
        last_device_check=0
        while not self.stop_event.wait(.5):
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

    def stop(self):
        with self.lock:
            if self.phase=='stopping':return self.state()
            if self.phase=='off' and self.proc is None:return self.state()
            self.phase='stopping';self.stop_event.set();proc=self.proc
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
            if not self.saving:self._cleanup_session(self.session);self.session=None
        self.suite.log('replay_stop')
        return self.state()

    def save(self,job):
        with self.lock:
            if self.phase!='recording':raise ValueError('Сначала включи повтор')
            if self.saving:raise ValueError('Предыдущий повтор ещё сохраняется')
            self.saving=True;session=self.session
            rows=closed_segments(session)
            cutoff=max(self.media_time,rows[-1]['end'] if rows else 0)
        stage=self.suite.data/'exports'/('.replay-stage-'+uuid.uuid4().hex)
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
            for i,row in enumerate(selected):
                shutil.copy2(row['path'],stage/row['path'].name)
            listing=stage/'concat.txt'
            listing.write_text(''.join(f"file '{r['path'].name}'\nduration {r['end']-r['start']:.9f}\n" for r in selected),encoding='utf-8')
            name='Повтор-'+time.strftime('%Y-%m-%d_%H-%M-%S')+'-'+uuid.uuid4().hex[:4]+'.mp4'
            target=self.suite.data/'exports'/name
            partial=target.with_suffix('.partial.mp4')
            cmd=[self.suite.ff(),'-hide_banner','-loglevel','error','-ss',f'{max(0,skip):.6f}','-f','concat','-safe','1',
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
            if stage.resolve().parent==(self.suite.data/'exports').resolve() and stage.name.startswith('.replay-stage-'):
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
            notice('Сохраняю повтор…','Game Clips · подготовка видео','saving')
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
        if os.name!='nt':return
        def hotkeys():
            self.hotkey_tid=ctypes.windll.kernel32.GetCurrentThreadId()
            self.hotkey_ok=bool(ctypes.windll.user32.RegisterHotKey(None,1,0x4000|0x0002|0x0001,0x79))
            if not self.hotkey_ok:return
            msg=wintypes.MSG()
            while ctypes.windll.user32.GetMessageW(ctypes.byref(msg),None,0,0)>0:
                if msg.message==0x0312:self.save_job()
            ctypes.windll.user32.UnregisterHotKey(None,1)
        self.hotkey_thread=threading.Thread(target=hotkeys,daemon=True)
        self.hotkey_thread.start()

    def shutdown(self):
        self.stop()
        if self.hotkey_tid:ctypes.windll.user32.PostThreadMessageW(self.hotkey_tid,0x0012,0,0)
        if self.tray:
            icon=self.tray;self.tray=None
            try:icon.stop()
            except Exception:pass
