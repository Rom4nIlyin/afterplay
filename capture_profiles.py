"""Per-executable settings; capture_border is a global replay preference."""
import copy
import math
import ntpath
import uuid
import video_quality

FIELDS = {'seconds','fps','mbps','monitor','audio','audio_mode','capture_mode',
          'quality_mode','cq','max_mbps','height','preset','encoder','audio_bitrate',
          'audio_offset_ms','audio_follow_window','cursor',
          'capture_backend','save_format','gif_seconds','chat_path','microphone_enabled','microphone_device','microphone_name','microphone_gain','microphone_voice_cleanup'}
DEFAULT_PROFILE='screen:default'


def ensure_defaults(suite):
    """One editable desktop profile, with previous settings retained on migration."""
    with suite.lock:
        profiles=suite.cfg.setdefault('capture_profiles',{})
        changed=False
        # Migrate legacy per-profile border values. The replay setting is canonical.
        for profile in profiles.values():
            settings=profile.get('settings',{})
            if isinstance(settings,dict) and 'capture_border' in settings:
                del settings['capture_border']
                changed=True
        default=profiles.get(DEFAULT_PROFILE)
        if default and (default.get('path') or default.get('settings',{}).get('capture_mode')=='window'):
            # Older forms could accidentally save an application's fields into
            # the reserved desktop identity. Preserve its application copy.
            path=default.get('path','')
            if path and key(path) not in profiles:
                profiles[key(path)]={**copy.deepcopy(default),'id':path}
            profiles.pop(DEFAULT_PROFILE)
        if DEFAULT_PROFILE not in profiles:
            settings={**validated(suite.replay.settings),'capture_mode':'monitor','audio_mode':'system',
                      'monitor':'primary','audio':'default','chat_path':''}
            profiles[DEFAULT_PROFILE]={'id':DEFAULT_PROFILE,'path':'','name':'По умолчанию · весь экран','settings':settings}
            changed=True
        selected=suite.cfg.get('selected_capture_profile')
        if selected and key(selected) in profiles:
            if changed and key(selected)==DEFAULT_PROFILE:
                apply(suite,DEFAULT_PROFILE)
                return
            suite.replay.active_profile=profiles[key(selected)]['name']
            if changed:suite.save_cfg()
            return
        previous=copy.deepcopy(suite.replay.settings)
        if previous.get('capture_mode')!='monitor' or previous.get('audio_mode')!='system':
            old_key=key(previous.get('window_path','')) if previous.get('window_path') else 'screen:previous'
            profiles.setdefault(old_key,{'id':old_key,'path':previous.get('window_path',''),
                                        'name':'Прежние настройки','settings':validated(previous)})
        apply(suite,DEFAULT_PROFILE)


def configure(suite,args):
    """Save the visible form and its selected profile in the same config write."""
    replay=suite.replay
    with replay.lock,suite.lock:
        if replay.phase in {'starting','recording','stopping'} or replay.saving:raise ValueError('Сначала остановите повтор')
        identifier=args.get('id') or suite.cfg.get('selected_capture_profile')
        profile=suite.cfg.get('capture_profiles',{}).get(key(identifier))
        if not profile:raise ValueError('Выберите профиль')
        path=str(args.get('path','')).strip().strip('"');name=str(args.get('name','')).strip()
        if not name:raise ValueError('Укажите название профиля')
        values=args.get('settings',{})
        validated(values)
        # An old form must not overwrite the global border preference.
        values={name:value for name,value in values.items() if name!='capture_border'}
        if key(identifier)==DEFAULT_PROFILE and (path or values.get('capture_mode',profile['settings'].get('capture_mode'))!='monitor'):
            raise ValueError('Профиль по умолчанию предназначен для экрана. Для приложения создай отдельный профиль.')
        if path and (not ntpath.isabs(path) or ntpath.splitext(path)[1].lower()!='.exe'):raise ValueError('Укажите полный путь к приложению .exe')
        old_settings=copy.deepcopy(replay.settings);old_cfg=copy.deepcopy(suite.cfg)
        try:
            replay.configure({**values,'window_path':path},persist=False)
            # The reserved desktop profile keeps its identity when renamed.
            if key(identifier)==DEFAULT_PROFILE:
                updated={'id':DEFAULT_PROFILE,'path':path,'name':name[:100],'settings':validated(replay.settings)}
                suite.cfg['capture_profiles'][DEFAULT_PROFILE]=updated
            else:
                updated=save(suite,{'id':identifier,'path':path,'name':name,'settings':replay.settings},persist=False)
            suite.cfg['replay']=copy.deepcopy(replay.settings)
            suite.cfg['selected_capture_profile']=updated['id'];replay.active_profile=updated['name']
            suite.save_cfg()
            return updated
        except Exception:
            replay.settings=old_settings;suite.cfg=old_cfg
            raise


def create(suite):
    if suite.replay.phase in {'starting','recording','stopping'} or suite.replay.saving:raise ValueError('Сначала остановите повтор')
    default=suite.cfg['capture_profiles'][DEFAULT_PROFILE]
    profile=save(suite,{'name':'Новый профиль','settings':{**default['settings'],'capture_mode':'monitor','audio_mode':'system'}})
    apply(suite,profile['id']);return profile


def key(path):
    return ntpath.normcase(ntpath.normpath(str(path).strip().strip('"')))


