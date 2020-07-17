
import scaper
from scaper.scaper_exceptions import ScaperError
from scaper.scaper_warnings import ScaperWarning
from scaper.util import _close_temp_files
import pytest
from scaper.core import EventSpec
import tempfile
import backports.tempfile
import os
import numpy as np
import soundfile
import jams
import csv
import numbers
from collections import namedtuple
from copy import deepcopy
import shutil
from contextlib import contextmanager


# FIXTURES
# Paths to files for testing
FG_PATH = 'tests/data/audio/foreground'
BG_PATH = 'tests/data/audio/background'
SHORT_BG_PATH = 'tests/data/audio/short_background'

ALT_FG_PATH = 'tests/data/audio_alt_path/foreground'
ALT_BG_PATH = 'tests/data/audio_alt_path/background'

# fg and bg labels for testing
FB_LABELS = ['car_horn', 'human_voice', 'siren']
BG_LABELS = ['park', 'restaurant', 'street']

_EXTS = ('wav', 'jams', 'txt')
_TestFiles = namedtuple('TestFiles', _EXTS)

SAMPLE_RATES = [44100, 22050]


def _get_test_paths(name):
    return _TestFiles(*[
        os.path.join('tests/data/regression/', name + '.' + ext)
        for ext in _EXTS
    ])


TEST_PATHS = {
    22050: {
        'REG': _get_test_paths('soundscape_20200501_22050'),
        'REG_BGONLY': _get_test_paths('bgonly_soundscape_20200501_22050'),
        'REG_REVERB': _get_test_paths('reverb_soundscape_20200501_22050'),
    },
    44100: {
        'REG': _get_test_paths('soundscape_20200501_44100'),
        'REG_BGONLY': _get_test_paths('bgonly_soundscape_20200501_44100'),
        'REG_REVERB': _get_test_paths('reverb_soundscape_20200501_44100'),
    },
}


def _compare_scaper_jams(jam, regjam):
    """
    Check whether two scaper jams objects are equal up to floating point
    precision, ignoring jams_version and scaper_version.

    Parameters
    ----------
    jam : JAMS
        In memory jams object
    regjam : JAMS
        Regression jams (loaded from disk)

    Raises
    ------
    AssertionError
        If the comparison fails.

    """
    # Note: can't compare directly, since:
    # 1. scaper/and jams library versions may change
    # 2. raw annotation sandbox stores specs as OrderedDict and tuples, whereas
    #    loaded ann (regann) simplifies those to dicts and lists
    # 3. floats might be marginally different (need to use np.allclose())

    # Must compare each part "manually"
    # 1. compare file metadata
    for k in set(jam.file_metadata.keys()) | set(regjam.file_metadata.keys()):
        if k != 'jams_version':
            assert jam.file_metadata[k] == regjam.file_metadata[k]

    # 2. compare jams sandboxes
    assert jam.sandbox == regjam.sandbox

    # 3. compare annotations
    assert len(jam.annotations) == len(regjam.annotations) == 1
    ann = jam.annotations[0]
    regann = regjam.annotations[0]

    # 3.1 compare annotation metadata
    assert ann.annotation_metadata == regann.annotation_metadata

    # 3.2 compare sandboxes
    # Note: can't compare sandboxes directly, since in raw jam scaper sandbox
    # stores event specs in EventSpec object (named tuple), whereas in loaded
    # jam these will get converted to list of lists.
    # assert ann.sandbox == regann.sandbox
    assert len(ann.sandbox.keys()) == len(regann.sandbox.keys()) == 1
    assert 'scaper' in ann.sandbox.keys()
    assert 'scaper' in regann.sandbox.keys()

    excluded_scaper_sandbox_keys = [
        'bg_spec', 'fg_spec', 'scaper_version', 'soundscape_audio_path', 
        'isolated_events_audio_path',
    ]
    # everything but the specs and version can be compared directly:
    for k in set(ann.sandbox.scaper.keys()) | set(regann.sandbox.scaper.keys()):
        if k not in excluded_scaper_sandbox_keys:
            assert ann.sandbox.scaper[k] == regann.sandbox.scaper[k], (
                'Unequal values for "{}"'.format(k))

    # to compare specs need to covert raw specs to list of lists
    bg_spec_list = [[list(x) if isinstance(x, tuple) else x for x in e] for e in
                    ann.sandbox.scaper['bg_spec']] 
    fg_spec_list = [[list(x) if isinstance(x, tuple) else x for x in e] for e in
                    ann.sandbox.scaper['fg_spec']]
    
    assert (fg_spec_list == regann.sandbox.scaper['fg_spec'])
    assert (bg_spec_list == regann.sandbox.scaper['bg_spec'])

    # 3.3. compare namespace, time and duration
    assert ann.namespace == regann.namespace
    assert ann.time == regann.time
    assert ann.duration == regann.duration

    # 3.4 compare data
    for obs, regobs in zip(ann.data, regann.data):
        # compare time, duration and confidence
        assert np.allclose(obs.time, regobs.time)
        assert np.allclose(obs.duration, regobs.duration)
        assert np.allclose(obs.confidence, regobs.confidence)

        # compare value dictionaries
        v, regv = obs.value, regobs.value
        for k in set(v.keys()) | set(regv.keys()):
            if isinstance(v[k], numbers.Number):
                assert np.allclose(v[k], regv[k])
            else:
                assert v[k] == regv[k]


def test_generate_from_jams(atol=1e-5, rtol=1e-8):

    # Test for invalid jams: no annotations
    tmpfiles = []
    with _close_temp_files(tmpfiles):
        jam = jams.JAMS()
        jam.file_metadata.duration = 10

        jam_file = tempfile.NamedTemporaryFile(suffix='.jams', delete=True)
        gen_file = tempfile.NamedTemporaryFile(suffix='.jams', delete=True)

        jam.save(jam_file.name)

        pytest.raises(ScaperError, scaper.generate_from_jams, jam_file.name,
                      gen_file.name)

    # Test for valid jams files
    tmpfiles = []
    with _close_temp_files(tmpfiles):

        # Create all necessary temp files
        orig_wav_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=True)
        orig_jam_file = tempfile.NamedTemporaryFile(suffix='.jams', delete=True)

        gen_wav_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=True)
        gen_jam_file = tempfile.NamedTemporaryFile(suffix='.jams', delete=True)

        tmpfiles.append(orig_wav_file)
        tmpfiles.append(orig_jam_file)
        tmpfiles.append(gen_wav_file)
        tmpfiles.append(gen_jam_file)

        # --- Define scaper --- *
        sc = scaper.Scaper(10, FG_PATH, BG_PATH)
        sc.protected_labels = []
        sc.ref_db = -50
        sc.add_background(label=('choose', []),
                          source_file=('choose', []),
                          source_time=('const', 0))
        # Add 5 events
        for _ in range(5):
            sc.add_event(label=('choose', []),
                         source_file=('choose', []),
                         source_time=('const', 0),
                         event_time=('uniform', 0, 9),
                         event_duration=('choose', [1, 2, 3]),
                         snr=('uniform', 10, 20),
                         pitch_shift=('uniform', -1, 1),
                         time_stretch=('uniform', 0.8, 1.2))

        # generate, then generate from the jams and compare audio files
        # repeat 5 times
        for _ in range(5):
            sc.generate(orig_wav_file.name, orig_jam_file.name,
                        disable_instantiation_warnings=True)
            scaper.generate_from_jams(orig_jam_file.name, gen_wav_file.name)

            # validate audio
            orig_wav, sr = soundfile.read(orig_wav_file.name)
            gen_wav, sr = soundfile.read(gen_wav_file.name)
            assert np.allclose(gen_wav, orig_wav, atol=atol, rtol=rtol)

        # Now add in trimming!
        for _ in range(5):
            sc.generate(orig_wav_file.name, orig_jam_file.name,
                        disable_instantiation_warnings=True)
            scaper.trim(orig_wav_file.name, orig_jam_file.name,
                        orig_wav_file.name, orig_jam_file.name,
                        np.random.uniform(0, 5), np.random.uniform(5, 10))
            scaper.generate_from_jams(orig_jam_file.name, gen_wav_file.name)

            # validate audio
            orig_wav, sr = soundfile.read(orig_wav_file.name)
            gen_wav, sr = soundfile.read(gen_wav_file.name)
            assert np.allclose(gen_wav, orig_wav, atol=atol, rtol=rtol)

        # Double trimming
        for _ in range(2):
            sc.generate(orig_wav_file.name, orig_jam_file.name,
                        disable_instantiation_warnings=True)
            scaper.trim(orig_wav_file.name, orig_jam_file.name,
                        orig_wav_file.name, orig_jam_file.name,
                        np.random.uniform(0, 2), np.random.uniform(8, 10))
            scaper.trim(orig_wav_file.name, orig_jam_file.name,
                        orig_wav_file.name, orig_jam_file.name,
                        np.random.uniform(0, 2), np.random.uniform(4, 6))
            scaper.generate_from_jams(orig_jam_file.name, gen_wav_file.name)

        # Triple trimming
        for _ in range(2):
            sc.generate(orig_wav_file.name, orig_jam_file.name,
                        disable_instantiation_warnings=True)
            scaper.trim(orig_wav_file.name, orig_jam_file.name,
                        orig_wav_file.name, orig_jam_file.name,
                        np.random.uniform(0, 2), np.random.uniform(8, 10))
            scaper.trim(orig_wav_file.name, orig_jam_file.name,
                        orig_wav_file.name, orig_jam_file.name,
                        np.random.uniform(0, 1), np.random.uniform(5, 6))
            scaper.trim(orig_wav_file.name, orig_jam_file.name,
                        orig_wav_file.name, orig_jam_file.name,
                        np.random.uniform(0, 1), np.random.uniform(3, 4))
            scaper.generate_from_jams(orig_jam_file.name, gen_wav_file.name)

            # validate audio
            orig_wav, sr = soundfile.read(orig_wav_file.name)
            gen_wav, sr = soundfile.read(gen_wav_file.name)
            assert np.allclose(gen_wav, orig_wav, atol=atol, rtol=rtol)

        # Test with new FG and BG paths
        for _ in range(5):
            sc.generate(orig_wav_file.name, orig_jam_file.name,
                        disable_instantiation_warnings=True)
            scaper.generate_from_jams(orig_jam_file.name, gen_wav_file.name,
                                      fg_path=ALT_FG_PATH, bg_path=ALT_BG_PATH)
            # validate audio
            orig_wav, sr = soundfile.read(orig_wav_file.name)
            gen_wav, sr = soundfile.read(gen_wav_file.name)
            assert np.allclose(gen_wav, orig_wav, atol=atol, rtol=rtol)

        # Ensure jam file saved correctly
        scaper.generate_from_jams(orig_jam_file.name, gen_wav_file.name,
                                  jams_outfile=gen_jam_file.name)
        orig_jam = jams.load(orig_jam_file.name)
        gen_jam = jams.load(gen_jam_file.name)
        _compare_scaper_jams(orig_jam, gen_jam)


