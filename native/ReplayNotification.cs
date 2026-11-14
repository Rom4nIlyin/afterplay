using System;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Windows.Forms;

[assembly:System.Reflection.AssemblyTitle("AFTERPLAY")]
[assembly:System.Reflection.AssemblyProduct("AFTERPLAY")]
[assembly:System.Reflection.AssemblyCompany("AFTERPLAY")]
[assembly:System.Reflection.AssemblyVersion("1.10.0.0")]
[assembly:System.Reflection.AssemblyFileVersion("1.10.0.0")]

namespace Afterplay {
    // A native title bar remains usable above browser dialogs and video editors.
    public sealed class WindowChrome : NativeWindow {
        [DllImport("user32.dll",EntryPoint="GetWindowLongW")] static extern int GetWindowLong(IntPtr hwnd,int index);
        [DllImport("user32.dll",EntryPoint="SetWindowLongW")] static extern int SetWindowLong(IntPtr hwnd,int index,int value);
        [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr hwnd,IntPtr after,int x,int y,int width,int height,uint flags);
        [DllImport("user32.dll")] static extern bool ReleaseCapture();
        [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr hwnd,int msg,IntPtr wp,IntPtr lp);
        [DllImport("user32.dll")] static extern IntPtr MonitorFromWindow(IntPtr hwnd,uint flags);
        [DllImport("user32.dll",CharSet=CharSet.Auto)] static extern bool GetMonitorInfo(IntPtr monitor,ref MonitorInfo info);
        [StructLayout(LayoutKind.Sequential)] struct Rect { public int Left,Top,Right,Bottom; }
        [StructLayout(LayoutKind.Sequential)] struct Point { public int X,Y; }
        [StructLayout(LayoutKind.Sequential)] struct MinMax { public Point Reserved,MaxSize,MaxPosition,MinTrack,MaxTrack; }
        [StructLayout(LayoutKind.Sequential,CharSet=CharSet.Auto)] struct MonitorInfo { public int Size;public Rect Monitor,Work;public uint Flags; }
        const int Frame=0x00C00000|0x00040000|0x00080000|0x00020000|0x00010000;
        readonly Form host;
        readonly ChromeBar bar;
        bool fullscreen,layoutBusy;
        WindowChrome(Form form) {
            host=form;AssignHandle(form.Handle);
            bar=new ChromeBar(form,this);bar.Dock=DockStyle.Top;host.Controls.Add(bar);bar.SendToBack();
            host.Resize+=delegate { LayoutFrame();bar.Invalidate(); };
            host.Activated+=delegate { bar.Active=true;bar.Invalidate(); };
            host.Deactivate+=delegate { bar.Active=false;bar.Invalidate(); };
            Rectangle initial=host.Bounds;ApplyFrame();host.Bounds=initial;LayoutFrame();
        }
        public static WindowChrome Attach(Form form) { return new WindowChrome(form); }
        void ApplyFrame() {
            int style=GetWindowLong(host.Handle,-16);
            SetWindowLong(host.Handle,-16,fullscreen?style&~Frame:style|Frame);
            SetWindowPos(host.Handle,IntPtr.Zero,0,0,0,0,0x0001|0x0002|0x0004|0x0020|0x0010);
        }
        void LayoutFrame() {
            if(layoutBusy)return;layoutBusy=true;
            try {
                int edge=fullscreen||host.WindowState==FormWindowState.Maximized?0:Math.Max(4,(int)(5*host.DeviceDpi/96f));
                host.Padding=new Padding(edge);bar.Height=(int)(34*host.DeviceDpi/96f);bar.Visible=!fullscreen;
            } finally { layoutBusy=false; }
        }
        public void SetFullscreen(bool value) { fullscreen=value;ApplyFrame();LayoutFrame(); }
        public void Configure(string background,string panel,string text,string muted,string accent,string status) {
            bar.Configure(background,panel,text,muted,accent,status);host.BackColor=ColorTranslator.FromHtml(background);
        }
        public void BeginMove(int edge) {
            if(fullscreen)return;
            ReleaseCapture();Point p=new Point { X=Cursor.Position.X,Y=Cursor.Position.Y };
            long packed=((long)p.X&0xffffL)|(((long)p.Y&0xffffL)<<16);
            SendMessage(host.Handle,0x00A1,new IntPtr(edge),new IntPtr(packed));
        }
        protected override void WndProc(ref Message message) {
            if(message.Msg==0x0083 && !fullscreen) {
                if((GetWindowLong(host.Handle,-16)&0x01000000)!=0) {
                    var area=new MonitorInfo();area.Size=Marshal.SizeOf(typeof(MonitorInfo));
                    if(GetMonitorInfo(MonitorFromWindow(host.Handle,2),ref area))Marshal.StructureToPtr(area.Work,message.LParam,false);
                }
                message.Result=IntPtr.Zero;return;
            }
            base.WndProc(ref message);
            if(message.Msg==0x0084 && !fullscreen && host.WindowState==FormWindowState.Normal) {
                long packed=message.LParam.ToInt64();var p=host.PointToClient(new System.Drawing.Point((short)(packed&0xffff),(short)((packed>>16)&0xffff)));
                int edge=host.Padding.Left,w=host.ClientSize.Width,h=host.ClientSize.Height;
                int hit=p.Y<edge?(p.X<edge?13:p.X>=w-edge?14:12):p.Y>=h-edge?(p.X<edge?16:p.X>=w-edge?17:15):p.X<edge?10:p.X>=w-edge?11:1;
                message.Result=new IntPtr(hit);
            }
            if(message.Msg==0x0024 && !fullscreen) {
                var monitor=new MonitorInfo();monitor.Size=Marshal.SizeOf(typeof(MonitorInfo));
                if(GetMonitorInfo(MonitorFromWindow(host.Handle,2),ref monitor)) {
                    var bounds=(MinMax)Marshal.PtrToStructure(message.LParam,typeof(MinMax));
                    bounds.MaxPosition.X=monitor.Work.Left-monitor.Monitor.Left;bounds.MaxPosition.Y=monitor.Work.Top-monitor.Monitor.Top;
                    bounds.MaxSize.X=monitor.Work.Right-monitor.Work.Left;bounds.MaxSize.Y=monitor.Work.Bottom-monitor.Work.Top;
                    Marshal.StructureToPtr(bounds,message.LParam,false);
                }
            }
        }
    }
    internal sealed class ChromeBar : Panel {
        readonly Form host;readonly WindowChrome chrome;readonly ChromeButton minimize,maximize,close;
        readonly Font titleFont=new Font("Segoe UI",10,FontStyle.Bold,GraphicsUnit.Pixel);
        readonly Font statusFont=new Font("Segoe UI",10,FontStyle.Regular,GraphicsUnit.Pixel);
        Color background=Color.FromArgb(13,20,21),panel=Color.FromArgb(21,30,32),ink=Color.FromArgb(236,244,242),muted=Color.FromArgb(143,166,160),accent=Color.FromArgb(139,245,200);
        string status="";public bool Active=true;
        public ChromeBar(Form form,WindowChrome owner) {
            host=form;chrome=owner;DoubleBuffered=true;TabStop=false;Name="AfterplayWindowBar";
            minimize=new ChromeButton(this,0);maximize=new ChromeButton(this,1);close=new ChromeButton(this,2);
            Controls.AddRange(new Control[]{minimize,maximize,close});
            minimize.Click+=delegate { host.WindowState=FormWindowState.Minimized; };
            maximize.Click+=delegate { ToggleMaximize(); };close.Click+=delegate { host.Close(); };
            Resize+=delegate { LayoutButtons(); };
            MouseDown+=delegate(object sender,MouseEventArgs e) { if(e.Button==MouseButtons.Left && e.Clicks==1)chrome.BeginMove(2); };
            MouseDoubleClick+=delegate(object sender,MouseEventArgs e) { if(e.Button==MouseButtons.Left)ToggleMaximize(); };
            AccessibleName="AFTERPLAY";
        }
        public void ToggleMaximize() { host.WindowState=host.WindowState==FormWindowState.Maximized?FormWindowState.Normal:FormWindowState.Maximized; }
        void LayoutButtons() {
            int width=(int)(44*DeviceDpi/96f);
            minimize.Bounds=new Rectangle(Width-width*3,0,width,Height);maximize.Bounds=new Rectangle(Width-width*2,0,width,Height);close.Bounds=new Rectangle(Width-width,0,width,Height);
            minimize.Invalidate();maximize.Invalidate();close.Invalidate();
        }
        public void Configure(string bg,string surface,string text,string secondary,string highlight,string detail) {
            background=ColorTranslator.FromHtml(bg);panel=ColorTranslator.FromHtml(surface);ink=ColorTranslator.FromHtml(text);muted=ColorTranslator.FromHtml(secondary);accent=ColorTranslator.FromHtml(highlight);status=detail;
            BackColor=background;Invalidate(true);
        }
        protected override void OnPaint(PaintEventArgs e) {
            float scale=DeviceDpi/96f;var g=e.Graphics;g.ScaleTransform(scale,scale);float width=Width/scale,height=Height/scale;
            using(var fill=new System.Drawing.Drawing2D.LinearGradientBrush(new PointF(0,0),new PointF(width,height),panel,background))g.FillRectangle(fill,0,0,width,height);
            using(var line=new Pen(Color.FromArgb(48,accent)))g.DrawLine(line,0,height-1,width,height-1);
            g.SmoothingMode=System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
            using(var brush=new SolidBrush(Active?accent:muted)) {
                g.FillPolygon(brush,new PointF[]{new PointF(15,11),new PointF(21,7),new PointF(27,11),new PointF(27,18),new PointF(21,22),new PointF(15,18)});
            }
            using(var cut=new SolidBrush(background))g.FillPolygon(cut,new PointF[]{new PointF(19,11),new PointF(25,15),new PointF(19,19)});
            using(var brush=new SolidBrush(Active?ink:muted))g.DrawString("AFTERPLAY",titleFont,brush,36,9);
            if(!String.IsNullOrEmpty(status)) {
                using(var brush=new SolidBrush(Color.FromArgb(240,133,129)))g.FillEllipse(brush,width-304,14,5,5);
                using(var brush=new SolidBrush(muted))g.DrawString(status,statusFont,brush,new RectangleF(width-291,9,145,18));
            }
            LayoutButtons();
        }
        internal sealed class ChromeButton : Control {
            readonly ChromeBar bar;readonly int kind;bool hover;
            public ChromeButton(ChromeBar parent,int type) {
                bar=parent;kind=type;DoubleBuffered=true;TabStop=true;Cursor=Cursors.Default;
                Name=type==0?"WindowMinimize":type==1?"WindowMaximize":"WindowClose";
                AccessibleRole=AccessibleRole.PushButton;AccessibleName=type==0?"Свернуть":type==1?"Развернуть или восстановить":"Закрыть";
                MouseEnter+=delegate { hover=true;Invalidate(); };MouseLeave+=delegate { hover=false;Invalidate(); };
                SetStyle(ControlStyles.Selectable,true);
            }
            protected override void OnKeyDown(KeyEventArgs e) { base.OnKeyDown(e);if(e.KeyCode==Keys.Enter||e.KeyCode==Keys.Space){e.Handled=true;OnClick(EventArgs.Empty);} }
            protected override void OnPaint(PaintEventArgs e) {
                var g=e.Graphics;g.Clear(bar.background);float s=DeviceDpi/96f;g.ScaleTransform(s,s);float x=Width/s/2,y=Height/s/2;
                if(hover)using(var fill=new SolidBrush(kind==2?Color.FromArgb(190,56,70):Color.FromArgb(24,bar.accent)))g.FillRectangle(fill,0,0,Width/s,Height/s);
                using(var pen=new Pen(hover&&kind==2?Color.White:bar.Active?bar.ink:bar.muted,1.1f)) {
                    if(kind==0)g.DrawLine(pen,x-5,y+2,x+5,y+2);
                    else if(kind==2){g.DrawLine(pen,x-4,y-4,x+4,y+4);g.DrawLine(pen,x+4,y-4,x-4,y+4);}
                    else if(bar.host.WindowState==FormWindowState.Maximized){g.DrawRectangle(pen,x-2,y-5,8,8);using(var b=new SolidBrush(bar.background))g.FillRectangle(b,x-5,y-2,8,8);g.DrawRectangle(pen,x-5,y-2,8,8);}
                    else g.DrawRectangle(pen,x-4,y-4,8,8);
                }
                if(Focused)using(var pen=new Pen(bar.accent))g.DrawRectangle(pen,4,4,Width/s-9,Height/s-9);
            }
        }
        protected override void Dispose(bool disposing) { if(disposing){titleFont.Dispose();statusFont.Dispose();}base.Dispose(disposing); }
    }
    // A local WinForms message filter, active only inside this application's form.
    // It does not register a system mouse hook or observe other applications.
    public sealed class DesktopNavigation : IMessageFilter {
        private readonly Form host;
        private readonly Action<int> navigate;
        private DesktopNavigation(Form form, Action<int> action) { host=form; navigate=action; }
        public static DesktopNavigation Attach(Form form, Action<int> action) {
            var filter=new DesktopNavigation(form,action);
            Application.AddMessageFilter(filter);
            form.FormClosed += delegate { Application.RemoveMessageFilter(filter); };
            return filter;
        }
        public bool PreFilterMessage(ref Message message) {
            Control control=Control.FromChildHandle(message.HWnd);
            if(control==null || control.FindForm()!=host)return false;
            int direction=0;bool invoke=true;
            if(message.Msg==0x0319) {
                int command=(int)((message.LParam.ToInt64()>>16)&0xfff);
                if(command==1)direction=-1;else if(command==2)direction=1;
            } else if(message.Msg==0x020B || message.Msg==0x020C) {
                int button=(int)((message.WParam.ToInt64()>>16)&0xffff);
                if(button==1)direction=-1;else if(button==2)direction=1;
                invoke=message.Msg==0x020C;
            } else if(message.Msg==0x0100 || message.Msg==0x0101) {
                int key=message.WParam.ToInt32();
                if(key==0xA6)direction=-1;else if(key==0xA7)direction=1;
                invoke=message.Msg==0x0101;
            }
            if(direction==0)return false;
            if(invoke)navigate(direction);
            return true;
        }
    }

