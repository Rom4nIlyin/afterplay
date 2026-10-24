"""Bounded, silent animated GIF exports with a per-clip optimized palette."""
import math
import os
from pathlib import Path
import subprocess
import uuid


def validate_duration(value):
    value = float(value)
    if not math.isfinite(value) or not 2 <= value <= 15:
        raise ValueError('Для GIF выберите отрезок от 2 до 15 секунд')
    return value


def encode(suite, source, target, start, duration, job, width=720):
    duration = validate_duration(duration)
    if width not in (480, 720, 960):
        raise ValueError('Ширина GIF: 480, 720 или 960 пикселей')
    target = Path(target)
    partial = target.with_name(target.stem + '-' + uuid.uuid4().hex[:6] + '.partial.gif')
    # Scale before splitting so the palette pass only buffers bounded small frames.
    transport = Path(source).suffix.lower() == '.ts'
    # Rolling TS packets can have a nonzero clock and no seek index. Decode the
    # bounded selected segments and trim on their normalized presentation clock.
    trim_start = start if transport else 0
    graph = (f"[0:v]setpts=PTS-STARTPTS,trim=start={trim_start:.6f}:duration={duration:.6f},setpts=PTS-STARTPTS,"
             f"fps=15,scale=w='min({width},iw)':h=-2:flags=lanczos,setsar=1,split[a][b];"
             '[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=sierra2_4a[v]')
    seek = [] if transport else ['-ss', f'{start:.6f}', '-t', f'{duration:.6f}']
    command = [suite.ff(), '-hide_banner', '-loglevel', 'error', *seek,
               '-i', str(source), '-filter_complex', graph,
               '-map', '[v]', '-an', '-loop', '0', '-progress', 'pipe:1', '-nostats', '-y', str(partial)]
    log = suite.data/'logs'/('gif-' + uuid.uuid4().hex[:12] + '.log')
    proc = None
    try:
        with log.open('wb') as errors:
            proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=errors, creationflags=0x08000000 if os.name == 'nt' else 0)
            with suite.lock:
                suite.children.add(proc)
            for line in iter(proc.stdout.readline, b''):
                if line.startswith(b'out_time_us='):
                    try:
                        elapsed = int(line.strip().split(b'=')[1])/1000000
                        job.update(progress=min(95, int(elapsed/duration*95)), message='Создание GIF · без звука')
                    except ValueError:
                        pass
            proc.wait()
        if proc.returncode or not partial.is_file() or partial.stat().st_size < 1000:
            raise ValueError('Не удалось создать GIF. Подробности в data/logs. '+log.read_text('utf-8',errors='replace')[-700:])
        info = suite.probe(partial)
        if abs(info['duration']-duration) > .15 or info['audio'] or info['width'] > width:
            suite.log('gif_validation_failed', expected_duration=duration, expected_width=width, actual=info)
            raise ValueError(f"GIF не прошла проверку: ожидалось {duration:.3f} с, получено {info['duration']:.3f} с; {info['width']} px")
        os.replace(partial, target)
        return {'path': str(target), 'format': 'gif', 'bytes': target.stat().st_size, **info}
    finally:
        if proc:
            with suite.lock:
                suite.children.discard(proc)
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            if proc.stdout:
                proc.stdout.close()
        partial.unlink(missing_ok=True)