def test_trim(atol=1e-5, rtol=1e-8):

    # Things we want to test:
    # 1. Jam trimmed correctly (mainly handled by jams.slice)
    # 2. value dict updated correctly (event_time, event_duration, source_time)
    # 3. scaper sandbox updated correctly (n_events, poly, gini, duration)
    # 4. audio trimmed correctly

    tmpfiles = []
    with _close_temp_files(tmpfiles):

        # Create all necessary temp files
        orig_wav_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=True)
        orig_jam_file = tempfile.NamedTemporaryFile(suffix='.jams', delete=True)

        trim_wav_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=True)
        trim_jam_file = tempfile.NamedTemporaryFile(suffix='.jams', delete=True)

        trimstrict_wav_file = tempfile.NamedTemporaryFile(
            suffix='.wav', delete=True)
        trimstrict_jam_file = tempfile.NamedTemporaryFile(
            suffix='.jams', delete=True)

        tmpfiles.append(orig_wav_file)
        tmpfiles.append(orig_jam_file)
        tmpfiles.append(trim_wav_file)
        tmpfiles.append(trim_jam_file)
        tmpfiles.append(trimstrict_wav_file)
        tmpfiles.append(trimstrict_jam_file)

        # --- Create soundscape and save to tempfiles --- #
        sc = scaper.Scaper(10, FG_PATH, BG_PATH)
        sc.protected_labels = []
        sc.ref_db = -50
        sc.add_background(label=('const', 'park'),
                          source_file=('choose', []),
                          source_time=('const', 0))
        # Add 5 events
        start_times = [0.5, 2.5, 4.5, 6.5, 8.5]
        for event_time in start_times:
            sc.add_event(label=('const', 'siren'),
                         source_file=('choose', []),
                         source_time=('const', 5),
                         event_time=('const', event_time),
                         event_duration=('const', 1),
                         snr=('const', 10),
                         pitch_shift=None,
                         time_stretch=None)
        sc.generate(orig_wav_file.name, orig_jam_file.name,
                    disable_instantiation_warnings=True)

        # --- Trim soundscape using scaper.trim with strict=False --- #
        scaper.trim(orig_wav_file.name, orig_jam_file.name,
                    trim_wav_file.name, trim_jam_file.name,
                    3, 7, no_audio=False)

        # --- Validate output --- #
        # validate JAMS
        trimjam = jams.load(trim_jam_file.name)
        trimann = trimjam.annotations.search(namespace='scaper')[0]

        # Time and duration of annotation observation must be changed, but
        # values in the value dict must remained unchanged!
        for event in trimann.data:
            if event.value['role'] == 'background':
                assert (event.time == 0 and
                        event.duration == 4 and
                        event.value['event_time'] == 0 and
                        event.value['event_duration'] == 10 and
                        event.value['source_time'] == 0)
            else:
                if event.time == 0:
                    assert (event.duration == 0.5 and
                            event.value['event_time'] == 2.5 and
                            event.value['event_duration'] == 1 and
                            event.value['source_time'] == 5)
                elif event.time == 1.5:
                    assert (event.duration == 1 and
                            event.value['event_time'] == 4.5 and
                            event.value['event_duration'] == 1 and
                            event.value['source_time'] == 5)
                elif event.time == 3.5:
                    assert (event.duration == 0.5 and
                            event.value['event_time'] == 6.5 and
                            event.value['event_duration'] == 1 and
                            event.value['source_time'] == 5)
                else:
                    assert False

        # validate audio
        orig_wav, sr = soundfile.read(orig_wav_file.name)
        trim_wav, sr = soundfile.read(trim_wav_file.name)
        assert np.allclose(trim_wav, orig_wav[3*sr:7*sr], atol=atol, rtol=rtol)


def test_get_value_from_dist():
    rng = scaper.util._check_random_state(0)
    # const
    x = scaper.core._get_value_from_dist(('const', 1), rng)
    assert x == 1

    # choose
    for _ in range(10):
        x = scaper.core._get_value_from_dist(('choose', [1, 2, 3]), rng)
        assert x in [1, 2, 3]

    # uniform
    for _ in range(10):
        x = scaper.core._get_value_from_dist(('choose', [1, 2, 3]), rng)
        assert x in [1, 2, 3]

    # normal
    for _ in range(10):
        x = scaper.core._get_value_from_dist(('normal', 5, 1), rng)
        assert scaper.util.is_real_number(x)

    # truncnorm
    for _ in range(10):
        x = scaper.core._get_value_from_dist(('truncnorm', 5, 10, 0, 10), rng)
        assert scaper.util.is_real_number(x)
        assert 0 <= x <= 10

    # COPY TESTS FROM test_validate_distribution (to ensure validation applied)
    def __test_bad_tuple_list(tuple_list):
        rng = scaper.util._check_random_state(0)
        for t in tuple_list:
            if isinstance(t, tuple):
                print(t, len(t))
            else:
                print(t)
            pytest.raises(ScaperError, scaper.core._get_value_from_dist, t, random_state=rng)

    # not tuple = error
    nontuples = [[], 5, 'yes']
    __test_bad_tuple_list(nontuples)

    # tuple must be at least length 2
    shortuples = [tuple(), tuple(['const'])]
    __test_bad_tuple_list(shortuples)

    # unsupported distribution tuple name
    badnames = [('invalid', 1), ('constant', 1, 2, 3)]
    __test_bad_tuple_list(badnames)

    # supported dist tuples, but bad arugments
    badargs = [('const', 1, 2),
               ('choose', 1), ('choose', [], 1),
               ('uniform', 1), ('uniform', 1, 2, 3), ('uniform', 2, 1),
               ('uniform', 'one', 2), ('uniform', 1, 'two'),
               ('uniform', 0, 1j), ('uniform', 1j, 2),
               ('normal', 1),
               ('normal', 1, 2, 3), ('normal', 1, -1),
               ('normal', 0, 1j), ('normal', 1j, 1), ('normal', 'one', 2),
               ('normal', 1, 'two'),
               ('truncnorm', 1), ('truncnorm', 1, 2, 3),
               ('truncnorm', 1, -1, 0, 1),
               ('truncnorm', 0, 1j, 0, 1), ('truncnorm', 1j, 1, 0, 1),
               ('truncnorm', 'one', 2, 0, 1), ('truncnorm', 1, 'two', 0, 1),
               ('truncnorm', 1, 2, 'three', 5),
               ('truncnorm', 1, 2, 3, 'four'),
               ('truncnorm', 0, 2, 2, 0)]
    __test_bad_tuple_list(badargs)


