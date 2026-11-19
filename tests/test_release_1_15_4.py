"""1.15.4: library sync for files changed outside the app, quiet local server, UI prefs, mic status."""
import json
import os
from pathlib import Path
import socket
import struct
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from app import Suite, server_for
import quick_clips


def touch_video(path, size=4096, age=120):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(os.urandom(size))
    old = time.time() - age
    os.utime(path, (old, old))


class LibrarySyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); root = Path(self.temp.name)
        self.videos = root / 'videos'; self.records = root / 'records'; self.videos.mkdir(); self.records.mkdir()
        self.suite = Suite(str(root / 'data'))
        self.suite.cfg['video_roots'] = [str(self.videos)]
        self.suite.cfg['storage'] = {'recordings_dir': str(self.records), 'previous_dirs': []}
        info = {'duration': 3.0, 'width': 320, 'height': 180, 'audio': 0}
        self.thumbs = patch.object(Suite, '_index_thumbnail', return_value=info); self.thumbs.start()

    def tearDown(self):
        self.thumbs.stop(); self.temp.cleanup()

    def rows(self):
        with self.suite.db() as db:
            return {r['path']: dict(r) for r in db.execute('SELECT id,path,name,favorite,marks FROM clips')}

    def test_rename_and_move_keep_the_row_and_its_notes(self):
        a = self.videos / 'Катка.mp4'; touch_video(a)
        r = self.records / 'Повтор-2026-11-18_10-00-00-aaaa.mp4'; touch_video(r, 5000)
        self.assertEqual(self.suite.sync_library(), 2)
        row = self.rows()[str(a)]
        with self.suite.db() as db:
            db.execute('UPDATE clips SET favorite=1, marks=? WHERE id=?', ('[1.5]', row['id']))
        moved = self.videos / 'Папка' / 'Финал.mp4'; moved.parent.mkdir(); os.rename(a, moved)
        renamed = self.records / 'Мой повтор.mp4'; os.rename(r, renamed)
        self.suite.sync_library(); self.suite.prune_missing()
        rows = self.rows()
        self.assertEqual(set(rows), {str(moved), str(renamed)})
        self.assertEqual(rows[str(moved)]['id'], row['id'])
        self.assertEqual((rows[str(moved)]['name'], rows[str(moved)]['favorite'], rows[str(moved)]['marks']), ('Финал.mp4', 1, '[1.5]'))

    def test_file_still_being_written_waits_and_deleted_file_is_pruned(self):
        fresh = self.videos / 'Пишется.mp4'; touch_video(fresh, age=0)
        self.suite.sync_library(); self.assertNotIn(str(fresh), self.rows())
        old = time.time() - 120; os.utime(fresh, (old, old))
        self.suite.sync_library(); self.assertIn(str(fresh), self.rows())
        fresh.unlink(); self.suite.sync_library(); self.suite.prune_missing()
        self.assertNotIn(str(fresh), self.rows())

    def test_idle_pass_does_nothing(self):
        touch_video(self.videos / 'a.mp4'); self.suite.sync_library()
        self.assertEqual(self.suite.sync_library(), 0)


class VisibleWindowSyncTests(unittest.TestCase):
    def test_folders_are_scanned_only_while_the_window_is_visible(self):
        # 1.15.5: in the tray or minimized the UI polls with visible=False and no scan starts.
        with tempfile.TemporaryDirectory() as temp:
            suite = Suite(temp)
            with patch.object(suite, 'prune_missing_soon') as scan:
                suite.dispatch('state', {'visible': False}); scan.assert_not_called()
                suite.dispatch('state', {'visible': True}); scan.assert_called_once()
                suite.dispatch('state', {}); self.assertEqual(scan.call_count, 2)


class QuietServerTests(unittest.TestCase):
    def test_client_that_drops_the_connection_leaves_no_traceback(self):
        with tempfile.TemporaryDirectory() as temp:
            suite = Suite(temp); server, token = server_for(suite)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                with patch('sys.stderr') as stderr:
                    for _ in range(5):
                        s = socket.create_connection(server.server_address)
                        s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
                        s.sendall(f'GET /{token}/index.html HTTP/1.1\r\nHost: x\r\n'.encode()); time.sleep(.05); s.close()
                    time.sleep(.5)
                    written = ''.join(str(c.args[0]) for c in stderr.write.call_args_list if c.args)
                self.assertNotIn('Traceback', written)
            finally:
                server.shutdown(); server.server_close()


class UiPrefsTests(unittest.TestCase):
    def test_volume_and_export_quality_are_validated_and_saved(self):
        with tempfile.TemporaryDirectory() as temp:
            suite = Suite(temp)
            self.assertEqual(suite.dispatch('ui_prefs', {'volume': .35, 'export_quality': {'discord': '60'}}),
                             {'volume': .35, 'export_quality': {'discord': '60'}})
            for bad in ({'volume': 5}, {'volume': True}, {'export_quality': 'x'}, {'export_quality': {'a': 1}}):
                with self.assertRaises(ValueError): suite.dispatch('ui_prefs', bad)
            saved = json.loads(Path(temp, 'settings.json').read_text('utf-8'))
            self.assertEqual(saved['ui_prefs'], {'volume': .35, 'export_quality': {'discord': '60'}})


class CoreShortcutTests(unittest.TestCase):
    def test_record_and_mark_suggested_once_without_overriding_choices(self):
        fresh = {}; quick_clips.migrate(fresh)
        self.assertEqual((fresh['hotkeys']['record'], fresh['hotkeys']['mark']), ('Ctrl+Alt+F9', 'Ctrl+Alt+F11'))
        cleared = {'hotkeys': {'record': ''}}; quick_clips.migrate(cleared)
        self.assertEqual(cleared['hotkeys']['record'], '')
        taken = {'hotkeys': {'save': 'Ctrl+Alt+F9'}}; quick_clips.migrate(taken)
        self.assertNotIn('record', taken['hotkeys'])
        done = {'core_keys_version': 1, 'hotkeys': {}}; quick_clips.migrate(done)
        self.assertNotIn('record', done['hotkeys'])


class MicrophoneStatusTests(unittest.TestCase):
    def test_state_reports_whether_the_microphone_is_really_connected(self):
        from replay import Replay
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as temp:
            rec = Replay(Suite(temp))
            rec.settings['microphone_enabled'] = False
            self.assertEqual(rec._microphone_status(), {'enabled': False})
            rec.settings['microphone_enabled'] = True
            capture = SimpleNamespace(last_state=('waiting', 'Микрофон не найден'), error='Микрофон не найден')
            rec._optional_audio = [{'optional': 'microphone', '_capture': capture}]
            self.assertEqual(rec._microphone_status(), {'enabled': True, 'connected': False, 'error': 'Микрофон не найден', 'muted': False})
            capture.last_state = ('connected', ''); capture.error = ''
            self.assertTrue(rec._microphone_status()['connected'])


if __name__ == '__main__':
    unittest.main()
