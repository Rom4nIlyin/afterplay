"""Generate the initial browser catalog from the authoritative English JSON."""
from pathlib import Path
import argparse,json
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
content="'use strict';\nwindow.AFTERPLAY_EN="+json.dumps(json.loads((root/'ui/en.json').read_text('utf-8')),ensure_ascii=False)+';\n'
target=root/'ui/en-catalog.js'
if args.check:
    if target.read_text('utf-8')!=content:raise SystemExit('English browser catalog is stale; run scripts/build_translations.py')
else:target.write_text(content,'utf-8')