def test_ensure_satisfiable_source_time_tuple():
    # Documenting the expected behavior of _ensure_satisfiable_source_time_tuple
    source_duration = 10
    event_duration = 5

    _test_dist = ('uniform', 4, 10)
    _adjusted, warn = scaper.core._ensure_satisfiable_source_time_tuple(
        _test_dist, source_duration, event_duration)
    assert (warn)
    assert np.allclose(_adjusted[1:], (4, 5))

    _test_dist = ('truncnorm', 8, 1, 4, 10)
    _adjusted, warn = scaper.core._ensure_satisfiable_source_time_tuple(
        _test_dist, source_duration, event_duration)
    assert (warn)
    assert np.allclose(_adjusted[1:], (5, 1, 4, 5))

    _test_dist = ('const', 6)
    _adjusted, warn = scaper.core._ensure_satisfiable_source_time_tuple(
        _test_dist, source_duration, event_duration)
    assert (warn)
    assert np.allclose(_adjusted[1:], (5))

    _test_dist = ('uniform', 1, 10)
    _adjusted, warn = scaper.core._ensure_satisfiable_source_time_tuple(
        _test_dist, source_duration, event_duration)
    assert (warn)
    assert np.allclose(_adjusted[1:], (1, 5))

    _test_dist = ('truncnorm', 4, 1, 1, 10)
    _adjusted, warn = scaper.core._ensure_satisfiable_source_time_tuple(
        _test_dist, source_duration, event_duration)
    assert (warn)
    assert np.allclose(_adjusted[1:], (4, 1, 1, 5))

    _test_dist = ('uniform', 6, 10)
    _adjusted, warn = scaper.core._ensure_satisfiable_source_time_tuple(
        _test_dist, source_duration, event_duration)
    assert (warn)
    assert np.allclose(_adjusted[1], (5))

    _test_dist = ('truncnorm', 8, 1, 6, 10)
    _adjusted, warn = scaper.core._ensure_satisfiable_source_time_tuple(
        _test_dist, source_duration, event_duration)
    assert (warn)
    assert np.allclose(_adjusted[1], (5))

    _test_dist = ('choose', [0, 1, 2, 10, 12, 15, 20])
    _adjusted, warn = scaper.core._ensure_satisfiable_source_time_tuple(
        _test_dist, source_duration, event_duration)
    assert (warn)
    assert np.allclose(_adjusted[1], [0, 1, 2, 5])


def test_validate_distribution():

    def __test_bad_tuple_list(tuple_list):
        for t in tuple_list:
            if isinstance(t, tuple):
                print(t, len(t))
            else:
                print(t)
            pytest.raises(ScaperError, scaper.core._validate_distribution, t)

    # not tuple = error
    nontuples = [[], 5, 'yes']
    __test_bad_tuple_list(nontuples)

    # tuple must be at least length 2
    shortuples = [tuple(), tuple(['const'])]
    __test_bad_tuple_list(shortuples)

    # unsupported distribution tuple name
    badnames = [('invalid', 1), ('constant', 1, 2, 3)]
    __test_bad_tuple_list(badnames)

    # supported dist tuples, but bad arugments
    badargs = [('const', 1, 2),
               ('choose', 1), ('choose', [], 1),
               ('uniform', 1), ('uniform', 1, 2, 3), ('uniform', 2, 1),
               ('uniform', 'one', 2), ('uniform', 1, 'two'),
               ('uniform', 0, 1j), ('uniform', 1j, 2),
               ('normal', 1),
               ('normal', 1, 2, 3), ('normal', 1, -1),
               ('normal', 0, 1j), ('normal', 1j, 1), ('normal', 'one', 2),
               ('normal', 1, 'two'),
               ('truncnorm', 1), ('truncnorm', 1, 2, 3),
               ('truncnorm', 1, -1, 0, 1),
               ('truncnorm', 0, 1j, 0, 1), ('truncnorm', 1j, 1, 0, 1),
               ('truncnorm', 'one', 2, 0, 1), ('truncnorm', 1, 'two', 0, 1),
               ('truncnorm', 1, 2, 'three', 5), ('truncnorm', 1, 2, 3, 'four'),
               ('truncnorm', 0, 2, 2, 0)]
    __test_bad_tuple_list(badargs)


def test_validate_label():

    # label must be in list of allowed labels
    allowed_labels = ['yes']
    pytest.raises(ScaperError, scaper.core._validate_label, ('const', 'no'),
                  allowed_labels)

    # Choose list must be subset of allowed labels
    allowed_labels = ['yes', 'hello']
    pytest.raises(ScaperError, scaper.core._validate_label, ('choose', ['no']),
                  allowed_labels)

    # Label tuple must start with either 'const' or 'choose'
    bad_label_dists = [('uniform', 0, 1), ('normal', 0, 1),
                       ('truncnorm', 0, 1, 0, 1)]
    for bld in bad_label_dists:
        pytest.raises(ScaperError, scaper.core._validate_label, bld,
                      allowed_labels)


def test_validate_source_file():

    # file must exist
    # create temp folder so we have path to file we know doesn't exist
    with backports.tempfile.TemporaryDirectory() as tmpdir:
        nonfile = os.path.join(tmpdir, 'notafile')
        pytest.raises(ScaperError, scaper.core._validate_source_file,
                      ('const', nonfile), ('const', 'siren'))

    # label must be const and match file foldername
    sourcefile = 'tests/data/audio/foreground/siren/69-Siren-1.wav'
    pytest.raises(ScaperError, scaper.core._validate_source_file,
                  ('const', sourcefile), ('choose', []))

    pytest.raises(ScaperError, scaper.core._validate_source_file,
                  ('const', sourcefile), ('const', 'car_horn'))

    # if choose, all files in list of files must exist
    sourcefile = 'tests/data/audio/foreground/siren/69-Siren-1.wav'
    with backports.tempfile.TemporaryDirectory() as tmpdir:
        nonfile = os.path.join(tmpdir, 'notafile')
        source_file_list = [sourcefile, nonfile]
        pytest.raises(ScaperError, scaper.core._validate_source_file,
                      ('choose', source_file_list), ('const', 'siren'))

    # must be const or choose
    bad_label_dists = [('uniform', 0, 1), ('normal', 0, 1),
                       ('truncnorm', 0, 1, 0, 1)]
    for bld in bad_label_dists:
        pytest.raises(ScaperError, scaper.core._validate_source_file, bld,
                      ('const', 'siren'))


def test_validate_time():

    def __test_bad_time_tuple(time_tuple):
        pytest.raises(ScaperError, scaper.core._validate_time, time_tuple)

    # bad consts
    bad_time_values = [None, -1, 1j, 'yes', [], [5]]
    for btv in bad_time_values:
        __test_bad_time_tuple(('const', btv))

    # empty list for choose
    __test_bad_time_tuple(('choose', []))

    # bad consts in list for choose
    for btv in bad_time_values:
        __test_bad_time_tuple(('choose', [btv]))

    # uniform can't have negative min value
    __test_bad_time_tuple(('uniform', -1, 1))

    # using normal will issue a warning since it can generate neg values
    pytest.warns(ScaperWarning, scaper.core._validate_time, ('normal', 5, 2))

    # truncnorm can't have negative min value
    __test_bad_time_tuple(('truncnorm', 0, 1, -1, 1))
    

