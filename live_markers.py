"""Session timestamps become clip-relative bookmarks only after a successful save."""
import json
import math


def relative(values,start,duration):
    return sorted({round(max(0,min(duration,float(value)-start)),6) for value in values
                   if math.isfinite(float(value)) and start-1e-6<=float(value)<=start+duration+1e-6})


def persist(session,values):
    temporary=session/'markers.tmp'
    temporary.write_text(json.dumps(values),encoding='utf-8')
    temporary.replace(session/'markers.json')


def attach(suite,path,values,start,duration):
    marks=relative(values,start,duration)
    with suite.db() as db:
        row=db.execute('SELECT id,marks FROM clips WHERE path=?',(str(path),)).fetchone()
        if row:
            combined=sorted(set(json.loads(row['marks'] or '[]'))|set(marks))
            db.execute('UPDATE clips SET marks=? WHERE id=?',(json.dumps(combined),row['id']))
    return marks
