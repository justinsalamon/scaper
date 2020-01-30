.. _changes:

Changelog
---------

v1.1.0
~~~~~~
- Added functionality which modifies a source_time distribution tuple according to the duration of the source and the duration of the event.
- This release alters behavior of Scaper compared to earlier versions.

v1.0.3
~~~~~~
- Fix bug where temp files might not be closed if an error is raised

v1.0.2
~~~~~~
- Store sample rate in output JAMS inside the scaper sandbox

v1.0.1
~~~~~~
- Fix bug where estimated duration of time stretched event is different to actual duration leading to incorrect silence padding and sometimes incorrect soundscape duration (in audio samples).

v1.0.0
~~~~~~
- Major revision
- Support jams>=0.3
- Switch from the sound_event to the scaper namespace.
- While the API remains compatible with previous versions, the change of underlying namespace breaks compatibility with jams files created using scaper for versions <1.0.0.

v0.2.1
~~~~~~
- Fix bug related to creating temp files on Windows.

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
