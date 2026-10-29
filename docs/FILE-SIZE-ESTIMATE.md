# File size preview

The recording page previews unsaved profile settings immediately. Wide windows show a sticky card beside the form; compact windows place it under the bitrate controls. Settings and recording are never changed by the preview.

MP4 CBR and VBR use `duration × (video Mbit/s + AAC kbit/s × track count / 1000) / 8`, in decimal GB. VBR additionally shows the size at maxrate. Resolution and frame rate are already included in a target bitrate; multiplying by FPS again would overestimate size. Audio includes the mix plus each isolated source: one track for a single source, three for game/chat or system/microphone, four for game/chat/microphone. Audio gain, offset and cursor visibility do not independently multiply a specified bitrate.

CQ/CRF shows a broad heuristic range using actual selected source dimensions, output downscaling, FPS, CQ/CRF, encoder, preset and maxrate. Reference rates were measured with the application's real FFmpeg encoder options on two two-second 1080p60 testsrc2 scenes at CQ/CRF 19, including one with seeded temporal noise at strength 5. The model scales reference rates by pixel-count ratio^0.85, FPS ratio^0.65 and 2^((19-CQ)/6), with a 0.35–1.6 scene allowance. These scaling and allowance factors are approximations, not a statistical confidence interval. Real scenes can fall outside it. Auto encoder uses the union of CPU/NVENC references until a recording resolves the encoder. Maxrate is a reference, not a strict file-size bound.

Source dimensions come from available windows/monitors. A closed or minimized window uses monitor dimensions or a labelled 1920×1080 fallback. Downscaling matches the recorder: preserve aspect ratio, even dimensions, never upscale. Window bounds can differ slightly from the captured client area.

GIF uses its actual output settings (at most 720 pixels wide, 15 FPS, chosen 2–15-second duration, no audio), with a rough 0.06–0.9 bytes/pixel/frame content model. This is an indication only; GIF compression is strongly dependent on motion and color. MP4 bitrate does not directly determine GIF size.

Container overhead and separate input/event sidecars are excluded. The chosen buffer duration is the reference interval for MP4; manual recordings continue to grow for the whole session.
