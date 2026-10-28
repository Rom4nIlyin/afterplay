import ssl
import tempfile
import unittest
import urllib.error
from unittest.mock import patch,Mock
import app_update

class UpdateTLSTests(unittest.TestCase):
    def test_native_context_keeps_hostname_and_chain_checks_and_redirect_rules(self):
        import truststore
        opener=Mock()
        with patch('app_update.urllib.request.build_opener',return_value=opener) as build:
            app_update.open_url(app_update.LATEST_URL)
        redirect,https=build.call_args.args
        self.assertIsInstance(redirect,app_update.GitHubRedirect)
        self.assertIsInstance(https._context,truststore.SSLContext)
        self.assertTrue(https._context.check_hostname)
        self.assertEqual(https._context.verify_mode,ssl.CERT_REQUIRED)
        with self.assertRaises(ValueError):app_update.allowed_url('http://github.com/insecure')
        with self.assertRaises(ValueError):app_update.allowed_url('https://example.com/foreign')
    def test_invalid_certificate_remains_a_failure_with_specific_message(self):
        with tempfile.TemporaryDirectory() as d,patch('app_update.open_url',side_effect=urllib.error.URLError(ssl.SSLCertVerificationError('untrusted'))):
            updater=app_update.AppUpdater(d,d)
            with self.assertRaisesRegex(ValueError,'сертификат'):updater.check()
            self.assertIsNone(updater.latest)

if __name__=='__main__':unittest.main()
