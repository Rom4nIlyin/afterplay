"""Elapsed export time, rendered after sizing and timestamp normalization."""
import os
from pathlib import Path


def video_filter(settings=None,fps=60,language='ru'):
    from customization import DEFAULTS,validate
    cfg={**DEFAULTS,**validate(settings or {})}
    font = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / ('consolab.ttf' if cfg['timer_font']=='mono' else 'segoeuib.ttf')
    if cfg['timer_font']=='sans':font=Path(__file__).parent/'ui/fonts/Inter-SemiBold.ttf'
    font_path = font.as_posix().replace(':', r'\:').replace("'", r"\'")
    text = (r'%{eif\:floor(t/60)\:d\:2}\:'
            r'%{eif\:mod(floor(t),60)\:d\:2}')
    if cfg['timer_format']=='milliseconds':text+=r'.%{eif\:mod(floor(t*1000+0.0001),1000)\:d\:3}'
    elif cfg['timer_format']=='frames':text=('Frame ' if language=='en' else 'Кадр ')+r'%{eif\:floor(t*'+str(float(fps))+r'+0.0001)\:d}'
    scale=.032*cfg['timer_size']/100;color=cfg['timer_color'].replace('#','0x')
    return (f"setpts=PTS-STARTPTS,drawtext=fontfile='{font_path}':text='{text}':"
            f"fontsize=max(14\\,h*{scale:.6f}):fontcolor={color}:box=1:boxcolor=black@{cfg['timer_background']/100:.3f}:"
            f"boxborderw=6:x=(w-tw)*{cfg['timer_x']/100:.6f}:y=(h-th)*{cfg['timer_y']/100:.6f}")
