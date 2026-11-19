import unittest
from unittest.mock import patch,Mock
from capture_media import create_video_source

class WindowsCompatibilityTests(unittest.TestCase):
    def test_gdi_preserves_negative_monitor_coordinates_and_bgra_frames(self):
        from PIL import Image
        from capture_media import GdiVideoSource
        with patch('PIL.ImageGrab.grab',return_value=Image.new('RGB',(4,2),(10,20,30))) as grabbed:
            source=GdiVideoSource(monitor={'x':-1200,'y':25,'width':1200,'height':800},fps=1)
            try:
                self.assertEqual(grabbed.call_args.kwargs['bbox'],(-1200,25,0,825))
                self.assertEqual(source.first[1][0,0].tolist(),[30,20,10,255])
                self.assertGreater(source.first[0],0)
            finally:source.stop()
    def test_gdi_window_reads_live_desktop_at_its_client_area(self):
        # The window's own DC freezes on the first frame for DirectX games.
        from PIL import Image
        from capture_media import GdiVideoSource
        with patch('capture_media.window_screen_rect',return_value=(-800,40,-400,240)) as rect,              patch('PIL.ImageGrab.grab',return_value=Image.new('RGB',(400,200))) as grabbed:
            source=GdiVideoSource(hwnd=123,fps=1)
            try:
                self.assertEqual(grabbed.call_args.kwargs,{'bbox':(-800,40,-400,240),'all_screens':True})
                rect.assert_called_with(123)
                self.assertEqual((source.width,source.height),(400,200))
            finally:source.stop()
    def test_window_screen_rect_follows_a_real_window(self):
        import ctypes
        from capture_media import window_screen_rect
        hwnd=ctypes.windll.user32.GetDesktopWindow()
        left,top,right,bottom=window_screen_rect(hwnd)
        self.assertGreater(right-left,100);self.assertGreater(bottom-top,100)
        with self.assertRaises(RuntimeError):window_screen_rect(0x7FFFFFF0)
    def test_old_windows_10_uses_gdi_without_importing_wgc(self):
        for build in (10240,10586,14393,15063,16299,17134,17763):
            with self.subTest(build=build),patch('process_audio.windows_version',return_value=(10,0,build)),patch('capture_media.VideoSource') as modern,patch('capture_media.GdiVideoSource') as legacy:
                source,name=create_video_source(hwnd=123,monitor={},fps=30)
                modern.assert_not_called();legacy.assert_called_once()
                self.assertIs(source,legacy.return_value);self.assertIn('GDI',name)
    def test_windows_10_window_and_monitor_capture_never_start_wgc(self):
        for build in (18362,19045):
            with self.subTest(build=build),patch('process_audio.windows_version',return_value=(10,0,build)),patch('capture_media.VideoSource') as modern,patch('capture_media.GdiVideoSource') as legacy:
                source,name=create_video_source(hwnd=123,monitor={},fps=60)
                self.assertIs(source,legacy.return_value);self.assertIn('GDI',name)
                source,name=create_video_source(monitor={'wgc_index':1},fps=60)
                self.assertIs(source,legacy.return_value);self.assertIn('GDI',name)
                modern.assert_not_called()
                self.assertEqual(legacy.call_count,2)

    def test_windows_11_uses_wgc_and_falls_back_if_unavailable(self):
        for build in (22000,22631,26100):
            with self.subTest(build=build),patch('process_audio.windows_version',return_value=(10,0,build)),patch('capture_media.VideoSource') as modern,patch('capture_media.GdiVideoSource') as legacy:
                source,name=create_video_source(hwnd=123,monitor={},fps=60)
                self.assertIs(source,modern.return_value);legacy.assert_not_called()
                modern.side_effect=OSError('API not available')
                source,name=create_video_source(hwnd=123,monitor={},fps=60)
                self.assertIs(source,legacy.return_value)
