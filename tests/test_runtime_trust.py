"""NTFS regression tests for portable .NET startup; no application is launched."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from runtime_trust import prepare_runtime

@unittest.skipUnless(os.name == 'nt', 'Requires Windows NTFS alternate streams')
class RuntimeTrustTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def component(self, name, content=b'verified fixture'):
        path = self.root / name
        path.write_bytes(content)
        Path(str(path) + ':Zone.Identifier').write_bytes(b'[ZoneTransfer]\r\nZoneId=3\r\n')
        return path, hashlib.sha256(content).hexdigest()

    def manifest(self, entries):
        (self.root / 'SHA256SUMS.json').write_text(json.dumps(entries), encoding='utf-8')

    def marked(self, path):
        return Path(str(path) + ':Zone.Identifier').exists()

    def test_only_verified_bundle_component_is_prepared(self):
        good, digest = self.component('ProcessAudio.dll')
        other, other_digest = self.component('unrelated.dll')
        self.manifest({'ProcessAudio.dll': digest, 'unrelated.dll': other_digest})
        self.assertEqual(prepare_runtime(self.root), ['ProcessAudio.dll'])
        self.assertFalse(self.marked(good))
        self.assertTrue(self.marked(other))
        self.assertEqual(prepare_runtime(self.root), [])

    def test_modified_component_prevents_partial_preparation(self):
        good, digest = self.component('ProcessAudio.dll')
        changed, original = self.component('ReplayNotification.dll')
        changed.write_bytes(b'modified after packaging')
        Path(str(changed) + ':Zone.Identifier').write_bytes(b'[ZoneTransfer]\r\nZoneId=3\r\n')
        self.manifest({'ProcessAudio.dll': digest, 'ReplayNotification.dll': original})
        with self.assertRaisesRegex(RuntimeError, 'изменён'):
            prepare_runtime(self.root)
        self.assertTrue(self.marked(good))
        self.assertTrue(self.marked(changed))

    def test_development_installation_without_catalog_is_unchanged(self):
        self.assertEqual(prepare_runtime(self.root), [])

    def test_incomplete_portable_bundle_reports_missing_catalog(self):
        (self.root / 'runtime').mkdir()
        (self.root / 'runtime/python313._pth').write_text('python313.zip', encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'SHA256SUMS.json'):
            prepare_runtime(self.root)

if __name__ == '__main__':
    unittest.main()
