"""Local appearance, owned background assets, covers and desktop sound feedback."""
import copy
import hashlib
import io
import json
import math
import queue
import os
from pathlib import Path
import re
import shutil
import struct
import threading
import time
import uuid
import wave
import zipfile

THEMES=('obsidian','glass','aurora','ember','mist','paper')
THEME_PALETTES={'obsidian':('#090b0f','#9ccfc9'),'glass':('#1d2536','#c5bdff'),
                'aurora':('#0a1721','#76dccb'),'ember':('#19110f','#e6ac79'),
                'mist':('#e9eef3','#4b6c89'),'paper':('#f0eade','#875d40')}
THEME_ALIASES={'standard':'aurora','dark':'obsidian','light':'mist','neon':'obsidian',
               'cyberpunk':'mist','lagoon':'aurora','sunset':'paper'}
LEGACY_PALETTES={
    'standard':(('#121818','#8fc9c4'),),'dark':(('#0e1421','#94bcfa'),),
    'light':(('#edf3f5','#116272'),),
    'neon':(('#211047','#c4ff42'),('#141b26','#9db8d2')),
    'cyberpunk':(('#361343','#ffe449'),('#e9eef3','#4b6c89')),
    'lagoon':(('#063d59','#35f2ce'),('#18221f','#a6c4b0')),
    'sunset':(('#54203f','#ffb15e'),('#efe8dd','#947355')),
}

def migrate_theme(cfg):
    old=cfg.get('theme');theme=THEME_ALIASES.get(old)
    if not theme:return
    cfg['theme']=theme
    for i,key in enumerate(('background_color','accent')):
        if any(cfg.get(key)==palette[i] for palette in LEGACY_PALETTES.get(old,())):
            cfg[key]=THEME_PALETTES[theme][i]

def migrate_palettes(settings):
    for cfg in [settings.get('appearance',{}),settings.get('customization',{}),
                *settings.get('appearance_presets',{}).values()]:
        migrate_theme(cfg)

EVENTS=('mark','saving','success','error')
DEFAULTS={
    'theme':'obsidian','accent':'#9ccfc9','background':'scene','scene':'smoke','asset':'',
    'background_color':'#090c10','dim':62,'blur':0,'saturation':85,'fit':'cover','speed':1,
    'pause_recording':True,'pause_export':True,'motion':True,'glow':True,'animation':'calm',
    'panel_opacity':94,'scale':100,'card_size':270,'card_ratio':'16/9','radius':14,
    'colors_custom':False,'panel_color':'#14181f','text_color':'#edf1f5','muted_color':'#a8b0bf',
    'card_date':True,'card_game':False,'card_size_label':True,'card_duration':True,'card_tags':True,
    'hover_enabled':True,'hover_delay':450,'hover_sound':False,'hover_speed':1,'hover_mode':'play',
    'nav_compact':False,'nav_order':['library','replay','favorites','tags','exports','settings'],
    'nav_hidden':[],'pinned_tags':[],
    'notice_position':'top-right','notice_size':100,'notice_opacity':96,'notice_duration':4.5,'notice_cover':True,
    'timer_color':'#ffffff','timer_background':65,'timer_size':100,'timer_font':'mono',
    'timer_format':'milliseconds','timer_x':97.5,'timer_y':2.5,
    'editor_width':340,'timeline_height':150,'editor_start':'view','editor_tab':'trim',
    'sounds':{'enabled':False,'pack':'soft',**{key:{'enabled':True,'volume':30,'asset':''} for key in EVENTS}},
}
_sound_lock=threading.Lock()
_sound_queue=queue.Queue(maxsize=8)
_sound_worker=None

def current(suite):
    cfg=copy.deepcopy(DEFAULTS)
    cfg.update(copy.deepcopy(suite.cfg.get('customization',{})))
    return cfg

