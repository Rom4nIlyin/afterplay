"""Russian source messages with English and Korean UI catalogs. User data is never rewritten."""
import json
from functools import lru_cache
from pathlib import Path
import re

LANGUAGES=('ru','en','ko')

def language(suite):return suite.cfg.get('language','ru') if suite.cfg.get('language','ru') in LANGUAGES else 'ru'

@lru_cache(maxsize=2)
def catalog(code='en'):return json.loads((Path(__file__).parent/f'ui/{code}.json').read_text('utf-8'))

@lru_cache(maxsize=2)
def templates(code='en'):
    """Keys with {0}, {1}… match whole messages; the parts in braces are kept."""
    out=[]
    for key,value in catalog(code).items():
        if re.search(r'\{#?\d\}',key):
            order=[int(n) for n in re.findall(r'\{#?(\d)\}',key)]
            source=''.join((r'(\d+(?:[.,]\d+)?)' if piece[1]=='#' else '(.+?)') if re.fullmatch(r'\{#?\d\}',piece) else re.escape(piece) for piece in re.split(r'(\{#?\d\})',key))
            out.append((re.compile('^'+source+'$'),value,order))
    return out

@lru_cache(maxsize=2)
def fragments(code='en'):
    keys=sorted((key for key in catalog(code) if not re.search(r'\{#?\d\}',key)),key=len,reverse=True)
    return re.compile(r'(?<![А-Яа-яЁё])(?:'+'|'.join(re.escape(key) for key in keys)+r')(?![А-Яа-яЁё])')

def translate(suite,text):
    code=language(suite)
    if code=='ru' or not isinstance(text,str):return text
    if re.search(r'\.(mp4|gif|mkv|webm|mov|avi|afterplay-theme)$',text,re.IGNORECASE) and not text.startswith('Мой AFTERPLAY.'):return text
    mapping=catalog(code)
    if text in mapping:return mapping[text]
    for pattern,value,order in templates(code):
        match=pattern.match(text)
        if match:return re.sub(r'\{#?(\d)\}',lambda m:translate(suite,match.group(order.index(int(m[1]))+1)) if int(m[1]) in order else '',value)
    return fragments(code).sub(lambda match:mapping[match[0]],text)

def configure(suite,value):
    if value not in LANGUAGES:raise ValueError('Неподдерживаемый язык')
    with suite.lock:suite.cfg['language']=value;suite.save_cfg()
    if suite.desktop:
        try:suite.desktop.icon.update_menu()
        except Exception:pass
    return {'language':value}
