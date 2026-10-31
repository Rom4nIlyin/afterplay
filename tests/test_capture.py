import struct
import unittest
from capture_media import AudioTimeline
from replay import DEFAULTS,select_segments
from video_quality import validate,output_size,encoder_options

def pcm(*values):return struct.pack('<'+'f'*len(values),*values)

class TimelineTests(unittest.TestCase):
    def test_partial_packets_keep_real_gaps_without_accumulating_delay(self):
        line=AudioTimeline(1000,1,10)
        line.add(10.002,pcm(1,2,3));line.add(10.008,pcm(4,5))
        _,data=line.read(6)
        self.assertEqual(struct.unpack('<6f',data),(0,0,1,2,3,0))
        _,data=line.read(6)
        self.assertEqual(struct.unpack('<6f',data),(0,0,4,5,0,0))

    def test_late_packets_are_trimmed_instead_of_shifting_future_audio(self):
        line=AudioTimeline(1000,1,10);line.read(4)
        line.add(10.002,pcm(1,2,3,4));line.add(10.006,pcm(5))
        self.assertEqual(struct.unpack('<4f',line.read(4)[1]),(3,4,5,0))
        self.assertEqual(line.late_frames,2)

    def test_negative_offset_moves_sound_earlier(self):
        line=AudioTimeline(1000,1,10,-10);line.add(10.012,pcm(7))
        self.assertEqual(struct.unpack('<4f',line.read(4)[1]),(0,0,7,0))

