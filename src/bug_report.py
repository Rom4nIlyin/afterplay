"""Problem reports: the journal tail, cleaned of personal data, for copying or sending.

A report is built locally and shown to the user in full before anything leaves the
computer. Sending goes to a small proxy (tools/report-proxy) that holds the GitHub
token and files the report as an issue; the app itself never carries a token.
"""
import hashlib
import json
import os
import platform
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from version import VERSION

# The proxy from tools/report-proxy. Empty: copy only.
REPORT_ENDPOINT = 'https://afterplay-reports.report-proxy.workers.dev/report'
# Not a secret: it only lets the proxy drop requests that did not come from AFTERPLAY.
APP_KEY = 'afterplay-report-v1'

MAX_EVENTS = 150
MAX_TRACE = 4000
MAX_REPORT = 48 * 1024
MAX_DESCRIPTION = 4000
TAIL_BYTES = 2 * 1024 ** 2
# Clip names, notes and tags are the user's own words, not diagnostics.
HIDDEN_KEYS = {'metadata', 'name', 'note', 'tags', 'title', 'clip_name', 'description', 'text', 'profile', 'profile_name'}


def endpoint(suite=None):
    value = os.environ.get('AFTERPLAY_REPORT_ENDPOINT') or ''
    if not value and suite is not None:
        value = ((suite.cfg.get('bug_report') or {}).get('endpoint') or '') if isinstance(suite.cfg.get('bug_report'), dict) else ''
    value = value or REPORT_ENDPOINT
    if not value:
        return ''
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != 'https' or parsed.username or parsed.password or not parsed.hostname:
        return ''
    return value


