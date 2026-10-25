import copy
import ctypes
import io
import json
from pathlib import Path
import queue
import tempfile
import threading
import unittest
from unittest.mock import patch

import av
import numpy as np
from app import Suite,run
from replay import Replay,closed_segments
import capture_profiles as profiles
import editor_media
from audio_tracks import AudioPackets,export_audio
from hotkeys import validate,GlobalHotkeys
from live_markers import relative
from test_automation import window
import test_automation


class ProfileTests(unittest.TestCase):
    def test_new_profile_persists_while_state_is_polled(self):
        with tempfile.TemporaryDirectory() as temp:
            suite=Suite(temp);suite.replay=Replay(suite);profiles.ensure_defaults(suite)
            stop=threading.Event();errors=[]
            def poll():
                while not stop.is_set():
                    try:suite.dispatch('state',{})
                    except Exception as error:errors.append(error);break
            worker=threading.Thread(target=poll);worker.start()
            try:
                for _ in range(15):
                    created=profiles.create(suite)
                    self.assertIn(profiles.key(created['id']),json.loads(suite.cfg_path.read_text('utf-8'))['capture_profiles'])
            finally:stop.set();worker.join(5)
            self.assertFalse(errors);self.assertFalse(worker.is_alive())

    def test_default_desktop_and_inline_save_persist_profile_and_keep_hotkeys(self):
        with tempfile.TemporaryDirectory() as temp:
            suite=Suite(temp);suite.replay=Replay(suite)
            suite.cfg['hotkeys']={'save':'Alt+F10','auto':'Alt+F9','window':'Alt+M'}
            profiles.ensure_defaults(suite)
            self.assertEqual(suite.replay.settings['capture_mode'],'monitor')
            self.assertEqual(suite.replay.settings['audio_mode'],'system')
            updated=profiles.configure(suite,{'id':profiles.DEFAULT_PROFILE,'name':'Desktop','path':'',
                                             'settings':{**suite.replay.settings,'fps':30,'seconds':600}})
            self.assertEqual(updated['settings']['fps'],30)
            self.assertEqual(suite.cfg['replay']['seconds'],600)
            self.assertEqual(json.loads(suite.cfg_path.read_text('utf-8'))['capture_profiles'][profiles.DEFAULT_PROFILE]['name'],'Desktop')
            original=suite.cfg_path.read_bytes()
            with self.assertRaises(ValueError):profiles.configure(suite,{'id':profiles.DEFAULT_PROFILE,'name':'','settings':suite.replay.settings})
            self.assertEqual(suite.cfg_path.read_bytes(),original)
            self.assertEqual(suite.cfg['hotkeys']['window'],'Alt+M')
            with self.assertRaises(ValueError):profiles.remove(suite,profiles.DEFAULT_PROFILE)

    def test_screen_profiles_have_distinct_identity_without_executable_and_edit_in_place(self):
        with tempfile.TemporaryDirectory() as temp:
            suite=Suite(temp);suite.replay=Replay(suite)
            settings={**suite.replay.settings,'capture_mode':'monitor','audio_mode':'system'}
            first=profiles.save(suite,{'name':'Screen 1','settings':settings})
            second=profiles.save(suite,{'name':'Screen 2','settings':settings})
            self.assertNotEqual(first['id'],second['id']);self.assertEqual(first['path'],'')
            updated=profiles.save(suite,{'id':first['id'],'name':'Renamed','settings':{**settings,'fps':30}})
            self.assertEqual(updated['id'],first['id']);self.assertEqual(len(suite.cfg['capture_profiles']),2)
            profiles.apply(suite,first['id'])
            self.assertEqual(suite.replay.settings['capture_mode'],'monitor')
            self.assertEqual(suite.replay.settings['window_path'],'')
            self.assertEqual(suite.replay.settings['game_pid'],0)
            self.assertEqual(suite.replay.settings['fps'],30)
            profiles.remove(suite,first['id']);self.assertEqual(len(suite.cfg['capture_profiles']),1)
            with self.assertRaises(ValueError):profiles.save(suite,{'settings':{**settings,'capture_mode':'window'}})

    def test_profiles_validate_offline_apply_without_live_pids_and_keep_global_hotkeys(self):
        with tempfile.TemporaryDirectory() as temp:
            suite=Suite(temp);suite.replay=Replay(suite)
            suite.cfg['hotkeys']={'save':'Alt+F10','auto':'Alt+F9','window':'Alt+M'};suite.save_cfg()
            profile=profiles.save(suite,{'path':r'C:\Games\One\game.exe','name':'Game One',
                                        'settings':{**suite.replay.settings,'fps':90,'seconds':600,'window_hwnd':123,'game_pid':999}})
            self.assertNotIn('window_hwnd',profile['settings']);self.assertNotIn('game_pid',profile['settings'])
            profiles.save(suite,{'path':r'C:\Games\Two\game.exe','settings':{**suite.replay.settings,'fps':30}})
            profiles.apply(suite,r'c:\games\one\GAME.EXE')
            self.assertEqual(suite.replay.settings['fps'],90);self.assertEqual(suite.replay.settings['seconds'],600)
            self.assertEqual(suite.replay.settings['window_pid'],0)
            self.assertEqual(suite.cfg['hotkeys'],{'save':'Alt+F10','auto':'Alt+F9','window':'Alt+M'})
            original=suite.cfg_path.read_bytes()
            with self.assertRaises(ValueError):profiles.save(suite,{'path':profile['path'],'settings':{'fps':float('nan')}})
            self.assertEqual(suite.cfg_path.read_bytes(),original)
            suite.replay.phase='recording'
            with self.assertRaises(ValueError):profiles.apply(suite,profile['path'])

    def test_optional_marker_binding_preserves_existing_keys_and_rejects_conflicts(self):
        old={'save':'Alt+F10','auto':'Alt+F9','window':'Alt+M'}
        self.assertEqual(validate(old),old);self.assertEqual(validate({**old,'mark':''}),old)
        with self.assertRaises(ValueError):validate({**old,'mark':'Alt+F10'})
        hit=threading.Event()
        manager=GlobalHotkeys({'save':lambda:None,'auto':lambda:None,'window':lambda:None,'mark':hit.set},lambda *a,**k:None)
        try:
            manager.configure({'save':'Ctrl+Alt+Shift+F17','auto':'Ctrl+Alt+Shift+F18','window':'Ctrl+Alt+Shift+F19','mark':'Ctrl+Alt+Shift+F20'})
            identifier=next(i for i,a in manager.actions.items() if a=='mark')
            ctypes.windll.user32.PostThreadMessageW(manager.tid,0x0312,identifier,0)
            self.assertTrue(hit.wait(3))
        finally:manager.shutdown()


