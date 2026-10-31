"""Profile identities survive stale forms and failed starts for absent apps."""
import copy
import json
import tempfile
import unittest
from unittest.mock import patch

from app import Suite
from replay import Replay
from auto_record import AutoRecorder
import capture_profiles as profiles


class ProfileIntegrityTests(unittest.TestCase):
    def setup_suite(self,temp):
        suite=Suite(temp);suite.replay=Replay(suite);profiles.ensure_defaults(suite)
        game=profiles.save(suite,{'path':r'C:\Missing\Gloria Victis\gv.exe','name':'Gloria Victis',
                                 'settings':{**suite.replay.settings,'capture_mode':'window','audio_mode':'none'}})
        suite.auto=AutoRecorder(suite,applications=lambda:[])
        return suite,game

    def test_repeated_failed_starts_preserve_both_profiles_and_config(self):
        with tempfile.TemporaryDirectory() as temp:
            suite,game=self.setup_suite(temp);profiles.apply(suite,game['id'])
            original=suite.cfg_path.read_bytes();original_profiles=copy.deepcopy(suite.cfg['capture_profiles'])
            for operation in ('start_recording','start_replay')*4:
                with patch('replay.monitors',return_value=[]),patch('process_audio.applications',return_value=[]):
                    with self.assertRaisesRegex(ValueError,'окно недоступно'):suite.auto.manual(operation)
                self.assertEqual(suite.cfg_path.read_bytes(),original)
                self.assertEqual(suite.cfg['capture_profiles'],original_profiles)
                self.assertEqual(suite.cfg['selected_capture_profile'],game['id'])
            self.assertEqual(len(original_profiles),2)
            self.assertEqual(original_profiles[profiles.DEFAULT_PROFILE]['path'],'')

    def test_desktop_profile_cannot_be_overwritten_by_an_application_form(self):
        with tempfile.TemporaryDirectory() as temp:
            suite,game=self.setup_suite(temp);original=suite.cfg_path.read_bytes()
            wrong={'id':profiles.DEFAULT_PROFILE,'path':game['path'],'name':game['name'],'settings':game['settings']}
            for save in (profiles.configure,profiles.save):
                with self.assertRaisesRegex(ValueError,'по умолчанию'):save(suite,wrong)
                self.assertEqual(suite.cfg_path.read_bytes(),original)

    def test_creating_duplicate_app_profile_does_not_overwrite_existing_one(self):
        with tempfile.TemporaryDirectory() as temp:
            suite,game=self.setup_suite(temp);original=suite.cfg_path.read_bytes()
            with self.assertRaisesRegex(ValueError,'уже есть профиль'):
                profiles.save(suite,{'path':game['path'],'name':'Accidental replacement','settings':game['settings']})
            self.assertEqual(suite.cfg_path.read_bytes(),original)

    def test_startup_repairs_corrupted_default_without_changing_game_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            suite,game=self.setup_suite(temp);profiles.apply(suite,game['id'])
            suite.cfg['capture_profiles'][profiles.DEFAULT_PROFILE]={**copy.deepcopy(game),'id':profiles.DEFAULT_PROFILE}
            suite.save_cfg();profiles.ensure_defaults(suite)
            self.assertEqual(suite.cfg['capture_profiles'][profiles.key(game['id'])],game)
            default=suite.cfg['capture_profiles'][profiles.DEFAULT_PROFILE]
            self.assertEqual(default['path'],'');self.assertEqual(default['settings']['capture_mode'],'monitor')
            self.assertEqual(suite.cfg['selected_capture_profile'],game['id'])
            self.assertEqual(json.loads(suite.cfg_path.read_text('utf-8'))['capture_profiles'],suite.cfg['capture_profiles'])

    def test_repaired_default_is_applied_when_it_is_selected(self):
        with tempfile.TemporaryDirectory() as temp:
            suite,game=self.setup_suite(temp)
            suite.cfg['capture_profiles'][profiles.DEFAULT_PROFILE]={**copy.deepcopy(game),'id':profiles.DEFAULT_PROFILE}
            suite.cfg['selected_capture_profile']=profiles.DEFAULT_PROFILE
            suite.replay.settings.update(capture_mode='window',window_path=game['path'])
            profiles.ensure_defaults(suite)
            self.assertEqual(suite.replay.settings['capture_mode'],'monitor')
            self.assertEqual(suite.replay.settings['window_path'],'')

    def test_border_toggle_is_global_across_profiles(self):
        with tempfile.TemporaryDirectory() as temp:
            suite,game=self.setup_suite(temp)
            self.assertNotIn('capture_border',game['settings'])
            suite.replay.configure({'capture_border':True})
            profiles.apply(suite,game['id'])
            self.assertTrue(suite.replay.settings['capture_border'])
            profiles.apply(suite,profiles.DEFAULT_PROFILE)
            self.assertTrue(suite.replay.settings['capture_border'])
            suite.replay.configure({'capture_border':False})
            profiles.apply(suite,game['id'])
            self.assertFalse(suite.replay.settings['capture_border'])
            self.assertFalse(suite.cfg['replay']['capture_border'])
            self.assertNotIn('capture_border',profiles.for_app(suite.cfg,game['path']))

    def test_legacy_profile_border_values_are_removed_on_startup(self):
        with tempfile.TemporaryDirectory() as temp:
            suite,game=self.setup_suite(temp)
            saved=suite.cfg['capture_profiles']
            saved[profiles.DEFAULT_PROFILE]['settings']['capture_border']=True
            saved[profiles.key(game['id'])]['settings']['capture_border']=True
            suite.save_cfg()
            profiles.ensure_defaults(suite)
            self.assertFalse(suite.replay.settings['capture_border'])
            self.assertFalse(suite.cfg['replay']['capture_border'])
            for profile in suite.cfg['capture_profiles'].values():
                self.assertNotIn('capture_border',profile['settings'])
            persisted=json.loads(suite.cfg_path.read_text('utf-8'))
            for profile in persisted['capture_profiles'].values():
                self.assertNotIn('capture_border',profile['settings'])

    def test_profile_form_cannot_override_global_border(self):
        with tempfile.TemporaryDirectory() as temp:
            suite,game=self.setup_suite(temp)
            suite.replay.configure({'capture_border':False})
            values={**game['settings'],'capture_border':True}
            updated=profiles.configure(suite,{'id':game['id'],'path':game['path'],
                                             'name':game['name'],'settings':values})
            self.assertNotIn('capture_border',updated['settings'])
            self.assertFalse(suite.replay.settings['capture_border'])
            self.assertFalse(suite.cfg['replay']['capture_border'])
