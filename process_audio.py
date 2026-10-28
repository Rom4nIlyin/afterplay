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


def audio_applications():
    """Include tray applications and choose the root of each executable's tree."""
    import ntpath
    class Entry(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('usage',wintypes.DWORD),('pid',wintypes.DWORD),
                  ('heap',ctypes.c_size_t),('module',wintypes.DWORD),('threads',wintypes.DWORD),
                  ('parent',wintypes.DWORD),('priority',ctypes.c_long),('flags',wintypes.DWORD),
                  ('exe',wintypes.WCHAR*260)]
    kernel=ctypes.windll.kernel32
    kernel.CreateToolhelp32Snapshot.argtypes=[wintypes.DWORD,wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
    kernel.Process32FirstW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)]
    kernel.Process32NextW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    snapshot=kernel.CreateToolhelp32Snapshot(2,0)
    if snapshot==wintypes.HANDLE(-1).value:return applications()
    rows={}
    try:
        entry=Entry();entry.size=ctypes.sizeof(entry)
        success=kernel.Process32FirstW(snapshot,ctypes.byref(entry))
        while success:
            if entry.pid:
                handle=kernel.OpenProcess(0x1000,False,entry.pid)
                if handle:
                    try:
                        path=ctypes.create_unicode_buffer(32768);size=wintypes.DWORD(len(path))
                        if kernel.QueryFullProcessImageNameW(handle,0,path,ctypes.byref(size)):
                            rows[entry.pid]={'pid':int(entry.pid),'parent':int(entry.parent),'path':path.value,'name':ntpath.basename(path.value)}
                    finally:kernel.CloseHandle(handle)
            success=kernel.Process32NextW(snapshot,ctypes.byref(entry))
    finally:kernel.CloseHandle(snapshot)
    roots=[row for row in rows.values() if rows.get(row['parent'],{}).get('path','').casefold()!=row['path'].casefold()]
    return sorted(roots,key=lambda row:(row['name'].casefold(),row['pid']))


def resolve_chat(settings):
    rows=audio_applications();path=settings.get('chat_path','')
    matches=[a for a in rows if a['path'].casefold()==path.casefold()] if path else [a for a in rows if a['name'].casefold() in {'discord.exe','discordptb.exe','discordcanary.exe'}]
    exact=next((a for a in matches if a['pid']==settings.get('chat_pid')),None)
    if exact:return exact
    if len(matches)==1:return matches[0]
    if not matches:raise ValueError('Запустите Discord / приложение чата и выберите его для отдельных дорожек')
    raise ValueError('Открыто несколько приложений чата. Выберите нужный процесс в списке')

def open_capture(pid,exclude=False):
    if not supported():raise ValueError('Звук отдельного приложения требует Windows 11 или Windows build 20348+. Выбери весь звук устройства.')
    import clr
    clr.AddReference(str(Path(__file__).parent/'ProcessAudio.dll'))
    from AfterplayAudio import ProcessCapture
    capture=ProcessCapture()
    try:capture.Start(pid,exclude)
    except Exception:
        capture.Dispose();raise
    return capture
