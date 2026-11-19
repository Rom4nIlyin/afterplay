import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

import bug_report


class FakeSuite:
    def __init__(self, data, videos):
        self.data = Path(data)
        self.cfg = {'video_roots': [videos], 'language': 'ru'}
        self.videos = videos
        self.logged = []

    def recordings_dir(self):
        return self.videos

    def log(self, event, **detail):
        self.logged.append((event, detail))


TRACE = ('Traceback (most recent call last):\n'
         '  File "{root}\\app\\replay.py", line 837, in begin_replay\n'
         '    return self.start()\n'
         '  File "{root}\\app\\replay.py", line 419, in start\n'
         '    raise ValueError("no window")\n'
         'ValueError: no window\n')


class BugReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, 'AFTERPLAY Portable')
        self.data = os.path.join(self.root, 'data')
        os.makedirs(self.data)
        self.videos = r'D:\Видео\Captures'
        self.suite = FakeSuite(self.data, self.videos)
        events = [
            {'at': '1', 'event': 'replay_start', 'settings': {'game_path': r'C:\Program Files (x86)\Steam\steamapps\common\Secret Game\game.exe',
                                                          'window_title': 'Secret Game — chat with friend'}},
            {'at': '2', 'event': 'video_deleted_permanently', 'path': self.videos + r'\my private clip.gif',
             'metadata': {'name': 'my private clip.gif', 'note': 'birthday'}},
            {'at': '3', 'event': 'manual_screen_fallback', 'profile': 'Secret Game'},
            {'at': '4', 'event': 'error', 'job': 'Включение повтора', 'error': 'no window',
             'trace': TRACE.format(root=self.root)},
            {'at': '5', 'event': 'note', 'url': 'http://127.0.0.1:5555/abcdefghijklmnopqrstuvwxyz0123/api', 'mail': 'me@example.com'},
        ]
        with open(os.path.join(self.data, 'journal.jsonl'), 'w', encoding='utf-8') as f:
            for e in events:
                f.write(json.dumps(e, ensure_ascii=False) + '\n')

    def tearDown(self):
        self.tmp.cleanup()

    def build(self):
        with mock.patch.dict(os.environ, {'USERNAME': 'roman', 'COMPUTERNAME': 'ROMAN-PC'}):
            return bug_report.build(self.suite, self.root)

    def test_report_keeps_diagnostics_and_drops_personal_data(self):
        report = self.build()
        text = report['text']
        for secret in ('Secret Game', 'my private clip', 'birthday', 'Видео', 'Steam', 'me@example.com',
                       'abcdefghijklmnopqrstuvwxyz0123', self.tmp.name):
            self.assertNotIn(secret, text)
        # Journal lines are JSON, so backslashes appear escaped.
        self.assertIn(r'<AFTERPLAY>\\app\\replay.py', text)
        self.assertIn(r'"<videos>\\<file>.gif"', text)
        self.assertIn(r'"<path>\\<file>.exe"', text)
        self.assertNotIn('private', text)
        self.assertIn('ValueError: no window', text)
        self.assertEqual(report['errors'], 1)
        self.assertRegex(report['fingerprint'], r'^[0-9a-f]{12}$')
        self.assertIn('replay.py:start', report['summary'])

    def test_fingerprint_ignores_install_folder_and_line_numbers(self):
        a = bug_report.fingerprint([{'event': 'error', 'trace': TRACE.format(root=r'C:\A')}])
        b = bug_report.fingerprint([{'event': 'error', 'trace': TRACE.format(root=r'E:\B').replace('line 419', 'line 500')}])
        self.assertEqual(a, b)

    def test_failed_report_send_is_not_the_reported_error(self):
        own = {'event': 'error', 'job': 'Отправка отчёта', 'error': 'offline',
               'trace': 'Traceback\n  File "x\\bug_report.py", line 1, in send\nValueError: offline\n'}
        with open(os.path.join(self.data, 'journal.jsonl'), 'a', encoding='utf-8') as f:
            f.write(json.dumps(own, ensure_ascii=False) + '\n')
        report = self.build()
        self.assertEqual(report['last_error'], 'no window')
        self.assertIn('replay.py:start', report['summary'])

    def test_user_name_is_replaced_as_whole_word(self):
        with mock.patch.dict(os.environ, {'USERNAME': 'roman', 'COMPUTERNAME': 'ROMAN-PC'}):
            r = bug_report.Redactor()
            self.assertEqual(r.text('user roman on ROMAN-PC, romantic'), 'user <user> on <user>, romantic')

    def test_large_journal_is_trimmed_from_the_start(self):
        with open(os.path.join(self.data, 'journal.jsonl'), 'a', encoding='utf-8') as f:
            for i in range(140):
                f.write(json.dumps({'at': str(i), 'event': 'filler', 'detail': 'x' * 600}) + '\n')
        report = self.build()
        self.assertLessEqual(len(report['text'].encode('utf-8')), bug_report.MAX_REPORT)
        self.assertIn('"at": "139"', report['text'])

    def test_send_requires_configured_endpoint(self):
        with mock.patch.object(bug_report, 'REPORT_ENDPOINT', ''), mock.patch.dict(os.environ, {'AFTERPLAY_REPORT_ENDPOINT': ''}):
            self.assertFalse(self.build()['can_send'])
            with self.assertRaisesRegex(ValueError, 'не настроена'):
                bug_report.send(self.suite, 'x', self.root)

    def test_endpoint_must_be_https(self):
        with mock.patch.dict(os.environ, {'AFTERPLAY_REPORT_ENDPOINT': 'http://example.com/report'}):
            self.assertEqual(bug_report.endpoint(), '')

    def test_send_posts_redacted_report(self):
        sent = {}
        class Response(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): return False
        def opener(request, timeout):
            sent['url'] = request.full_url
            sent['headers'] = dict(request.header_items())
            sent['body'] = json.loads(request.data)
            return Response(json.dumps({'ok': True, 'number': 42, 'url': 'https://github.com/x/y/issues/42'}).encode())
        with mock.patch.dict(os.environ, {'AFTERPLAY_REPORT_ENDPOINT': 'https://reports.example.workers.dev/report',
                                          'USERNAME': 'roman', 'COMPUTERNAME': 'ROMAN-PC'}):
            result = bug_report.send(self.suite, 'roman: crashed in ' + self.videos + r'\game clip.mp4', self.root, opener=opener)
        self.assertEqual(result['number'], 42)
        self.assertEqual(sent['url'], 'https://reports.example.workers.dev/report')
        self.assertEqual(sent['headers'].get('X-afterplay-key'), bug_report.APP_KEY)
        self.assertNotIn('roman', sent['body']['description'])
        self.assertNotIn('game clip', sent['body']['description'])
        self.assertNotIn('Secret Game', sent['body']['report'])
        self.assertEqual(self.suite.logged[-1][0], 'bug_report_sent')

    def test_send_explains_rate_limit(self):
        def opener(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 429, 'Too Many', {}, io.BytesIO(b'{}'))
        with mock.patch.dict(os.environ, {'AFTERPLAY_REPORT_ENDPOINT': 'https://r.example.dev/report'}):
            with self.assertRaisesRegex(ValueError, 'Слишком много'):
                bug_report.send(self.suite, '', self.root, opener=opener)


if __name__ == '__main__':
    unittest.main()
