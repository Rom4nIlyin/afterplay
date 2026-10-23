# Bundled components

Python 3.13.0 x64 embeddable distribution (Python Software Foundation):
https://www.python.org/ftp/python/3.13.0/python-3.13.0-embed-amd64.zip
License: runtime/LICENSE.txt.

FFmpeg 7.1 essentials build by gyan.dev, bundled by imageio-ffmpeg 0.6.0:
runtime/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe
License: GPL version 3 or later; see FFmpeg-COPYING.GPLv3.txt.
FFmpeg source: https://github.com/FFmpeg/FFmpeg/tree/n7.1
Build provider and build/dependency information: https://www.gyan.dev/ffmpeg/builds/
Imageio packaging source: https://github.com/imageio/imageio-ffmpeg/tree/v0.6.0
The unmodified FFmpeg executable runs as a separate process.

Microsoft WebView2 Evergreen Standalone Installer, x64:
https://go.microsoft.com/fwlink/p/?LinkId=2124701
Signed by Microsoft Corporation. Installer is used only when WebView2 is missing.
Distribution documentation and applicable terms:
https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution

pywebview 6.2.1, Pillow 13.0.0, imageio-ffmpeg 0.6.0, PyAudioWPatch 0.2.12.9,
pystray 0.19.5, Send2Trash 2.1.0, pywin32 312, Python.NET 3.2.1 and their
dependencies retain distribution metadata and licenses under runtime/Lib/site-packages.

Process-specific audio uses the public Windows WASAPI process loopback API:
https://learn.microsoft.com/en-us/windows/win32/api/audioclientactivationparams/ns-audioclientactivationparams-audioclient_process_loopback_params
Its source is included as ProcessAudio.cs and process_audio.py.
