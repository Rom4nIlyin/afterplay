using System;
using System.Drawing;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using Afterplay;
class ChromeProbe {
 [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr hwnd,int msg,IntPtr wp,IntPtr lp);
 static void Check(bool value,string detail) { if(!value)throw new Exception(detail); }
 static void Click(Control control) { typeof(Control).GetMethod("OnClick",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(control,new object[]{EventArgs.Empty});Application.DoEvents(); }
 [STAThread] static int Main() {
  try {
   using(var form=new Form { Width=1200,Height=800,MinimumSize=new Size(1050,700),FormBorderStyle=FormBorderStyle.None,Opacity=0,ShowInTaskbar=false }) {
    var browser=new Panel { Dock=DockStyle.Fill };form.Controls.Add(browser);form.Show();
    var chrome=WindowChrome.Attach(form);Application.DoEvents();var bar=form.Controls["AfterplayWindowBar"];
    Check(bar!=null && browser.Top>=bar.Bottom,"WebView overlaps title bar");
    chrome.Configure("#0d1517","#182327","#edf9f2","#96afa8","#8bf5c8","");
    var origin=form.Bounds;var screen=Screen.FromHandle(form.Handle).WorkingArea;
    Click(bar.Controls["WindowMaximize"]);
    Check(form.WindowState==FormWindowState.Maximized,"Maximize button failed");
    var client=new Rectangle(form.PointToScreen(System.Drawing.Point.Empty),form.ClientSize);
    Check(client==screen,"Maximized client covers taskbar or wrong screen: "+client+" expected "+screen);
    Click(bar.Controls["WindowMaximize"]);Check(form.WindowState==FormWindowState.Normal,"Restore button failed");
    Check(form.Bounds==origin,"Restore changed window bounds: "+form.Bounds+" expected "+origin);
    var point=form.PointToScreen(new Point(1,form.ClientSize.Height/2));long packed=((long)point.X&0xffffL)|(((long)point.Y&0xffffL)<<16);
    Check(SendMessage(form.Handle,0x0084,IntPtr.Zero,new IntPtr(packed)).ToInt32()==10,"Left resize hit failed");
    chrome.SetFullscreen(true);Application.DoEvents();Check(!bar.Visible,"Title bar visible in fullscreen");
    chrome.SetFullscreen(false);Application.DoEvents();Check(bar.Visible && browser.Top>=bar.Bottom,"Fullscreen restore lost chrome layout");
    Click(bar.Controls["WindowMinimize"]);Check(form.WindowState==FormWindowState.Minimized,"Minimize failed");form.WindowState=FormWindowState.Normal;
    bool closing=false;form.FormClosing+=delegate(object sender,FormClosingEventArgs e){closing=true;e.Cancel=true;form.Hide();};
    Click(bar.Controls["WindowClose"]);Check(closing&&!form.IsDisposed&&!form.Visible,"Close did not preserve tray closing event");
    Console.WriteLine("Native chrome: docking, maximize within work area, restore bounds, resize hit, fullscreen, minimize and tray close passed");
   }
   return 0;
  } catch(Exception error) { Console.WriteLine(error);return 1; }
 }
}
