"""Process-loopback COM lifetime and preservation of activation diagnostics."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import wave
from types import SimpleNamespace
from unittest.mock import Mock, patch
import process_audio
from concurrent.futures import ThreadPoolExecutor


class ProcessAudioErrors(unittest.TestCase):
    def test_original_start_error_survives_failed_legacy_cleanup(self):
        original=RuntimeError('activation failed')
        capture=Mock();capture.Start.side_effect=original
        capture.Dispose.side_effect=RuntimeError('cleanup failed')
        module=SimpleNamespace(ProcessCapture=Mock(return_value=capture))
        with patch('process_audio.supported',return_value=True),patch('clr.AddReference'),patch.dict('sys.modules',{'AfterplayAudio':module}):
            with self.assertRaises(RuntimeError) as raised:process_audio.open_capture(123)
        self.assertIs(raised.exception,original)
        capture.Dispose.assert_called_once()

    @unittest.skipUnless(os.name=='nt','Windows process enumeration')
    def test_ui_and_watcher_can_enumerate_processes_concurrently(self):
        def read(_):
            version=process_audio.windows_version()
            rows=process_audio.audio_applications()
            return version, isinstance(rows,list)
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(read,range(32)))
        self.assertTrue(all(version[0]>=6 and valid for version,valid in results))


@unittest.skipUnless(os.name=='nt','Windows COM lifetime')
class NativeProcessAudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        source=Path(__file__).resolve().parents[1]
        cls.exe=cls.root/'ProcessAudioProbe.exe'
        compiler=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        subprocess.run([str(compiler),'/nologo','/platform:x64','/out:'+str(cls.exe),str(source/'ProcessAudio.cs'),str(source/'tests/ProcessAudioProbe.cs')],check=True,capture_output=True,timeout=30)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_dispose_before_start_is_idempotent(self):
        result=subprocess.run([str(self.exe)],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    @unittest.skipUnless(os.environ.get('AFTERPLAY_TEST_PROCESS_AUDIO')=='1','Set AFTERPLAY_TEST_PROCESS_AUDIO=1 on Windows with a running audio service')
    def test_sta_mta_repeated_capture_and_foreign_thread_disposal(self):
        # Render silence, never record the user's microphone or desktop audio.
        path=self.root/'silence.wav'
        with wave.open(str(path),'wb') as media:
            media.setnchannels(2);media.setsampwidth(2);media.setframerate(48000)
            media.writeframes(b'\0'*(48000*2*2))
        result=subprocess.run([str(self.exe),str(path)],capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(result.stdout.count('OK '),12,result.stdout)


if __name__=='__main__':unittest.main()