def validate(patch):
    if not isinstance(patch,dict):raise ValueError('Ожидались настройки оформления')
    if set(patch)-set(DEFAULTS):raise ValueError('Неизвестная настройка оформления')
    patch=copy.deepcopy(patch)
    migrate_theme(patch)
    enums={'theme':THEMES,'background':('none','color','scene','asset'),
           'scene':('smoke','aurora','ember','video'),'fit':('cover','contain','fill'),
           'card_ratio':('16/9','4/3','1/1'),'hover_mode':('play','scrub'),
           'animation':('off','calm','normal'),'notice_position':('top-right','top-left','bottom-right','bottom-left'),
           'timer_font':('mono','sans'),'timer_format':('milliseconds','seconds','frames'),
           'editor_start':('view','edit'),'editor_tab':('trim','sound','export','notes')}
    ranges={'dim':(0,95),'blur':(0,35),'saturation':(0,200),'speed':(.25,2),'panel_opacity':(65,100),
            'scale':(80,130),'card_size':(180,460),'radius':(0,28),'hover_delay':(0,2000),
            'hover_speed':(.25,2),'notice_size':(75,140),'notice_opacity':(35,100),'notice_duration':(1,15),
            'timer_background':(0,100),'timer_size':(50,200),'timer_x':(0,100),'timer_y':(0,100),
            'editor_width':(270,550),'timeline_height':(90,300)}
    for key,value in patch.items():
        if key in enums and value not in enums[key]:raise ValueError('Недопустимое значение: '+key)
        if key in ranges:
            low,high=ranges[key]
            if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:raise ValueError('Значение вне диапазона: '+key)
        if type(DEFAULTS[key]) is bool and type(value) is not bool:raise ValueError('Нужен переключатель: '+key)
        if key in ('accent','background_color','timer_color','panel_color','text_color','muted_color') and not re.fullmatch(r'#[0-9a-fA-F]{6}',str(value)):raise ValueError('Нужен цвет #RRGGBB')
        if key=='asset' and value and not re.fullmatch(r'[a-f0-9]{64}\.(mp4|webm|png|jpg|jpeg|gif|wav)',str(value)):raise ValueError('Неизвестный фон')
        if key=='nav_order' and (not isinstance(value,list) or len(value)!=6 or set(value)!=set(DEFAULTS['nav_order'])):raise ValueError('Некорректный порядок разделов')
        if key=='nav_hidden' and (not isinstance(value,list) or not set(value)<=set(DEFAULTS['nav_order'])-{'settings'}):raise ValueError('Настройки должны оставаться доступными')
        if key=='pinned_tags' and (not isinstance(value,list) or len(value)>15 or any(not isinstance(x,str) or len(x)>80 for x in value)):raise ValueError('Не более 15 закреплённых тегов')
        if key=='sounds':
            if not isinstance(value,dict) or set(value)-{'enabled','pack',*EVENTS}:raise ValueError('Неверные звуки')
            if 'enabled' in value and type(value['enabled']) is not bool:raise ValueError('Нужен переключатель звука')
            if value.get('pack','soft') not in ('soft','digital','chime'):raise ValueError('Неизвестный звуковой набор')
            for event in EVENTS:
                item=value.get(event)
                if item is None:continue
                if not isinstance(item,dict) or set(item)-{'enabled','volume','asset'}:raise ValueError('Неверное событие')
                if 'enabled' in item and type(item['enabled']) is not bool:raise ValueError('Нужен переключатель события')
                if type(item.get('volume',30)) not in (int,float) or not 0<=item.get('volume',30)<=100:raise ValueError('Громкость от 0 до 100')
                if item.get('asset') and not re.fullmatch(r'[a-f0-9]{64}\.wav',str(item['asset'])):raise ValueError('Неизвестный звук')
    return copy.deepcopy(patch)

def configure(suite,patch):
    patch=validate(patch)
    cfg=current(suite)
    if 'sounds' in patch:
        sounds=cfg['sounds']
        for key,value in patch.pop('sounds').items():
            if key in EVENTS:sounds[key].update(value)
            else:sounds[key]=value
    cfg.update(patch)
    with suite.lock:
        suite.cfg['customization']=cfg
        suite.cfg.setdefault('appearance',{})['theme']=cfg['theme']
        suite.save_cfg()
    return cfg

def assets_dir(suite):
    root=suite.data/'customization'/'assets';root.mkdir(parents=True,exist_ok=True);return root

def asset_path(suite,name):
    if not re.fullmatch(r'[a-f0-9]{64}\.(mp4|webm|png|jpg|jpeg|gif|wav)',name):raise ValueError('Неизвестный файл оформления')
    return assets_dir(suite)/name

def select_file(suite,kind):
    if not suite.window:raise ValueError('Выбор файла доступен в окне приложения')
    import webview
    types={'background':('Фон (*.png;*.jpg;*.jpeg;*.gif;*.mp4;*.webm)',),
           'sound':('Звук (*.wav;*.mp3;*.ogg;*.m4a)',),
           'theme':('Оформление AFTERPLAY (*.*)',)}
    from localization import translate
    result=suite.window.create_file_dialog(webview.FileDialog.OPEN,file_types=tuple(translate(suite,value) for value in types[kind]))
    return result[0] if result else None

