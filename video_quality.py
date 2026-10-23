"""Validated capture settings and FFmpeg encoder options."""
DEFAULTS={'capture_mode':'monitor','window_hwnd':0,'window_pid':0,'window_path':'','window_title':'',
          'audio_follow_window':True,'quality_mode':'quality','cq':19,'max_mbps':80,'height':0,
          'preset':'balanced','encoder':'auto','audio_bitrate':192,'audio_offset_ms':0,'cursor':True}
FPS=(24,30,60,90,120)

def validate(cfg):
    choices={'fps':FPS,'capture_mode':('monitor','window'),'quality_mode':('quality','vbr','cbr'),
             'preset':('performance','balanced','quality'),'encoder':('auto','h264_nvenc','libx264'),
             'height':(0,720,1080,1440,2160),'audio_bitrate':(128,192,256,320)}
    for key,values in choices.items():
        if cfg[key] not in values:raise ValueError('Неподдерживаемая настройка: '+key)
    for key,low,high in [('mbps',5,200),('max_mbps',5,200),('cq',14,32),('audio_offset_ms',-2000,2000)]:
        if not low<=cfg[key]<=high:raise ValueError(f'{key}: допустимый диапазон {low}…{high}')
    if cfg['quality_mode']=='vbr' and cfg['max_mbps']<cfg['mbps']:
        raise ValueError('Максимальный битрейт не может быть меньше среднего')

def output_size(cfg,width,height):
    scale=min(1,cfg['height']/height) if cfg['height'] else 1
    return max(2,int(width*scale)//2*2),max(2,int(height*scale)//2*2)

def encoder_options(cfg,encoder,width,height):
    w,h=output_size(cfg,width,height)
    args=['-vf',f'scale={w}:{h}:flags=lanczos:out_color_matrix=bt709:out_range=tv,format=yuv420p',
          '-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709',
          '-c:v',encoder,'-profile:v','high']
    mode=cfg['quality_mode'];cap=cfg['mbps'] if mode=='cbr' else cfg['max_mbps']
    if encoder=='h264_nvenc':
        preset={'performance':'p3','balanced':'p5','quality':'p6'}[cfg['preset']]
        args+=['-preset',preset,'-tune','hq','-rc','cbr' if mode=='cbr' else 'vbr',
               '-spatial-aq','1','-temporal-aq','1','-aq-strength','8','-bf','2',
               '-rc-lookahead','0' if cfg['preset']=='performance' else '8','-forced-idr','1']
        if mode=='quality':args+=['-cq',str(cfg['cq']),'-b:v','0']
        else:args+=['-b:v',f'{cfg["mbps"]}M']
    else:
        args+=['-preset',{'performance':'ultrafast','balanced':'veryfast','quality':'fast'}[cfg['preset']],'-bf','2']
        if mode=='quality':args+=['-crf',str(cfg['cq'])]
        else:args+=['-b:v',f'{cfg["mbps"]}M']
        if mode=='cbr':args+=['-minrate',f'{cap}M','-x264-params','nal-hrd=cbr:force-cfr=1']
    return args+['-maxrate',f'{cap}M','-bufsize',f'{cap*2}M','-g',str(cfg['fps']*2),
                 '-force_key_frames','expr:gte(t,n_forced*2)','-fps_mode','cfr','-r',str(cfg['fps'])]
