import copy
import ctypes
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from auto_record import AutoRecorder,validate as validate_auto,path_key
from hotkeys import GlobalHotkeys,parse,validate

class ShortcutsTests(unittest.TestCase):
    def test_editing_releases_and_restores_keys_and_new_binding(self):
        manager=GlobalHotkeys({'save':lambda:None,'mark':lambda:None,'window':lambda:None},lambda *a,**k:None)
        try:
            first={'save':'Ctrl+Alt+Shift+F21','mark':'Ctrl+Alt+Shift+F22','window':'Ctrl+Alt+Shift+F24'}
            manager.configure(first);manager.editing(True)
            self.assertEqual(manager.registered,{})
            manager.editing(False);self.assertEqual(set(manager.registered),set(first.values()))
            manager.editing(True)
            second={**first,'save':'Ctrl+Alt+Shift+F23'}
            manager.configure(second)
            self.assertEqual(set(manager.registered),set(second.values()))
            self.assertFalse(manager.edit_until)
        finally:manager.shutdown()

    def test_normalizes_and_rejects_unsafe_or_reserved_keys(self):
        self.assertEqual(parse('alt+control+f10')[0],'Ctrl+Alt+F10')
        self.assertEqual(parse('F8')[2],0x77)
        for bad in ('a','F','Alt+F12','Ctrl+Ctrl+A','Win+G','Ctrl+F25','Ctrl+','Ctrl+Escape'):
            with self.assertRaises(ValueError):parse(bad)
        with self.assertRaises(ValueError):validate({'save':'F8','mark':'F8'})

    def test_win32_registration_rebind_conflict_rollback_and_action_swap(self):
        hit=threading.Event();manager=GlobalHotkeys({'save':hit.set,'mark':lambda:None,'window':lambda:None},lambda *a,**k:None)
        reserved=False
        try:
            first={'save':'Ctrl+Alt+Shift+F18','mark':'Ctrl+Alt+Shift+F19','window':'Ctrl+Alt+Shift+F24'}
            manager.configure(first);before=dict(manager.registered)
            reserved=bool(ctypes.windll.user32.RegisterHotKey(None,992,0x4007,0x83)) # F20
            self.assertTrue(reserved)
            with self.assertRaises(ValueError):manager.configure({'save':'Ctrl+Alt+Shift+F20','mark':first['mark'],'window':first['window']})
            self.assertEqual(manager.registered,before)
            manager.configure({'save':first['mark'],'mark':first['save'],'window':first['window']})
            identifier=next(i for i,a in manager.actions.items() if a=='save')
            ctypes.windll.user32.PostThreadMessageW(manager.tid,0x0312,identifier,0)
            self.assertTrue(hit.wait(3))
            self.assertEqual(manager.registered,before)
        finally:
            manager.shutdown()
            if reserved:ctypes.windll.user32.UnregisterHotKey(None,992)

def window(pid=10,path=r'C:\Games\Example\game.exe',minimized=False):
    return {'path':path,'pid':pid,'hwnd':pid+100,'name':'game.exe','title':'Game',
            'width':1280,'height':720,'minimized':minimized}

class FakeReplay:
    def __init__(self):
        self.settings={'capture_mode':'monitor','audio_mode':'game','seconds':300}
        self.phase='off';self.saving=False;self.session=None;self.auto_owned=False
        self.start=Mock(side_effect=self._start);self.stop=Mock(side_effect=self._stop)
        self.save=Mock(return_value={'duration':5});self._cleanup_session=Mock()
    def configure(self,args):self.settings.update(args)
    def _start(self):self.phase='recording';self.session='session'
    def _stop(self,preserve=None):self.phase='off'

class AutoTests(unittest.TestCase):
    def setUp(self):
        self.rows=[];self.now=0;self.replay=FakeReplay()
        self.suite=SimpleNamespace(replay=self.replay,cfg={},save_cfg=Mock(),log=Mock(),desktop=None)
        self.auto=AutoRecorder(self.suite,lambda:self.rows,lambda:self.now)
        self.config={'enabled':True,'save_on_exit':True,'apps':[{'path':window()['path'],'name':'Example'}]}
    def start(self):
        self.auto.configure(self.config);self.rows=[window()]
        self.auto.tick();self.now+=3;self.auto.tick()
    def test_disabled_and_unlisted_windows_are_never_recorded(self):
        self.rows=[window()];self.auto.tick();self.now=10;self.auto.tick();self.replay.start.assert_not_called()
        self.auto.configure(self.config);self.rows=[window(path=r'C:\Other\game.exe')]
        self.auto.tick();self.now+=3;self.auto.tick();self.replay.start.assert_not_called()
    def test_starts_only_after_stable_visible_window_and_uses_live_handles(self):
        self.auto.configure(self.config);self.rows=[window(minimized=True)]
        self.auto.tick();self.now+=3;self.auto.tick();self.replay.start.assert_not_called()
        self.rows=[window(pid=87)];self.auto.tick();self.replay.start.assert_not_called()
        self.now+=3;self.auto.tick();self.replay.start.assert_called_once()
        self.assertEqual(self.replay.settings['window_hwnd'],187)
        self.assertEqual(self.replay.settings['game_pid'],87)
        self.assertTrue(self.replay.auto_owned)
    def test_close_saves_buffer_and_restores_manual_settings(self):
        original=copy.deepcopy(self.replay.settings);self.start();self.rows=[];self.auto.tick()
        self.replay.save.assert_called_once_with({'progress':0},allow_stopped=True)
        self.assertIsNone(self.auto.owner);self.assertEqual(self.replay.settings,original)
    def test_manual_stop_does_not_restart_until_process_has_exited(self):
        self.start();self.auto.manual('stop');self.now+=4;self.auto.tick();self.now+=4;self.auto.tick()
        self.assertEqual(self.replay.start.call_count,1)
        self.rows=[];self.auto.tick();self.rows=[window(pid=12)]
        self.auto.tick();self.now+=3;self.auto.tick();self.assertEqual(self.replay.start.call_count,2)
    def test_manual_recording_is_never_replaced(self):
        self.auto.configure(self.config);self.rows=[window()];self.replay.phase='recording'
        self.auto.tick();self.now+=3;self.auto.tick();self.replay.start.assert_not_called();self.replay.stop.assert_not_called()
    def test_disabling_finishes_automatic_session(self):
        self.start();self.auto.configure({**self.config,'enabled':False})
        self.replay.save.assert_called_once();self.assertIsNone(self.auto.owner)
    def test_errors_are_not_retried_every_second(self):
        self.replay.start.side_effect=ValueError('encoder unavailable');self.start()
        for _ in range(8):self.now+=3;self.auto.tick()
        self.assertEqual(self.replay.start.call_count,1);self.assertEqual(self.auto.error,'encoder unavailable')
    def test_allowlist_requires_executable_and_rejects_duplicate_paths(self):
        for bad in ('game.exe',r'C:\Games\game.bat'):
            with self.assertRaises(ValueError):validate_auto({'apps':[{'path':bad}]})
        with self.assertRaises(ValueError):validate_auto({'apps':[{'path':window()['path']},{'path':window()['path'].upper()}]})
        self.assertEqual(path_key(r'C:\Games\Example\..\game.exe'),path_key(r'c:\games\game.exe'))

if __name__=='__main__':unittest.main()
