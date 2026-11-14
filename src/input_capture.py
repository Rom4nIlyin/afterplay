"""Opt-in Raw Input event track. A message-only HWND never draws on screen.

Only physical key/button identifiers and timestamps are stored, never text.
The capture's QPC clock is also used for the video timeline.
"""
import ctypes
from ctypes import wintypes as W
import json
import math
import os
from pathlib import Path
import threading
import time
import uuid

SUFFIX = '.inputs.json'
MOUSE = {'M1', 'M2', 'M3', 'M4', 'M5', 'WU', 'WD', 'WL', 'WR'}


def keyboard_code(vk,scan,flags):
    if vk in (0,255): return None
    if vk==16: vk=161 if scan==0x36 else 160
    elif vk==17: vk=163 if flags&2 else 162
    elif vk==18: vk=165 if flags&2 else 164
    elif vk==13 and flags&2: vk=256
    elif not flags&2 and scan in (0x47,0x48,0x49,0x4B,0x4C,0x4D,0x4F,0x50,0x51,0x52,0x53):
        vk={0x47:103,0x48:104,0x49:105,0x4B:100,0x4C:101,0x4D:102,0x4F:97,0x50:98,0x51:99,0x52:96,0x53:110}[scan]
    return 'K'+str(vk)


def valid_code(code):
    return isinstance(code, str) and (code in MOUSE or code == 'K256' or
           (code.startswith('K') and code[1:].isdigit() and 1 <= int(code[1:]) <= 254))


def sidecar(path):
    return Path(str(path) + SUFFIX)


def read(path):
    source = sidecar(path)
    if not source.is_file():
        return None
    if source.stat().st_size > 128 * 1024 ** 2:
        raise ValueError('Дорожка нажатий слишком большая')
    value = json.loads(source.read_text('utf-8'))
    if not isinstance(value, dict) or value.get('version') != 1:
        raise ValueError('Неизвестный формат дорожки нажатий')
    duration = value.get('duration')
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration < 0:
        raise ValueError('Некорректная длительность дорожки нажатий')
    events = value.get('events')
    if not isinstance(events, list) or len(events) > 2000000:
        raise ValueError('Некорректная дорожка нажатий')
    previous = -1
    for event in events:
        if (not isinstance(event, list) or len(event) != 3 or type(event[0]) not in (int, float)
                or not math.isfinite(event[0]) or not previous <= event[0] <= duration + .001
                or not valid_code(event[1]) or type(event[2]) is not bool):
            raise ValueError('Повреждена дорожка нажатий')
        previous = event[0]
    return value


def cut(events, start, duration):
    """Carry keys held at the trim boundary; release all keys at the end."""
    held = set()
    result = []
    for t, code, down in events:
        if t < start:
            if down: held.add(code)
            else: held.discard(code)
        else:
            break
    result.extend([0., code, True] for code in sorted(held))
    for t, code, down in events:
        if t < start: continue
        if t >= start + duration: break
        result.append([round(max(0., t - start), 6), code, down])
        if down: held.add(code)
        else: held.discard(code)
    result.extend([round(duration, 6), code, False] for code in sorted(held))
    return result


def write(path, events, duration):
    target = sidecar(path)
    temporary = target.with_name(target.name + '.tmp-' + uuid.uuid4().hex)
    try:
        temporary.write_text(json.dumps({'version': 1, 'duration': duration, 'events': events},
                                       separators=(',', ':')), encoding='utf-8')
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return {'events': len(events), 'path': str(target)}


def copy_trim(source, target, start, duration):
    data = read(source)
    if data is not None:
        return write(target, cut(data['events'], start, duration), duration)


class InputTrack:
    def __init__(self, session, epoch):
        self.lock = threading.RLock()
        self.epoch = epoch
        self.path = Path(session) / 'inputs.jsonl'
        self.handle = None
        self.held = set()
        self.last = 0.

    def event(self, code, down, now=None):
        if not valid_code(code): return
        with self.lock:
            if down == (code in self.held): return
            t = max(self.last, 0., (time.perf_counter() if now is None else now) - self.epoch)
            self.last = t
            if down: self.held.add(code)
            else: self.held.discard(code)
            if self.handle is None:
                self.handle = self.path.open('a', encoding='utf-8')
            self.handle.write(json.dumps([round(t, 6), code, bool(down)], separators=(',', ':')) + '\n')

    def release(self, now=None):
        with self.lock:
            for code in sorted(self.held): self.event(code, False, now)
            if self.handle: self.handle.flush()

    def attach(self, target, start, duration):
        with self.lock:
            if self.handle: self.handle.flush()
            if not self.path.exists(): return None
            events = [json.loads(line) for line in self.path.read_text('utf-8').splitlines() if line]
        return write(target, cut(events, start, duration), duration)

    def close(self):
        with self.lock:
            self.release()
            if self.handle: self.handle.close(); self.handle = None


