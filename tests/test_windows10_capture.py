"""Windows 10 records through DXGI Desktop Duplication, falling back to GDI."""
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch


def recorder(encoder,height=0):
    from replay import Replay
    rec=Replay.__new__(Replay)
    rec.settings={'fps':60,'cursor':True,'height':height};rec.encoder=encoder
    rec.native_gpu=False;rec.gpu_frames=False;rec.desktop_duplication=False;rec.backend_note=''
    rec.suite=Mock();rec.suite.ff.return_value='ffmpeg.exe'
    return rec

REGION={'output':0,'x':0,'y':0,'width':1920,'height':1080,'full':False}


class Windows10CaptureTests(unittest.TestCase):
    def test_nvenc_at_native_size_keeps_frames_on_the_gpu(self):
        rec=recorder('h264_nvenc')
        with patch('gpu_capture.desktop_region',return_value=REGION),patch('video_quality.output_size',return_value=(1920,1080)), \
             patch('replay.subprocess.run',return_value=SimpleNamespace(returncode=0,stderr=b'')) as probe:
            self.assertEqual(rec._desktop_duplication({'hwnd':1},None),(1920,1080))
        self.assertTrue(rec.native_gpu and rec.gpu_frames and rec.desktop_duplication)
        self.assertNotIn('hwdownload',rec.capture_graph);self.assertIn('h264_nvenc',probe.call_args.args[0])

    def test_cpu_encoder_or_scaling_downloads_frames_once_in_ffmpeg(self):
        for encoder,size in (('libx264',(1920,1080)),('h264_nvenc',(1280,720))):
            rec=recorder(encoder)
            with self.subTest(encoder=encoder),patch('gpu_capture.desktop_region',return_value=REGION), \
                 patch('video_quality.output_size',return_value=size), \
                 patch('replay.subprocess.run',return_value=SimpleNamespace(returncode=0,stderr=b'')):
                rec._desktop_duplication(None,{'id':'x'})
                self.assertTrue(rec.native_gpu);self.assertFalse(rec.gpu_frames)
                self.assertTrue(rec.capture_graph.endswith(',hwdownload,format=bgra'))

    def test_failures_fall_back_to_gdi(self):
        cases=[(None,None),(REGION,SimpleNamespace(returncode=1,stderr=b'no dda')),(REGION,subprocess.TimeoutExpired('ffmpeg',5))]
        for region,result in cases:
            rec=recorder('libx264')
            run=patch('replay.subprocess.run',side_effect=result) if isinstance(result,Exception) else patch('replay.subprocess.run',return_value=result)
            with self.subTest(region=region,result=result),patch('gpu_capture.desktop_region',return_value=region),run:
                self.assertIsNone(rec._desktop_duplication({'hwnd':1},None))
                self.assertFalse(rec.native_gpu or rec.desktop_duplication);self.assertTrue(rec.backend_note)


if __name__=='__main__':unittest.main()