def test_validate_duration():

    def __test_bad_duration_tuple(duration_tuple):
        pytest.raises(ScaperError, scaper.core._validate_duration,
                      duration_tuple)

    # bad consts
    bad_dur_values = [None, -1, 0, 1j, 'yes', [], [5]]
    for bdv in bad_dur_values:
        __test_bad_duration_tuple(('const', bdv))

    # empty list for choose
    __test_bad_duration_tuple(('choose', []))

    # bad consts in list for choose
    for bdv in bad_dur_values:
        __test_bad_duration_tuple(('choose', [bdv]))

    # uniform can't have negative or 0 min value
    __test_bad_duration_tuple(('uniform', -1, 1))
    __test_bad_duration_tuple(('uniform', 0, 1))

    # using normal will issue a warning since it can generate neg values
    pytest.warns(ScaperWarning, scaper.core._validate_duration,
                 ('normal', 5, 2))

    # truncnorm can't have negative or zero min value
    __test_bad_duration_tuple(('truncnorm', 0, 1, -1, 1))
    __test_bad_duration_tuple(('truncnorm', 0, 1, 0, 1))


def test_validate_snr():

    def __test_bad_snr_tuple(snr_tuple):
        pytest.raises(ScaperError, scaper.core._validate_snr, snr_tuple)

    # bad consts
    bad_snr_values = [None, 1j, 'yes', [], [5]]
    for bsv in bad_snr_values:
        __test_bad_snr_tuple(('const', bsv))

    # empty list for choose
    __test_bad_snr_tuple(('choose', []))

    # bad consts in list for choose
    for bsv in bad_snr_values:
        __test_bad_snr_tuple(('choose', [bsv]))


def test_validate_pitch_shift():

    def __test_bad_ps_tuple(ps_tuple):
        pytest.raises(ScaperError, scaper.core._validate_pitch_shift, ps_tuple)

    # bad consts
    bad_ps_values = [None, 1j, 'yes', [], [5]]
    for bv in bad_ps_values:
        __test_bad_ps_tuple(('const', bv))

    # empty list for choose
    __test_bad_ps_tuple(('choose', []))

    # bad consts in list for choose
    for bv in bad_ps_values:
        __test_bad_ps_tuple(('choose', [bv]))


def test_validate_time_stretch():

    def __test_bad_ts_tuple(ts_tuple):
        pytest.raises(ScaperError, scaper.core._validate_time_stretch,
                      ts_tuple)

    # bad consts
    bad_ps_values = [None, 1j, 'yes', [], [5], -5, 0]
    for bv in bad_ps_values:
        __test_bad_ts_tuple(('const', bv))

    # empty list for choose
    __test_bad_ts_tuple(('choose', []))

    # bad consts in list for choose
    for bv in bad_ps_values:
        __test_bad_ts_tuple(('choose', [bv]))

    # bad start time in distributions
    __test_bad_ts_tuple(('uniform', 0, 1))
    __test_bad_ts_tuple(('uniform', -5, 1))
    __test_bad_ts_tuple(('truncnorm', 5, 1, 0, 10))
    __test_bad_ts_tuple(('truncnorm', 5, 1, -5, 10))

    # Using normal dist must raise warning since can give neg or 0 values
    pytest.warns(
        ScaperWarning, scaper.core._validate_time_stretch, ('normal', 5, 1))


def test_validate_event():

    bad_allowed_labels = [0, 'yes', 1j, np.array([1, 2, 3])]

    for bal in bad_allowed_labels:
        pytest.raises(ScaperError, scaper.core._validate_event,
                      label=('choose', []),
                      source_file=('choose', []),
                      source_time=('const', 0),
                      event_time=('const', 0),
                      event_duration=('const', 1),
                      snr=('const', 0),
                      allowed_labels=bal,
                      pitch_shift=None,
                      time_stretch=None)


def test_scaper_init():
    '''
    Test creation of Scaper object.
    '''

    # bad duration
    sc = pytest.raises(ScaperError, scaper.Scaper, -5, FG_PATH, BG_PATH)

    # all args valid
    sc = scaper.Scaper(10.0, FG_PATH, BG_PATH)
    assert sc.fg_path == FG_PATH
    assert sc.bg_path == BG_PATH

    # bad fg path
    sc = pytest.raises(ScaperError, scaper.Scaper, 10.0,
                       'tests/data/audio/wrong',
                       BG_PATH)

    # bad bg path
    sc = pytest.raises(ScaperError, scaper.Scaper, 10.0,
                       FG_PATH,
                       'tests/data/audio/wrong')

    # ensure fg_labels and bg_labels populated properly
    sc = scaper.Scaper(10.0, FG_PATH, BG_PATH)
    assert sc.fg_labels == FB_LABELS
    assert sc.bg_labels == BG_LABELS

    # ensure default values have been set
    assert sc.sr == 44100
    assert sc.ref_db == -12
    assert sc.n_channels == 1
    assert sc.fade_in_len == 0.01  # 10 ms
    assert sc.fade_out_len == 0.01  # 10 ms


def test_reset_fg_bg_event_spec():
    def _add_fg_event(sc):
        sc.add_event(label=('const', 'siren'),
                 source_file=('choose', []),
                 source_time=('const', 0),
                 event_time=('uniform', 0, 9),
                 event_duration=('truncnorm', 2, 1, 1, 3),
                 snr=('uniform', 10, 20),
                 pitch_shift=('normal', 0, 1),
                 time_stretch=('uniform', 0.8, 1.2))
    
    def _add_bg_event(sc):
        sc.add_background(("const", "park"), ("choose", []), ("const", 0))

    sc = scaper.Scaper(
        10.0, fg_path=FG_PATH, bg_path=BG_PATH, random_state=0)

    # there should be no events initially
    assert len(sc.fg_spec) == 0
    assert len(sc.bg_spec) == 0

    # there should be one foreground event now
    _add_fg_event(sc)
    assert len(sc.fg_spec) == 1
    first_fg_spec = deepcopy(sc.fg_spec)

    # after this there should be no foreground events
    sc.reset_fg_event_spec()
    assert len(sc.fg_spec) == 0

    # add the foreground event back. now the original fg_spec and this one should be
    # the same.
    _add_fg_event(sc)
    assert first_fg_spec == sc.fg_spec

    # start over, this time using reset_bg_spec too.
    sc.reset_fg_event_spec()

    # there should be one background event and one foreground event now 
    _add_fg_event(sc)
    _add_bg_event(sc)
    assert len(sc.fg_spec) == 1
    assert len(sc.bg_spec) == 1
    first_fg_spec = deepcopy(sc.fg_spec)
    first_bg_spec = deepcopy(sc.bg_spec)

    # after this there should be no foreground or background events
    sc.reset_fg_event_spec()
    sc.reset_bg_event_spec()
    assert len(sc.fg_spec) == 0
    assert len(sc.bg_spec) == 0

    # add the both events back. now both event spec sshould match the original
    _add_fg_event(sc)
    _add_bg_event(sc)
    assert first_fg_spec == sc.fg_spec
    assert first_bg_spec == sc.bg_spec


def test_scaper_add_background():
    '''
    Test Scaper.add_background function

    '''
    sc = scaper.Scaper(10.0, FG_PATH, BG_PATH)

    # Set concrete background label
    # label, source_file, source_time
    sc.add_background(("const", "park"), ("choose", []), ("const", 0))

    # Check that event has been added to the background spec, and that the
    # values that are set automatically by this method (event_time,
    # event_duration, snr and role) are correctly set to their expected values.
    bg_event_expected = EventSpec(label=("const", "park"),
                                  source_file=("choose", []),
                                  source_time=("const", 0),
                                  event_time=("const", 0),
                                  event_duration=("const", sc.duration),
                                  snr=("const", 0),
                                  role='background',
                                  pitch_shift=None,
                                  time_stretch=None)
    assert sc.bg_spec == [bg_event_expected]


def test_scaper_add_event():

    sc = scaper.Scaper(10.0, FG_PATH, BG_PATH)

    # Initially fg_spec should be empty
    assert sc.fg_spec == []

    # Add one event
    sc.add_event(label=('const', 'siren'),
                 source_file=('choose', []),
                 source_time=('const', 0),
                 event_time=('uniform', 0, 9),
                 event_duration=('truncnorm', 2, 1, 1, 3),
                 snr=('uniform', 10, 20),
                 pitch_shift=('normal', 0, 1),
                 time_stretch=('uniform', 0.8, 1.2))
    # Now should be one event in fg_spec
    assert len(sc.fg_spec) == 1
    fg_event_expected = EventSpec(label=('const', 'siren'),
                                  source_file=('choose', []),
                                  source_time=('const', 0),
                                  event_time=('uniform', 0, 9),
                                  event_duration=('truncnorm', 2, 1, 1, 3),
                                  snr=('uniform', 10, 20),
                                  role='foreground',
                                  pitch_shift=('normal', 0, 1),
                                  time_stretch=('uniform', 0.8, 1.2))
    assert sc.fg_spec[0] == fg_event_expected


