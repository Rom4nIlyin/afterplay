import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from app import Suite
from auto_record import validate as auto_settings
from hotkeys import validate as hotkeys
from shortcuts import initialize_autostart

class StartupTests(unittest.TestCase):
    def test_removed_themes_migrate_appearance_presets_and_imported_settings(self):
        from customization import THEMES,THEME_ALIASES,validate
        self.assertEqual(THEMES,('obsidian','glass','aurora','ember','mist','paper'))
        for old,new in THEME_ALIASES.items():
            with self.subTest(theme=old),tempfile.TemporaryDirectory() as d:
                cfg={'appearance':{'theme':old},'customization':{'theme':old,'accent':'#123456','background':'asset','asset':'a'*64+'.png'},
                     'appearance_presets':{'saved':{'theme':old,'sounds':{'enabled':True}}}}
                (Path(d)/'settings.json').write_text(json.dumps(cfg),'utf-8')
                migrated=Suite(d).cfg
                self.assertEqual(migrated['appearance']['theme'],new)
                self.assertEqual(migrated['customization']['theme'],new)
                self.assertEqual(migrated['customization']['accent'],'#123456')
                self.assertEqual(migrated['customization']['asset'],cfg['customization']['asset'])
                self.assertEqual(migrated['appearance_presets']['saved'],{'theme':new,'sounds':{'enabled':True}})
                patch={'theme':old,'accent':'#123456'}
                self.assertEqual(validate(patch),{'theme':new,'accent':'#123456'})
                self.assertEqual(patch['theme'],old)
    def test_replaced_palette_migrates_only_old_stock_colors(self):
        from customization import migrate_palettes,THEME_PALETTES
        cfg={'customization':{'theme':'neon','background_color':'#211047','accent':'#c4ff42'},
             'appearance_presets':{'mine':{'theme':'lagoon','background_color':'#063d59','accent':'#123456'}}}
        migrate_palettes(cfg)
        self.assertEqual(cfg['customization']['background_color'],THEME_PALETTES['obsidian'][0])
        self.assertEqual(cfg['customization']['accent'],THEME_PALETTES['obsidian'][1])
        self.assertEqual(cfg['appearance_presets']['mine']['background_color'],THEME_PALETTES['aurora'][0])
        self.assertEqual(cfg['appearance_presets']['mine']['accent'],'#123456')
    def test_theme_settings_apply_complete_palette(self):
        from customization import THEME_PALETTES
        with tempfile.TemporaryDirectory() as d:
            suite=Suite(d)
            for name,(background,accent) in THEME_PALETTES.items():
                suite.dispatch('appearance_config',{'theme':name})
                cfg=Suite(d).cfg['customization']
                self.assertEqual((cfg['theme'],cfg['background_color'],cfg['accent']),(name,background,accent))
                self.assertEqual(cfg['background'],'color')
    def test_defaults_and_retired_binding_migration_preserve_choices(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'settings.json'
            original={'hotkeys':{'auto':'Alt+F7','save':'Alt+F10','window':'Alt+M','record':'Alt+F9','mark':'F5'},'desktop':{'clips':{'autostart':False,'close_action':'close'}},'auto_record':{'save_on_exit':True}}
            p.write_text(json.dumps(original),'utf-8')
            suite=Suite(d)
            self.assertNotIn('auto',suite.cfg['hotkeys'])
            self.assertEqual(suite.cfg['hotkeys']['record'],'Alt+F9')
            self.assertEqual(suite.cfg['desktop'],original['desktop'])
            self.assertTrue(suite.cfg['auto_record']['save_on_exit'])
            self.assertNotIn('auto',hotkeys(original['hotkeys']))
        with tempfile.TemporaryDirectory() as d:
            suite=Suite(d)
            self.assertEqual(suite.cfg['desktop']['clips']['close_action'],'tray')
            self.assertFalse(auto_settings({})['save_on_exit'])
    def test_autostart_is_created_once_and_respects_opt_out(self):
        with tempfile.TemporaryDirectory() as d:
            suite=Suite(d)
            with patch('shortcuts.set_autostart',return_value={'enabled':True}) as setter:
                initialize_autostart(suite,d);initialize_autostart(suite,d)
                setter.assert_called_once_with(d,True)
                suite.cfg['desktop']['clips']['autostart']=False
                initialize_autostart(suite,d)
                setter.assert_called_once()
    def test_failed_autostart_can_retry_and_does_not_claim_success(self):
        with tempfile.TemporaryDirectory() as d:
            suite=Suite(d)
            with patch('shortcuts.set_autostart',side_effect=OSError('test failure')):
                initialize_autostart(suite,d)
            self.assertNotIn('autostart',suite.cfg['desktop']['clips'])
    def test_onboarding_persists_skip_and_completion_and_rejects_bad_status(self):
        with tempfile.TemporaryDirectory() as d:
            suite=Suite(d)
            for status in ('skipped','completed'):
                suite.dispatch('onboarding_config',{'status':status})
                self.assertEqual(Suite(d).cfg['onboarding']['status'],status)
            with self.assertRaises(ValueError):suite.dispatch('onboarding_config',{'status':'other'})
    def test_onboarding_is_offered_once_even_when_quit_before_skip(self):
        with tempfile.TemporaryDirectory() as d:
            first=Suite(d);other=Suite(d)
            self.assertTrue(first.dispatch('onboarding_offer',{})['show'])
            self.assertFalse(other.dispatch('onboarding_offer',{})['show'])
            self.assertFalse(Suite(d).dispatch('onboarding_offer',{})['show'])
            first.dispatch('onboarding_config',{'status':'completed'})
            self.assertFalse(Suite(d).dispatch('onboarding_offer',{})['show'])
    def test_editor_height_survives_reopen_and_rejects_invalid_values(self):
        with tempfile.TemporaryDirectory() as d:
            suite=Suite(d);suite.dispatch('editor_layout_config',{'timeline_height':300})
            self.assertEqual(Suite(d).cfg['editor_layout']['timeline_height'],300)
            for value in (True,float('nan'),float('inf'),0,1300):
                with self.assertRaises(ValueError):suite.dispatch('editor_layout_config',{'timeline_height':value})
