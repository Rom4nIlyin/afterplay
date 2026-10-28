import sys,threading,time,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from export_control import ExportControl,ExportCancelled
from app import Suite

class CancellationTests(unittest.TestCase):
    def test_portable_builder_includes_required_cancellation_module(self):
        import ast
        tree=ast.parse((Path(__file__).resolve().parents[1]/'scripts/build_portable.py').read_text('utf-8'))
        files=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='FILES' for target in node.targets))
        self.assertIn('export_control.py',files)

    def test_cancel_before_spawn_never_starts_process(self):
        control=ExportControl({});self.assertTrue(control.cancel())
        with patch('export_control.subprocess.Popen') as spawn:
            with self.assertRaises(ExportCancelled):control.start(['not-a-real-command'])
            spawn.assert_not_called()

    def test_cancel_terminates_only_owned_process_and_is_repeatable(self):
        own=Mock();own.poll.side_effect=lambda:0 if own.terminate.called else None
        other=Mock();control=ExportControl({})
        with patch('export_control.subprocess.Popen',return_value=own):control.start(['owned'])
        self.assertTrue(control.cancel());self.assertTrue(control.cancel())
        own.terminate.assert_called_once();other.terminate.assert_not_called()

    def test_committed_output_cannot_be_reported_as_cancelled(self):
        control=ExportControl({});control.commit()
        self.assertFalse(control.cancel());self.assertFalse(control.cancelled.is_set())

    def test_commit_cancel_race_has_exactly_one_winner(self):
        for _ in range(150):
            control=ExportControl({});gate=threading.Barrier(2);outcome={}
            def finish():
                gate.wait()
                try:control.commit();outcome['committed']=True
                except ExportCancelled:outcome['committed']=False
            thread=threading.Thread(target=finish);thread.start();gate.wait()
            outcome['cancelled']=control.cancel();thread.join(timeout=2)
            self.assertFalse(thread.is_alive());self.assertNotEqual(outcome['cancelled'],outcome['committed'])

    def test_job_cancellation_has_no_result_and_no_success_or_error_sound(self):
        with tempfile.TemporaryDirectory() as temp,patch('customization.sound') as sound:
            suite=Suite(Path(temp));entered=threading.Event();release=threading.Event()
            def work(job):
                entered.set();release.wait(3);suite.export_controls[job['id']].check();return {'unexpected':True}
            identifier=suite.job('Экспорт видео',work,cancellable=True)['job'];self.assertTrue(entered.wait(2))
            self.assertTrue(suite.cancel_export(identifier)['accepted']);release.set()
            deadline=time.monotonic()+3
            while suite.jobs[identifier]['status']=='running' and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(suite.jobs[identifier]['status'],'cancelled');self.assertNotIn('result',suite.jobs[identifier]);sound.assert_not_called()
            self.assertFalse(suite.cancel_export(identifier)['accepted']);suite.shutdown()

    def test_cancel_rejects_other_jobs_and_unknown_identifiers(self):
        with tempfile.TemporaryDirectory() as temp:
            suite=Suite(Path(temp));entered=threading.Event();release=threading.Event()
            identifier=suite.job('Проверка',lambda job:(entered.set(),release.wait(2)))['job'];self.assertTrue(entered.wait(2))
            with self.assertRaises(ValueError):suite.cancel_export(identifier)
            with self.assertRaises(ValueError):suite.cancel_export('not-a-job')
            release.set();suite.shutdown()

if __name__=='__main__':unittest.main()
