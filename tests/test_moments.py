import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import av
import numpy as np
from app import Suite,run
from replay import Replay
from hotkeys import validate
import input_capture as inputs
import input_overlay
import montage
import quick_clips


class InputTrackTests(unittest.TestCase):
    def test_trim_carries_held_keys_releases_boundary_and_drops_future(self):
        events=[[1,'K87',True],[2,'M1',True],[3,'M1',False],[5,'K87',False],[7,'K65',True]]
        self.assertEqual(inputs.cut(events,2.5,1),[[0.,'K87',True],[0.,'M1',True],[.5,'M1',False],[1,'K87',False]])
        self.assertEqual(inputs.cut(events,5,1),[[0.,'K87',True],[0.,'K87',False]])

    def test_track_suppresses_repeat_flushes_and_keeps_capture_epoch(self):
        with tempfile.TemporaryDirectory() as temp:
            track=inputs.InputTrack(temp,100)
            self.assertFalse(track.path.exists())
            track.event('K87',True,101);track.event('K87',True,101.5);track.event('M2',True,102)
            track.release(103)
            dest=Path(temp)/'clip.mp4';track.attach(dest,1.5,2)
            self.assertEqual(inputs.read(dest)['events'],[[0.,'K87',True],[.5,'M2',True],[1.5,'K87',False],[1.5,'M2',False]])
            track.close()

    def test_reader_rejects_malformed_or_unordered_events(self):
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/'clip.mp4'
            for events in ([[float('nan'),'K87',True]],[[2,'K87',True],[1,'K87',False]],[[1,'password',True]],[[1,'K87',1]]):
                inputs.sidecar(dest).write_text(json.dumps({'version':1,'duration':3,'events':events}))
                with self.assertRaises(ValueError):inputs.read(dest)

    def test_physical_modifiers_numpad_and_arrows_are_distinct(self):
        self.assertEqual(inputs.keyboard_code(16,0x36,0),'K161')
        self.assertEqual(inputs.keyboard_code(17,0x1D,2),'K163')
        self.assertEqual(inputs.keyboard_code(13,0x1C,2),'K256')
        self.assertEqual(inputs.keyboard_code(38,0x48,0),'K104')
        self.assertEqual(inputs.keyboard_code(38,0x48,2),'K38')

    def test_full_layout_includes_both_sides_caps_arrows_numpad_and_mouse(self):
        codes={k['code'] for k in input_overlay.geometry()['keys']}
        self.assertTrue({'K20','K160','K161','K162','K163','K164','K165','K38','K96','K256','M1','M5','WU','WD'}<=codes)
        self.assertEqual(len(codes),len(input_overlay.geometry()['keys']))

    @unittest.skipUnless(os.name=='nt','Native Raw Input')
    def test_native_recorder_is_message_only_and_stops_without_input(self):
        import ctypes
        from ctypes import wintypes
        with tempfile.TemporaryDirectory() as temp:
            track=inputs.InputTrack(temp,time.perf_counter())
            recorder=inputs.RawInputRecorder(track,target_path=r'C:\does-not-exist\test.exe')
            self.assertTrue(recorder.thread.is_alive(),recorder.error)
            user=ctypes.windll.user32
            user.IsWindowVisible.argtypes=[wintypes.HWND]
            self.assertFalse(user.IsWindowVisible(recorder.hwnd))
            recorder.close();self.assertFalse(recorder.thread.is_alive());track.close()
            self.assertEqual(track.path.read_text(), '')

    def test_configure_inputs_does_not_restart_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            suite=Suite(temp);rec=Replay(suite);rec.phase='recording';rec.input_track=inputs.InputTrack(temp,time.perf_counter())
            with patch.object(rec,'_start_inputs') as start,patch.object(rec,'start') as capture:
                rec.configure_inputs(True);start.assert_called_once();capture.assert_not_called()
            self.assertTrue(suite.cfg['input_recording']['enabled'])
            self.assertFalse(rec.configure_inputs(False)['input_recording']['enabled'])


