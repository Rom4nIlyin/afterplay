import hashlib,json,tempfile,threading,unittest,urllib.request
from pathlib import Path
from unittest.mock import patch,Mock
from types import SimpleNamespace
from app import Suite,server_for,verify_interface_bundle,monitor_interface

class UiDeliveryTests(unittest.TestCase):
    def test_assets_keep_browser_mime_types_when_windows_associations_are_broken(self):
        with tempfile.TemporaryDirectory() as d:
            suite=Suite(d);server,token=server_for(suite)
            threading.Thread(target=server.serve_forever,daemon=True).start()
            try:
                self.assertGreaterEqual(server.request_queue_size,64)
                with patch('mimetypes.guess_type',side_effect=RuntimeError('Broken registry association')):
                    for name,expected in [('index.html','text/html'),('style.css','text/css'),('ui.js','text/javascript'),('recording-size.js','text/javascript'),('settings-layout.js','text/javascript'),('comfort.css','text/css'),('fonts/Inter-Regular.ttf','font/ttf')]:
                        with urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/{token}/{name}') as response:
                            self.assertEqual(response.headers.get_content_type(),expected)
                            self.assertEqual(response.version,11)
                            self.assertEqual(response.headers['Cache-Control'],'no-store')
                            self.assertGreater(len(response.read()),10)
            finally:server.shutdown();server.server_close()
    def test_failed_first_load_retries_once_and_writes_diagnostics(self):
        with tempfile.TemporaryDirectory() as d:
            window=SimpleNamespace(events=SimpleNamespace(loaded=Mock()),evaluate_js=Mock(side_effect=[{'ready':False},{'ready':False},{'ready':True}]),load_url=Mock())
            suite=SimpleNamespace(window=window,desktop=None,data=Path(d),log=Mock())
            self.assertTrue(monitor_interface(suite,'http://127.0.0.1:123/abc/',pause=lambda _:None,polls=2))
            window.load_url.assert_called_once()
            self.assertEqual(json.loads((Path(d)/'logs/ui-startup.json').read_text('utf-8'))['attempt'],2)
    def test_persistent_failure_stops_after_one_retry(self):
        with tempfile.TemporaryDirectory() as d:
            window=SimpleNamespace(events=SimpleNamespace(loaded=Mock()),evaluate_js=Mock(return_value={'ready':False}),load_url=Mock())
            suite=SimpleNamespace(window=window,desktop=None,data=Path(d),log=Mock())
            self.assertFalse(monitor_interface(suite,'http://127.0.0.1:123/abc/',pause=lambda _:None,polls=2))
            window.load_url.assert_called_once();self.assertEqual(window.evaluate_js.call_count,4)
    def test_incomplete_extraction_reports_the_missing_or_modified_asset(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);ui=root/'app/ui';ui.mkdir(parents=True)
            (ui/'index.html').write_text('<link href="style.css?v=local"><script src="ui.js"></script>','utf-8')
            (ui/'style.css').write_text('body{color:white}','utf-8');(ui/'ui.js').write_text('window.ready=true','utf-8')
            catalog={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in ui.iterdir()}
            (root/'app/SHA256SUMS.json').write_text(json.dumps(catalog),'utf-8')
            verify_interface_bundle(root)
            (ui/'style.css').unlink()
            with self.assertRaisesRegex(RuntimeError,'style.css'):verify_interface_bundle(root)
            (ui/'style.css').write_text('modified','utf-8')
            with self.assertRaisesRegex(RuntimeError,'style.css'):verify_interface_bundle(root)
