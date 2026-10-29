"""Optional inputs keep their fixed tracks and reconnect without stopping video."""
from pathlib import Path
import queue
import tempfile
import unittest
from unittest.mock import Mock,patch
from app import Suite
from replay import Replay
from audio_tracks import AudioPackets

GAME={'pid':123,'path':r'C:\game.exe','name':'game.exe'}
MIC={'id':'7','name':'USB mic','default':True,'rate':48000,'channels':1}

class OptionalAudioTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.rec=Replay(Suite(Path(self.temp.name)/'data'))
        self.rec.settings.update(audio_mode='multitrack',microphone_enabled=True)
        self.chat=patch('process_audio.resolve_chat',side_effect=ValueError('not running')).start()
        self.microphone=Mock();self.microphone.is_active.return_value=True
        self.mic_opener=patch('microphone.OptionalInput',return_value=self.microphone).start()
        self.addCleanup(patch.stopall)
        self.device=self.rec._audio_device(GAME)
        self.rec._optional_audio=self.device['sources'][1:]
        self.addCleanup(self.close_sources)
    def close_sources(self):
        for source in self.rec._optional_audio:self.rec._close_optional_audio(source)
    def test_missing_sources_keep_tracks_in_recording_and_replay(self):
        for continuous in (False,True):
            self.rec.continuous=continuous
            with patch('microphone.devices',return_value=[]):self.rec._refresh_optional_audio()
            self.assertEqual(self.device['titles'],['Общий звук','Игра','Discord / чат','Микрофон'])
            self.assertFalse(self.rec.stop_event.is_set())
            import av
            from io import BytesIO
            with av.open(BytesIO(),mode='w',format='nut') as mux:
                packets=AudioPackets(mux,self.device,queue.Queue(),0,0)
                self.assertEqual(len(packets.streams),4)
                self.assertTrue(all(not any(block) for block in packets.read(1024)[1]))
    def test_late_chat_disconnect_and_relaunch_keep_same_queue(self):
        source=self.rec._optional_audio[0];original=source['queue']
        first=Mock(Error='',ReadPacket=Mock(return_value=None));second=Mock(Error='',ReadPacket=Mock(return_value=None))
        self.chat.side_effect=None;self.chat.return_value={'pid':456,'name':'Discord.exe','path':r'C:\Discord.exe'}
        with patch('microphone.devices',return_value=[]),patch('process_audio.open_capture',side_effect=[first,second]) as opener,patch('process_audio.is_alive',return_value=True) as alive:
            self.rec._refresh_optional_audio();self.assertIs(source['_capture'],first)
            alive.return_value=False;self.chat.return_value={'pid':789,'name':'Discord.exe','path':r'C:\Discord.exe'}
            self.rec._refresh_optional_audio();self.assertIs(source['_capture'],second)
            first.Dispose.assert_called_once();self.assertIs(source['queue'],original)
            self.assertEqual([call.args[0] for call in opener.call_args_list],[456,789])
    def test_muted_or_unplugged_microphone_does_not_reopen_or_stop_video(self):
        source=self.rec._optional_audio[1];original=source['queue']
        with patch('microphone.devices',side_effect=AssertionError('driver must stay out of recorder')):
            self.rec._refresh_optional_audio()
            self.microphone.error='device muted or unavailable'
            self.rec._refresh_optional_audio()
        self.mic_opener.assert_called_once()
        self.assertIs(source['_capture'],self.microphone);self.assertIs(source['queue'],original)
        self.assertFalse(self.rec.stop_event.is_set())
        self.microphone.close.assert_not_called()
    def test_dead_microphone_supervisor_is_replaced_without_stopping(self):
        self.rec._refresh_optional_audio()
        self.microphone.is_active.return_value=False
        self.rec._refresh_optional_audio()
        self.assertEqual(self.mic_opener.call_count,2)
        self.microphone.close.assert_called_once()
        self.assertFalse(self.rec.stop_event.is_set())
    def test_stop_does_not_open_new_optional_handles(self):
        self.rec.stop_event.set()
        with patch('microphone.devices') as devices:self.rec._refresh_optional_audio();devices.assert_not_called()
    def test_chat_closing_between_form_selection_and_start_keeps_saved_path(self):
        self.rec.settings.update(capture_mode='window',window_path=GAME['path'],window_pid=GAME['pid'],chat_path=r'C:\Discord.exe')
        with patch('process_audio.audio_applications',return_value=[]),patch('process_audio.supported',return_value=True):
            self.rec.configure({'chat_pid':456})
        self.assertEqual(self.rec.settings['chat_pid'],0)
        self.assertEqual(self.rec.settings['chat_path'],r'C:\Discord.exe')

if __name__=='__main__':unittest.main()