class QuickClipTests(unittest.TestCase):
    def test_optional_shortcuts_keep_existing_keys_and_reject_conflicts(self):
        old={'save':'Alt+F10','window':'Alt+M','record':'F5','mark':'F6'}
        values=validate({**old,'clip_1':'F7','clip_2':'F8','clip_3':'F9','inputs':'F11'})
        self.assertEqual({k:values[k] for k in old},old)
        with self.assertRaises(ValueError):validate({**old,'clip_1':'F5'})
        for values in ([0,30,60],[30,120,1801],[True,120,300],[30,60],['30',60,120]):
            with self.assertRaises(ValueError):quick_clips.durations(values)

    def test_only_assigned_shortcuts_expand_retention(self):
        with tempfile.TemporaryDirectory() as temp:
            suite=Suite(temp);rec=Replay(suite);rec.settings['seconds']=60
            self.assertEqual(quick_clips.retention(rec),60)
            suite.cfg['hotkeys']={'clip_3':'F9'};self.assertEqual(quick_clips.retention(rec),300)

    def test_fixed_length_saves_overlap_without_advancing_ordinary_interval(self):
        with tempfile.TemporaryDirectory() as temp:
            suite=Suite(Path(temp)/'data');rec=Replay(suite);session=rec.root/('c'*32);session.mkdir();rec.session=session
            (session/'.afterplay-buffer').touch()
            result=run([suite.ff(),'-v','error','-f','lavfi','-i','testsrc2=size=64x36:rate=10:duration=150',
                        '-c:v','libx264','-preset','ultrafast','-g','10','-bf','0','-an','-f','segment','-segment_time','1',
                        '-segment_format','mpegts','-segment_list',session/'segments.csv','-y',session/'seg-%07d.ts'],timeout=30)
            self.assertEqual(result.returncode,0)
            rec.phase='recording';rec.capture_epoch=100;rec.settings.update(seconds=60,fps=10,audio_mode='none');rec.interval_start=140
            with patch('replay.time.perf_counter',return_value=245):first=rec.save({},clip_seconds=30)
            with patch('replay.time.perf_counter',return_value=249):second=rec.save({},clip_seconds=120)
            self.assertAlmostEqual(first['capture_start'],115);self.assertAlmostEqual(first['duration'],30,delta=.02)
            self.assertAlmostEqual(second['capture_start'],29);self.assertAlmostEqual(second['duration'],120,delta=.02)
            self.assertEqual(rec.interval_start,140);self.assertEqual(rec.phase,'recording')


class MontageMediaTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.suite=Suite(self.root/'data')
        self.sources=[]
        for i,(size,color,audio) in enumerate([('640x360','black',True),('240x320','red',False),('320x180','blue',True)]):
            target=self.root/f'source-{i}.mp4'
            command=[self.suite.ff(),'-v','error','-f','lavfi','-i',f'color=c={color}:size={size}:rate=30:duration=4']
            if audio:command+=['-f','lavfi','-i','sine=frequency=700:sample_rate=48000:duration=4']
            command+=['-c:v','libx264','-preset','ultrafast','-g','30','-pix_fmt','yuv420p']
            if audio:command+=['-c:a','aac']
            command+=['-y',target]
            result=run(command,timeout=30);self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
            cid=self.suite.index_video(target);self.sources.append((cid,target))
        inputs.write(self.sources[0][1],[[.5,'K87',True],[1,'M1',True],[2.25,'M1',False],[2.5,'K87',False]],4)

    def tearDown(self):self.temp.cleanup()

    def frame(self,path,at):
        with av.open(str(path)) as media:
            for frame in media.decode(video=0):
                if frame.time>=at:return frame.to_ndarray(format='rgb24')

    def test_single_export_can_show_or_hide_inputs_and_keeps_original(self):
        cid,source=self.sources[0];before=hashlib.sha256(source.read_bytes()).hexdigest()
        plain=self.suite.export({'id':cid,'start':1,'end':3,'show_inputs':False},{})
        self.assertEqual(inputs.read(plain['path'])['events'][0],[0.,'K87',True])
        baked=self.suite.export({'id':cid,'start':1,'end':3,'show_inputs':True,
                                 'input_overlay':{'layout':'compact','size':60}},{})
        self.assertIsNone(inputs.read(baked['path']))
        early=self.frame(baked['path'],.2);late=self.frame(baked['path'],1.8)
        self.assertGreater(np.abs(early.astype(float)-late).sum(),10000)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),before)
        decoded=run([self.suite.ff(),'-v','error','-i',baked['path'],'-f','null','-'],timeout=30)
        self.assertEqual(decoded.returncode,0,decoded.stderr.decode(errors='replace'))

    def test_montage_normalizes_aspect_silence_and_input_times(self):
        rows=[{'id':cid,'start':1,'end':2.5} for cid,_ in self.sources]
        result=montage.export(self.suite,{'segments':rows,'name':'Test'},{})
        self.assertEqual((result['width'],result['height'],result['audio']),(640,360,1))
        self.assertAlmostEqual(result['duration'],4.5,delta=.15)
        track=inputs.read(result['path']);self.assertEqual(track['events'][0],[0.,'K87',True])
        self.assertTrue(all(t<=1.55 for t,_,_ in track['events']))
        second=self.frame(result['path'],2.1)
        self.assertGreater(second[180,320,0],200);self.assertLess(second[180,10,0],10)
        decoded=run([self.suite.ff(),'-v','error','-i',result['path'],'-f','null','-'],timeout=30)
        self.assertEqual(decoded.returncode,0,decoded.stderr.decode(errors='replace'))
        self.assertFalse(list(self.suite.recordings_dir().glob('.replay-stage-*')))

    def test_gif_export_renders_inputs_without_changing_source_track(self):
        cid,path=self.sources[0]
        before=inputs.sidecar(path).read_bytes()
        result=self.suite.export({'id':cid,'start':1,'end':3,'format':'gif','show_inputs':True,
                                 'input_overlay':{'layout':'compact'}},{})
        self.assertEqual(result['audio'],0);self.assertEqual(result['format'],'gif')
        self.assertEqual(inputs.sidecar(path).read_bytes(),before)
        self.assertGreater(np.abs(self.frame(result['path'],.2).astype(float)-self.frame(result['path'],1.8)).sum(),10000)

    def test_montage_supports_per_segment_overlay_and_rejects_missing_data(self):
        rows=[{'id':self.sources[0][0],'start':1,'end':3,'show_inputs':True,'input_overlay':{'layout':'compact'}},
              {'id':self.sources[1][0],'start':0,'end':1,'show_inputs':False}]
        result=montage.export(self.suite,{'segments':rows,'audio_mode':'none'},{})
        self.assertEqual(result['audio'],0);self.assertIsNone(inputs.read(result['path']))
        rows[1]['show_inputs']=True
        with self.assertRaisesRegex(ValueError,'не записаны'):montage.segments(self.suite,rows)

    def test_bad_trims_and_missing_sources_fail_before_writing_output(self):
        cid,path=self.sources[0]
        for start,end in ((float('nan'),2),(-1,2),(2,1),(1,100)):
            with self.assertRaises(ValueError):montage.segments(self.suite,[{'id':cid,'start':start,'end':end}])
        path.unlink()
        with self.assertRaisesRegex(ValueError,'исходник'):montage.segments(self.suite,[{'id':cid}])

    def test_cancelled_montage_does_not_publish_or_modify_sources(self):
        from export_control import ExportControl,ExportCancelled
        job={'id':'cancel-test'};control=ExportControl(job);self.suite.export_controls[job['id']]=control
        control.cancel();before={path:hashlib.sha256(path.read_bytes()).hexdigest() for _,path in self.sources}
        with self.assertRaises(ExportCancelled):montage.export(self.suite,{'segments':[{'id':self.sources[0][0],'start':0,'end':2}]},job)
        self.assertEqual(before,{path:hashlib.sha256(path.read_bytes()).hexdigest() for _,path in self.sources})
        self.assertFalse(list(self.suite.recordings_dir().glob('*.mp4')))

    def test_timeline_positions_export_black_gap_and_input_offset(self):
        rows=[{'id':self.sources[2][0],'start':0,'end':1,'at':0},
              {'id':self.sources[0][0],'start':1,'end':2,'at':2}]
        result=montage.export(self.suite,{'segments':rows},{})
        self.assertAlmostEqual(result['duration'],3,delta=.1)
        self.assertGreater(self.frame(result['path'],.3)[90,160,2],180)
        self.assertLess(self.frame(result['path'],1.5).max(),8)
        self.assertEqual(inputs.read(result['path'])['events'][0],[2.,'K87',True])
        rows[1]['at']=.5
        with self.assertRaisesRegex(ValueError,'перекрываются'):montage.segments(self.suite,rows)

    def test_segment_audio_selection_and_project_restore(self):
        cid,_=self.sources[0]
        project={'name':'Edit','segments':[{'id':cid,'uid':'one','start':1,'end':2,'at':1,
                 'audio':{'audio_mode':'custom','audio_tracks':[{'index':0,'gain':0}]},'timer':True}]}
        self.suite.dispatch('montage_project_save',{'project':project})
        self.assertEqual(Suite(self.suite.data).dispatch('montage_project',{})['project'],project)
        result=montage.export(self.suite,project,{})
        with av.open(result['path']) as media:
            values=np.concatenate([frame.to_ndarray().ravel() for frame in media.decode(audio=0)])
        self.assertLess(np.abs(values).max(),1e-5)
        project['segments'][0]['at']=float('nan')
        with self.assertRaises(ValueError):self.suite.dispatch('montage_project_save',{'project':project})

    def test_montage_gif_preserves_selected_order(self):
        rows=[{'id':self.sources[2][0],'start':0,'end':1},{'id':self.sources[1][0],'start':0,'end':1}]
        result=montage.export(self.suite,{'segments':rows,'format':'gif'},{})
        self.assertEqual(result['format'],'gif');self.assertEqual(result['audio'],0)
        self.assertGreater(self.frame(result['path'],.2)[90,160,2],180)