def validated(values):
    from replay import DEFAULTS, MINUTES
    result = {name: copy.deepcopy(value) for name,value in values.items() if name in FIELDS}
    combined = {**DEFAULTS, **result}
    for name in ('seconds','fps','mbps','cq','max_mbps','height','audio_bitrate','audio_offset_ms'):
        value=combined[name]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or int(value)!=value:
            raise ValueError('Некорректная настройка профиля: '+name)
    video_quality.validate(combined)
    if combined['seconds'] not in {n*60 for n in MINUTES}:raise ValueError('Недопустимая длительность буфера')
    if combined['audio_mode'] not in {'system','game','exclude','none','multitrack'}:raise ValueError('Неизвестный режим звука')
    if combined['capture_mode'] not in {'window','monitor'}:raise ValueError('Неизвестный источник записи')
    if combined.get('save_format','mp4') not in {'mp4','gif'}:raise ValueError('Неизвестный формат')
    from gif_media import validate_duration
    validate_duration(combined.get('gif_seconds',5))
    for name in ('cursor','capture_border','audio_follow_window','microphone_enabled','microphone_voice_cleanup'):
        if not isinstance(combined[name],bool):raise ValueError('Ожидался переключатель: '+name)
    if type(combined['microphone_gain']) not in (int,float) or not 0<=combined['microphone_gain']<=100:raise ValueError('Громкость микрофона: 0–100%')
    for name in ('monitor','audio','chat_path','microphone_device','microphone_name'):
        if name in result and not isinstance(result[name],str):raise ValueError('Ожидалась строка: '+name)
    chat=result.get('chat_path','')
    if chat and (not ntpath.isabs(chat) or ntpath.splitext(chat)[1].lower()!='.exe'):raise ValueError('Укажите полный путь к приложению чата .exe')
    return result


def for_app(config,path):
    profile=config.get('capture_profiles',{}).get(key(path))
    return validated(profile['settings']) if profile else {}


def state(suite):
    rows=copy.deepcopy(list(suite.cfg.get('capture_profiles',{}).values()))
    return sorted(rows,key=lambda p:p['name'].casefold())


def save(suite,args,persist=True):
    path=str(args.get('path','')).strip().strip('"')
    values=args.get('settings',suite.replay.settings)
    if not isinstance(values,dict):raise ValueError('Некорректные настройки профиля')
    settings=validated(values)
    if path and (not ntpath.isabs(path) or ntpath.splitext(path)[1].lower()!='.exe'):raise ValueError('Выберите полный путь к приложению .exe')
    if not path and settings.get('capture_mode',suite.replay.settings['capture_mode'])!='monitor':raise ValueError('Для профиля окна выберите приложение .exe')
    with suite.lock:
        profiles=suite.cfg.setdefault('capture_profiles',{})
        previous=key(args.get('id','')) if args.get('id') else None
        if previous and previous not in profiles:raise ValueError('Редактируемый профиль не найден')
        if previous==DEFAULT_PROFILE and (path or settings.get('capture_mode',suite.replay.settings['capture_mode'])!='monitor'):
            raise ValueError('Профиль по умолчанию предназначен для экрана. Для приложения создай отдельный профиль.')
        identifier=path or (previous if previous and previous.startswith('screen:') else 'screen:'+uuid.uuid4().hex)
        if previous is None and key(identifier) in profiles:raise ValueError('Для этого приложения уже есть профиль. Выбери его для изменения.')
        if previous and key(identifier)!=previous and key(identifier) in profiles:raise ValueError('Для этого приложения уже есть профиль')
        profile={'id':identifier,'path':path,'name':str(args.get('name') or ntpath.basename(path) or 'Весь экран')[:100],'settings':settings}
        if len(profiles)>=100 and key(identifier) not in profiles and previous is None:raise ValueError('Не больше 100 профилей')
        profiles[key(identifier)]=profile
        if previous and previous!=key(identifier):profiles.pop(previous,None)
        if persist:suite.save_cfg()
    return profile


def remove(suite,path):
    with suite.replay.lock,suite.lock:
        if key(path)==DEFAULT_PROFILE:raise ValueError('Профиль по умолчанию нельзя удалить')
        selected=key(suite.cfg.get('selected_capture_profile',''))==key(path)
        if selected and (suite.replay.phase in {'starting','recording','stopping'} or suite.replay.saving):raise ValueError('Сначала остановите повтор')
        suite.cfg.setdefault('capture_profiles',{}).pop(key(path),None)
        if selected:
            suite.cfg.pop('selected_capture_profile',None)
            if DEFAULT_PROFILE in suite.cfg['capture_profiles']:apply(suite,DEFAULT_PROFILE)
        suite.save_cfg()
    return {'ok':True}


def apply(suite,path):
    replay=suite.replay
    with replay.lock,suite.lock:
        if replay.phase in {'starting','recording','stopping'} or replay.saving:raise ValueError('Сначала остановите повтор')
        profile=suite.cfg.get('capture_profiles',{}).get(key(path))
        if not profile:raise ValueError('Профиль не найден')
        settings={**replay.settings,**validated(profile['settings'])}
        path=profile.get('path','')
        settings.update(window_path=path,window_hwnd=0,window_pid=0,
                        window_title=profile['name'] if path else '',game_path=path,game_pid=0,chat_pid=0)
        replay.settings=settings;replay.active_profile=profile['name']
        suite.cfg['selected_capture_profile']=profile.get('id') or profile['path']
        suite.cfg['replay']=copy.deepcopy(settings);suite.save_cfg()
    return replay.state()
