import io,json,tempfile,unittest,wave
from pathlib import Path
from unittest.mock import patch
import numpy as np
from app import Suite
from replay import Replay
import customization,localization
from webview.util import parse_file_type

class LocalFixTests(unittest.TestCase):
    def test_native_file_filters_accept_the_real_preset_extension(self):
        for value in ['Оформление AFTERPLAY (*.*)','AFTERPLAY preset (*.*)','Фон (*.png;*.jpg;*.gif;*.mp4;*.webm)']:
            self.assertTrue(parse_file_type(value))
        with self.assertRaises(ValueError):parse_file_type('Оформление AFTERPLAY (*.afterplay-theme)')
    def test_markers_expire_without_another_key_press_and_persist(self):
        with tempfile.TemporaryDirectory() as temp:
            suite=Suite(temp);rec=Replay(suite);rec.phase='recording';rec.session=Path(temp)/'session';rec.session.mkdir();rec.capture_epoch=100
            rec.settings['seconds']=60;rec.session_marks=[1,25,60,90]
            with patch('replay.time.perf_counter',return_value=190):state=rec.state()
            self.assertEqual(rec.session_marks,[60,90]);self.assertEqual(state['marker_count'],2)
            self.assertEqual(json.loads((rec.session/'markers.json').read_text()),[60,90])
            rec.interval_start=75
            with patch('replay.time.perf_counter',return_value=195):self.assertEqual(rec.state()['marker_count'],1)
            rec.phase='off';rec.session=None;self.assertEqual(rec.state()['marker_count'],0)
    def test_marker_snapshot_survives_later_buffer_expiration(self):
        with tempfile.TemporaryDirectory() as temp:
            suite=Suite(temp);rec=Replay(suite);rec.phase='recording';rec.session=Path(temp);rec.capture_epoch=100;rec.settings['seconds']=60
            rec.session_marks=[1,40,61];snapshot=tuple(rec._prune_markers(61))
            self.assertEqual(snapshot,(1,40,61));rec._prune_markers(125)
            self.assertEqual(rec.session_marks,[]);self.assertEqual(snapshot,(1,40,61))
    def test_mark_cue_has_two_audible_notes_at_thirty_percent(self):
        with wave.open(io.BytesIO(customization.tone('mark','soft',.3)),'rb') as media:
            samples=np.frombuffer(media.readframes(media.getnframes()),dtype='<i2').astype(float)/32768
            self.assertGreater(len(samples)/media.getframerate(),.3)
            self.assertGreater(np.sqrt(np.mean(samples*samples)),.08)
    def test_language_persists_without_rewriting_user_data(self):
        with tempfile.TemporaryDirectory() as temp:
            suite=Suite(temp);suite.cfg['hotkeys']={'save':'Alt+F10','mark':'F5'};suite.cfg['appearance_presets']={'Мой дефолт':{'theme':'aurora'}};suite.save_cfg()
            localization.configure(suite,'en')
            self.assertEqual(localization.translate(suite,'Момент отмечен'),'Moment marked')
            self.assertEqual(localization.translate(suite,'Сохранить последние 5 мин'),'Save the last 5 min')
            self.assertEqual(suite.cfg['appearance_presets'],{'Мой дефолт':{'theme':'aurora'}})
            self.assertEqual(Suite(temp).cfg['language'],'en')
            original=suite.cfg_path.read_bytes()
            with self.assertRaises(ValueError):localization.configure(suite,'fr')
            self.assertEqual(suite.cfg_path.read_bytes(),original)
    def test_english_catalog_has_no_russian_translations(self):
        import re
        self.assertGreater(len(localization.catalog()),900)
        self.assertFalse(any(re.search('[А-Яа-яЁё]',value) for value in localization.catalog().values()))
