# Speech denoiser

`speech.rnnn` is the unmodified somnolent-hogwash RNNoise model by Gregor Richards,
trained for speech with recording noise (fans, computers and air conditioning).
It runs locally through FFmpeg's `arnndn` filter provided by PyAV.

Source, pinned revision:
https://github.com/GregorR/rnnoise-models/tree/3eee541a283fd3b8f81b85b1748e3b9ccbefa04d/somnolent-hogwash-2018-09-01

Original filename: `sh.rnnn`.
SHA-256: `70bb6685eb0c2a1d18e2918dca3fbfbd39317010b1802eb1b6ea73a92f3fdec0`.

The author's repository README states that the model data (outside its tools
directory and README) is not creative work and is not subject to copyright:
https://github.com/GregorR/rnnoise-models/blob/3eee541a283fd3b8f81b85b1748e3b9ccbefa04d/README.md

Speech suppression cannot identify a particular speaker or guarantee removal
of other voices, loud overlapping sounds, microphone clipping or room echo.
