"""Native .NET-hosted Python regression, including the former crashing path."""
from pathlib import Path
import os,subprocess,sys,tempfile,unittest

@unittest.skipUnless(os.name=='nt','Windows .NET desktop host')
class RuntimeExitTests(unittest.TestCase):
    def test_bound_python_delegate_reproduces_soft_shutdown_error_and_exits_cleanly(self):
        root=Path(__file__).resolve().parents[1]
        # Embedded release runtime locally; official Python + installed wheel on CI.
        runtime=Path(sys.executable).parent
        if not (runtime/'python313.dll').is_file():self.skipTest('Python 3.13 x64 runtime required')
        candidates=[runtime/'Lib/site-packages/pythonnet/runtime/Python.Runtime.dll']
        if not any(p.is_file() for p in candidates):self.skipTest('Python.NET runtime required')
        with tempfile.TemporaryDirectory() as temp:
            executable=Path(temp)/'ShutdownProbe.exe'
            compiler=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
            built=subprocess.run([str(compiler),'/nologo','/platform:x64','/out:'+str(executable),str(root/'RuntimeExit.cs'),str(root/'tests/ShutdownProbe.cs')],capture_output=True,timeout=30)
            self.assertEqual(built.returncode,0,built.stdout+built.stderr)
            baseline=subprocess.run([str(executable),str(runtime),'baseline'],capture_output=True,timeout=30)
            self.assertEqual(baseline.returncode,2,baseline.stdout+baseline.stderr)
            self.assertIn(b'SerializationException',baseline.stdout)
            fixed=subprocess.run([str(executable),str(runtime),'terminate'],capture_output=True,timeout=30)
            self.assertEqual(fixed.returncode,0,fixed.stdout+fixed.stderr)
            self.assertIn(b'initialized=False',fixed.stdout)
