import sox
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


# FIXTURES
# Paths to files for testing
FG_PATH = 'tests/data/audio/foreground'
BG_PATH = 'tests/data/audio/background'

ALT_FG_PATH = 'tests/data/audio_alt_path/foreground'
ALT_BG_PATH = 'tests/data/audio_alt_path/background'

_EXTS = ('wav', 'jams', 'txt')
_TestFiles = namedtuple('TestFiles', _EXTS)

def _get_test_paths(name):
    return _TestFiles(*[
        os.path.join('tests/data/regression/', name + '.' + ext)
        for ext in _EXTS
    ])

TEST_PATHS = {
    22050: {
        'REG': _get_test_paths('soundscape_20190401_22050'),
        'REG_BGONLY': _get_test_paths('bgonly_soundscape_20190326_22050'),
        'REG_REVERB': _get_test_paths('reverb_soundscape_20190401_22050'),
    },
    44100: {
        'REG': _get_test_paths('soundscape_20170928'),
        'REG_BGONLY': _get_test_paths('bgonly_soundscape_20170928'),
        'REG_REVERB': _get_test_paths('reverb_soundscape_20170928'),
    },
}

# fg and bg labels for testing
FG_LABELS = ['car_horn', 'human_voice', 'siren']
BG_LABELS = ['birds', 'park', 'restaurant', 'street']


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

    # everything but the specs and version can be compared directly:
    for k in set(ann.sandbox.scaper.keys()) | set(regann.sandbox.scaper.keys()):
        if k not in ['bg_spec', 'fg_spec', 'scaper_version']:
            assert ann.sandbox.scaper[k] == regann.sandbox.scaper[k], (
                'Unequal values for "{}"'.format(k))

    # to compare specs need to covert raw specs to list of lists
    assert ([[list(x) if isinstance(x, tuple) else x for x in e] for e in
             ann.sandbox.scaper['bg_spec']] == regann.sandbox.scaper['bg_spec'])

    assert ([[list(x) if isinstance(x, tuple) else x for x in e] for e in
             ann.sandbox.scaper['fg_spec']] == regann.sandbox.scaper['fg_spec'])

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
        # repeat 5 time
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

        # Tripple trimming
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
        assert orig_jam == gen_jam


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

    # const
    x = scaper.core._get_value_from_dist(('const', 1))
    assert x == 1

    # choose
    for _ in range(10):
        x = scaper.core._get_value_from_dist(('choose', [1, 2, 3]))
        assert x in [1, 2, 3]

    # uniform
    for _ in range(10):
        x = scaper.core._get_value_from_dist(('choose', [1, 2, 3]))
        assert x in [1, 2, 3]

    # normal
    for _ in range(10):
        x = scaper.core._get_value_from_dist(('normal', 5, 1))
        assert scaper.util.is_real_number(x)

    # truncnorm
    for _ in range(10):
        x = scaper.core._get_value_from_dist(('truncnorm', 5, 10, 0, 10))
        assert scaper.util.is_real_number(x)
        assert 0 <= x <= 10

    # COPY TESTS FROM test_validate_distribution (to ensure validation applied)
    def __test_bad_tuple_list(tuple_list):
        for t in tuple_list:
            if isinstance(t, tuple):
                print(t, len(t))
            else:
                print(t)
            pytest.raises(ScaperError, scaper.core._get_value_from_dist, t)

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
    assert sc.fg_labels == FG_LABELS
    assert sc.bg_labels == BG_LABELS

    # ensure default values have been set
    assert sc.sr == 44100
    assert sc.ref_db == -12
    assert sc.n_channels == 1
    assert sc.fade_in_len == 0.01  # 10 ms
    assert sc.fade_out_len == 0.01  # 10 ms


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
    # test scaper default event values
    duration = 10.0
    sc = scaper.Scaper(duration, fg_path=FG_PATH, bg_path=BG_PATH)

    # check background event defaults
    sc.add_background()
    bg_event = sc.bg_spec[0]
    instantiated_event = sc._instantiate_event(
        bg_event, allow_repeated_label=True,
        allow_repeated_source=True, used_labels=[], used_source_files=[],
        disable_instantiation_warnings=True)

    # make sure a proper source file was selected
    assert os.path.isfile(instantiated_event.source_file)

    # Get the duration of the source audio file
    source_duration = sox.file_info.duration(instantiated_event.source_file)
    max_source_time = source_duration - instantiated_event.event_duration
    assert instantiated_event.event_duration == duration
    assert 0 <= instantiated_event.source_time <= max_source_time

    # check foreground event defaults
    sc.add_event()
    fg_event = sc.fg_spec[0]
    instantiated_event = sc._instantiate_event(
        fg_event, allow_repeated_label=True,
        allow_repeated_source=True, used_labels=[], used_source_files=[],
        disable_instantiation_warnings=True)

    # make sure a proper source file was selected
    assert os.path.isfile(instantiated_event.source_file)

    # Get the duration of the source audio file
    source_duration = sox.file_info.duration(instantiated_event.source_file)
    max_event_time = duration - instantiated_event.event_duration
    assert 0 <= instantiated_event.event_duration <= source_duration
    assert 0 <= instantiated_event.event_time <= max_event_time


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
        fg_event, allow_repeated_label=True,
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
            fg_event8, allow_repeated_label=False,
            allow_repeated_source=True, used_labels=['siren', 'human_voice'],
            disable_instantiation_warnings=True)
        assert instantiated_event.label == 'car_horn'

    # when a source file needs to be replaced because it's used already
    fg_event9 = fg_event._replace(label=('const', 'human_voice'))
    # repeat several times to increase chance of hitting the line we need to
    # test
    for _ in range(20):
        instantiated_event = sc._instantiate_event(
            fg_event9, allow_repeated_label=True,
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
    assert instantiated_event.event_duration == 0.806236

    # repeated label when not allowed throws error
    sc = scaper.Scaper(10.0, fg_path=FG_PATH, bg_path=BG_PATH)
    pytest.raises(ScaperError, sc._instantiate_event, fg_event,
                  allow_repeated_label=False,
                  allow_repeated_source=True,
                  used_labels=['siren'])

    # repeated source when not allowed throws error
    pytest.raises(ScaperError, sc._instantiate_event, fg_event,
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

    # source_time + event_duration > source_duration: warning
    fg_event5 = fg_event._replace(event_time=('const', 0),
                                  event_duration=('const', 8),
                                  source_time=('const', 20))
    pytest.warns(ScaperWarning, sc._instantiate_event, fg_event5)

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


def _create_test_scaper(sr):
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

    sc.add_background(
        label=('const', 'birds'),
        source_file=(
            'const',
            'tests/data/audio/background/birds/'
            '142009__jop9798__birds-in-the-city-1.wav'),
        source_time=('const', 0),
        snr=('const', -10))

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

    return sc

def test_scaper_instantiate():
    for sr in (44100, 22050):
        REG_JAM_PATH = TEST_PATHS[sr]['REG'].jams
        # Here we just instantiate a known fixed spec and check if that jams
        # we get back is as expected.
        sc = _create_test_scaper(sr)

        jam = sc._instantiate(disable_instantiation_warnings=True)
        regjam = jams.load(REG_JAM_PATH)
        _compare_scaper_jams(jam, regjam)


def test_generate_audio():
    for sr in (44100, 22050):
        REG_WAV_PATH = TEST_PATHS[sr]['REG'].wav
        REG_BGONLY_WAV_PATH = TEST_PATHS[sr]['REG_BGONLY'].wav
        REG_REVERB_WAV_PATH = TEST_PATHS[sr]['REG_REVERB'].wav
        _test_generate_audio(sr, REG_WAV_PATH, REG_BGONLY_WAV_PATH, REG_REVERB_WAV_PATH)


def _test_generate_audio(SR, REG_WAV_PATH, REG_BGONLY_WAV_PATH, REG_REVERB_WAV_PATH, atol=1e-4, rtol=1e-8):
    # Regression test: same spec, same audio (not this will fail if we update
    # any of the audio processing techniques used (e.g. change time stretching
    # algorithm.
    sc = _create_test_scaper(SR)

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


def test_generate():
    for sr in (44100, 22050):
        REG_WAV_PATH, REG_JAM_PATH, REG_TXT_PATH = TEST_PATHS[sr]['REG']
        _test_generate(sr, REG_WAV_PATH, REG_JAM_PATH, REG_TXT_PATH)


def _test_generate(SR, REG_WAV_PATH, REG_JAM_PATH, REG_TXT_PATH, atol=1e-4, rtol=1e-8):
    # Final regression test on all files
    sc = _create_test_scaper(SR)

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