    public static class ReplayNotifications {
        private static ReplayNotice current;
        private static string position="top-right", cover="";
        private static double size=1,opacity=.96;
        private static int duration=4500;
        public static void Configure(string corner,double scale,double alpha,int milliseconds,string image) {
            position=corner;size=scale;opacity=alpha;duration=milliseconds;cover=image;
        }
        public static bool Visible { get { return current != null && !current.IsDisposed && current.Visible; } }
        public static IntPtr WindowHandle { get { return Visible ? current.Handle : IntPtr.Zero; } }
        public static string CurrentTitle { get { return Visible ? current.Heading : ""; } }
        public static void Show(string title, string message, string kind) {
            if (current == null || current.IsDisposed) current = new ReplayNotice();
            current.Configure(position,size,opacity,duration,cover);
            current.Display(title, message, kind);
        }
        public static void Close() {
            if (current != null && !current.IsDisposed) current.Close();
            current = null;
        }
    }

    internal sealed class ReplayNotice : Form {
        [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr hwnd, IntPtr after, int x, int y, int w, int h, uint flags);
        private readonly Timer lifetime = new Timer();
        private readonly Font headingFont = new Font("Segoe UI", 15, FontStyle.Bold, GraphicsUnit.Pixel);
        private readonly Font messageFont = new Font("Segoe UI", 12, FontStyle.Regular, GraphicsUnit.Pixel);
        private string message = "", kind = "";
        private string corner="top-right";
        private float customScale=1;
        private int duration=4500;
        private Image thumbnail;
        public string Heading = "";
        protected override bool ShowWithoutActivation { get { return true; } }
        protected override CreateParams CreateParams {
            get {
                CreateParams p = base.CreateParams;
                // A non-activating, click-through tool window; no extra taskbar button.
                p.ExStyle |= 0x08000000 | 0x00000080 | 0x00000020;
                return p;
            }
        }
        public ReplayNotice() {
            Text = "AFTERPLAY — уведомление";
            FormBorderStyle = FormBorderStyle.None;
            ShowInTaskbar = false;
            TopMost = true;
            StartPosition = FormStartPosition.Manual;
            AutoScaleMode = AutoScaleMode.Dpi;
            BackColor = Color.FromArgb(22, 31, 29);
            Opacity = 0.98;
            DoubleBuffered = true;
            lifetime.Tick += delegate { lifetime.Stop(); Close(); };
        }
        public void Configure(string position,double scale,double alpha,int milliseconds,string image) {
            corner=position;customScale=(float)Math.Max(.75,Math.Min(1.4,scale));
            Opacity=Math.Max(.35,Math.Min(1,alpha));duration=Math.Max(1000,Math.Min(15000,milliseconds));
            if(thumbnail!=null){thumbnail.Dispose();thumbnail=null;}
            try { if(!String.IsNullOrEmpty(image))using(var source=Image.FromFile(image))thumbnail=new Bitmap(source); } catch {}
        }
        public void Display(string title, string detail, string status) {
            Heading = title; message = detail; kind = status;
            Rectangle area = Screen.FromHandle(GetForegroundWindow()).WorkingArea;
            float scale = DeviceDpi / 96f * customScale;
            Size = new Size((int)(410 * scale), (int)(94 * scale));
            int margin = (int)(20 * scale);
            Location = new Point(corner.EndsWith("left")?area.Left+margin:area.Right-Width-margin,
                                 corner.StartsWith("bottom")?area.Bottom-Height-margin:area.Top+margin);
            lifetime.Stop();
            lifetime.Interval = duration;
            Invalidate();
            Show();
            SetWindowPos(Handle, new IntPtr(-1), Left, Top, Width, Height, 0x0010 | 0x0040);
            lifetime.Start();
        }
        protected override void OnPaint(PaintEventArgs e) {
            base.OnPaint(e);
            Graphics g = e.Graphics;
            float s = DeviceDpi / 96f * customScale;
            g.ScaleTransform(s, s);
            g.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
            Color accent = kind == "error" ? Color.FromArgb(242, 120, 112) : Color.FromArgb(143, 201, 196);
            using (Pen edge = new Pen(Color.FromArgb(61, 79, 73))) g.DrawRectangle(edge, 0, 0, 410 - 1, 94 - 1);
            using (SolidBrush strip = new SolidBrush(accent)) g.FillRectangle(strip, 0, 0, 4, 94);
            if(thumbnail!=null)g.DrawImage(thumbnail,new Rectangle(16,29,40,36));
            if(thumbnail==null) {
            using (Pen pen = new Pen(accent, 2.4f)) {
                g.DrawEllipse(pen, 20, 30, 30, 30);
                if (kind == "success") g.DrawLines(pen, new PointF[] { new PointF(28,45), new PointF(33,50), new PointF(43,39) });
                else if (kind == "error") { g.DrawLine(pen, 35,37,35,47); g.DrawEllipse(pen,34,52,2,2); }
                else { g.DrawLine(pen,35,36,35,45); g.DrawLine(pen,35,45,42,49); }
            }
            }
            using (StringFormat format = new StringFormat()) {
                format.Trimming = StringTrimming.EllipsisCharacter;
                format.FormatFlags = StringFormatFlags.NoWrap;
                using (SolidBrush ink = new SolidBrush(Color.FromArgb(235, 242, 239)))
                    g.DrawString(Heading, headingFont, ink, new RectangleF(66, 21, 326, 25), format);
                using (SolidBrush ink = new SolidBrush(Color.FromArgb(172, 190, 182)))
                    g.DrawString(message, messageFont, ink, new RectangleF(66, 51, 326, 23), format);
            }
        }
        protected override void Dispose(bool disposing) {
            if (disposing) { lifetime.Dispose(); headingFont.Dispose(); messageFont.Dispose(); if(thumbnail!=null)thumbnail.Dispose(); }
            base.Dispose(disposing);
        }
    }
}
