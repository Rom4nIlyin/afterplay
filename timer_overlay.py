"""Elapsed export time, rendered after sizing and timestamp normalization."""
import os
from pathlib import Path


def video_filter():
    font = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'consolab.ttf'
    font_path = font.as_posix().replace(':', r'\:').replace("'", r"\'")
    text = (r'%{eif\:floor(t/60)\:d\:2}\:'
            r'%{eif\:mod(floor(t),60)\:d\:2}.'
            r'%{eif\:mod(floor(t*1000+0.0001),1000)\:d\:3}')
    return (f"setpts=PTS-STARTPTS,drawtext=fontfile='{font_path}':text='{text}':"
            "fontsize=max(14\\,h*0.032):fontcolor=white:box=1:boxcolor=black@0.65:"
            "boxborderw=6:x=w-tw-h*0.025:y=h*0.025")
