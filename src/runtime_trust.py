"""Prepare only checksum-verified .NET components of this portable bundle.

Explorer propagates a downloaded ZIP's Zone.Identifier to extracted DLLs.
.NET Framework rejects those assemblies even after the app has been launched.
No Windows policy, registry setting, or files outside this bundle are changed.
"""
import hashlib
import json
import os
from pathlib import Path
from portable_paths import catalog, component as portable_component

MANAGED_COMPONENTS = {
    'processaudio.dll',
    'replaynotification.dll',
    'runtime/lib/site-packages/pythonnet/runtime/python.runtime.dll',
    'runtime/lib/site-packages/webview/lib/microsoft.web.webview2.core.dll',
    'runtime/lib/site-packages/webview/lib/microsoft.web.webview2.winforms.dll',
    'runtime/lib/site-packages/webview/lib/webbrowserinterop.x64.dll',
    'runtime/lib/site-packages/webview/lib/webbrowserinterop.x86.dll',
}

def prepare_runtime(base):
    if os.name != 'nt':
        return []
    base = Path(base).resolve()
    manifest = catalog(base)
    if not manifest.is_file():
        if portable_component(base, 'runtime/python313._pth').is_file():
            raise RuntimeError('Не найден SHA256SUMS.json. Распакуйте архив AFTERPLAY целиком.')
        return []  # Development/source installations use their own pip environment.
    expected = json.loads(manifest.read_text(encoding='utf-8-sig'))
    pending = []
    for relative, digest in expected.items():
        managed = relative.replace('\\', '/').lower()
        if managed.startswith('app/'):
            managed = managed[4:]
        if managed not in MANAGED_COMPONENTS:
            continue
        component = (base / relative).resolve()
        if not component.is_relative_to(base):
            raise RuntimeError('Путь компонента выходит за пределы папки AFTERPLAY.')
        zone = str(component) + ':Zone.Identifier'
        try:
            with open(zone, 'rb'):
                pass
        except FileNotFoundError:
            continue
        if hashlib.sha256(component.read_bytes()).hexdigest() != digest.lower():
            raise RuntimeError('Компонент AFTERPLAY изменён: ' + relative + '. Распакуйте официальный архив заново.')
        pending.append((relative, zone))
    # Validate every candidate first; do not partially prepare a damaged bundle.
    for relative, zone in pending:
        try:
            os.remove(zone)
        except OSError as error:
            raise RuntimeError('Нет доступа к компоненту ' + relative + '. Переместите AFTERPLAY в папку с правом записи.') from error
    return [relative for relative, _ in pending]
