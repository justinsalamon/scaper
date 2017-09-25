
import scaper
from scaper.scaper_exceptions import ScaperError
from scaper.scaper_warnings import ScaperWarning
import pytest
from scaper.core import EventSpec
# import tempfile
from backports import tempfile
import os


# FIXTURES
# Paths to files for testing
FG_PATH = 'tests/data/audio/foreground'
BG_PATH = 'tests/data/audio/background'

# fg and bg labels for testing
FB_LABELS = ['car_horn', 'human_voice', 'siren']
BG_LABELS = ['park', 'restaurant', 'street']


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
    assert sorted(sc.fg_labels) == sorted(FB_LABELS)
    assert sorted(sc.bg_labels) == sorted(BG_LABELS)


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
    with tempfile.TemporaryDirectory() as tmpdir:
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
    with tempfile.TemporaryDirectory() as tmpdir:
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

