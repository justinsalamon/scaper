
import scaper
from scaper.exceptions import ScaperError
import pytest


# FIXTURES
# Paths to files for testing
FG_PATH = 'tests/data/audio/foreground'
BG_PATH = 'tests/data/audio/background'

# fg and bg labels for testing
FB_LABELS = ['car_horn', 'human_voice', 'siren']
BG_LABELS = ['park', 'restaurant', 'street']


def test_scaper(recwarn):
    '''
    Test creation of Scaper object.
    '''

    # bad duration
    sc = pytest.raises(ScaperError, scaper.Scaper, -5)

    # only duration
    sc = pytest.warns(UserWarning, scaper.Scaper, 10.0)
    # for x in recwarn:
    #     print(x.message)
    assert len(recwarn) == 2
    assert sc.fg_path is None
    assert sc.bg_path is None

    # duration and fg_path
    sc = pytest.warns(UserWarning, scaper.Scaper, 10.0, fg_path=FG_PATH)
    assert len(recwarn) == 3
    assert sc.fg_path == FG_PATH
    assert sc.bg_path is None

    # all args
    sc = scaper.Scaper(10.0, FG_PATH, BG_PATH)
    assert sc.fg_path == FG_PATH
    assert sc.bg_path == BG_PATH
    assert len(recwarn) == 3

    # key value args
    sc = scaper.Scaper(10.0,
                       fg_path=FG_PATH,
                       bg_path=BG_PATH)
    assert sc.fg_path == FG_PATH
    assert sc.bg_path == BG_PATH
    assert len(recwarn) == 3

    # bad fg and bg paths
    sc = pytest.warns(UserWarning, scaper.Scaper, 10.0,
                      fg_path='tests/data/audio/wrong',
                      bg_path='tests/data/audio/wwrong')
    assert sc.fg_path is None
    assert sc.bg_path is None
    assert len(recwarn) == 5

    # ensure fg_labels and bg_labels populated properly
    sc = scaper.Scaper(10.0, FG_PATH, BG_PATH)
    assert sorted(sc.fg_labels) == sorted(FB_LABELS)
    assert sorted(sc.bg_labels) == sorted(BG_LABELS)
