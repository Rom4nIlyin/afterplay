from types import SimpleNamespace
from unittest.mock import Mock,patch
import tempfile,unittest
import os,subprocess
from pathlib import Path
from app import Suite
from window_chrome import WindowChrome

class WindowChromeTests(unittest.TestCase):
    @unittest.skipUnless(os.name=='nt','Windows native frame')
    def test_native_frame_operations_preserve_work_area_and_closing_event(self):
        root=Path(__file__).resolve().parents[1]
        compiler=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        with tempfile.TemporaryDirectory() as d:
            dll=Path(d)/'ReplayNotification.dll';probe=Path(d)/'ChromeProbe.exe'
            common=[str(compiler),'/nologo','/platform:x64','/r:System.Windows.Forms.dll','/r:System.Drawing.dll']
            for args in ([*common,'/target:library','/out:'+str(dll),str(root/'ReplayNotification.cs')],[*common,'/target:exe','/r:'+str(dll),'/out:'+str(probe),str(root/'tests/WindowChromeProbe.cs')]):
                result=subprocess.run(args,capture_output=True,timeout=30)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            result=subprocess.run([str(probe)],capture_output=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    def test_browser_server_has_no_native_controls(self):
        with tempfile.TemporaryDirectory() as d:
            suite=Suite(d)
            self.assertFalse(suite.dispatch('window_state',{})['native'])
            self.assertFalse(suite.dispatch('window_chrome_config',{})['styled'])
            with self.assertRaises(ValueError):suite.dispatch('window_control',{'command':'close'})
    def test_close_uses_existing_window_closing_event_and_maximize_restores(self):
        window=Mock();window.native=SimpleNamespace(WindowState='Normal',Visible=True,ShowInTaskbar=True)
        chrome=WindowChrome(SimpleNamespace(window=window))
        chrome.control('maximize');window.maximize.assert_called_once()
        window.native.WindowState='Maximized';chrome.control('maximize');window.restore.assert_called_once()
        with patch('window_chrome.threading.Timer') as timer:
            chrome.control('close');self.assertIs(timer.call_args.args[1],window.destroy);timer.return_value.start.assert_called_once()
    def test_only_resolved_colors_reach_native_drawing(self):
        chrome=WindowChrome(SimpleNamespace(window=None))
        for colors in (None,{},dict.fromkeys(('background','panel','text','muted','accent'),'red')):
            with self.assertRaises(ValueError):chrome.configure(colors)
        self.assertFalse(chrome.configure(dict.fromkeys(('background','panel','text','muted','accent'),'#aabbcc'))['native'])

if __name__=='__main__':unittest.main()