def import_asset(suite,path,kind):
    from app import run
    path=Path(path)
    allowed={ 'background':{'.png','.jpg','.jpeg','.gif','.mp4','.webm'},'sound':{'.wav','.mp3','.ogg','.m4a'}}
    if kind not in allowed or path.suffix.lower() not in allowed[kind] or not path.is_file():raise ValueError('Неподдерживаемый файл')
    if path.stat().st_size>300*1024**2:raise ValueError('Выберите файл до 300 МБ')
    root=assets_dir(suite);temp=root/('import-'+uuid.uuid4().hex+path.suffix.lower())
    try:
        if kind=='sound':
            temp=temp.with_suffix('.wav')
            result=run([suite.ff(),'-v','error','-i',path,'-t','10','-ac','1','-ar','44100','-c:a','pcm_s16le','-y',temp],timeout=30)
            if result.returncode:raise ValueError('Не удалось прочитать звуковой файл')
        elif path.suffix.lower()=='.gif':
            # Video can actually pause when hidden; animated GIF img elements cannot.
            temp=temp.with_suffix('.mp4')
            result=run([suite.ff(),'-v','error','-i',path,'-t','30','-vf','scale=trunc(iw/2)*2:trunc(ih/2)*2',
                        '-an','-c:v','libx264','-preset','veryfast','-pix_fmt','yuv420p','-movflags','+faststart','-y',temp],timeout=90)
            if result.returncode:raise ValueError('Не удалось прочитать GIF')
        else:shutil.copy2(path,temp)
        if kind=='background':
            # Probe before exposing an imported file to WebView.
            import av
            with av.open(str(temp)) as container:
                if not container.streams.video:raise ValueError('В файле нет изображения')
                if next(container.decode(video=0),None) is None:raise ValueError('В файле нет доступных кадров')
        name=hashlib.sha256(temp.read_bytes()).hexdigest()+temp.suffix.lower()
        target=root/name
        if not target.exists():os.replace(temp,target)
        return {'asset':name,'name':path.name,'video':target.suffix in {'.mp4','.webm'}}
    finally:temp.unlink(missing_ok=True)

def cover(suite,cid,position):
    from app import run
    clip=suite.clip(str(cid));position=float(position)
    if not math.isfinite(position) or not 0<=position<=clip['duration']:raise ValueError('Кадр вне записи')
    target=suite.data/'thumbs'/f'{clip["id"]}.jpg';temp=target.with_suffix('.new.jpg')
    try:
        result=run([suite.ff(),'-v','error','-ss',max(0,min(position,clip['duration']-.05)),'-i',clip['path'],
                    '-frames:v','1','-vf','scale=640:-2','-q:v','3','-y',temp],timeout=30)
        if result.returncode or not temp.exists():raise ValueError('Не удалось извлечь обложку')
        os.replace(temp,target)
        version=time.time_ns()
        with suite.lock:
            suite.cfg.setdefault('clip_covers',{})[str(cid)]={'time':position,'version':version};suite.save_cfg()
        return {'ok':True,'version':version}
    finally:temp.unlink(missing_ok=True)