def test_scaper_instantiate_event():

    # GF EVENT TO WORK WITH
    fg_event = EventSpec(label=('const', 'siren'),
                         source_file=('choose', []),
                         source_time=('const', 0),
                         event_time=('uniform', 0, 9),
                         event_duration=('truncnorm', 2, 1, 1, 3),
                         snr=('uniform', 10, 20),
                         role='foreground',
                         pitch_shift=('normal', 0, 1),
                         time_stretch=('uniform', 0.8, 1.2))

    # test valid case
    sc = scaper.Scaper(10.0, fg_path=FG_PATH, bg_path=BG_PATH)
    instantiated_event = sc._instantiate_event(
        fg_event, isbackground=False, allow_repeated_label=True,
        allow_repeated_source=True, used_labels=[], used_source_files=[],
        disable_instantiation_warnings=True)
    assert instantiated_event.label == 'siren'
    assert instantiated_event.source_file == (
        'tests/data/audio/foreground/siren/69-Siren-1.wav')
    assert instantiated_event.source_time == 0
    assert 0 <= instantiated_event.event_time <= 9
    assert 1 <= instantiated_event.event_duration <= 3
    assert 10 <= instantiated_event.snr <= 20
    assert instantiated_event.role == 'foreground'
    assert scaper.util.is_real_number(instantiated_event.pitch_shift)
    assert 0.8 <= instantiated_event.time_stretch <= 1.2

    # when a label needs to be replaced because it's used already
    fg_event8 = fg_event._replace(label=('choose', []))
    # repeat several times to increase chance of hitting the line we need to
    # test
    for _ in range(20):
        instantiated_event = sc._instantiate_event(
            fg_event8, isbackground=False, allow_repeated_label=False,
            allow_repeated_source=True, used_labels=['siren', 'human_voice'],
            disable_instantiation_warnings=True)
        assert instantiated_event.label == 'car_horn'

    # when a source file needs to be replaced because it's used already
    fg_event9 = fg_event._replace(label=('const', 'human_voice'))
    # repeat several times to increase chance of hitting the line we need to
    # test
    for _ in range(20):
        instantiated_event = sc._instantiate_event(
            fg_event9, isbackground=False, allow_repeated_label=True,
            allow_repeated_source=False,
            used_labels=[],
            used_source_files=(
                ['tests/data/audio/foreground/human_voice/'
                 '42-Human-Vocal-Voice-all-aboard_edit.wav',
                 'tests/data/audio/foreground/human_voice/'
                 '42-Human-Vocal-Voice-taxi-1_edit.wav']),
            disable_instantiation_warnings=True)
        assert instantiated_event.source_file == (
            'tests/data/audio/foreground/human_voice/'
            '42-Human-Vocal-Voice-taxi-2_edit.wav')

    # Protected labels must have original source duration and source time 0
    sc = scaper.Scaper(10.0, fg_path=FG_PATH, bg_path=BG_PATH,
                       protected_labels='human_voice')
    fg_event10 = fg_event._replace(
        label=('const', 'human_voice'),
        source_file=('const', 'tests/data/audio/foreground/human_voice/'
                              '42-Human-Vocal-Voice-taxi-2_edit.wav'),
        source_time=('const', 0.3),
        event_duration=('const', 0.4))
    instantiated_event = sc._instantiate_event(
        fg_event10, disable_instantiation_warnings=True)
    assert instantiated_event.source_time == 0
    assert np.allclose(instantiated_event.event_duration, 0.806236, atol=1e-5)

    # repeated label when not allowed throws error
    sc = scaper.Scaper(10.0, fg_path=FG_PATH, bg_path=BG_PATH)
    pytest.raises(ScaperError, sc._instantiate_event, fg_event,
                  isbackground=False,
                  allow_repeated_label=False,
                  allow_repeated_source=True,
                  used_labels=['siren'])

    # repeated source when not allowed throws error
    pytest.raises(ScaperError, sc._instantiate_event, fg_event,
                  isbackground=False,
                  allow_repeated_label=True,
                  allow_repeated_source=False,
                  used_labels=['siren'],
                  used_source_files=(
                      ['tests/data/audio/foreground/siren/69-Siren-1.wav']))

    # event duration longer than source duration: warning
    fg_event2 = fg_event._replace(label=('const', 'car_horn'),
                                  event_duration=('const', 5))
    pytest.warns(ScaperWarning, sc._instantiate_event, fg_event2)

    # event duration longer than soundscape duration: warning
    fg_event3 = fg_event._replace(event_time=('const', 0),
                                  event_duration=('const', 15),
                                  time_stretch=None)
    pytest.warns(ScaperWarning, sc._instantiate_event, fg_event3)

    # stretched event duration longer than soundscape duration: warning
    fg_event4 = fg_event._replace(event_time=('const', 0),
                                  event_duration=('const', 6),
                                  time_stretch=('const', 2))
    pytest.warns(ScaperWarning, sc._instantiate_event, fg_event4)

    # 'const' source_time + event_duration > source_duration: warning
    fg_event5a = fg_event._replace(event_time=('const', 0),
                                  event_duration=('const', 8),
                                  source_time=('const', 20))
    pytest.warns(ScaperWarning, sc._instantiate_event, fg_event5a)

    # 'choose' source_time + event_duration > source_duration: warning
    fg_event5b = fg_event._replace(event_time=('const', 0),
                                  event_duration=('const', 8),
                                  source_time=('choose', [20, 20]))
    pytest.warns(ScaperWarning, sc._instantiate_event, fg_event5b)

    # 'uniform' source_time + event_duration > source_duration: warning
    fg_event5c = fg_event._replace(event_time=('const', 0),
                                  event_duration=('const', 8),
                                  source_time=('uniform', 20, 25))
    pytest.warns(ScaperWarning, sc._instantiate_event, fg_event5c)

    # 'normal' source_time + event_duration > source_duration: warning
    fg_event5d = fg_event._replace(event_time=('const', 0),
                                  event_duration=('const', 8),
                                  source_time=('normal', 20, 2))
    pytest.warns(ScaperWarning, sc._instantiate_event, fg_event5d)

    # 'truncnorm' source_time + event_duration > source_duration: warning
    fg_event5e = fg_event._replace(event_time=('const', 0),
                                  event_duration=('const', 8),
                                  source_time=('truncnorm', 20, 2, 20, 20))
    pytest.warns(ScaperWarning, sc._instantiate_event, fg_event5e)

    # 'normal' random draw above mean with mean = source_duration - event_duration 
    # source_time + event_duration > source_duration: warning
    fg_event5f = fg_event._replace(event_time=('const', 0),
                            event_duration=('const', 8),
                            source_time=('normal', 18.25, 2))

    def _repeat_instantiation(event):
        # keep going till we hit a draw that covers when the draw exceeds 
        # source_duration - event_duration (18.25). Use max_draws
        # just in case so that testing is guaranteed to terminate. 
        source_time = 0
        num_draws = 0
        max_draws = 1000
        while source_time < 18.25 and num_draws < max_draws:
            instantiated_event = sc._instantiate_event(event)
            source_time = instantiated_event.source_time
            num_draws += 1

    pytest.warns(ScaperWarning, _repeat_instantiation, fg_event5f)

    # event_time + event_duration > soundscape duration: warning
    fg_event6 = fg_event._replace(event_time=('const', 8),
                                  event_duration=('const', 5),
                                  time_stretch=None)
    pytest.warns(ScaperWarning, sc._instantiate_event, fg_event6)

    # event_time + stretched event_duration > soundscape duration: warning
    fg_event7 = fg_event._replace(event_time=('const', 5),
                                  event_duration=('const', 4),
                                  time_stretch=('const', 2))
    pytest.warns(ScaperWarning, sc._instantiate_event, fg_event7)

    # stretched duration should always be adjusted to be <= self.duration
    for stretch in [2, 3, 1.5]:
        fg_event11 = fg_event._replace(event_time=('const', 2),
                                       event_duration=('const', 7),
                                       time_stretch=('const', stretch))
        fg_event11_inst = sc._instantiate_event(fg_event11)
        assert fg_event11_inst.event_time == 0
        assert fg_event11_inst.event_duration == sc.duration / stretch

    # Make sure event time is respected when possible
    for e_stretch, e_duration in zip([1, 1.25, 0.5], [7, 7, 18]):
        fg_event12 = fg_event._replace(event_time=('const', 1),
                                       event_duration=('const', e_duration),
                                       time_stretch=('const', e_stretch))
        fg_event12_inst = sc._instantiate_event(fg_event12)
        assert fg_event12_inst.event_time == 1
        assert fg_event12_inst.event_duration == e_duration


