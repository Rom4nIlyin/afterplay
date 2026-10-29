"""Real child-process failures cannot block the recorder or its audio clock."""
from pathlib import Path
import queue
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import microphone

FIXTURE=Path(__file__).with_name('MicrophoneWorkerFixture.py')


class MicrophoneIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.phase=Path(self.temp.name)/'phase';self.phase.write_text('voice','utf-8')
        self.output=queue.Queue(maxsize=256)
        self.command=patch.object(microphone.OptionalInput,'_command',return_value=[sys.executable,'-u',str(FIXTURE),str(self.phase)])
        self.command.start();self.addCleanup(self.command.stop)
        self.timeout=patch.object(microphone.OptionalInput,'HEARTBEAT_TIMEOUT',.8);self.timeout.start();self.addCleanup(self.timeout.stop)
        self.retry=patch.object(microphone.OptionalInput,'RETRY_SECONDS',.05);self.retry.start();self.addCleanup(self.retry.stop)
        self.worker=None;self.addCleanup(lambda:self.worker and self.worker.close())

    def start(self):
        started=time.monotonic();self.worker=microphone.OptionalInput({},self.output)
        self.assertLess(time.monotonic()-started,.2)

    def sample(self,value,timeout=4):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            try:stamp,data=self.output.get(timeout=.1)
            except queue.Empty:continue
            self.assertGreater(stamp,0)
            if struct.unpack_from('<f',data)[0]==value:return
        self.fail('Expected microphone sample was not received; '+str(self.worker.error))

    def test_mute_no_callbacks_and_unplug_stay_active_and_recover(self):
        self.start();self.sample(.125)
        self.phase.write_text('mute','utf-8');self.sample(0.)
        self.phase.write_text('no_callbacks','utf-8');time.sleep(.15)
        while not self.output.empty():self.output.get_nowait()
        with self.assertRaises(queue.Empty):self.output.get(timeout=.15)
        self.assertTrue(self.worker.is_active())
        self.phase.write_text('unavailable','utf-8')
        deadline=time.monotonic()+2
        while not self.worker.error and time.monotonic()<deadline:time.sleep(.02)
        self.assertEqual(self.worker.error,'device missing');self.assertTrue(self.worker.is_active())
        self.phase.write_text('voice','utf-8');self.sample(.125)

    def test_hung_driver_starts_without_waiting_and_is_restarted(self):
        self.phase.write_text('hang','utf-8');self.start()
        deadline=time.monotonic()+2
        while self.worker.process is None and time.monotonic()<deadline:time.sleep(.01)
        first=self.worker.process;self.assertIsNotNone(first)
        time.sleep(1.1);self.phase.write_text('voice','utf-8');self.sample(.125)
        self.assertIsNot(self.worker.process,first)
        self.assertIsNotNone(first.poll());self.assertTrue(self.worker.is_active())

    def test_crashed_worker_recovers_and_close_drains_tail(self):
        self.phase.write_text('crash','utf-8');self.start();time.sleep(.3)
        self.phase.write_text('voice','utf-8');self.sample(.125)
        process=self.worker.process;self.worker.close()
        self.sample(.75)
        self.assertIsNotNone(process.poll());self.assertFalse(self.worker.is_active())
        self.assertFalse(self.worker.thread.is_alive())

    def test_production_worker_imports_native_modules_and_closes_on_eof(self):
        command=[sys.executable,'-u',str(FIXTURE.with_name('MicrophoneNativeImportProbe.py')),str(Path(microphone.__file__).parent)]
        with patch.object(microphone.OptionalInput,'_command',return_value=command),patch.object(microphone.OptionalInput,'HEARTBEAT_TIMEOUT',4):
            self.start();self.sample(0.)
            process=self.worker.process;self.worker.close()
        self.assertIsNotNone(process.poll());self.assertFalse(self.worker.thread.is_alive())

    @unittest.skipUnless(sys.platform=='win32','Windows worker job lifetime')
    def test_worker_is_killed_if_recorder_process_exits_abruptly(self):
        self.phase.write_text('hang','utf-8');pid_file=Path(self.temp.name)/'pid'
        source="""
import os,sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from microphone import OptionalInput
import queue
OptionalInput._command=lambda self:[sys.executable,'-u',sys.argv[2],sys.argv[3]]
w=OptionalInput({},queue.Queue())
for _ in range(200):
 if w.process is not None:break
 time.sleep(.01)
if w.process is None:raise RuntimeError(w.error)
Path(sys.argv[4]).write_text(str(w.process.pid))
os._exit(0)
"""
        result=subprocess.run([sys.executable,'-c',source,str(Path(microphone.__file__).parent),str(FIXTURE),str(self.phase),str(pid_file)],capture_output=True,timeout=8)
        self.assertEqual(result.returncode,0,result.stderr)
        import process_audio
        pid=int(pid_file.read_text());deadline=time.monotonic()+2
        while process_audio.is_alive(pid) and time.monotonic()<deadline:time.sleep(.05)
        self.assertFalse(process_audio.is_alive(pid),'Microphone worker outlived recorder')


if __name__=='__main__':unittest.main()
