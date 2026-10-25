# Bundled components

Python 3.13.0 x64 embeddable distribution (Python Software Foundation):
https://www.python.org/ftp/python/3.13.0/python-3.13.0-embed-amd64.zip
License: app/runtime/LICENSE.txt.

FFmpeg 7.1 essentials build by gyan.dev, bundled by imageio-ffmpeg 0.6.0:
app/runtime/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe
License: GPL version 3 or later; see FFmpeg-COPYING.GPLv3.txt.
FFmpeg source: https://github.com/FFmpeg/FFmpeg/tree/n7.1
Build provider and build/dependency information: https://www.gyan.dev/ffmpeg/builds/
Imageio packaging source: https://github.com/imageio/imageio-ffmpeg/tree/v0.6.0
The unmodified FFmpeg executable runs as a separate process.

FFmpeg 9.0.2 essentials build by gyan.dev: app/runtime/ffmpeg.exe
Build archive: https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-9.0.2-essentials_build.zip
Archive SHA-256: 60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba
License: GPL version 3 or later; see FFmpeg-COPYING.GPLv3.txt.
Corresponding source: https://github.com/FFmpeg/FFmpeg/tree/n9.0.2
Build configuration and dependency sources: https://www.gyan.dev/ffmpeg/builds/
The GPU capture path uses gfxcapture / ddagrab D3D11 frames directly with NVENC; only audio
is packetized by Python. The imageio executable remains a development fallback.

Microsoft WebView2 Evergreen Standalone Installer, x64:
https://go.microsoft.com/fwlink/p/?LinkId=2124701
Signed by Microsoft Corporation. Installer is used only when WebView2 is missing.
Distribution documentation and applicable terms:
https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution

pywebview 6.2.1, Pillow 13.0.0, imageio-ffmpeg 0.6.0, PyAudioWPatch 0.2.12.9,
pystray 0.19.5, Send2Trash 2.1.0, pywin32 312, Python.NET 3.2.1 and their
dependencies retain distribution metadata and licenses under app/runtime/Lib/site-packages.

Process-specific audio uses the public Windows WASAPI process loopback API:
https://learn.microsoft.com/en-us/windows/win32/api/audioclientactivationparams/ns-audioclientactivationparams-audioclient_process_loopback_params
Source: https://github.com/Rom4nIlyin/afterplay/blob/main/ProcessAudio.cs and app/process_audio.py in the portable bundle.

Windows Capture 2.0.1 (MIT): https://github.com/NiiightmareXD/windows-capture
PyAV 19.0.2 (BSD-3-Clause): https://github.com/PyAV-Org/PyAV
PyAV wheels include their own FFmpeg libraries; applicable licenses and build
information are retained in av-*.dist-info and av.libs in the distribution.
NumPy 2.5.4 (BSD-3-Clause): https://numpy.org
OpenCV Python 5.0.0.93: https://github.com/opencv/opencv-python
Bundled wheels retain component licenses and notices in their dist-info folders.
The capture bridge uses PyAV for raw video / PCM packet multiplexing, without
re-encoding video before the separate FFmpeg process.
