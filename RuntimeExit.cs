using System;
using System.Reflection;

// The desktop host owns one interpreter for the entire process lifetime.
// Python.NET's normal soft shutdown stores CLR objects for an in-process reload.
// At final process exit that snapshot is unused and cannot serialize live Python
// delegates. Keep Python.NET's resource cleanup, but identify this as termination.
internal static class RuntimeExit {
    internal static void Shutdown(Assembly pythonRuntime, Type engine) {
        Type runtime=pythonRuntime.GetType("Python.Runtime.Runtime",true);
        FieldInfo terminating=runtime.GetField("ProcessIsTerminating",BindingFlags.Static|BindingFlags.NonPublic);
        if(terminating==null || terminating.FieldType!=typeof(bool))
            throw new NotSupportedException("Bundled Python.NET does not support process termination shutdown.");
        terminating.SetValue(null,true);
        engine.GetMethod("Shutdown",Type.EmptyTypes).Invoke(null,null);
    }
}
