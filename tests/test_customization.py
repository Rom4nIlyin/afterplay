import copy,io,json,queue,tempfile,unittest,wave,zipfile
from pathlib import Path
import av
import numpy as np
from app import Suite
from audio_tracks import AudioPackets,export_audio
import customization as custom
import capture_profiles
from replay import Replay

class CustomizationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.suite=Suite(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_appearance_preserves_hotkeys_library_and_updates(self):
        original={'save':'Alt+F10','auto':'Alt+F9','window':'Alt+M','mark':'F5'}
        self.suite.cfg['hotkeys']=copy.deepcopy(original);self.suite.cfg['updates']={'auto_enabled':False};self.suite.save_cfg()
        custom.configure(self.suite,{'theme':'glass','sounds':{'success':{'volume':12}},'blur':7})
        self.assertEqual(self.suite.cfg['hotkeys'],original)
        self.assertFalse(self.suite.cfg['updates']['auto_enabled'])
        cfg=custom.current(self.suite)
        self.assertEqual(cfg['sounds']['success']['volume'],12);self.assertIn('error',cfg['sounds'])
        self.assertEqual(self.suite.cfg['appearance']['theme'],'glass')
    def test_invalid_input_is_atomic(self):
        original=self.suite.cfg_path.read_bytes()
        for patch in ({'blur':float('nan')},{'theme':'unknown'},{'nav_hidden':['settings']},{'accent':'red;url(x)'},{'asset':'../settings.json'},
                      {'sounds':{'success':{'volume':101}}},{'motion':1},{'nav_order':['settings']}):
            with self.assertRaises(ValueError):custom.configure(self.suite,patch)
            self.assertEqual(self.suite.cfg_path.read_bytes(),original)
    def test_asset_route_never_serves_arbitrary_paths(self):
        for value in ('../settings.json','C:/Windows/win.ini','a'*64+'.exe','a'*64+'.mp4/other'):
            with self.assertRaises(ValueError):custom.asset_path(self.suite,value)
    def test_presets_are_independent_copies(self):
        custom.configure(self.suite,{'theme':'aurora','dim':40});custom.save_preset(self.suite,'Aurora')
        custom.configure(self.suite,{'theme':'paper','dim':80})
        self.assertEqual(self.suite.cfg['appearance_presets']['Aurora']['dim'],40)
    def test_deleting_a_preset_preserves_active_appearance_assets_and_other_settings(self):
        from unittest.mock import patch
        name='Удалить <этот> "набор"'
        asset=custom.asset_path(self.suite,'a'*64+'.png');asset.write_bytes(b'keep active background')
        custom.configure(self.suite,{'theme':'aurora','asset':asset.name,'background':'asset'})
        custom.save_preset(self.suite,name);custom.save_preset(self.suite,'Оставить')
        before=copy.deepcopy(self.suite.cfg)
        for bad_name in ('Нет такого набора',None,[]):
            with self.assertRaises(ValueError):custom.dispatch(self.suite,'customize_preset_delete',{'name':bad_name})
            self.assertEqual(self.suite.cfg,before)
        with patch.object(self.suite,'save_cfg',side_effect=OSError('write failed')):
            with self.assertRaises(OSError):custom.delete_preset(self.suite,name)
        self.assertEqual(self.suite.cfg,before)
        remaining=custom.dispatch(self.suite,'customize_preset_delete',{'name':name})
        self.assertEqual(set(remaining),{'Оставить'})
        del before['appearance_presets'][name]
        self.assertEqual(self.suite.cfg,before)
        self.assertEqual(Suite(self.temp.name).cfg['appearance_presets'],remaining)
        self.assertEqual(asset.read_bytes(),b'keep active background')
        self.assertEqual(custom.delete_preset(self.suite,'Оставить'),{})
    def test_invalid_theme_archive_does_not_apply_settings(self):
        path=Path(self.temp.name)/'broken.afterplay-theme'
        cfg=copy.deepcopy(custom.DEFAULTS);cfg['asset']='a'*64+'.mp4'
        with zipfile.ZipFile(path,'w') as archive:archive.writestr('theme.json',json.dumps(cfg));archive.writestr('assets/'+cfg['asset'],b'wrong content')
        with self.assertRaises(ValueError):custom.import_preset(self.suite,path)
        self.assertNotIn('customization',self.suite.cfg)
    def test_generated_sounds_are_valid_and_volume_scales(self):
        for pack in ('soft','digital','chime'):
            with wave.open(io.BytesIO(custom.tone('success',pack,.3)),'rb') as sound:
                self.assertEqual(sound.getframerate(),44100);self.assertGreater(sound.getnframes(),1000)
        quiet=np.frombuffer(custom.tone('mark','soft',0)[44:],dtype='<i2')
        self.assertEqual(np.max(np.abs(quiet)),0)
    def test_four_tracks_mix_and_microphone_remain_isolated(self):
        sources=[]
        for index in range(3):
            q=queue.Queue();q.put((10,np.full(4800*2,.1*(index+1),dtype='<f4').tobytes()));sources.append({'queue':q})
        out=io.BytesIO();mux=av.open(out,'w',format='nut')
        audio=AudioPackets(mux,{'rate':48000,'channels':2,'sources':sources,'titles':['Общий звук','Игра','Discord / чат','Микрофон']},None,10,0)
        audio.drain();_,blocks=audio.read(4800)
        self.assertEqual(len(blocks),4)
        self.assertAlmostEqual(float(np.frombuffer(blocks[0],dtype='<f4')[0]),.6,places=5)
        self.assertAlmostEqual(float(np.frombuffer(blocks[3],dtype='<f4')[0]),.3,places=5)
        mux.close()
    def test_device_microphone_is_not_misidentified_as_chat(self):
        info={'audio':3,'audio_titles':['Общий звук','Звук устройства','Микрофон']}
        with self.assertRaises(ValueError):export_audio(info,{'audio_mode':'chat'})
        filters,maps,count,_=export_audio(info,{'audio_mode':'custom','audio_tracks':[{'index':2,'gain':50}]})
        self.assertIn('[0:a:2]volume=0.500000',filters[1]);self.assertEqual(count,1)
    def test_microphone_profile_is_opt_in_and_validated(self):
        self.suite.replay=Replay(self.suite)
        self.assertFalse(self.suite.replay.settings['microphone_enabled'])
        cfg=capture_profiles.validated({'microphone_enabled':True,'microphone_device':'9','microphone_gain':75})
        self.assertTrue(cfg['microphone_enabled'])
        for value in (-1,101,True,float('nan')):
            with self.assertRaises(ValueError):capture_profiles.validated({'microphone_gain':value})

if __name__=='__main__':unittest.main()
