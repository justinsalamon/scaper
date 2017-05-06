
import scaper
from scaper.scaper_exceptions import ScaperError
import pytest
from scaper.core import EventSpec


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

