"""Theme-aware native window bar that stays above the WebView's dialogs."""
from pathlib import Path
import threading
import re
import time
from localization import translate

class WindowChrome:
    def __init__(self,suite):
        self.suite=suite;self.native=None;self.ready=False

    def attach(self):
        from System import Action
        if not self.suite.window.events.loaded.wait(20):
            raise RuntimeError('Окно AFTERPLAY не загрузилось')
        def attach_native():
            try:
                import clr
                clr.AddReference(str(Path(__file__).parent/'ReplayNotification.dll'))
                from Afterplay import WindowChrome as NativeChrome
                self.native=NativeChrome.Attach(self.suite.window.native);self.ready=True
            except Exception as error:
                # An unavailable native helper must leave a usable standard frame.
                from System.Windows.Forms import FormBorderStyle
                self.suite.window.native.FormBorderStyle=FormBorderStyle.Sizable
                self.suite.log('window_chrome_failed',error=str(error))
        self.suite.window.native.Invoke(Action(attach_native))

    def state(self):
        window=self.suite.window
        return {'native':bool(window),'styled':self.ready,
                'maximized':bool(window and window.native and str(window.native.WindowState)=='Maximized'),
                'minimized':bool(window and window.native and str(window.native.WindowState)=='Minimized'),
                'visible':bool(window and window.native and window.native.Visible),
                'taskbar':bool(window and window.native and window.native.ShowInTaskbar)}

    def configure(self,colors):
        names=('background','panel','text','muted','accent')
        if not isinstance(colors,dict) or any(not isinstance(colors.get(name),str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',colors[name]) for name in names):
            raise ValueError('Некорректные цвета панели окна')
        if self.ready:
            replay=self.suite.replay;status=''
            if replay and replay.phase=='recording':
                label='Запись + повтор' if replay.continuous and replay.replay_enabled else 'Запись' if replay.continuous else 'Повтор'
                seconds=max(0,int(time.monotonic()-(replay.started or time.monotonic())))
                status=translate(self.suite,label)+' · '+f'{seconds//3600:02}:{seconds//60%60:02}:{seconds%60:02}'
            from System import Action
            self.suite.window.native.Invoke(Action(lambda:self.native.Configure(*(colors[name] for name in names),status)))
        return self.state()

    def control(self,command,edge=None):
        window=self.suite.window
        if not window:raise ValueError('Управление окном доступно в AFTERPLAY')
        if command=='minimize':window.minimize()
        elif command=='maximize':
            if self.state()['maximized']:window.restore()
            else:window.maximize()
        elif command=='close':
            # Destroy uses the existing closing event, including close-to-tray.
            threading.Timer(.05,window.destroy).start()
        elif command in {'drag','resize'}:
            if not self.ready:raise ValueError('Панель окна ещё загружается')
            edges={'left':10,'right':11,'top':12,'top-left':13,'top-right':14,'bottom':15,'bottom-left':16,'bottom-right':17}
            if command=='resize' and edge not in edges:raise ValueError('Неизвестная граница окна')
            from System import Action
            hit=2 if command=='drag' else edges[edge]
            window.native.BeginInvoke(Action(lambda:self.native.BeginMove(hit)))
        else:raise ValueError('Неизвестная команда окна')
        return self.state()
