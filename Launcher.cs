using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;
using System.Runtime.InteropServices;
class Launcher {
    [DllImport("WebView2Loader.dll", CharSet=CharSet.Unicode)]
    static extern int GetAvailableCoreWebView2BrowserVersionString(string folder, out IntPtr version);
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode)]
    static extern IntPtr LoadLibrary(string path);
    static bool HasWebView(string root) {
        string loader = Path.Combine(root, "runtime", "Lib", "site-packages", "webview", "lib", "runtimes", "win-x64", "native", "WebView2Loader.dll");
        if (!File.Exists(loader)) loader = Path.Combine(root, "runtime", "Lib", "site-packages", "webview", "lib", "win-x64", "WebView2Loader.dll");
        if (LoadLibrary(loader)==IntPtr.Zero) throw new Exception("Не найден компонент WebView2Loader. Распакуйте архив целиком.");
        IntPtr version; int result=GetAvailableCoreWebView2BrowserVersionString(null,out version);
        if(version!=IntPtr.Zero)Marshal.FreeCoTaskMem(version);
        return result>=0;
    }
    [STAThread] static void Main(string[] args) {
        try {
            string root = AppDomain.CurrentDomain.BaseDirectory;
            string python = Path.Combine(root, "runtime", "pythonw.exe");
            if(!File.Exists(python)) python = Path.Combine(root, "runtime", "Scripts", "pythonw.exe");
            string script = Path.Combine(root, "app.py");
            if (!File.Exists(python) || !File.Exists(script))
                throw new Exception("Не найдены runtime или app.py. Сохраните папку приложения целиком.");
            if(!Environment.Is64BitOperatingSystem) throw new Exception("Требуется Windows 10/11 x64.");
            if(!HasWebView(root)) {
                string setup=Path.Combine(root,"prerequisites","MicrosoftEdgeWebView2RuntimeInstallerX64.exe");
                if(!File.Exists(setup)) throw new Exception("Отсутствует WebView2. Запустите установщик из папки prerequisites.");
                Application.EnableVisualStyles();
                using(var progress=new Form()) {
                    progress.Text="Game Clips — первый запуск";progress.Width=470;progress.Height=140;
                    progress.StartPosition=FormStartPosition.CenterScreen; progress.ControlBox=false;
                    progress.Controls.Add(new Label { Text="Установка Microsoft WebView2…\nЭто требуется один раз. Подождите.", Dock=DockStyle.Fill, TextAlign=System.Drawing.ContentAlignment.MiddleCenter });
                    progress.Show(); Application.DoEvents();
                    using(var install=Process.Start(new ProcessStartInfo(setup,"/silent /install") { UseShellExecute=false,CreateNoWindow=true,WindowStyle=ProcessWindowStyle.Hidden })) {
                        while(!install.WaitForExit(100))Application.DoEvents();
                    }
                    progress.Close();
                }
                if(!HasWebView(root))throw new Exception("Не удалось установить WebView2. Запустите установщик из prerequisites вручную и повторите запуск.");
            }
            string mode = "clips";
            string check = Array.IndexOf(args, "--smoke") >= 0 ? " --smoke" : "";
            Process.Start(new ProcessStartInfo(python, "\"" + script + "\" --mode " + mode + check) {
                WorkingDirectory = root, UseShellExecute = false, CreateNoWindow = true,
                WindowStyle = ProcessWindowStyle.Hidden
            });
        } catch(Exception e) { MessageBox.Show(e.Message, "Game Clips", MessageBoxButtons.OK, MessageBoxIcon.Error); }
    }
}
