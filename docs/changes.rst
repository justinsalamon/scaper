.. _changes:

Changelog
---------
v.1.3.3
~~~~~~~
- Fixed a bug with the format and subtype of audio files not being maintained in 
  match_sample_length.

v.1.3.2
~~~~~~~
- Fixed a bug with generating the file names when saving the isolated events. The idx for
  background and foreground events now increment separately.

v.1.3.1
~~~~~~~
- Fixed a bug with generating docs on ReadTheDocs.

v.1.3.0
~~~~~~~
- Source separation support! Add option to save isolated foreground events and background audio files.
- Makes pysoundfile a formal dependency.
- Seeding tests more robust.

v1.2.0
~~~~~~
- Added a random_state parameter to Scaper object, which allows all runs to be perfectly reproducible given the same audio and the same random seed.
- Switched from numpydoc to napoleon for generating the documentation. Also switched Sphinx to the most recent version.
- Added functions to Scaper object that allow one to reset the foreground and background event specifications independently. This allows users to reuse the same Scaper object and generate multiple soundscapes.
- Added a function to Scaper that allows the user to set the random state after creation.

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
