"""Generate the browser catalogs from the authoritative JSON files (ui/en.json, ui/ko.json).

Every catalog must translate exactly the same Russian keys as English, with the same
{0} / {#0} placeholders, so no language silently falls back to Russian.
"""
from pathlib import Path
import argparse,json,re
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
english=json.loads((root/'ui/en.json').read_text('utf-8'))
problems=[]
for code in ('en','ko'):
    data=json.loads((root/f'ui/{code}.json').read_text('utf-8'))
    if code!='en':
        missing=[key for key in english if key not in data];extra=[key for key in data if key not in english]
        if missing:problems.append(f'{code}.json misses {len(missing)} keys, e.g. {missing[:3]}')
        if extra:problems.append(f'{code}.json has {len(extra)} keys not in en.json, e.g. {extra[:3]}')
    for key,value in data.items():
        if not isinstance(value,str) or not value.strip():problems.append(f'{code}.json: empty translation for {key!r}')
        elif sorted(re.findall(r'\{#?\d\}',key))!=sorted(re.findall(r'\{#?\d\}',value)):problems.append(f'{code}.json: placeholders differ for {key!r}')
    content=f"'use strict';\nwindow.AFTERPLAY_{code.upper()}="+json.dumps(data,ensure_ascii=False)+';\n'
    target=root/f'ui/{code}-catalog.js'
    if args.check:
        if not target.is_file() or target.read_text('utf-8')!=content:problems.append(f'{target.name} is stale; run scripts/build_translations.py')
    else:target.write_text(content,'utf-8')
if problems:raise SystemExit('\n'.join(problems))
