"""Windows process-tree audio, independent of the selected output endpoint."""
import ctypes
from ctypes import wintypes
from pathlib import Path
import sys

def windows_version():
    # A native host without a supportedOS manifest can report Windows 8 through
    # GetVersionEx/sys.getwindowsversion even on Windows 11. Read the real build.
    class Version(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('major',wintypes.DWORD),('minor',wintypes.DWORD),
                  ('build',wintypes.DWORD),('platform',wintypes.DWORD),('service',wintypes.WCHAR*128)]
    info=Version();info.size=ctypes.sizeof(info)
    get_version=ctypes.WinDLL('ntdll').RtlGetVersion
    get_version.argtypes=[ctypes.POINTER(Version)];get_version.restype=ctypes.c_long
    if get_version(ctypes.byref(info))!=0:raise RuntimeError('Не удалось определить версию Windows')
    return info.major,info.minor,info.build

def supported():
    return windows_version()[2] >= 20348

def is_alive(pid):
    kernel=ctypes.windll.kernel32
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:return False
    try:
        code=wintypes.DWORD()
        return bool(kernel.GetExitCodeProcess(handle,ctypes.byref(code))) and code.value==259
    finally:kernel.CloseHandle(handle)

def applications():
    result={}
    user=ctypes.windll.user32
    kernel=ctypes.windll.kernel32
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    def visit(hwnd,_):
        if not user.IsWindowVisible(hwnd):return True
        length=user.GetWindowTextLengthW(hwnd)
        if not length:return True
        title=ctypes.create_unicode_buffer(length+1);user.GetWindowTextW(hwnd,title,length+1)
        pid=wintypes.DWORD();user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        handle=kernel.OpenProcess(0x1000,False,pid.value)
        if handle:
            try:
                path=ctypes.create_unicode_buffer(32768);size=wintypes.DWORD(len(path))
                if kernel.QueryFullProcessImageNameW(handle,0,path,ctypes.byref(size)):
                    rect=wintypes.RECT();user.GetWindowRect(hwnd,ctypes.byref(rect))
                    candidate={'pid':pid.value,'hwnd':int(hwnd),'path':path.value,'name':Path(path.value).name,'title':title.value,
                               'width':rect.right-rect.left,'height':rect.bottom-rect.top,'minimized':bool(user.IsIconic(hwnd))}
                    previous=result.get(pid.value)
                    if not previous or candidate['width']*candidate['height']>previous['width']*previous['height']:
                        result[pid.value]=candidate
            finally:kernel.CloseHandle(handle)
        return True
    user.EnumWindows(callback(visit),0)
    return sorted(result.values(),key=lambda x:x['name'].lower())

def resolve_target(settings):
    path=settings.get('game_path','')
    candidates=[a for a in applications() if a['path'].lower()==path.lower()]
    match=next((a for a in candidates if a['pid']==settings.get('game_pid')),None)
    if not match and len(candidates)==1:match=candidates[0]
    if not match:
        raise ValueError('Запусти игру и выбери её окно в настройках звука. Если открыто несколько копий — выбери нужную заново.')
    return match

def open_capture(pid,exclude=False):
    if not supported():raise ValueError('Звук отдельного приложения требует Windows 11 или Windows build 20348+. Выбери весь звук устройства.')
    import clr
    clr.AddReference(str(Path(__file__).parent/'ProcessAudio.dll'))
    from GameClipsAudio import ProcessCapture
    capture=ProcessCapture()
    capture.Start(pid,exclude)
    return capture
