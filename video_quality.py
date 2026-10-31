"""Validated capture settings and FFmpeg encoder options."""
DEFAULTS={'capture_mode':'monitor','window_hwnd':0,'window_pid':0,'window_path':'','window_title':'',
          'audio_follow_window':True,'quality_mode':'quality','cq':19,'max_mbps':80,'height':0,
          'preset':'performance','encoder':'auto','audio_bitrate':192,'audio_offset_ms':0,'cursor':True,
          'capture_backend':'auto'}
FPS=(24,30,60,90,120)

def validate(cfg):
    choices={'fps':FPS,'capture_mode':('monitor','window'),'quality_mode':('quality','vbr','cbr'),
             'preset':('performance','balanced','quality'),'encoder':('auto','h264_nvenc','libx264'),
             'height':(0,720,1080,1440,2160),'audio_bitrate':(128,192,256,320)}
    for key,values in choices.items():
        if cfg[key] not in values:raise ValueError('Неподдерживаемая настройка: '+key)
    if cfg.get('capture_backend','auto') not in ('auto','compatibility'):
        raise ValueError('Неподдерживаемый способ захвата')
    for key,low,high in [('mbps',5,200),('max_mbps',5,200),('cq',14,32),('audio_offset_ms',-2000,2000)]:
        if not low<=cfg[key]<=high:raise ValueError(f'{key}: допустимый диапазон {low}…{high}')
    if cfg['quality_mode']=='vbr' and cfg['max_mbps']<cfg['mbps']:
        raise ValueError('Максимальный битрейт не может быть меньше среднего')

def output_size(cfg,width,height):
    scale=min(1,cfg['height']/height) if cfg['height'] else 1
    return max(2,int(width*scale)//2*2),max(2,int(height*scale)//2*2)

def encoder_options(cfg,encoder,width,height,*,gpu_frames=False):
    w,h=output_size(cfg,width,height)
    args=[] if gpu_frames else ['-vf',f'scale={w}:{h}:flags=lanczos:out_color_matrix=bt709:out_range=tv,format=yuv420p']
    args+=['-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-color_range','tv',
          '-c:v',encoder,'-profile:v','high']
    mode=cfg['quality_mode'];cap=cfg['mbps'] if mode=='cbr' else cfg['max_mbps']
    if encoder=='h264_nvenc':
        preset={'performance':'p1','balanced':'p4','quality':'p6'}[cfg['preset']]
        performance=cfg['preset']=='performance';quality=cfg['preset']=='quality'
        args+=['-preset',preset,'-tune','ll' if performance else 'hq','-rc','cbr' if mode=='cbr' else 'vbr',
               '-multipass','disabled','-spatial-aq','0' if performance else '1',
               '-temporal-aq','1' if quality else '0','-aq-strength','8','-bf','0',
               '-rc-lookahead','8' if quality else '0','-forced-idr','1']
        if performance:args+=['-delay','0','-zerolatency','1']
        if mode=='quality':args+=['-cq',str(cfg['cq']),'-b:v','0']
        else:args+=['-b:v',f'{cfg["mbps"]}M']
    else:
        args+=['-preset',{'performance':'ultrafast','balanced':'veryfast','quality':'fast'}[cfg['preset']],'-bf','0']
        if mode=='quality':args+=['-crf',str(cfg['cq'])]
        else:args+=['-b:v',f'{cfg["mbps"]}M']
        if mode=='cbr':args+=['-minrate',f'{cap}M','-x264-params','nal-hrd=cbr:force-cfr=1']
    return args+['-maxrate',f'{cap}M','-bufsize',f'{cap*2}M','-g',str(cfg['fps']),
                 '-force_key_frames','expr:gte(t,n_forced)','-fps_mode','cfr','-r',str(cfg['fps'])]