class RawInputRecorder:
    def __init__(self, track, target_hwnd=None, target_path=''):
        if os.name != 'nt': raise ValueError('Запись нажатий доступна в Windows')
        self.track = track
        self.target_hwnd = target_hwnd
        self.target_path = target_path.casefold()
        self.ready = threading.Event()
        self.hwnd = None
        self.error = ''
        self.last_foreground = None
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name='AFTERPLAY Raw Input', daemon=True)
        self.track.path.touch(exist_ok=True)
        self.thread.start()
        if not self.ready.wait(5):
            self.stop_event.set()
            raise ValueError('Поток записи нажатий не отвечает')
        if self.error: raise ValueError(self.error)

    def _run(self):
        user = ctypes.WinDLL('user32', use_last_error=True)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
        class WC(ctypes.Structure):
            _fields_ = [('style', W.UINT), ('proc', WNDPROC), ('clsExtra', ctypes.c_int),
                        ('wndExtra', ctypes.c_int), ('instance', W.HINSTANCE), ('icon', W.HANDLE),
                        ('cursor', W.HANDLE), ('brush', W.HANDLE), ('menu', W.LPCWSTR), ('name', W.LPCWSTR)]
        class Device(ctypes.Structure):
            _fields_ = [('page', W.USHORT), ('usage', W.USHORT), ('flags', W.DWORD), ('hwnd', W.HWND)]
        class Header(ctypes.Structure):
            _fields_ = [('kind', W.DWORD), ('size', W.DWORD), ('device', W.HANDLE), ('param', W.WPARAM)]
        class Keyboard(ctypes.Structure):
            _fields_ = [('scan', W.USHORT), ('flags', W.USHORT), ('reserved', W.USHORT),
                        ('vk', W.USHORT), ('message', W.UINT), ('extra', W.ULONG)]
        user.DefWindowProcW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
        user.DefWindowProcW.restype = LRESULT
        user.RegisterClassW.argtypes = [ctypes.POINTER(WC)]
        user.CreateWindowExW.argtypes = [W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD, ctypes.c_int,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, W.HWND, W.HMENU, W.HINSTANCE, W.LPVOID]
        user.CreateWindowExW.restype = W.HWND
        user.RegisterRawInputDevices.argtypes = [ctypes.POINTER(Device), W.UINT, W.UINT]
        user.GetRawInputData.argtypes = [W.HANDLE, W.UINT, W.LPVOID, ctypes.POINTER(W.UINT), W.UINT]
        user.GetRawInputData.restype = W.UINT
        user.GetForegroundWindow.restype = W.HWND
        user.GetWindowThreadProcessId.argtypes = [W.HWND, ctypes.POINTER(W.DWORD)]
        user.SetTimer.argtypes = [W.HWND, ctypes.c_size_t, W.UINT, W.LPVOID]
        user.DestroyWindow.argtypes = [W.HWND]
        user.UnregisterClassW.argtypes = [W.LPCWSTR, W.HINSTANCE]
        kernel.GetModuleHandleW.restype = W.HMODULE
        kernel.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
        kernel.OpenProcess.restype = W.HANDLE
        kernel.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, ctypes.POINTER(W.DWORD)]
        kernel.CloseHandle.argtypes = [W.HANDLE]
        instance = kernel.GetModuleHandleW(None)
        name = 'AFTERPLAY_Input_' + uuid.uuid4().hex
        registered = False
        pending_wheels = []
        def allowed():
            foreground = user.GetForegroundWindow()
            if foreground != self.last_foreground:
                self.track.release()
                self.last_foreground = foreground
            pid = W.DWORD()
            user.GetWindowThreadProcessId(foreground, ctypes.byref(pid))
            if not pid.value or pid.value == os.getpid(): return False
            if self.target_hwnd:
                target_pid = W.DWORD()
                user.GetWindowThreadProcessId(W.HWND(self.target_hwnd), ctypes.byref(target_pid))
                return pid.value == target_pid.value
            if self.target_path:
                handle = kernel.OpenProcess(0x1000, False, pid.value)
                if not handle: return False
                try:
                    buffer = ctypes.create_unicode_buffer(32768); size = W.DWORD(len(buffer))
                    return bool(kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size))) and buffer.value.casefold() == self.target_path
                finally: kernel.CloseHandle(handle)
            return True
        def receive(raw_handle):
            size = W.UINT()
            if user.GetRawInputData(raw_handle, 0x10000003, None, ctypes.byref(size), ctypes.sizeof(Header)) == 0xFFFFFFFF: return
            if not ctypes.sizeof(Header) <= size.value <= 4096: return
            buffer = ctypes.create_string_buffer(size.value)
            if user.GetRawInputData(raw_handle, 0x10000003, buffer, ctypes.byref(size), ctypes.sizeof(Header)) == 0xFFFFFFFF: return
            header = Header.from_buffer(buffer)
            offset = ctypes.sizeof(Header)
            if header.kind == 1 and size.value >= offset + ctypes.sizeof(Keyboard):
                key = Keyboard.from_buffer(buffer, offset)
                code=keyboard_code(key.vk,key.scan,key.flags)
                if code:
                    self.track.event(code, not bool(key.flags & 1))
                    if code=='K19' and not key.flags&1:pending_wheels.append((time.perf_counter()+.12,code))
            elif header.kind == 0 and size.value >= offset + 8:
                flags = ctypes.c_ushort.from_buffer(buffer, offset + 4).value
                data = ctypes.c_short.from_buffer(buffer, offset + 6).value
                for i in range(5):
                    if flags & (1 << (i * 2)): self.track.event('M' + str(i + 1), True)
                    if flags & (2 << (i * 2)): self.track.event('M' + str(i + 1), False)
                if flags & (0x400 | 0x800):
                    code = ('WU' if data > 0 else 'WD') if flags & 0x400 else ('WR' if data > 0 else 'WL')
                    self.track.event(code, True)
                    pending_wheels.append((time.perf_counter() + .12, code))
        @WNDPROC
        def proc(hwnd, message, wp, lp):
            try:
                if message == 0x00FF and allowed(): receive(W.HANDLE(lp))
                elif message == 0x0113:
                    if not allowed(): self.track.release()
                    now = time.perf_counter()
                    for due, code in list(pending_wheels):
                        if due <= now:
                            self.track.event(code, False); pending_wheels.remove((due, code))
                    if self.stop_event.is_set(): user.DestroyWindow(hwnd)
                elif message == 0x0002: user.PostQuitMessage(0)
            except Exception as error:
                self.error = str(error)
                self.stop_event.set()
            return user.DefWindowProcW(hwnd, message, wp, lp)
        try:
            wc = WC(0, proc, 0, 0, instance, None, None, None, None, name)
            if not user.RegisterClassW(ctypes.byref(wc)): raise ctypes.WinError(ctypes.get_last_error())
            self.hwnd = user.CreateWindowExW(0, name, '', 0, 0, 0, 0, 0, W.HWND(-3), None, instance, None)
            if not self.hwnd: raise ctypes.WinError(ctypes.get_last_error())
            devices = (Device * 2)(Device(1, 6, 0x100, self.hwnd), Device(1, 2, 0x100, self.hwnd))
            if not user.RegisterRawInputDevices(devices, 2, ctypes.sizeof(Device)): raise ctypes.WinError(ctypes.get_last_error())
            registered = True
            user.SetTimer(self.hwnd, 1, 50, None)
            self.ready.set()
            message = W.MSG()
            while user.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                user.TranslateMessage(ctypes.byref(message)); user.DispatchMessageW(ctypes.byref(message))
        except Exception as error:
            self.error = 'Не удалось включить запись нажатий: ' + str(error)
        finally:
            self.track.release()
            if registered:
                devices = (Device * 2)(Device(1, 6, 1, None), Device(1, 2, 1, None))
                user.RegisterRawInputDevices(devices, 2, ctypes.sizeof(Device))
            if self.hwnd: user.DestroyWindow(self.hwnd)
            user.UnregisterClassW(name, instance)
            self.hwnd = None
            self.ready.set()

    def close(self):
        self.stop_event.set()
        if threading.current_thread() is not self.thread: self.thread.join(timeout=3)
        if self.thread.is_alive(): raise ValueError('Не удалось остановить запись нажатий')
        self.track.release()