def test_scaper_instantiate():
    for sr in SAMPLE_RATES:
        REG_JAM_PATH = TEST_PATHS[sr]['REG'].jams
        # Here we just instantiate a known fixed spec and check if that jams
        # we get back is as expected.
        sc = scaper.Scaper(10.0, fg_path=FG_PATH, bg_path=BG_PATH)
        sc.ref_db = -50
        sc.sr = sr

        # background
        sc.add_background(
            label=('const', 'park'),
            source_file=(
                'const',
                'tests/data/audio/background/park/'
                '268903__yonts__city-park-tel-aviv-israel.wav'),
            source_time=('const', 0))

        # foreground events
        sc.add_event(
            label=('const', 'siren'),
            source_file=('const',
                         'tests/data/audio/foreground/'
                         'siren/69-Siren-1.wav'),
            source_time=('const', 5),
            event_time=('const', 2),
            event_duration=('const', 5),
            snr=('const', 5),
            pitch_shift=None,
            time_stretch=None)

        sc.add_event(
            label=('const', 'car_horn'),
            source_file=('const',
                         'tests/data/audio/foreground/'
                         'car_horn/17-CAR-Rolls-Royce-Horn.wav'),
            source_time=('const', 0),
            event_time=('const', 5),
            event_duration=('const', 2),
            snr=('const', 20),
            pitch_shift=('const', 1),
            time_stretch=None)

        sc.add_event(
            label=('const', 'human_voice'),
            source_file=('const',
                         'tests/data/audio/foreground/'
                         'human_voice/42-Human-Vocal-Voice-taxi-2_edit.wav'),
            source_time=('const', 0),
            event_time=('const', 7),
            event_duration=('const', 2),
            snr=('const', 10),
            pitch_shift=None,
            time_stretch=('const', 1.2))

        jam = sc._instantiate(disable_instantiation_warnings=True)
        regjam = jams.load(REG_JAM_PATH)
        _compare_scaper_jams(jam, regjam)


def test_generate_with_seeding(atol=1e-4, rtol=1e-8):
    # test a scaper generator with different random seeds. init with same random seed
    # over and over to make sure the output wav stays the same
    seeds = [
        0, 10, 20, 
        scaper.util._check_random_state(0),
        scaper.util._check_random_state(10),
        scaper.util._check_random_state(20)
    ]
    num_generators = 2
    for seed in seeds:
        generators = []
        for i in range(num_generators):
            generators.append(_create_scaper_with_random_seed(deepcopy(seed)))

        _compare_generators(generators)


def test_set_random_state(atol=1e-4, rtol=1e-8):
    # test a scaper generator with different random seeds. this time use
    # set_random_state to change the seed instead 
    seeds = [
        0, 10, 20, 
        scaper.util._check_random_state(0),
        scaper.util._check_random_state(10),
        scaper.util._check_random_state(20)
    ]
    num_generators = 2
    for seed in seeds:
        generators = []
        for i in range(num_generators):
            _sc = _create_scaper_with_random_seed(None)
            _sc.set_random_state(deepcopy(seed))
            generators.append(_sc)

        _compare_generators(generators)


def _compare_generators(generators, atol=1e-4, rtol=1e-8):
    tmpfiles = []
    with _close_temp_files(tmpfiles):
        wav_files = [
            tempfile.NamedTemporaryFile(suffix='.wav', delete=True) 
            for i in range(len(generators))
        ]
        jam_files = [
            tempfile.NamedTemporaryFile(suffix='.jams', delete=True) 
            for i in range(len(generators))
        ]
        txt_files = [
            tempfile.NamedTemporaryFile(suffix='.txt', delete=True) 
            for i in range(len(generators))
        ]

        tmpfiles += wav_files + jam_files + txt_files
        for i, sc in enumerate(generators):
            generators[i].generate(
                wav_files[i].name, jam_files[i].name, txt_path=txt_files[i].name,
                    disable_instantiation_warnings=True
            )
        
        audio = [soundfile.read(wav_file.name)[0] for wav_file in wav_files]
        for i, a in enumerate(audio):
            assert np.allclose(audio[0], a, atol=atol, rtol=rtol)

        # load all the jams data
        # make sure they are all the same as the first one
        jams_data = [jams.load(jam_file.name) for jam_file in jam_files]
        for x in jams_data:
            _compare_scaper_jams(x, jams_data[0])

        # load the txt files and compare them
        def _load_txt(txt_file):
            txt_data = []
            with open(txt_file.name) as file:
                reader = csv.reader(file, delimiter='\t')
                for row in reader:
                    txt_data.append(row)
            txt_data = np.asarray(txt_data)
            return txt_data
        
        txt_data = [_load_txt(txt_file) for txt_file in txt_files]
        regtxt_data = txt_data[0]

        for t in txt_data:
            assert np.allclose([float(x) for x in t[:, 0]],
                                [float(x) for x in regtxt_data[:, 0]])
            assert np.allclose([float(x) for x in t[:, 1]],
                                [float(x) for x in regtxt_data[:, 1]])
            # compare labels
            assert (t[:, 2] == regtxt_data[:, 2]).all()


def _create_scaper_with_random_seed(seed):
    sc = scaper.Scaper(10.0, fg_path=FG_PATH, bg_path=BG_PATH, random_state=deepcopy(seed))
    sc.ref_db = -50
    sc.sr = 44100

    # background
    sc.add_background(
        label=('choose', []),
        source_file=('choose', []),
        source_time=('const', 0))

    # foreground events
    sc.add_event(
        label=('choose', []),
        source_file=('choose', []),
        source_time=('uniform', 0, 8),
        event_time=('truncnorm', 4, 1, 0, 8),
        event_duration=('normal', 4, 1),
        snr=('const', 5),
        pitch_shift=None,
        time_stretch=None)

    sc.add_event(
        label=('choose', []),
        source_file=('choose', []),
        source_time=('uniform', 0, 8),
        event_time=('truncnorm', 4, 1, 0, 8),
        event_duration=('normal', 4, 1),
        snr=('const', 20),
        pitch_shift=None,
        time_stretch=None)

    sc.add_event(
        label=('choose', []),
        source_file=('choose', []),
        source_time=('const', 0),
        event_time=('const', 7),
        event_duration=('const', 2),
        snr=('const', 10),
        pitch_shift=None,
        time_stretch=None)

    return sc


def test_generate_audio():
    for sr in SAMPLE_RATES:
        REG_WAV_PATH = TEST_PATHS[sr]['REG'].wav
        REG_BGONLY_WAV_PATH = TEST_PATHS[sr]['REG_BGONLY'].wav
        REG_REVERB_WAV_PATH = TEST_PATHS[sr]['REG_REVERB'].wav
        _test_generate_audio(sr, REG_WAV_PATH, REG_BGONLY_WAV_PATH, REG_REVERB_WAV_PATH)


