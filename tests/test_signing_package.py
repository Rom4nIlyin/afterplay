import hashlib,importlib.util,json,tempfile,unittest,zipfile
from pathlib import Path
spec=importlib.util.spec_from_file_location('repackage',Path(__file__).resolve().parents[1]/'scripts/repackage_portable.py')
pack=importlib.util.module_from_spec(spec);spec.loader.exec_module(pack)

class SignedPackageTests(unittest.TestCase):
    def fixture(self,root):
        bundle=root/'bundle';bundle.mkdir()
        files={'version.py':b"VERSION = '1.7.0'\n",'app.py':b'original source','AFTERPLAY.exe':b'unsigned fixture'}
        for name,data in files.items():(bundle/name).write_bytes(data)
        sums={name:hashlib.sha256(data).hexdigest() for name,data in files.items()}
        (bundle/'SHA256SUMS.json').write_text(json.dumps(sums),encoding='utf-8')
        return bundle,sums

    def test_signature_changes_are_catalogued_and_user_data_is_not_packaged(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);bundle,_=self.fixture(root)
            (bundle/'AFTERPLAY.exe').write_bytes(b'authenticode signed fixture')
            (bundle/'data').mkdir();(bundle/'data/private.mp4').write_bytes(b'private')
            archive=pack.repackage(bundle,root/'out','1.7.0')
            with zipfile.ZipFile(archive) as z:
                self.assertFalse(any('/data/' in name for name in z.namelist()))
                sums=json.loads(z.read('AFTERPLAY Portable/SHA256SUMS.json'))
                for name,checksum in sums.items():self.assertEqual(hashlib.sha256(z.read('AFTERPLAY Portable/'+name)).hexdigest(),checksum)

    def test_signing_must_not_modify_application_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);bundle,_=self.fixture(root);(bundle/'app.py').write_bytes(b'changed source')
            with self.assertRaisesRegex(ValueError,'Unexpected signing modification'):pack.repackage(bundle,root/'out','1.7.0')

    def test_catalog_cannot_include_user_data_or_traversal(self):
        for name in ('../outside','data/settings.json','backups/app.py','data\\settings.json'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);bundle,sums=self.fixture(root);sums[name]='a'*64
                (bundle/'SHA256SUMS.json').write_text(json.dumps(sums),encoding='utf-8')
                with self.assertRaises(ValueError):pack.repackage(bundle,root/'out','1.7.0')
