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
    def test_gdi_window_uses_its_handle_instead_of_a_screen_crop(self):
        from PIL import Image
        from capture_media import GdiVideoSource
        with patch('PIL.ImageGrab.grab',return_value=Image.new('RGB',(4,2))) as grabbed:
            source=GdiVideoSource(hwnd=123,fps=1)
            try:self.assertEqual(grabbed.call_args.kwargs,{'window':123})
            finally:source.stop()
    def test_old_windows_10_uses_gdi_without_importing_wgc(self):
        for build in (10240,10586,14393,15063,16299,17134,17763):
            with self.subTest(build=build),patch('process_audio.windows_version',return_value=(10,0,build)),patch('capture_media.VideoSource') as modern,patch('capture_media.GdiVideoSource') as legacy:
                source,name=create_video_source(hwnd=123,monitor={},fps=30)
                modern.assert_not_called();legacy.assert_called_once()
                self.assertIs(source,legacy.return_value);self.assertIn('GDI',name)
    def test_modern_windows_10_and_11_keep_wgc_and_fall_back_if_unavailable(self):
        for build in (18362,19045,22000,22631,26100):
            with self.subTest(build=build),patch('process_audio.windows_version',return_value=(10,0,build)),patch('capture_media.VideoSource') as modern,patch('capture_media.GdiVideoSource') as legacy:
                source,name=create_video_source(hwnd=123,monitor={},fps=60)
                self.assertIs(source,modern.return_value);legacy.assert_not_called()
                modern.side_effect=OSError('API not available')
                source,name=create_video_source(hwnd=123,monitor={},fps=60)
                self.assertIs(source,legacy.return_value)
