import unittest
from unittest.mock import patch,Mock
from capture_media import create_video_source

class WindowsCompatibilityTests(unittest.TestCase):
    def test_gdi_preserves_negative_monitor_coordinates_and_bgra_frames(self):
        import numpy as np
        from capture_media import GdiVideoSource
        frame=np.full((800,1200,4),(30,20,10,255),dtype=np.uint8)
        with patch('capture_media.ScreenCopier.copy',return_value=frame) as copied:
            source=GdiVideoSource(monitor={'x':-1200,'y':25,'width':1200,'height':800},fps=1)
            try:
                copied.assert_called_with(-1200,25,0,825)
                self.assertEqual(source.first[1][0,0].tolist(),[30,20,10,255])
                self.assertGreater(source.first[0],0)
            finally:source.stop()
    def test_gdi_window_reads_live_desktop_at_its_client_area(self):
        # The window's own DC freezes on the first frame for DirectX games.
        import numpy as np
        from capture_media import GdiVideoSource
        with patch('capture_media.window_screen_rect',return_value=(-800,40,-400,240)) as rect,              patch('capture_media.ScreenCopier.copy',return_value=np.zeros((200,400,4),dtype=np.uint8)) as copied:
            source=GdiVideoSource(hwnd=123,fps=1)
            try:
                copied.assert_called_with(-800,40,-400,240)
                rect.assert_called_with(123)
                self.assertEqual((source.width,source.height),(400,200))
            finally:source.stop()
    def test_screen_copier_returns_opaque_bgra_of_the_area(self):
        from capture_media import ScreenCopier
        copier=ScreenCopier()
        try:
            frame=copier.copy(0,0,64,32)
            self.assertEqual(frame.shape,(32,64,4));self.assertTrue((frame[:,:,3]==255).all())
            self.assertEqual(copier.copy(0,0,40,20).shape,(20,40,4))
            with self.assertRaises(RuntimeError):copier.copy(5,5,5,5)
        finally:copier.release()
    def test_windows_10_desktop_duplication_crops_window_and_downloads_for_cpu_scaling(self):
        import gpu_capture
        region={'output':1,'x':40,'y':20,'width':1280,'height':720,'full':False}
        gpu=gpu_capture.desktop_filter({'fps':60,'cursor':True},region,gpu_frames=True)
        self.assertEqual(gpu,'ddagrab=output_idx=1:framerate=60:draw_mouse=1:dup_frames=1:video_size=1280x720:offset_x=40:offset_y=20')
        cpu=gpu_capture.desktop_filter({'fps':30,'cursor':False},{**region,'full':True},gpu_frames=False)
        self.assertEqual(cpu,'ddagrab=output_idx=1:framerate=30:draw_mouse=0:dup_frames=1,hwdownload,format=bgra')
        self.assertTrue(gpu_capture.native_source_allowed(gpu,19045))
    def test_desktop_region_skips_areas_off_the_first_adapter(self):
        import gpu_capture
        with patch('gpu_capture.desktop_output',return_value=(1,0)):
            self.assertIsNone(gpu_capture.desktop_region(None,{'id':'nope'}) or gpu_capture.desktop_region({'hwnd':gpu_capture.ctypes.windll.user32.GetDesktopWindow()},None))
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
