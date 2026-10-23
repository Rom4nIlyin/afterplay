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
        args=encoder_options(DEFAULTS,'h264_nvenc',2560,1440)
        self.assertIn('high',args);self.assertIn('-cq',args);self.assertIn('-spatial-aq',args)
        self.assertEqual(args[args.index('-rc')+1],'vbr')

    def test_each_buffer_duration_selects_correct_continuous_range(self):
        rows=[{'start':i*2,'end':i*2+2} for i in range(950)]
        for minutes in (1,3,5,10,15,20,30):
            _,_,duration=select_segments(rows,1900,minutes*60)
            self.assertEqual(duration,minutes*60)

if __name__=='__main__':unittest.main()