def tone(event,pack,gain):
    rate=44100;parts={'mark':(880,1175), 'saving':(440,660),'success':(660,880,1100),'error':(330,220)}[event]
    factor={'soft':1,'digital':1.4,'chime':.75}[pack];samples=[]
    for frequency in parts:
        duration=(.16 if pack!='chime' else .20) if event=='mark' else .10 if pack!='chime' else .17
        for i in range(int(duration*rate)):
            t=i/rate;envelope=min(1,t/.012)*(min(1,(duration-t)/.05) if event=='mark' else max(0,1-t/duration)**2)
            value=math.sin(2*math.pi*frequency*factor*t)
            if pack=='chime':value=.8*value+.2*math.sin(2*math.pi*frequency*2.01*t)
            samples.append(round(value*envelope*gain*(.6 if event=='mark' else .35)*32767))
        samples.extend([0]*int(.025*rate))
    out=io.BytesIO()
    with wave.open(out,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(struct.pack('<'+'h'*len(samples),*samples))
    return out.getvalue()

def sound(suite,event,preview=False,settings=None):
    global _sound_worker
    if event not in EVENTS:raise ValueError('Неизвестный звуковой сигнал')
    cfg=(validate(settings) if settings is not None else current(suite)).get('sounds',current(suite)['sounds']);item=cfg[event]
    if not preview and (not cfg['enabled'] or not item['enabled']):return {'played':False}
    def play(request):
        suite,event,cfg,item=request
        try:
            gain=item['volume']/100
            if item['asset']:
                import array
                with wave.open(str(asset_path(suite,item['asset'])),'rb') as src:
                    params=src.getparams();data=array.array('h');data.frombytes(src.readframes(src.getnframes()))
                data=array.array('h',(round(x*gain) for x in data));out=io.BytesIO()
                with wave.open(out,'wb') as dst:dst.setparams(params);dst.writeframes(data.tobytes())
                data=out.getvalue()
            else:data=tone(event,cfg['pack'],gain)
            import winsound
            winsound.PlaySound(data,winsound.SND_MEMORY|winsound.SND_NODEFAULT)
        except Exception as error:suite.log('sound_feedback_error',error=str(error))
    def worker():
        while True:
            request=_sound_queue.get()
            try:play(request)
            finally:_sound_queue.task_done()
    with _sound_lock:
        if _sound_worker is None or not _sound_worker.is_alive():
            _sound_worker=threading.Thread(target=worker,name='AFTERPLAY sounds',daemon=True);_sound_worker.start()
    request=(suite,event,copy.deepcopy(cfg),copy.deepcopy(item))
    try:_sound_queue.put_nowait(request)
    except queue.Full:
        try:_sound_queue.get_nowait();_sound_queue.task_done()
        except queue.Empty:pass
        try:_sound_queue.put_nowait(request)
        except queue.Full:return {'played':False}
    return {'played':True,'queued':True}

def save_preset(suite,name):
    name=str(name).strip()[:60]
    if not name:raise ValueError('Назовите оформление')
    values=suite.cfg.setdefault('appearance_presets',{})
    if len(values)>=30 and name not in values:raise ValueError('Можно сохранить до 30 оформлений')
    values[name]=current(suite);suite.save_cfg();return values

def delete_preset(suite,name):
    with suite.lock:
        values=suite.cfg.get('appearance_presets',{})
        if not isinstance(name,str) or name not in values:raise ValueError('Набор не найден')
        remaining={key:value for key,value in values.items() if key!=name}
        suite.cfg['appearance_presets']=remaining
        try:suite.save_cfg()
        except Exception:
            suite.cfg['appearance_presets']=values
            raise
        return remaining

def export_preset(suite):
    import webview
    from localization import translate
    selected=suite.window.create_file_dialog(webview.FileDialog.SAVE,save_filename=translate(suite,'Мой AFTERPLAY.afterplay-theme'),file_types=(translate(suite,'Оформление AFTERPLAY (*.*)'),))
    if not selected:return {'cancelled':True}
    target=Path(selected[0] if isinstance(selected,(list,tuple)) else selected)
    if target.suffix!='.afterplay-theme':target=target.with_suffix('.afterplay-theme')
    cfg=current(suite);names={cfg['asset'],*(cfg['sounds'][event]['asset'] for event in EVENTS)}-{''}
    temp=target.with_suffix('.partial')
    try:
        with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('theme.json',json.dumps(cfg,ensure_ascii=False))
            for name in names:archive.write(asset_path(suite,name),'assets/'+name)
        os.replace(temp,target)
    finally:temp.unlink(missing_ok=True)
    return {'path':str(target)}

def import_preset(suite,path):
    with zipfile.ZipFile(path) as archive:
        if len(archive.infolist())>10 or sum(x.file_size for x in archive.infolist())>350*1024**2:raise ValueError('Слишком большой набор оформления')
        cfg=validate(json.loads(archive.read('theme.json')))
        names={cfg.get('asset',''),*(cfg.get('sounds',{}).get(event,{}).get('asset','') for event in EVENTS)}-{''}
        for name in names:
            dest=asset_path(suite,name);data=archive.read('assets/'+name)
            if hashlib.sha256(data).hexdigest()!=name.split('.')[0]:raise ValueError('Файл оформления повреждён')
            if not dest.exists():dest.write_bytes(data)
    return configure(suite,cfg)

def dispatch(suite,action,args):
    if action=='customize_config':return configure(suite,args)
    if action=='customize_state':return {'settings':current(suite),'presets':suite.cfg.get('appearance_presets',{})}
    if action=='customize_reset':return configure(suite,copy.deepcopy(DEFAULTS))
    if action=='customize_import_asset':
        kind=args.get('kind','background');path=select_file(suite,kind)
        if not path:return {'cancelled':True}
        result=import_asset(suite,path,kind)
        if kind!='background':
            event=args.get('event')
            if event not in EVENTS:raise ValueError('Неизвестное событие')
        return result
    if action=='customize_sound':return sound(suite,args.get('event','success'),True,args.get('settings'))
    if action=='customize_notice':
        cfg=validate(args['settings']) if 'settings' in args else None
        if suite.desktop:suite.desktop.notify('Так выглядит сохранение','AFTERPLAY · локальный предпросмотр','success',feedback=False,appearance=cfg)
        return {'ok':True}
    if action=='customize_cover':return cover(suite,args['id'],args.get('time',0))
    if action=='customize_preset_save':return save_preset(suite,args.get('name',''))
    if action=='customize_preset_delete':return delete_preset(suite,args.get('name'))
    if action=='customize_preset_export':return export_preset(suite)
    if action=='customize_preset_import':
        path=select_file(suite,'theme')
        return {'cancelled':True} if not path else import_preset(suite,path)
    raise ValueError('Неизвестное действие оформления')
