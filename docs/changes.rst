.. _changes:

Changelog
---------

v1.0.1
~~~~~~
- Added sample rate into jams instantiation

v0.2.0
~~~~~~
- :pr:`28`: Improve LUFS calculation:

    - Compute LUFS *after* initial processing (e.g. trimming, augmentation) of foreground and background events
    - Self-concatenate short events (< 500 ms) to avoid ffmpeg constant of -70.0 LUFS

v0.1.2
~~~~~~
- Fix markdown display on PyPi

v0.1.1
~~~~~~
- Increases minimum version of pysox to 1.3.3 to prevent crashing on Windows

v0.1.0
~~~~~~
- First release.
