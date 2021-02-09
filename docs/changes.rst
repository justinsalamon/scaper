.. _changes:

Changelog
---------
v1.6.5.rc0
~~~~~~~~~~
- Added a new distirbution tuple: ``("choose_weighted", list_of_options, probabilities)``, which supports weighted sampling: ``list_of_options[i]`` is chosen with probability ``probabilities[i]``.

v1.6.4
~~~~~~
- Scaper.generate now accepts a new argument for controlling trade-off between speed and quality in pitch shifting and time stretching:
    - quick_pitch_time: if True, both time stretching and pitch shifting will be applied in quick mode, which is much faster but has lower quality.

v1.6.3
~~~~~~
- Scaper.generate now accepts two new optional arguments for controlling audio clipping and normalization:
    - fix_clipping: if True and the soundscape audio is clipping, it will be peak normalized and all isolated events will be scaled accordingly.
    - peak_normalization: if True, sounscape audio will be peak normalized regardless of whether it's clipping or not and all isolated events will be scaled accordingly.
- All generate arguments are now documented in the scaper sandbox inside the JAMS annotation.
- Furthermore, we also document in the JAMS: the scale factor used for peak normalization, the change in ref_db, and the actual ref_db of the generated audio.

v1.6.2
~~~~~~
- Switching from FFMpeg LUFS calculation to pyloudnorm for better performance: runtime is reduced by approximately 30%
- The loudness calculation between FFMpeg LUFS and pyloudnorm is slightly different so this version will generate marginally different audio data compared to previous versions: the change is not perceptible, but np.allclose() tests on audio from previous versions of Scaper may fail.
- This change updates the regression data for Scaper's regression tests.
- This release used soxbindings 1.2.2 and pyloudnorm 0.1.0.

v1.6.1
~~~~~~
- Trimming now happens on read, rather than after read. This prevents the entire file from being loaded into memory. This is helpful for long source audio files.
- Since the audio processing pipeline has changed, this version will generate marginally different audio data compared to previous versions: the change is not perceptible, but np.allclose() tests on audio from previous versions of Scaper may fail.
- This change updates the regression data for Scaper's regression tests

v1.6.0
~~~~~~
- Uses soxbindings when installing on Linux or MacOS, which results in better performance.
- Adds explicit support for Python 3.7 and 3.8. Drops support for Python 2.7 and 3.4.

v1.5.1
~~~~~~
- Fixes a bug with fade in and out lengths are set to 0.
- This is the last version to support Python 2.7 and 3.4.

v1.5.0
~~~~~~
- Scaper now returns the generated audio and annotations directly in memory, allowing you to skip any/all file I/O!
- Saving the audio and annotations to disk is still supported, but is now optional.
- While this update modifies the API of several functions, it should still be backwards compatible.

v1.4.0
~~~~~~
- Operations on all files happen in-memory now, via new PySox features (build_array) and numpy operations for applying fades.
- Scaper is faster now due to the in-memory changes.

v1.3.9
~~~~~~
- Fixed a bug where trim before generating soundscapes from a JAMS file with saving of isolated events resulted in incorrect soundscape audio.

v1.3.8
~~~~~~
- Fixed a bug where _sample_trunc_norm returned an array in Scipy 1.5.1, but returns a scalar in Scipy 1.4.0.

v1.3.7
~~~~~~
- Fixed a bug where time stretched events could have a negative start time if they were longer than the soundscape duration.

v1.3.6
~~~~~~~
- Use sox flag -s for time stretching (speech mode), gives better sounding results.

v1.3.5
~~~~~~~
- Fixed a bug where short backgrounds did not concatenate to fill the entire soundscape.

v1.3.4
~~~~~~~
- Fixed a bug where the soundscapes were off by one sample when generated. Fixes bug 
  where generating from jams using a trimmed jams file was using the trimmed soundscape 
  duration instead of the original duration.
- Added a field to the sandbox that keeps track of the original duration of the 
  soundscape before any trimming is applied.

v1.3.3
~~~~~~~
- Fixed a bug with the format and subtype of audio files not being maintained in 
  match_sample_length.

v1.3.2
~~~~~~~
- Fixed a bug with generating the file names when saving the isolated events. The idx for
  background and foreground events now increment separately.

v1.3.1
~~~~~~~
- Fixed a bug with generating docs on ReadTheDocs.

v1.3.0
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
