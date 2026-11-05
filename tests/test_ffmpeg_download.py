import hashlib,importlib.util,io,tempfile,unittest,urllib.error,zipfile
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('portable_download',Path(__file__).resolve().parents[1]/'scripts/build_portable.py')
build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)


class PinnedFfmpegDownloadTests(unittest.TestCase):
    def fallback(self,actual=b'pinned executable',expected=b'pinned executable',bad_archive=False):
        content=io.BytesIO()
        with zipfile.ZipFile(content,'w') as archive:
            archive.writestr('AFTERPLAY Portable/app/runtime/ffmpeg.exe',actual)
            archive.writestr('AFTERPLAY Portable/data/settings.json',b'unrelated')
        data=content.getvalue();urls=[]
        def download(url,destination):
            urls.append(url)
            if url==build.FFMPEG_URL:raise urllib.error.HTTPError(url,404,'Expired build',{},None)
            destination.write_bytes(data)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);runtime=root/'runtime';runtime.mkdir()
            with patch.object(build,'download',side_effect=download),patch.object(build,'FFMPEG_FALLBACK_SHA256','0'*64 if bad_archive else hashlib.sha256(data).hexdigest()),patch.object(build,'FFMPEG_EXE_SHA256',hashlib.sha256(expected).hexdigest()):
                build.install_ffmpeg(root,runtime)
            self.assertEqual((runtime/'ffmpeg.exe').read_bytes(),expected)
            self.assertEqual(sorted(p.name for p in runtime.iterdir()),['ffmpeg.exe'])
        self.assertEqual(urls,[build.FFMPEG_URL,build.FFMPEG_FALLBACK_URL])

    def test_expired_archive_uses_identical_verified_release_binary(self):self.fallback()

    def test_fallback_archive_must_match_its_pinned_digest(self):
        with self.assertRaisesRegex(ValueError,'fallback archive SHA-256'):self.fallback(bad_archive=True)

    def test_fallback_must_not_replace_the_pinned_executable(self):
        with self.assertRaisesRegex(ValueError,'executable SHA-256'):self.fallback(actual=b'other executable')
