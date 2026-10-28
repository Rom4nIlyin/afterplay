import tempfile,unittest
from app import Suite
from customization import validate


class CinemaSettingsTests(unittest.TestCase):
    def test_cinema_values_validate_and_reject_unknown_choices(self):
        for palette in ['cinema','onyx','ocean','ember','rose','custom']:
            self.assertEqual(validate({'cinema_palette':palette}),{'cinema_palette':palette})
        for field,value in [('cinema_palette','unknown'),('cinema_sidebar','../outside.png'),('cinema_accent','url(remote)'),('cinema_motion','invalid')]:
            with self.subTest(field=field),self.assertRaises(ValueError):validate({field:value})

    def test_palette_and_motion_preserve_other_settings_across_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            suite=Suite(folder)
            suite.cfg['hotkeys']={'save':'Alt+F10','record':'Alt+F9','window':'Alt+M','mark':'F5'}
            suite.cfg['selected_capture_profile']='screen:default'
            suite.cfg['updates']={'auto_enabled':False}
            suite.save_cfg()
            values={'cinema_layout':True,'cinema_palette':'ocean','cinema_accent':'#79c7ff','cinema_motion':'off','cinema_sidebar':'citadel'}
            suite.dispatch('customize_config',values)
            reopened=Suite(folder)
            for key,value in values.items():self.assertEqual(reopened.cfg['customization'][key],value)
            self.assertEqual(reopened.cfg['hotkeys'],suite.cfg['hotkeys'])
            self.assertEqual(reopened.cfg['selected_capture_profile'],'screen:default')
            self.assertFalse(reopened.cfg['updates']['auto_enabled'])
