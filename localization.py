"""Russian source messages and an English UI catalog. User data is never rewritten."""
import json
from functools import lru_cache
from pathlib import Path
import re

def language(suite):return suite.cfg.get('language','ru') if suite.cfg.get('language','ru') in {'ru','en'} else 'ru'

@lru_cache(maxsize=1)
def catalog():return json.loads((Path(__file__).parent/'ui/en.json').read_text('utf-8'))

@lru_cache(maxsize=1)
def fragments():
    keys=sorted(catalog(),key=len,reverse=True)
    return re.compile(r'(?<![А-Яа-яЁё])(?:'+'|'.join(re.escape(key) for key in keys)+r')(?![А-Яа-яЁё])')

def translate(suite,text):
    if language(suite)!='en' or not isinstance(text,str):return text
    if re.search(r'\.(mp4|gif|mkv|webm|mov|avi|afterplay-theme)$',text,re.IGNORECASE) and not text.startswith('Мой AFTERPLAY.'):return text
    mapping=catalog()
    if text in mapping:return mapping[text]
    return fragments().sub(lambda match:mapping[match[0]],text)

def configure(suite,value):
    if value not in {'ru','en'}:raise ValueError('Неподдерживаемый язык')
    with suite.lock:suite.cfg['language']=value;suite.save_cfg()
    if suite.desktop:
        try:suite.desktop.icon.update_menu()
        except Exception:pass
    return {'language':value}