def _test_generate_audio(SR, REG_WAV_PATH, REG_BGONLY_WAV_PATH, REG_REVERB_WAV_PATH, atol=1e-4, rtol=1e-8):
    # Regression test: same spec, same audio (not this will fail if we update
    # any of the audio processing techniques used (e.g. change time stretching
    # algorithm.
    sc = scaper.Scaper(10.0, fg_path=FG_PATH, bg_path=BG_PATH)
    sc.ref_db = -50
    sc.sr = SR

    print("TEST SR: {}".format(SR))

    # background
    sc.add_background(
        label=('const', 'park'),
        source_file=(
            'const',
            'tests/data/audio/background/park/'
            '268903__yonts__city-park-tel-aviv-israel.wav'),
        source_time=('const', 0))

    # foreground events
    sc.add_event(
        label=('const', 'siren'),
        source_file=('const',
                     'tests/data/audio/foreground/'
                     'siren/69-Siren-1.wav'),
        source_time=('const', 5),
        event_time=('const', 2),
        event_duration=('const', 5),
        snr=('const', 5),
        pitch_shift=None,
        time_stretch=None)

    sc.add_event(
        label=('const', 'car_horn'),
        source_file=('const',
                     'tests/data/audio/foreground/'
                     'car_horn/17-CAR-Rolls-Royce-Horn.wav'),
        source_time=('const', 0),
        event_time=('const', 5),
        event_duration=('const', 2),
        snr=('const', 20),
        pitch_shift=('const', 1),
        time_stretch=None)

    sc.add_event(
        label=('const', 'human_voice'),
        source_file=('const',
                     'tests/data/audio/foreground/'
                     'human_voice/42-Human-Vocal-Voice-taxi-2_edit.wav'),
        source_time=('const', 0),
        event_time=('const', 7),
        event_duration=('const', 2),
        snr=('const', 10),
        pitch_shift=None,
        time_stretch=('const', 1.2))

    tmpfiles = []
    with _close_temp_files(tmpfiles):

        wav_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=True)
        tmpfiles.append(wav_file)

        jam = sc._instantiate(disable_instantiation_warnings=True)
        sc._generate_audio(wav_file.name, jam.annotations[0])

        # validate audio
        wav, sr = soundfile.read(wav_file.name)
        regwav, sr = soundfile.read(REG_WAV_PATH)
        assert np.allclose(wav, regwav, atol=atol, rtol=rtol)

        # with reverb
        sc._generate_audio(wav_file.name, jam.annotations[0], reverb=0.2)
        # validate audio
        wav, sr = soundfile.read(wav_file.name)
        regwav, sr = soundfile.read(REG_REVERB_WAV_PATH)
        assert np.allclose(wav, regwav, atol=atol, rtol=rtol)

        # Don't disable sox warnings (just to cover line)
        sc._generate_audio(wav_file.name, jam.annotations[0],
                           disable_sox_warnings=False)
        # validate audio
        wav, sr = soundfile.read(wav_file.name)
        regwav, sr = soundfile.read(REG_WAV_PATH)
        assert np.allclose(wav, regwav, atol=atol, rtol=rtol)

        # namespace must be scaper
        jam.annotations[0].namespace = 'tag_open'
        pytest.raises(ScaperError, sc._generate_audio, wav_file.name,
                      jam.annotations[0])

        # unsupported event role must raise error
        jam.annotations[0].namespace = 'scaper'
        jam.annotations[0].data[3].value['role'] = 'ewok'
        pytest.raises(ScaperError, sc._generate_audio, wav_file.name,
                      jam.annotations[0])

        # soundscape with no events will raise warning and won't generate audio
        sc = scaper.Scaper(10.0, fg_path=FG_PATH, bg_path=BG_PATH)
        sc.ref_db = -50
        jam = sc._instantiate(disable_instantiation_warnings=True)
        pytest.warns(ScaperWarning, sc._generate_audio, wav_file.name,
                     jam.annotations[0])

        # soundscape with only one event will use transformer (regression test)
        sc = scaper.Scaper(10.0, fg_path=FG_PATH, bg_path=BG_PATH)
        sc.ref_db = -20
        sc.sr = SR
        # background
        sc.add_background(
            label=('const', 'park'),
            source_file=('const',
                         'tests/data/audio/background/park/'
                         '268903__yonts__city-park-tel-aviv-israel.wav'),
            source_time=('const', 0))

        reverb = 0.2
        jam = sc._instantiate(disable_instantiation_warnings=True, reverb=reverb)
        sc._generate_audio(wav_file.name, jam.annotations[0], reverb=reverb)
        # validate audio
        wav, sr = soundfile.read(wav_file.name)
        regwav, sr = soundfile.read(REG_BGONLY_WAV_PATH)
        assert np.allclose(wav, regwav, atol=atol, rtol=rtol)


def create_scaper_scene_without_random_seed():
    sc = scaper.Scaper(10.0, fg_path=FG_PATH, bg_path=BG_PATH)
    sc.ref_db = -50
    sc.sr = 44100

    # background
    sc.add_background(
        label=('const', 'park'),
        source_file=(
            'const',
            'tests/data/audio/background/park/'
            '268903__yonts__city-park-tel-aviv-israel.wav'),
        source_time=('const', 0))

    # foreground events
    sc.add_event(
        label=('const', 'siren'),
        source_file=('const',
                     'tests/data/audio/foreground/'
                     'siren/69-Siren-1.wav'),
        source_time=('uniform', 0, 5),
        event_time=('normal', 5, 1),
        event_duration=('truncnorm', 5, 1, 4, 6),
        snr=('const', 5),
        pitch_shift=None,
        time_stretch=None)

    sc.add_event(
        label=('const', 'car_horn'),
        source_file=('const',
                     'tests/data/audio/foreground/'
                     'car_horn/17-CAR-Rolls-Royce-Horn.wav'),
        source_time=('const', 0),
        event_time=('const', 5),
        event_duration=('truncnorm', 3, 1, 1, 10),
        snr=('uniform', 10, 20),
        pitch_shift=('uniform', -1, 1),
        time_stretch=(None))

    sc.add_event(
        label=('const', 'human_voice'),
        source_file=('const',
                     'tests/data/audio/foreground/'
                     'human_voice/42-Human-Vocal-Voice-taxi-2_edit.wav'),
        source_time=('const', 0),
        event_time=('const', 7),
        event_duration=('const', 2),
        snr=('const', 10),
        pitch_shift=('uniform', -1, 1),
        time_stretch=('uniform', .8, 1.2))
        
    return sc    


def _test_generate_isolated_events(SR, isolated_events_path=None, atol=1e-4, rtol=1e-8):
    sc = create_scaper_scene_without_random_seed()
    tmpfiles = []

    @contextmanager
    def _delete_files(mix_file, directory):
        yield
        try:
            shutil.rmtree(directory)
            os.remove(mix_file)
        except:
            pass

    wav_file = 'tests/mix.wav'
    if isolated_events_path is None:
        isolated_events_path = 'tests/mix_events'
    with _delete_files(wav_file, isolated_events_path):
        jam = sc._instantiate(disable_instantiation_warnings=True)
        sc._generate_audio(wav_file, jam.annotations[0], save_isolated_events=True, 
                           isolated_events_path=isolated_events_path)
        source_directory = os.path.splitext(wav_file)[0] + '_events'
        

        isolated_events = []
        ann = jam.annotations.search(namespace='scaper')[0]

        soundscape_audio, _ = soundfile.read(ann.sandbox.scaper.soundscape_audio_path)
        isolated_event_audio_paths = ann.sandbox.scaper.isolated_events_audio_path
        isolated_audio = []

        role_counter = {
            'background': 0,
            'foreground': 0
        }

        for event_spec, event_audio_path in zip(ann, isolated_event_audio_paths):
            # event_spec contains the event description, label, etc
            # event_audio contains the path to the actual audio

            # make sure the path matches the event description
            look_for = '{:s}{:d}_{:s}.wav'.format(
                event_spec.value['role'], 
                role_counter[event_spec.value['role']],
                event_spec.value['label']
            )

            expected_path = os.path.join(isolated_events_path, look_for)
            # make sure the path exists
            assert os.path.exists(expected_path)

            # make sure what's in the sandbox also exists
            assert os.path.exists(event_audio_path)
            # is an audio file with the same contents as what we expect
            _isolated_expected_audio, sr = soundfile.read(expected_path)
            _isolated_sandbox_audio, sr = soundfile.read(event_audio_path)
            assert np.allclose(_isolated_sandbox_audio, _isolated_expected_audio)

            # make sure the filename matches
            assert look_for == os.path.basename(event_audio_path)

            # increment for the next role
            role_counter[event_spec.value['role']] += 1

            isolated_audio.append(_isolated_sandbox_audio)

        # the sum of the isolated audio should sum to the soundscape
        assert np.allclose(sum(isolated_audio), soundscape_audio, atol=1e-4, rtol=1e-8)

        jam = sc._instantiate(disable_instantiation_warnings=True)

        # Running with save_isolated_events = True and reverb not None raises a warning
        pytest.warns(ScaperWarning, sc._generate_audio, wav_file,
                    jam.annotations[0], save_isolated_events=True, reverb=.5)


