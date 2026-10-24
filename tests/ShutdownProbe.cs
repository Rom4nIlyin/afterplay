using System;
using System.IO;
using System.Reflection;

class ShutdownProbe {
    static int Main(string[] args) {
        try {
            string home=Path.GetFullPath(args[0]);
            Environment.SetEnvironmentVariable("PATH",home+";"+Environment.GetEnvironmentVariable("PATH"));
            var assembly=Assembly.LoadFrom(Path.Combine(home,@"Lib\site-packages\pythonnet\runtime\Python.Runtime.dll"));
            var runtime=assembly.GetType("Python.Runtime.Runtime");
            var engine=assembly.GetType("Python.Runtime.PythonEngine");
            runtime.GetProperty("PythonDLL").SetValue(null,Path.Combine(home,"python313.dll"),null);
            engine.GetProperty("PythonHome").SetValue(null,home,null);
            engine.GetMethod("Initialize",Type.EmptyTypes).Invoke(null,null);
            using(var gil=(IDisposable)assembly.GetType("Python.Runtime.Py").GetMethod("GIL").Invoke(null,null)) {
                string code="from System import Action, Int32\ncallback = Action[Int32](lambda direction: None)\ncallback(1)\n";
                int result=(int)engine.GetMethod("RunSimpleString",new Type[]{typeof(string)}).Invoke(null,new object[]{code});
                if(result!=0)throw new Exception("Could not create the Python-backed Action<Int32> delegate");
            }
            if(args[1]=="baseline")engine.GetMethod("Shutdown",Type.EmptyTypes).Invoke(null,null);
            else RuntimeExit.Shutdown(assembly,engine);
            bool initialized=(bool)engine.GetProperty("IsInitialized").GetValue(null,null);
            Console.WriteLine("shutdown_complete; initialized="+initialized);
            return initialized?3:0;
        }catch(Exception error) {
            Console.WriteLine(error.GetBaseException().GetType().FullName+": "+error.GetBaseException().Message);
            return 2;
        }
    }
}
