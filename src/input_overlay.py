"""Shared keyboard geometry for the editor's SVG and FFmpeg's ASS renderer."""
import math
from pathlib import Path
import input_capture

DEFAULTS = {'layout': 'full', 'position': 'bottom-left', 'size': 42, 'opacity': 90}


def settings(values=None):
    values = values or {}
    result = {**DEFAULTS, **{k: v for k, v in values.items() if k in DEFAULTS}}
    if result['layout'] not in ('full', 'compact'):
        raise ValueError('Неизвестный вид клавиатуры')
    if result['position'] not in ('bottom-left', 'bottom-right', 'top-left', 'top-right'):
        raise ValueError('Неизвестное положение нажатий')
    for key, low, high in (('size', 20, 70), ('opacity', 20, 100)):
        if type(result[key]) not in (int, float) or not math.isfinite(result[key]) or not low <= result[key] <= high:
            raise ValueError('Некорректная настройка нажатий: ' + key)
    return result


def geometry(layout='full'):
    keys = []
    def key(code, label, x, y, w=1, h=1):
        keys.append({'code': code if isinstance(code, str) else 'K'+str(code), 'label': label,
                     'x': round(x * 34, 3), 'y': round(y * 34, 3), 'w': round(w * 34 - 4, 3), 'h': round(h * 34 - 4, 3)})
    if layout == 'compact':
        for code, label, x, y, w in [(81,'Q',0,0,1),(87,'W',1,0,1),(69,'E',2,0,1),(82,'R',3,0,1),
                                   (65,'A',0,1,1),(83,'S',1,1,1),(68,'D',2,1,1),(70,'F',3,1,1),
                                   (160,'Shift',0,2,2),(162,'Ctrl',0,3,1.5),(164,'Alt',1.5,3,1.5),
                                   (32,'Space',2,2,2),(9,'Tab',3,3,1),(38,'↑',5,1,1),
                                   (37,'←',4,2,1),(40,'↓',5,2,1),(39,'→',6,2,1)]: key(code,label,x,y,w)
        mx, my = 7.5, 0
    else:
        key(27,'Esc',0,0)
        for i in range(12): key(112+i,'F'+str(i+1),2+i+(i//4)*.4,0)
        for i,(code,label) in enumerate([(192,'~'),(49,'1'),(50,'2'),(51,'3'),(52,'4'),(53,'5'),(54,'6'),(55,'7'),(56,'8'),(57,'9'),(48,'0'),(189,'−'),(187,'=')]): key(code,label,i,1.3)
        key(8,'Back',13,1.3,2)
        key(9,'Tab',0,2.3,1.5)
        for i,letter in enumerate('QWERTYUIOP'): key(ord(letter),letter,1.5+i,2.3)
        key(219,'[',11.5,2.3); key(221,']',12.5,2.3); key(220,'\\',13.5,2.3,1.5)
        key(20,'Caps',0,3.3,1.8)
        for i,letter in enumerate('ASDFGHJKL'): key(ord(letter),letter,1.8+i,3.3)
        key(186,';',10.8,3.3); key(222,"'",11.8,3.3); key(13,'Enter',12.8,3.3,2.2)
        key(160,'Shift',0,4.3,2.3)
        for i,letter in enumerate('ZXCVBNM'): key(ord(letter),letter,2.3+i,4.3)
        key(188,',',9.3,4.3); key(190,'.',10.3,4.3); key(191,'/',11.3,4.3); key(161,'Shift',12.3,4.3,2.7)
        x=0
        for code,label,w in [(162,'Ctrl',1.3),(91,'Win',1.2),(164,'Alt',1.2),(32,'Space',6.3),(165,'Alt',1.2),(92,'Win',1.2),(93,'Menu',1.3),(163,'Ctrl',1.3)]:
            key(code,label,x,5.3,w); x+=w
        for code,label,x,y in [(44,'Prt',15.5,0),(145,'Scr',16.5,0),(19,'Pause',17.5,0),
                               (45,'Ins',15.5,1.3),(36,'Home',16.5,1.3),(33,'PgUp',17.5,1.3),
                               (46,'Del',15.5,2.3),(35,'End',16.5,2.3),(34,'PgDn',17.5,2.3),
                               (38,'↑',16.5,4.3),(37,'←',15.5,5.3),(40,'↓',16.5,5.3),(39,'→',17.5,5.3)]: key(code,label,x,y)
        for code,label,x,y,w,h in [(144,'Num',19,1.3,1,1),(111,'/',20,1.3,1,1),(106,'*',21,1.3,1,1),(109,'−',22,1.3,1,1),
                                  (103,'7',19,2.3,1,1),(104,'8',20,2.3,1,1),(105,'9',21,2.3,1,1),(107,'+',22,2.3,1,2),
                                  (100,'4',19,3.3,1,1),(101,'5',20,3.3,1,1),(102,'6',21,3.3,1,1),
                                  (97,'1',19,4.3,1,1),(98,'2',20,4.3,1,1),(99,'3',21,4.3,1,1),(256,'Enter',22,4.3,1,2),
                                  (96,'0',19,5.3,2,1),(110,'.',21,5.3,1,1)]: key(code,label,x,y,w,h)
        mx, my = 24, 1.3
    for code,label,x,y,w,h in [('M1','LMB',0,0,1.4,1.6),('M2','RMB',1.4,0,1.4,1.6),('M3','MMB',0,1.6,2.8,1),
                             ('M4','M4',0,2.6,1.4,1),('M5','M5',1.4,2.6,1.4,1),('WU','↑',0,3.6,1.4,1),('WD','↓',1.4,3.6,1.4,1)]: key(code,label,mx+x,my+y,w,h)
    return {'width': max(k['x']+k['w'] for k in keys)+4,
            'height': max(k['y']+k['h'] for k in keys)+4, 'keys': keys}


def metadata(suite, cid):
    clip = suite.clip(cid)
    data = input_capture.read(clip['path'])
    return {'available': data is not None, 'duration': clip['duration'],
            'events': data['events'] if data else [],
            'settings': settings(suite.cfg.get('input_overlays', {}).get(cid)),
            'layouts': {name: geometry(name) for name in ('full','compact')}}


def configure(suite, cid, values):
    suite.clip(cid)
    value = settings(values)
    with suite.lock:
        suite.cfg.setdefault('input_overlays', {})[cid] = value
        suite.save_cfg()
    return value


def ass_time(t):
    ticks = max(0, round(t * 100))
    return f'{ticks//360000}:{ticks//6000%60:02d}:{ticks//100%60:02d}.{ticks%100:02d}'


def ass_filter(path):
    escaped = Path(path).resolve().as_posix().replace(':', r'\:').replace("'", r"\'")
    return "ass=filename='" + escaped + "'"


def render_ass(path, data, start, duration, width, height, options=None):
    cfg = settings(options)
    layout = geometry(cfg['layout'])
    scale = min(width * cfg['size']/100/layout['width'], height * .42/layout['height'])
    margin = max(8, round(min(width,height)*.02))
    x = margin if cfg['position'].endswith('left') else width-margin-layout['width']*scale
    y = margin if cfg['position'].startswith('top') else height-margin-layout['height']*scale
    alpha = f'{round(255*(1-cfg["opacity"]/100)):02X}'
    lines = ['[Script Info]', 'ScriptType: v4.00+', f'PlayResX: {width}', f'PlayResY: {height}',
             'ScaledBorderAndShadow: yes', '[V4+ Styles]',
             'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
             'Style: Default,Segoe UI,14,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1',
             '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    def event(layer,begin,end,text):
        if end <= begin: return
        lines.append(f'Dialogue: {layer},{ass_time(begin)},{ass_time(end)},Default,,0,0,0,,{text}')
    def box(k, color):
        px,py=x+k['x']*scale,y+k['y']*scale
        w,h=k['w']*scale,k['h']*scale
        # Subpixel rectangles are identical in the SVG and ASS coordinate spaces.
        return (r'{\an7\pos(' + f'{px:.2f},{py:.2f}' + r')\bord0\shad0\alpha&H'+alpha+
                r'&\1c&H'+color+r'&\p1}m 0 0 l '+f'{w:.2f} 0 {w:.2f} {h:.2f} 0 {h:.2f}'+r'{\p0}')
    codes = {k['code']:k for k in layout['keys']}
    for k in layout['keys']:
        event(0,0,duration,box(k,'312820'))
        px=x+(k['x']+k['w']/2)*scale;py=y+(k['y']+k['h']/2)*scale
        label = k['label'].replace('\\', r'\u005c').replace('{','').replace('}','')
        event(2,0,duration,r'{\an5\pos('+f'{px:.2f},{py:.2f}'+r')\fs'+f'{max(5,12*scale):.2f}'+r'\alpha&H'+alpha+r'&\bord0\shad0}'+label)
    held = {}
    for t,code,down in input_capture.cut(data['events'],start,duration):
        if code not in codes: continue
        if down: held.setdefault(code,t)
        elif code in held:
            event(1,held.pop(code),t,box(codes[code],'A07B24'))
    for code,t in held.items(): event(1,t,duration,box(codes[code],'A07B24'))
    Path(path).write_text('\n'.join(lines)+'\n',encoding='utf-8-sig')
    return ass_filter(path)
