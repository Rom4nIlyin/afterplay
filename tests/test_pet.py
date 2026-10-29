import json,tempfile,threading,unittest,urllib.request
from pathlib import Path
from app import Suite,server_for


class PetTests(unittest.TestCase):
    def test_pet_preferences_persist_without_changing_other_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            suite=Suite(folder);before=json.loads(json.dumps(suite.cfg))
            self.assertNotIn('pet',before)
            self.assertEqual(suite.dispatch('pet_config',{'enabled':True}),{'enabled':True,'sound':True})
            self.assertEqual(suite.dispatch('pet_config',{'sound':False}),{'enabled':True,'sound':False})
            reloaded=Suite(folder)
            self.assertEqual(reloaded.cfg.pop('pet'),{'enabled':True,'sound':False})
            self.assertEqual(reloaded.cfg,before)

    def test_invalid_values_do_not_partially_save(self):
        with tempfile.TemporaryDirectory() as folder:
            suite=Suite(folder)
            for value in ('false',1,None,[],{}):
                with self.assertRaises(ValueError):suite.dispatch('pet_config',{'enabled':True,'sound':value})
                self.assertNotIn('pet',suite.cfg)

    def test_pet_assets_are_served_locally(self):
        with tempfile.TemporaryDirectory() as folder:
            suite=Suite(folder);server,token=server_for(suite)
            threading.Thread(target=server.serve_forever,daemon=True).start()
            try:
                for path,mime in [('pet-ui.js','text/javascript'),('pet.css','text/css'),('pets/rysya.png','image/png'),('pets/rysya-groom.png','image/png'),('pets/purr.wav','audio/wav')]:
                    with urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/{token}/{path}') as response:
                        self.assertEqual(response.headers.get_content_type(),mime)
                        content=response.read();self.assertGreater(len(content),100)
                        if path.endswith('.png'):self.assertTrue(content.startswith(b'\x89PNG\r\n\x1a\n'))
            finally:server.shutdown();server.server_close()
