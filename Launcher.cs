using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Web.Script.Serialization;
using System.Windows.Forms;
[assembly:AssemblyTitle("AFTERPLAY")]
[assembly:AssemblyProduct("AFTERPLAY")]
[assembly:AssemblyDescription("AFTERPLAY — игровые моменты и мгновенный повтор")]
[assembly:AssemblyCompany("AFTERPLAY")]
[assembly:AssemblyVersion("1.8.3.0")]
[assembly:AssemblyFileVersion("1.8.3.0")]
class Launcher {
 [DllImport("WebView2Loader.dll",CharSet=CharSet.Unicode)] static extern int GetAvailableCoreWebView2BrowserVersionString(string folder,out IntPtr version);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode)] static extern IntPtr LoadLibrary(string path);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern IntPtr CreateFile(string path,uint access,uint share,IntPtr security,uint creation,uint flags,IntPtr template);
 [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool DeleteFile(string path);
 static bool HasWebView(string root) {
  string loader=Path.Combine(root,@"runtime\Lib\site-packages\webview\lib\runtimes\win-x64\native\WebView2Loader.dll");
  if(!File.Exists(loader))loader=Path.Combine(root,@"runtime\Lib\site-packages\webview\lib\win-x64\WebView2Loader.dll");
  if(LoadLibrary(loader)==IntPtr.Zero)throw new Exception("Не найден WebView2Loader. Распакуйте архив целиком.");
  IntPtr version;int result=GetAvailableCoreWebView2BrowserVersionString(null,out version);
  if(version!=IntPtr.Zero)Marshal.FreeCoTaskMem(version);return result>=0;
 }
 static void PrepareRuntime(string root) {
  string manifest=Path.Combine(root,"SHA256SUMS.json");
  if(!File.Exists(manifest))throw new Exception("Не найден SHA256SUMS.json. Распакуйте архив AFTERPLAY целиком.");
  var sums=new JavaScriptSerializer().Deserialize<System.Collections.Generic.Dictionary<string,string>>(File.ReadAllText(manifest));
  string[] components={"ProcessAudio.dll","ReplayNotification.dll","runtime/Lib/site-packages/pythonnet/runtime/Python.Runtime.dll","runtime/Lib/site-packages/webview/lib/Microsoft.Web.WebView2.Core.dll","runtime/Lib/site-packages/webview/lib/Microsoft.Web.WebView2.WinForms.dll","runtime/Lib/site-packages/webview/lib/WebBrowserInterop.x64.dll","runtime/Lib/site-packages/webview/lib/WebBrowserInterop.x86.dll"};
  var pending=new System.Collections.Generic.List<string>();
  foreach(string relative in components) {
   string path=Path.Combine(root,relative.Replace('/',Path.DirectorySeparatorChar));string zone=path+":Zone.Identifier";bool exists=false;
   IntPtr zoneHandle=CreateFile(zone,0x80000000,7,IntPtr.Zero,3,0,IntPtr.Zero);
   if(zoneHandle!=new IntPtr(-1)){exists=true;CloseHandle(zoneHandle);}
   else {int error=Marshal.GetLastWin32Error();if(error!=2&&error!=3)throw new System.ComponentModel.Win32Exception(error);}
   if(!exists)continue;string expected;
   if(!sums.TryGetValue(relative,out expected))throw new Exception("Компонент отсутствует в каталоге: "+relative);
   string actual;using(var sha=SHA256.Create())using(var stream=File.OpenRead(path))actual=BitConverter.ToString(sha.ComputeHash(stream)).Replace("-","").ToLowerInvariant();
   if(!String.Equals(actual,expected,StringComparison.OrdinalIgnoreCase))throw new Exception("Компонент AFTERPLAY изменён: "+relative);
   pending.Add(zone);
  }
  foreach(string zone in pending)if(!DeleteFile(zone))throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
 }
 [STAThread] static void Main(string[] args) {
  string root=AppDomain.CurrentDomain.BaseDirectory;
  try {
   if(!Environment.Is64BitOperatingSystem)throw new Exception("Требуется Windows x64.");
   if(!File.Exists(Path.Combine(root,"app.py")))throw new Exception("Не найден app.py. Сохраните папку программы целиком.");
   if(!HasWebView(root)) {
    string setup=Path.Combine(root,@"prerequisites\MicrosoftEdgeWebView2RuntimeInstallerX64.exe");
    if(!File.Exists(setup))throw new Exception("Установите WebView2 из папки prerequisites.");
    Application.EnableVisualStyles();
    using(var progress=new Form()) {
     progress.Text="AFTERPLAY — первый запуск";progress.Width=470;progress.Height=140;progress.StartPosition=FormStartPosition.CenterScreen;progress.ControlBox=false;
     progress.Controls.Add(new Label{Text="Установка Microsoft WebView2…\nЭто требуется один раз.",Dock=DockStyle.Fill,TextAlign=System.Drawing.ContentAlignment.MiddleCenter});progress.Show();Application.DoEvents();
     using(var install=Process.Start(new ProcessStartInfo(setup,"/silent /install"){UseShellExecute=false,CreateNoWindow=true,WindowStyle=ProcessWindowStyle.Hidden}))while(!install.WaitForExit(100))Application.DoEvents();
    }
    if(!HasWebView(root))throw new Exception("Не удалось установить WebView2.");
   }
   PrepareRuntime(root);
   Environment.SetEnvironmentVariable("PATH",Path.Combine(root,"runtime")+";"+Environment.GetEnvironmentVariable("PATH"));
   Environment.SetEnvironmentVariable("PYTHONNET_RUNTIME","netfx");
   var assembly=Assembly.LoadFrom(Path.Combine(root,@"runtime\Lib\site-packages\pythonnet\runtime\Python.Runtime.dll"));var engine=assembly.GetType("Python.Runtime.PythonEngine");
   assembly.GetType("Python.Runtime.Runtime").GetProperty("PythonDLL").SetValue(null,Path.Combine(root,@"runtime\python313.dll"),null);
   engine.GetProperty("PythonHome").SetValue(null,Path.Combine(root,"runtime"),null);engine.GetMethod("Initialize",Type.EmptyTypes).Invoke(null,null);
   var json=new JavaScriptSerializer();var gil=(IDisposable)assembly.GetType("Python.Runtime.Py").GetMethod("GIL").Invoke(null,null);int result;
   using(gil) {
    string code="import sys, os, runpy\nfrom pathlib import Path\nroot="+json.Serialize(root)+"\nsys.path.insert(0,root)\nos.chdir(root)\nsys.argv=[os.path.join(root,'app.py')]+"+json.Serialize(args)+"\nPath(root,'data','logs').mkdir(parents=True,exist_ok=True)\nsys.stdout=sys.stderr=open(Path(root,'data','logs','host.log'),'a',encoding='utf-8',buffering=1)\nrunpy.run_path(os.path.join(root,'app.py'),run_name='__main__')\n";
    result=(int)engine.GetMethod("RunSimpleString",new Type[]{typeof(string)}).Invoke(null,new object[]{code});
   }
   RuntimeExit.Shutdown(assembly,engine);
   if(result!=0)throw new Exception("Ошибка запуска. Подробности в data/logs/host.log.");
  }catch(Exception error) {
   try{File.WriteAllText(Path.Combine(root,"host-startup-error.log"),error.ToString());}catch{}
   MessageBox.Show(error.GetBaseException().Message,"AFTERPLAY",MessageBoxButtons.OK,MessageBoxIcon.Error);
  }
 }
}