def test_generate_isolated_events():
    for sr, isolated_events_path in zip(
            (16000, 22050, 44100), (None, 'tests/mix_events', None)):
        # try it a bunch of times
        for i in range(10):
            _test_generate_isolated_events(sr, isolated_events_path)


def test_generate():
    for sr in SAMPLE_RATES:
        REG_WAV_PATH, REG_JAM_PATH, REG_TXT_PATH = TEST_PATHS[sr]['REG']
        _test_generate(sr, REG_WAV_PATH, REG_JAM_PATH, REG_TXT_PATH)


def _test_generate(SR, REG_WAV_PATH, REG_JAM_PATH, REG_TXT_PATH, atol=1e-4, rtol=1e-8):
    # Final regression test on all files
    sc = scaper.Scaper(10.0, fg_path=FG_PATH, bg_path=BG_PATH)
    sc.ref_db = -50
    sc.sr = SR

    # background
    sc.add_background(
        label=('const', 'park'),
        source_file=(
            'const',
            'tests/data/audio/background/park/'
            '268903__yonts__city-park-tel-aviv-israel.wav'),
        source_time=('const', 0))

    # foreground events
    sc.add_event(
        label=('const', 'siren'),
        source_file=('const',
                     'tests/data/audio/foreground/'
                     'siren/69-Siren-1.wav'),
        source_time=('const', 5),
        event_time=('const', 2),
        event_duration=('const', 5),
        snr=('const', 5),
        pitch_shift=None,
        time_stretch=None)

    sc.add_event(
        label=('const', 'car_horn'),
        source_file=('const',
                     'tests/data/audio/foreground/'
                     'car_horn/17-CAR-Rolls-Royce-Horn.wav'),
        source_time=('const', 0),
        event_time=('const', 5),
        event_duration=('const', 2),
        snr=('const', 20),
        pitch_shift=('const', 1),
        time_stretch=None)

    sc.add_event(
        label=('const', 'human_voice'),
        source_file=('const',
                     'tests/data/audio/foreground/'
                     'human_voice/42-Human-Vocal-Voice-taxi-2_edit.wav'),
        source_time=('const', 0),
        event_time=('const', 7),
        event_duration=('const', 2),
        snr=('const', 10),
        pitch_shift=None,
        time_stretch=('const', 1.2))

    tmpfiles = []
    with _close_temp_files(tmpfiles):
        wav_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=True)
        jam_file = tempfile.NamedTemporaryFile(suffix='.jams', delete=True)
        txt_file = tempfile.NamedTemporaryFile(suffix='.txt', delete=True)
        tmpfiles.append(wav_file)
        tmpfiles.append(jam_file)
        tmpfiles.append(txt_file)

        sc.generate(wav_file.name, jam_file.name, txt_path=txt_file.name,
                    disable_instantiation_warnings=True)

        # validate audio
        wav, sr = soundfile.read(wav_file.name)
        regwav, sr = soundfile.read(REG_WAV_PATH)
        assert np.allclose(wav, regwav, atol=atol, rtol=rtol)

        # validate jams
        jam = jams.load(jam_file.name)
        regjam = jams.load(REG_JAM_PATH)
        _compare_scaper_jams(jam, regjam)

        # validate txt
        # read in both files
        txt_data = []
        with open(txt_file.name) as file:
            reader = csv.reader(file, delimiter='\t')
            for row in reader:
                txt_data.append(row)
        txt_data = np.asarray(txt_data)

        regtxt_data = []
        with open(REG_TXT_PATH) as file:
            reader = csv.reader(file, delimiter='\t')
            for row in reader:
                regtxt_data.append(row)
        regtxt_data = np.asarray(regtxt_data)

        # compare start and end times
        assert np.allclose([float(x) for x in txt_data[:, 0]],
                           [float(x) for x in regtxt_data[:, 0]])
        assert np.allclose([float(x) for x in txt_data[:, 1]],
                           [float(x) for x in regtxt_data[:, 1]])
        # compare labels
        assert (txt_data[:, 2] == regtxt_data[:, 2]).all()

        # reverb value must be in (0, 1) range
        for reverb in [-1, 2]:
            pytest.raises(ScaperError, sc.generate, wav_file.name,
                          jam_file.name, reverb=reverb,
                          disable_instantiation_warnings=True)


def test_scaper_off_by_one_with_jams():
    # this file broke in Scaper 1.3.3 and before as the duration
    # of the generated audio was incorrect. it was addressed by PR #88.
    # using it to test if it will ever break again
    jam_file = 'tests/data/regression/scaper_133_off_by_one_regression_test.jams'
    tmpfiles = []
    with _close_temp_files(tmpfiles):
        gen_wav_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=True)
        scaper.generate_from_jams(jam_file, gen_wav_file.name)
        gen_wav, sr = soundfile.read(gen_wav_file.name)

        assert gen_wav.shape[0] == 10 * 44100


def test_backwards_compat_for_duration():
    for sr in SAMPLE_RATES:
        REG_JAM_PATH = TEST_PATHS[sr]['REG'].jams
        tmpfiles = []
        with _close_temp_files(tmpfiles):
            orig_wav = tempfile.NamedTemporaryFile(suffix='.wav', delete=True)
            gen_wav = tempfile.NamedTemporaryFile(suffix='.wav', delete=True)
            jam_without_orig_duration = tempfile.NamedTemporaryFile(
                suffix='.jams', delete=True)

            jam = jams.load(REG_JAM_PATH)

            scaper.generate_from_jams(REG_JAM_PATH, orig_wav.name)

            ann = jam.annotations[0]
            ann.sandbox.scaper.pop('original_duration')
            jam.save(jam_without_orig_duration.name)

            scaper.generate_from_jams(
                jam_without_orig_duration.name, gen_wav.name)

            orig_audio, sr = soundfile.read(orig_wav.name)
            gen_audio, sr = soundfile.read(gen_wav.name)

            assert np.allclose(orig_audio, gen_audio)

            pytest.warns(ScaperWarning, scaper.generate_from_jams,
                jam_without_orig_duration.name, gen_wav.name)


def _generate_soundscape_with_short_background(background_file, audio_path, jams_path, ref_db):
    with backports.tempfile.TemporaryDirectory() as tmpdir:
        subdir = os.path.join(tmpdir, 'audio')
        shutil.copytree(SHORT_BG_PATH, subdir)
        OUTPUT_PATH = os.path.join(subdir, 'noise', 'noise.wav')
        shutil.copyfile(background_file, OUTPUT_PATH)

        sc = scaper.Scaper(10, FG_PATH, subdir, random_state=0)
        sc.sr = 16000
        sc.ref_db = ref_db
        sc.fade_in_len = 0
        sc.fade_out_len = 0

        sc.add_background(
            label=('const', 'noise'),
            source_file=('const', OUTPUT_PATH),
            source_time=('const', 0)
        )

        sc.generate(audio_path, jams_path)


def test_scaper_with_short_background():
    SHORT_BG_FILE = os.path.join(
        SHORT_BG_PATH, 'noise', 'noise-free-sound-0145.wav')

    tmpfiles = []
    with _close_temp_files(tmpfiles):
        jam_file = tempfile.NamedTemporaryFile(suffix='.jams', delete=True)
        tiled_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=True)
        wav1_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=True)
        wav2_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=True)

        tmpfiles.append(wav1_file)
        tmpfiles.append(wav2_file)
        tmpfiles.append(tiled_file)
        tmpfiles.append(jam_file)

        _generate_soundscape_with_short_background(
            SHORT_BG_FILE, wav1_file.name, jam_file.name, ref_db=-40)

        # what it should be is the file tiled with itself and then cut to 10s
        # write it to disk and then use it in a new scaper object
        source_audio, sr = soundfile.read(SHORT_BG_FILE)
        duration_samples = int(10 * sr)

        # tile the audio to what we expect
        tiled_audio = np.tile(
            source_audio, 1 + int(duration_samples / source_audio.shape[0]))

        # cut it to what we want
        tiled_audio = tiled_audio[:duration_samples]

        # save it somewhere to be used in a new Scaper object
        soundfile.write(tiled_file.name, tiled_audio, sr)

        _generate_soundscape_with_short_background(
            tiled_file.name, wav2_file.name, jam_file.name, ref_db=-40)

        # compare what is generated with a short bg compared to a long bg
        # should be the same
        audio1, sr = soundfile.read(wav1_file.name)
        audio2, sr = soundfile.read(wav2_file.name)

        assert np.allclose(audio1, audio2)
