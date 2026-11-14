"""One desktop per data directory; a second launch requests activation."""
import ctypes
from ctypes import wintypes
import hashlib
import threading


class DesktopInstance:
    def __init__(self, data):
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        self.kernel.CreateMutexW.restype = wintypes.HANDLE
        self.kernel.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
        self.kernel.CreateEventW.restype = wintypes.HANDLE
        self.kernel.SetEvent.argtypes = [wintypes.HANDLE]
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        name = 'Local\\AFTERPLAY-' + hashlib.sha256(str(data.resolve()).lower().encode()).hexdigest()[:16]
        self.mutex = self.kernel.CreateMutexW(None, False, name)
        if not self.mutex:
            raise ctypes.WinError(ctypes.get_last_error())
        self.primary = ctypes.get_last_error() != 183
        self.event = self.kernel.CreateEventW(None, False, False, name + '-activate')
        if not self.event:
            self.kernel.CloseHandle(self.mutex)
            raise ctypes.WinError(ctypes.get_last_error())
        self.stop = threading.Event()
        self.thread = None
        if not self.primary:
            # The foreground launcher grants activation to the existing process.
            ctypes.windll.user32.AllowSetForegroundWindow(0xffffffff)
            if not self.kernel.SetEvent(self.event):
                raise ctypes.WinError(ctypes.get_last_error())

    def listen(self, desktop):
        def receive():
            while not self.stop.is_set():
                if self.kernel.WaitForSingleObject(self.event, 250) == 0:
                    if desktop.suite.window.events.loaded.wait(30) and not self.stop.is_set():
                        desktop.show()
        self.thread = threading.Thread(target=receive, daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=1)
        self.kernel.CloseHandle(self.event)
        self.kernel.CloseHandle(self.mutex)
