from types import SimpleNamespace
from unittest.mock import Mock,patch
import unittest
from desktop import Desktop

class MinimizeTests(unittest.TestCase):
    def desktop(self,choice='tray',window_state='Minimized'):
        desktop=Desktop.__new__(Desktop);desktop.mode='clips';desktop.exiting=False
        native=Mock();native.Visible=True;native.WindowState=window_state
        desktop.suite=SimpleNamespace(window=Mock(native=native),cfg={'desktop':{'clips':{'close_action':choice}}})
        return desktop
    def test_minimize_keeps_native_window_visible_for_both_close_settings(self):
        for choice in ('tray','close'):
            desktop=self.desktop(choice)
            with patch('desktop.threading.Thread') as thread:
                desktop._visibility_changed();thread.call_args.kwargs['target']()
            desktop.suite.window.native.Hide.assert_not_called()
            desktop.suite.window.evaluate_js.assert_called_once_with('window.customNativeHidden=true;window.customUpdatePause?.()')
    def test_restore_resumes_rendering_and_close_still_uses_tray(self):
        desktop=self.desktop(window_state='Normal')
        with patch('desktop.threading.Thread') as thread:
            desktop._visibility_changed();thread.call_args.kwargs['target']()
        desktop.suite.window.evaluate_js.assert_called_once_with('window.customNativeHidden=false;window.customUpdatePause?.()')
        self.assertFalse(desktop.closing());desktop.suite.window.hide.assert_called_once()
        desktop=self.desktop('close');self.assertTrue(desktop.closing());desktop.suite.window.hide.assert_not_called()

if __name__=='__main__':unittest.main()