class Redactor:
    """Replaces paths, names and secrets that identify the user or their computer."""

    def __init__(self, suite=None, root=None, extra=()):
        pairs = []
        def add(value, label):
            value = str(value or '').rstrip('\\/')
            if len(value) >= 3:
                pairs.append((value, label))
        if root:
            add(root, '<AFTERPLAY>')
        if suite is not None:
            add(getattr(suite, 'data', ''), '<AFTERPLAY>\\data')
            try:
                add(suite.recordings_dir(), '<videos>')
            except Exception:
                pass
            for folder in (suite.cfg.get('video_roots') or []):
                add(folder, '<videos>')
        for folder in extra:
            add(folder, '<videos>')
        for name in ('USERPROFILE', 'HOME', 'OneDrive', 'LOCALAPPDATA', 'APPDATA', 'TEMP'):
            add(os.environ.get(name), {'LOCALAPPDATA': '<home>\\AppData\\Local', 'APPDATA': '<home>\\AppData\\Roaming', 'TEMP': '<temp>'}.get(name, '<home>'))
        add(str(Path.home()), '<home>')
        # Longest first, so a folder inside the home folder keeps its specific label.
        self.pairs = sorted(dict(pairs).items(), key=lambda pair: -len(pair[0]))
        # Longest first: a user "roman" must not cut the computer name "ROMAN-PC" in half.
        self.words = sorted({w for w in (os.environ.get('USERNAME', ''), os.environ.get('COMPUTERNAME', '')) if len(w) >= 3}, key=len, reverse=True)

    def text(self, value):
        value = str(value)
        for raw, label in self.pairs:
            for variant in {raw, raw.replace('\\', '/')}:
                value = re.sub(re.escape(variant), lambda _m, label=label: label, value, flags=re.I)
        # Any other absolute path: keep the extension, drop folders and the file name.
        # A value that is a path as a whole: the file name may contain spaces too.
        whole = re.fullmatch(r'(<(?:videos|home|temp)>|<AFTERPLAY>\\data|[A-Za-z]:|\\\\[^\\/\s]+)([\\/][^\r\n"<>|*?]*)?', value)
        if whole:
            label = whole.group(1) if whole.group(1).startswith('<') else '<path>'
            return label + (_hide_path(whole.group(2))[len('<path>'):] if whole.group(2) else '')
        # Folders may contain spaces ("Program Files (x86)\"), the last segment may not.
        value = re.sub(r'(?<![<\w])(?:[A-Za-z]:|\\\\[^\\\s"\']+)[\\/](?:[^\\/:*?"<>|\r\n]+[\\/])*[^\\/:*?"<>|\r\n\s,;)]*',
                       lambda m: _hide_path(m.group(0)), value)
        # Inside the user's folders the names themselves are personal (game, clip, project).
        value = re.sub(r'(<(?:videos|home|temp)>|<AFTERPLAY>\\data)([\\/](?:[^\\/:*?"<>|\r\n]+[\\/])*[^\\/:*?"<>|\r\n\s,;)]*)',
                       lambda m: m.group(1) + _hide_path(m.group(2))[len('<path>'):], value)
        value = re.sub(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+', '<email>', value)
        value = re.sub(r'(127\.0\.0\.1:\d+/)[A-Za-z0-9_-]{16,}', r'\1<token>', value)
        value = re.sub(r'\b(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{16,}', '<secret>', value)
        for word in self.words:
            value = re.sub(r'(?<![\w])' + re.escape(word) + r'(?![\w])', '<user>', value, flags=re.I)
        return value

    def value(self, value, key=''):
        # Window titles can carry a browser tab or a chat name.
        if (key in HIDDEN_KEYS or key.endswith('_title')) and value not in (None, '', [], {}):
            return '<hidden>'
        if isinstance(value, dict):
            return {k: self.value(v, k) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.value(v) for v in value]
        if isinstance(value, str):
            return self.text(value)
        return value


def _hide_path(path):
    suffix = Path(path.rstrip('\\/')).suffix
    # Program modules in a traceback are diagnostics, not personal names.
    if suffix.lower() in ('.py', '.pyw', '.pyd', '.dll'):
        return '<path>\\' + re.split(r'[\\/]', path.rstrip('\\/'))[-1]
    return '<path>' + ('\\<file>' + suffix if re.fullmatch(r'\.[A-Za-z0-9]{1,5}', suffix or '') else '')


def tail_lines(path, limit=TAIL_BYTES):
    try:
        with open(path, 'rb') as stream:
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(max(0, size - limit))
            data = stream.read()
    except OSError:
        return []
    lines = data.decode('utf-8', 'replace').splitlines()
    return lines[1:] if size > limit else lines


def journal(data, count=MAX_EVENTS, errors_only=False):
    data = Path(data)
    entries = []
    for name in ('journal.previous.jsonl', 'journal.jsonl'):
        for line in tail_lines(data / name):
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if isinstance(entry, dict):
                entries.append(entry)
    if errors_only:
        entries = [e for e in entries if is_error(e)]
    return entries[-count:]


def is_error(entry):
    event = str(entry.get('event', ''))
    # A report that failed to send is not the problem being reported.
    if entry.get('job') == 'Отправка отчёта' or event.startswith('bug_report_'):
        return False
    return bool(entry.get('trace') or entry.get('error')) or 'error' in event or 'failed' in event


def fingerprint(entries):
    """The same failure from different users groups under one issue."""
    for entry in reversed(entries):
        trace = str(entry.get('trace') or '')
        if not trace or not is_error(entry):
            continue
        frames = re.findall(r'File "([^"]+)", line \d+, in (\S+)', trace)
        lines = [line for line in trace.strip().splitlines() if line and not line.startswith(' ')]
        kind = lines[-1].split(':', 1)[0] if lines else ''
        where = '/'.join(Path(f.replace('\\', '/')).name + ':' + fn for f, fn in frames[-2:])
        seed = f'{entry.get("event")}|{kind}|{where}'
        return hashlib.sha1(seed.encode('utf-8')).hexdigest()[:12], f'{kind} в {where}'.strip()
    return '', ''


def system_info(suite=None):
    info = {
        'AFTERPLAY': VERSION,
        'Windows': platform.platform(),
        'Python': platform.python_version() + (' (portable)' if getattr(sys, 'frozen', False) or 'runtime' in sys.executable.lower() else ''),
    }
    if suite is not None:
        info['Язык'] = suite.cfg.get('language') or 'ru'
    return info


def build(suite, root=None, count=MAX_EVENTS, errors_only=False):
    redactor = Redactor(suite, root)
    entries = [redactor.value(e) for e in journal(suite.data, count, errors_only)]
    for entry in entries:
        if isinstance(entry.get('trace'), str) and len(entry['trace']) > MAX_TRACE:
            entry['trace'] = '…' + entry['trace'][-MAX_TRACE:]
    fp, summary = fingerprint(entries)
    errors = [e for e in entries if is_error(e)]
    info = system_info(suite)
    logs = {}
    for name in ('startup-error.log', 'host.log', 'ui-startup.json'):
        lines = tail_lines(Path(suite.data) / 'logs' / name, 3000)
        if lines:
            logs[name] = redactor.text('\n'.join(lines))
    head = ['AFTERPLAY — отчёт о проблеме', *[f'{k}: {v}' for k, v in info.items()],
            f'Событий: {len(entries)}, из них ошибок: {len(errors)}']
    if fp:
        head.append(f'Отпечаток: {fp} ({summary})')
    body = [json.dumps(e, ensure_ascii=False, default=str) for e in entries]
    text = '\n'.join(head) + '\n\n--- Журнал ---\n' + '\n'.join(body)
    for name, content in logs.items():
        text += f'\n\n--- {name} ---\n' + content
    if len(text.encode('utf-8')) > MAX_REPORT:
        # Keep the header and the newest events: the cause is usually at the end.
        while body and len(('\n'.join(head) + '\n'.join(body)).encode('utf-8')) > MAX_REPORT - 2000:
            body.pop(0)
        text = '\n'.join(head) + '\n\n--- Журнал (начало обрезано) ---\n' + '\n'.join(body)
    last_error = next((str(e.get('error') or e.get('event')) for e in reversed(errors)), '')
    return {'text': text, 'fingerprint': fp, 'summary': summary, 'events': len(entries),
            'errors': len(errors), 'last_error': last_error[:200], 'system': info,
            'can_send': bool(endpoint(suite))}


def title_for(report, description):
    first = (description or '').strip().splitlines()[0][:80] if (description or '').strip() else ''
    return first or (report.get('last_error') or 'Отчёт без ошибки')[:80]


def send(suite, description='', root=None, opener=None):
    url = endpoint(suite)
    if not url:
        raise ValueError('Отправка отчётов ещё не настроена. Скопируйте отчёт и пришлите его разработчику.')
    report = build(suite, root)
    description = Redactor(suite, root).text(str(description or '')[:MAX_DESCRIPTION])
    payload = {'version': VERSION, 'fingerprint': report['fingerprint'], 'summary': report['summary'],
               'title': title_for(report, description), 'description': description, 'report': report['text']}
    request = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), method='POST',
                                     headers={'Content-Type': 'application/json; charset=utf-8',
                                              'User-Agent': f'AFTERPLAY/{VERSION}', 'X-AfterPlay-Key': APP_KEY})
    if opener is None:
        try:
            import truststore
            context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        except ImportError:
            context = ssl.create_default_context()
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context)).open
    try:
        with opener(request, timeout=30) as response:
            result = json.loads(response.read(64 * 1024) or b'{}')
    except urllib.error.HTTPError as error:
        try:
            message = json.loads(error.read(4096)).get('error', '')
        except Exception:
            message = ''
        if error.code == 429:
            raise ValueError('Слишком много отчётов подряд. Попробуйте через минуту.') from None
        suite.log('bug_report_failed', status=error.code, error=message[:300])
        raise ValueError('Сервер отчётов ответил ошибкой ' + str(error.code)) from None
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise ValueError('Не удалось связаться с сервером отчётов. Проверьте интернет или скопируйте отчёт.') from error
    if not result.get('ok'):
        raise ValueError(result.get('error') or 'Сервер отчётов не принял отчёт')
    suite.log('bug_report_sent', issue=result.get('number'), fingerprint=report['fingerprint'], duplicate=bool(result.get('duplicate')))
    return {'url': result.get('url', ''), 'number': result.get('number'), 'duplicate': bool(result.get('duplicate'))}