class AutomaticProfileTests(unittest.TestCase):
    setUp=test_automation.AutoTests.setUp
    start=test_automation.AutoTests.start
    def test_automatic_profile_is_selected_and_global_settings_restored(self):
        original=copy.deepcopy(self.replay.settings)
        self.suite.cfg['capture_profiles']={profiles.key(window()['path']):{'name':'Per game','settings':{'fps':90,'seconds':600,'audio_mode':'multitrack'}}}
        self.start();self.assertEqual(self.replay.settings['fps'],90)
        self.assertEqual(self.replay.settings['audio_mode'],'multitrack')
        self.assertEqual(self.replay.active_profile,'Per game')
        self.rows=[];self.auto.tick();self.assertEqual(self.replay.settings,original)


def tone_frequency(path,index):
    with av.open(str(path)) as media:
        stream=media.streams.audio[index];rate=stream.codec_context.sample_rate
        chunks=[];count=0
        for frame in media.decode(stream):
            data=frame.to_ndarray()
            samples=data[0] if frame.format.is_planar else data.reshape(-1,len(frame.layout.channels)).mean(axis=1)
            chunks.append(samples.astype(np.float64));count+=len(samples)
            if count>=rate*2:break
    data=np.concatenate(chunks);spectrum=np.abs(np.fft.rfft(data*np.hanning(len(data))))
    return float(np.argmax(spectrum)*rate/len(data))


class StudioMediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name);cls.suite=Suite(cls.root/'data')
        cls.video=cls.root/'multitrack.mp4'
        result=run([cls.suite.ff(),'-v','error','-f','lavfi','-i','testsrc2=size=320x180:rate=30000/1001:duration=9',
                    '-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=9',
                    '-f','lavfi','-i','sine=frequency=880:sample_rate=48000:duration=9',
                    '-filter_complex','[1:a][2:a]amix=inputs=2:normalize=0[m]',
                    '-map','0:v','-map','[m]','-map','1:a','-map','2:a',
                    '-c:v','libx264','-preset','ultrafast','-g','30','-bf','0','-c:a','aac',
                    '-metadata:s:a:0','title=Общий звук','-metadata:s:a:1','title=Игра','-metadata:s:a:2','title=Discord / чат',
                    '-movflags','+faststart','-y',cls.video],timeout=35)
        if result.returncode:raise AssertionError(result.stderr.decode(errors='replace'))
        cls.clip=cls.suite.index_video(cls.video)
        with cls.suite.db() as db:cls.cid=db.execute('SELECT id FROM clips WHERE path=?',(str(cls.video),)).fetchone()['id']

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_exact_steps_follow_decoded_pts_and_waveform_uses_requested_audio(self):
        metadata=editor_media.info(self.suite,self.cid)
        self.assertAlmostEqual(metadata['fps'],30000/1001,places=5)
        self.assertEqual(len(metadata['audio']),3)
        forward=editor_media.frame_step(self.suite,self.cid,1.001,1)
        backward=editor_media.frame_step(self.suite,self.cid,forward['time'],-1)
        self.assertAlmostEqual(forward['time']-backward['time'],1001/30000,places=6)
        self.assertTrue(forward['image'].startswith('data:image/jpeg;base64,'))
        wave=editor_media.waveform(self.suite,self.cid,2,5,1)
        self.assertEqual(len(wave['peaks']),1000);self.assertFalse(wave['silent'])
        self.assertGreater(max(wave['peaks']),.05)
        self.assertEqual(editor_media.waveform(self.suite,self.cid,2,5,1),wave)
        with self.assertRaises(ValueError):editor_media.waveform(self.suite,self.cid,0,float('nan'))
        preview=editor_media.audio_preview(self.suite,self.cid,2)
        self.assertAlmostEqual(tone_frequency(preview,0),880,delta=2)

    def test_exports_isolated_tracks_gain_adjusted_mix_and_preserves_all(self):
        base={'id':self.cid,'start':1,'end':4,'format':'original','name':'tracks'}
        game=self.suite.export({**base,'audio_mode':'game'},{});self.assertEqual(game['audio'],1)
        self.assertAlmostEqual(tone_frequency(game['path'],0),440,delta=2)
        chat=self.suite.export({**base,'audio_mode':'mix','game_gain':0,'chat_gain':100},{})
        self.assertEqual(chat['audio'],1);self.assertAlmostEqual(tone_frequency(chat['path'],0),880,delta=2)
        all_tracks=self.suite.export({**base,'audio_mode':'all'},{})
        self.assertEqual(all_tracks['audio'],3)
        muted=self.suite.export({**base,'audio_mode':'none'},{});self.assertEqual(muted['audio'],0)
        chosen=self.suite.export({**base,'audio_mode':'custom','audio_tracks':[{'index':2,'gain':100}]},{})
        self.assertEqual(chosen['audio'],1);self.assertAlmostEqual(tone_frequency(chosen['path'],0),880,delta=2)
        disabled=self.suite.export({**base,'audio_mode':'custom','audio_tracks':[]},{})
        self.assertEqual(disabled['audio'],0)
        with self.assertRaises(ValueError):export_audio({'audio':3},{'audio_mode':'custom','audio_tracks':[{'index':9}]})

    def test_live_marks_are_translated_for_each_consecutive_saved_interval(self):
        rec=Replay(self.suite);session=rec.root/('b'*32);session.mkdir();(session/'.afterplay-buffer').touch()
        result=run([self.suite.ff(),'-v','error','-i',self.video,'-map','0','-c','copy','-f','segment','-segment_time','1',
                    '-reset_timestamps','0','-segment_format','mpegts','-segment_list',session/'segments.csv',
                    '-segment_list_type','csv','-y',session/'seg-%07d.ts'],timeout=20)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
        rec.session=session;rec.phase='recording';rec.capture_epoch=100
        rec.settings.update(seconds=60,fps=30,audio_mode='multitrack')
        with patch('replay.time.perf_counter',return_value=102):rec.add_marker()
        with patch('replay.time.perf_counter',return_value=106.5):first=rec.save({})
        with patch('replay.time.perf_counter',return_value=107):rec.add_marker()
        with patch('replay.time.perf_counter',return_value=108):second=rec.save({})
        self.assertEqual(first['audio'],3);self.assertEqual(second['audio'],3)
        self.assertAlmostEqual(first['marks'][0],2,places=3)
        self.assertAlmostEqual(second['marks'][0],7-first['capture_end'],places=3)
        with self.suite.db() as db:
            for saved in (first,second):
                value=db.execute('SELECT marks FROM clips WHERE path=?',(saved['path'],)).fetchone()
                self.assertEqual(json.loads(value['marks']),saved['marks'])
        rec.phase='off'
        with self.assertRaises(ValueError):rec.add_marker()

    def test_pcm_sources_and_mix_share_timestamps_and_keep_silent_gaps(self):
        game=queue.Queue();chat=queue.Queue();rate=48000;epoch=10
        sound=np.full(4800*2,.1,dtype='<f4').tobytes()
        game.put((epoch,sound));chat.put((epoch+.05,sound))
        buffer=io.BytesIO();mux=av.open(buffer,'w',format='nut')
        tracks=AudioPackets(mux,{'rate':rate,'channels':2,'sources':[{'queue':game},{'queue':chat}]},None,epoch,0)
        tracks.drain();position,blocks=tracks.read(7200)
        samples=[np.frombuffer(block,dtype='<f4').reshape(-1,2)[:,0] for block in blocks]
        self.assertEqual(position,0)
        self.assertAlmostEqual(samples[0][3000],.2,places=5)
        self.assertEqual(samples[1][6000],0);self.assertEqual(samples[2][1000],0)
        self.assertEqual([s.time_base for s in tracks.streams],[tracks.streams[0].time_base]*3)
        mux.close()


if __name__=='__main__':unittest.main()
