using System;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Windows.Forms;

[assembly:System.Reflection.AssemblyTitle("AFTERPLAY")]
[assembly:System.Reflection.AssemblyProduct("AFTERPLAY")]
[assembly:System.Reflection.AssemblyCompany("AFTERPLAY")]
[assembly:System.Reflection.AssemblyVersion("1.7.0.0")]
[assembly:System.Reflection.AssemblyFileVersion("1.7.0.0")]

namespace Afterplay {
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
        public static bool Visible { get { return current != null && !current.IsDisposed && current.Visible; } }
        public static IntPtr WindowHandle { get { return Visible ? current.Handle : IntPtr.Zero; } }
        public static string CurrentTitle { get { return Visible ? current.Heading : ""; } }
        public static void Show(string title, string message, string kind) {
            if (current == null || current.IsDisposed) current = new ReplayNotice();
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
        public void Display(string title, string detail, string status) {
            Heading = title; message = detail; kind = status;
            Rectangle area = Screen.FromHandle(GetForegroundWindow()).WorkingArea;
            float scale = DeviceDpi / 96f;
            Size = new Size((int)(410 * scale), (int)(94 * scale));
            int margin = (int)(20 * scale);
            Location = new Point(area.Right - Width - margin, area.Top + margin);
            lifetime.Stop();
            lifetime.Interval = kind == "error" ? 6000 : kind == "saving" ? 3500 : 4500;
            Invalidate();
            Show();
            SetWindowPos(Handle, new IntPtr(-1), Left, Top, Width, Height, 0x0010 | 0x0040);
            lifetime.Start();
        }
        protected override void OnPaint(PaintEventArgs e) {
            base.OnPaint(e);
            Graphics g = e.Graphics;
            float s = DeviceDpi / 96f;
            g.ScaleTransform(s, s);
            g.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
            Color accent = kind == "error" ? Color.FromArgb(242, 120, 112) : Color.FromArgb(143, 201, 196);
            using (Pen edge = new Pen(Color.FromArgb(61, 79, 73))) g.DrawRectangle(edge, 0, 0, 410 - 1, 94 - 1);
            using (SolidBrush strip = new SolidBrush(accent)) g.FillRectangle(strip, 0, 0, 4, 94);
            using (Pen pen = new Pen(accent, 2.4f)) {
                g.DrawEllipse(pen, 20, 30, 30, 30);
                if (kind == "success") g.DrawLines(pen, new PointF[] { new PointF(28,45), new PointF(33,50), new PointF(43,39) });
                else if (kind == "error") { g.DrawLine(pen, 35,37,35,47); g.DrawEllipse(pen,34,52,2,2); }
                else { g.DrawLine(pen,35,36,35,45); g.DrawLine(pen,35,45,42,49); }
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
            if (disposing) { lifetime.Dispose(); headingFont.Dispose(); messageFont.Dispose(); }
            base.Dispose(disposing);
        }
    }
}
