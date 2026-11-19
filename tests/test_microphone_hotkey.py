"""Mic mute hotkey and per-app audio on Windows 10 2004+."""
import unittest
from unittest.mock import Mock,patch
import hotkeys
import microphone
import process_audio


class PerAppAudioWindowsTests(unittest.TestCase):
    def test_windows_10_2004_and_later_support_process_loopback(self):
        for build in (19041,19042,19043,19044,19045,20348,22000,26100):
            with self.subTest(build=build),patch('process_audio.windows_version',return_value=(10,0,build)):
                self.assertTrue(process_audio.supported())

    def test_windows_10_before_2004_stays_on_device_audio(self):
        for build in (17763,18362,18363):
            with self.subTest(build=build),patch('process_audio.windows_version',return_value=(10,0,build)):
                self.assertFalse(process_audio.supported())
                with self.assertRaisesRegex(ValueError,'2004'):process_audio.open_capture(123)


class MicrophoneHotkeyTests(unittest.TestCase):
    def setUp(self):self.addCleanup(microphone.MUTED.clear)

    def test_mic_shortcut_is_optional_and_must_be_unique(self):
        self.assertNotIn('mic',hotkeys.validate({}))
        self.assertEqual(hotkeys.validate({'mic':'ctrl+alt+m'})['mic'],'Ctrl+Alt+M')
        with self.assertRaises(ValueError):hotkeys.validate({'mic':'Ctrl+Alt+F10'})

    def recorder(self,enabled):
        from replay import Replay
        recorder=Replay.__new__(Replay)
        recorder.settings={'microphone_enabled':enabled};recorder._optional_audio=[]
        recorder.suite=Mock();recorder.suite.desktop=Mock()
        return recorder

    def test_toggle_mutes_and_unmutes_recorded_microphone(self):
        recorder=self.recorder(True)
        with patch('customization.sound'):
            self.assertTrue(recorder.toggle_microphone()['muted'])
            self.assertTrue(microphone.MUTED.is_set())
            self.assertTrue(recorder._microphone_status()['muted'])
            self.assertFalse(recorder.toggle_microphone()['muted'])
        self.assertFalse(microphone.MUTED.is_set())

    def test_toggle_without_profile_microphone_explains_instead_of_muting(self):
        recorder=self.recorder(False)
        self.assertFalse(recorder.toggle_microphone()['enabled'])
        self.assertFalse(microphone.MUTED.is_set())
        self.assertEqual(recorder.suite.desktop.notify.call_args.args[2],'error')

    def test_output_loopback_is_never_muted_by_the_mic_hotkey(self):
        from loopback import OptionalOutput
        microphone.MUTED.set()
        self.assertFalse(OptionalOutput._muted(Mock()))
        self.assertTrue(microphone.OptionalInput._muted(Mock()))


if __name__=='__main__':unittest.main()