class QualityTests(unittest.TestCase):
    def test_invalid_settings_do_not_reach_encoder(self):
        for change in ({'fps':59},{'cq':4},{'audio_offset_ms':5000},{'quality_mode':'vbr','mbps':90,'max_mbps':50}):
            with self.assertRaises(ValueError):validate({**DEFAULTS,**change})

    def test_output_preserves_aspect_and_never_upscales(self):
        self.assertEqual(output_size({**DEFAULTS,'height':1080},2560,1440),(1920,1080))
        self.assertEqual(output_size({**DEFAULTS,'height':2160},1280,720),(1280,720))

    def test_quality_mode_uses_high_profile_and_adaptive_quantization(self):
        args=encoder_options({**DEFAULTS,'preset':'quality'},'h264_nvenc',2560,1440)
        self.assertIn('high',args);self.assertIn('-cq',args);self.assertIn('-spatial-aq',args)
        self.assertEqual(args[args.index('-rc')+1],'vbr')

    def test_gpu_path_does_not_download_or_cpu_filter_video(self):
        args=encoder_options(DEFAULTS,'h264_nvenc',2560,1440,gpu_frames=True)
        self.assertNotIn('-vf',args)
        self.assertNotIn('hwdownload',' '.join(args))
        self.assertEqual(args[args.index('-rc-lookahead')+1],'0')
        self.assertEqual(args[args.index('-spatial-aq')+1],'0')
        self.assertEqual(args[args.index('-temporal-aq')+1],'0')
        self.assertEqual(args[args.index('-bf')+1],'0')
        self.assertEqual(args[args.index('-preset')+1],'p1')

    def test_native_target_is_exact_window_handle_and_same_output_size(self):
        from gpu_capture import source_filter,input_options
        cfg={**DEFAULTS,'cursor':False}
        graph=source_filter(cfg,{'hwnd':123456789},None,(2560,1440))
        self.assertIn('hwnd=123456789',graph)
        self.assertIn('width=2560:height=1440',graph)
        self.assertIn('display_border=0',graph)
        cmd=input_options(graph,1700000000.25,True)
        self.assertIn('-copyts',cmd)
        self.assertNotIn('-use_wallclock_as_timestamps',cmd)
        self.assertIn('setpts=PTS-STARTPTS',cmd[cmd.index('-i')+1])
        self.assertIn('RTCTIME-1700000000250000',cmd[cmd.index('-i')+1])
        self.assertNotIn('-vf',cmd)

    def test_windows10_native_video_only_accepts_dxgi_without_wgc(self):
        from gpu_capture import native_source_allowed
        self.assertTrue(native_source_allowed('ddagrab=output_idx=0',19045))
        self.assertFalse(native_source_allowed('gfxcapture=hwnd=123',19045))
        self.assertFalse(native_source_allowed('gfxcapture=monitor_idx=0',19045))
        self.assertTrue(native_source_allowed('gfxcapture=hwnd=123',22631))

    def test_windows10_uses_non_wgc_capture_for_windows_and_monitors(self):
        from unittest.mock import patch
        from capture_media import can_use_wgc,create_video_source
        self.assertFalse(can_use_wgc(123,19045))
        self.assertFalse(can_use_wgc(None,19045))
        self.assertTrue(can_use_wgc(123,22631))
        monitor={'id':'test','width':1280,'height':720,'wgc_index':1}
        with patch('process_audio.windows_version',return_value=(10,0,19045)), \
             patch('capture_media.VideoSource',side_effect=AssertionError('WGC must not start')), \
             patch('capture_media.GdiVideoSource') as compatible:
            source,name=create_video_source(hwnd=123,fps=30)
            self.assertIs(source,compatible.return_value)
            self.assertIn('GDI',name)
            source,name=create_video_source(monitor=monitor,fps=30)
            self.assertIs(source,compatible.return_value)
            self.assertEqual(compatible.call_count,2)

    def test_desktop_uses_dxgi_identity_and_repeats_unchanged_frames(self):
        from unittest.mock import patch
        from gpu_capture import source_filter
        monitor={'id':'display-test','width':2560,'height':1440,'wgc_index':3}
        with patch('gpu_capture.desktop_output',return_value=(0,1)):
            graph=source_filter(DEFAULTS,None,monitor,(2560,1440))
        self.assertIn('ddagrab=output_idx=1',graph)
        self.assertIn('dup_frames=1',graph)

    def test_other_adapter_keeps_exact_wgc_monitor_selection(self):
        from unittest.mock import patch
        from gpu_capture import source_filter
        monitor={'id':'display-test','width':1920,'height':1080,'wgc_index':3}
        with patch('gpu_capture.desktop_output',return_value=(1,0)):
            graph=source_filter(DEFAULTS,None,monitor,(1920,1080))
        self.assertIn('gfxcapture=monitor_idx=2',graph)

    def test_idle_gpu_window_keeps_frames_and_clock_flowing(self):
        from gpu_capture import source_filter
        graph=source_filter(DEFAULTS,{'hwnd':123},None,(1000,600),idle_frames=True)
        self.assertIn('gfxcapture=hwnd=123',graph)
        self.assertIn(':dup_frames=1',graph)
        self.assertNotIn('hwdownload',graph)

    def test_old_ffmpeg_is_not_assumed_to_support_idle_frames(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from gpu_capture import repeats_idle_frames
        self.addCleanup(repeats_idle_frames.cache_clear)
        repeats_idle_frames.cache_clear()
        with patch('gpu_capture.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=b'Filter gfxcapture\n max_framerate <video_rate>')):
            self.assertFalse(repeats_idle_frames('old-ffmpeg'))
        with patch('gpu_capture.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=b'Filter gfxcapture\n   dup_frames <boolean> repeat last frame')):
            self.assertTrue(repeats_idle_frames('new-ffmpeg'))

    def test_each_buffer_duration_selects_correct_continuous_range(self):
        rows=[{'start':i*2,'end':i*2+2} for i in range(950)]
        for minutes in (1,3,5,10,15,20,30):
            _,_,duration=select_segments(rows,1900,minutes*60)
            self.assertEqual(duration,minutes*60)

    def test_new_interval_is_capped_at_limit_and_rejects_already_saved_frames(self):
        rows=[{'start':i*2,'end':i*2+2} for i in range(950)]
        selected,skip,duration=select_segments(rows,742.75,300,start_at=700.25)
        self.assertAlmostEqual(selected[0]['start']+skip,700.25)
        self.assertAlmostEqual(duration,42.5)
        selected,skip,duration=select_segments(rows,1042.75,300,start_at=700.25)
        self.assertAlmostEqual(selected[0]['start']+skip,742.75)
        self.assertEqual(duration,300)
        with self.assertRaises(ValueError):select_segments(rows,700.25,300,start_at=700.25)

if __name__=='__main__':unittest.main()
