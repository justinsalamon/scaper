# CREATED: 10/15/16 7:52 PM by Justin Salamon <justin.salamon@nyu.edu>

'''
Tests for functions in util.py
'''

from scaper.util import _close_temp_files
from scaper.util import _set_temp_logging_level
from scaper.util import _validate_folder_path
from scaper.util import _get_sorted_files
from scaper.util import _populate_label_list
from scaper.util import _sample_trunc_norm, _sample_choose
from scaper.util import max_polyphony
from scaper.util import polyphony_gini
from scaper.util import is_real_number, is_real_array
from scaper.util import _check_random_state
from scaper.scaper_exceptions import ScaperError
from scaper.scaper_warnings import ScaperWarning
import tempfile
import os
import logging
import pytest
import shutil
import numpy as np
from scipy.stats import truncnorm
import jams
from scaper.core import EventSpec
from scaper import Scaper


# FIXTURES
BG_PATH = 'tests/data/audio/background/'
FG_PATH = 'tests/data/audio/foreground/'
FG_PATH_HUMANVOICE = 'tests/data/audio/foreground/human_voice'

FG_LABEL_LIST = ['car_horn', 'human_voice', 'siren']
HUMANVOICE_FILES = (
    [os.path.join(FG_PATH_HUMANVOICE,
                  '42-Human-Vocal-Voice-all-aboard_edit.wav'),
     os.path.join(FG_PATH_HUMANVOICE, '42-Human-Vocal-Voice-taxi-1_edit.wav'),
     os.path.join(FG_PATH_HUMANVOICE, '42-Human-Vocal-Voice-taxi-2_edit.wav')])
SIREN_FILE = os.path.join(FG_PATH, 'siren', '69-Siren-1.wav')


def test_close_temp_files():
    '''
    Create a bunch of temp files and then make sure they've been closed and
    deleted.

    '''
    # With delete=True
    tmpfiles = []
    with _close_temp_files(tmpfiles):
        for _ in range(5):
            tmpfiles.append(
                tempfile.NamedTemporaryFile(suffix='.wav', delete=True))

    for tf in tmpfiles:
        assert tf.file.closed
        assert not os.path.isfile(tf.name)

    # With delete=False
    tmpfiles = []
    with _close_temp_files(tmpfiles):
        for _ in range(5):
            tmpfiles.append(
                tempfile.NamedTemporaryFile(suffix='.wav', delete=False))

    for tf in tmpfiles:
        assert tf.file.closed
        assert not os.path.isfile(tf.name)

    # with an exception before exiting
    try:
        tmpfiles = []
        with _close_temp_files(tmpfiles):
            tmpfiles.append(
                tempfile.NamedTemporaryFile(suffix='.wav', delete=True))
            raise ScaperError
    except ScaperError:
        for tf in tmpfiles:
            assert tf.file.closed
            assert not os.path.isfile(tf.name)
    else:
        assert False, 'Exception was not reraised.'


def test_set_temp_logging_level():
    '''
    Ensure temp logging level is set as expected

    '''
    logger = logging.getLogger()
    logger.setLevel('DEBUG')
    with _set_temp_logging_level('CRITICAL'):
        assert logging.getLevelName(logger.level) == 'CRITICAL'
    assert logging.getLevelName(logger.level) == 'DEBUG'


def test_get_sorted_files():
    '''
    Ensure files are returned in expected order.

    '''
    assert _get_sorted_files(FG_PATH_HUMANVOICE) == HUMANVOICE_FILES


def test_validate_folder_path():
    '''
    Make sure invalid folder paths are caught

    '''
    # bad folder path
    pytest.raises(ScaperError, _validate_folder_path,
                  '/path/to/invalid/folder/')

    # good folder path should raise no error
    # make temp folder
    tmpdir = tempfile.mkdtemp()
    # validate
    _validate_folder_path(tmpdir)
    # remove it
    shutil.rmtree(tmpdir)


def test_populate_label_list():
    '''
    Should add folder names contained within provided folder to provided list.

    '''
    labellist = []
    _populate_label_list(FG_PATH, labellist)
    assert sorted(labellist) == sorted(FG_LABEL_LIST)


def test_check_random_state():
    # seed is None
    rng_type = type(np.random.RandomState(10))
    rng = _check_random_state(None)
    assert type(rng) == rng_type

    # seed is int
    rng = _check_random_state(10)
    assert type(rng) == rng_type

    # seed is RandomState
    rng_test = np.random.RandomState(10)
    rng = _check_random_state(rng_test)
    assert type(rng) == rng_type

    # seed is none of the above : error
    pytest.raises(ValueError, _check_random_state, 'random')


def test_sample_choose():
    # using choose with duplicates will issue a warning
    rng = _check_random_state(0)
    pytest.warns(ScaperWarning, _sample_choose, [0, 1, 2, 2, 2], rng)


def test_sample_trunc_norm():
    '''
    Should return values from a truncated normal distribution.

    '''
    rng = _check_random_state(0)
    # sample values from a distribution
    mu, sigma, trunc_min, trunc_max = 2, 1, 0, 5
    x = [_sample_trunc_norm(mu, sigma, trunc_min, trunc_max, random_state=rng) for _ in range(100000)]
    x = np.asarray(x)

    # simple check: values must be within truncated bounds
    assert (x >= trunc_min).all() and (x <= trunc_max).all()

    # trickier check: values must approximate distribution's PDF
    hist, bins = np.histogram(x, bins=np.arange(0, 10.1, 0.2), density=True)
    xticks = bins[:-1] + 0.1
    a, b = (trunc_min - mu) / float(sigma), (trunc_max - mu) / float(sigma)
    trunc_closed = truncnorm.pdf(xticks, a, b, mu, sigma)
    assert np.allclose(hist, trunc_closed, atol=0.015)


def test_max_polyphony():
    '''
    Test the computation of polyphony of a scaper soundscape instantiation.

    '''
    def __create_annotation_with_overlapping_events(n_events):

        ann = jams.Annotation(namespace='scaper')
        ann.duration = n_events / 2. + 10

        for ind in range(n_events):
            instantiated_event = EventSpec(label='siren',
                                           source_file='/the/source/file.wav',
                                           source_time=0,
                                           event_time=ind / 2.,
                                           event_duration=10,
                                           snr=0,
                                           role='foreground',
                                           pitch_shift=None,
                                           time_stretch=None)

            ann.append(time=ind / 2.,
                       duration=10,
                       value=instantiated_event._asdict(),
                       confidence=1.0)

        return ann

    def __create_annotation_without_overlapping_events(n_events):

        ann = jams.Annotation(namespace='scaper')
        ann.duration = n_events * 10

        for ind in range(n_events):
            instantiated_event = EventSpec(label='siren',
                                           source_file='/the/source/file.wav',
                                           source_time=0,
                                           event_time=ind * 10,
                                           event_duration=5,
                                           snr=0,
                                           role='foreground',
                                           pitch_shift=None,
                                           time_stretch=None)

            ann.append(time=ind * 10,
                       duration=5,
                       value=instantiated_event._asdict(),
                       confidence=1.0)

        return ann

    # 0 through 10 overlapping events
    for poly in range(11):
        ann = __create_annotation_with_overlapping_events(poly)
        est_poly = max_polyphony(ann)
        assert est_poly == poly

    # 1 through 10 NON-overlapping events
    for n_events in range(1, 11):
        ann = __create_annotation_without_overlapping_events(n_events)
        est_poly = max_polyphony(ann)
        assert est_poly == 1


def test_polyphony_gini():
    '''
    Test computation of polyphony gini
    '''

    # Annotation must have namespace scaper, otherwise raise error
    ann = jams.Annotation('tag_open', duration=10)
    gini = pytest.raises(ScaperError, polyphony_gini, ann)

    # Annotation without duration set should raise error
    ann = jams.Annotation('scaper', duration=None)
    gini = pytest.raises(ScaperError, polyphony_gini, ann)

    # Annotation with no foreground events returns a gini of 0
    sc = Scaper(10.0, FG_PATH, BG_PATH)

    # add background
    sc.add_background(label=('choose', []),
                      source_file=('choose', []),
                      source_time=('const', 0))
    jam = sc._instantiate()
    ann = jam.annotations[0]
    gini = polyphony_gini(ann)
    assert gini == 0

    def __test_gini_from_event_times(event_time_list, expected_gini,
                                     hop_size=0.01):

        print(event_time_list)

        # create scaper
        sc = Scaper(10.0, FG_PATH, BG_PATH)

        # add background
        sc.add_background(label=('choose', []),
                          source_file=('choose', []),
                          source_time=('const', 0))

        # add foreground events based on the event time list
        # always use siren file since it is 26 s long, so we can choose the
        # event duration flexibly
        for onset, offset in event_time_list:

            sc.add_event(label=('const', 'siren'),
                         source_file=('const', SIREN_FILE),
                         source_time=('const', 0),
                         event_time=('const', onset),
                         event_duration=('const', offset - onset),
                         snr=('uniform', 6, 30),
                         pitch_shift=('uniform', -3, 3),
                         time_stretch=None)

        jam = sc._instantiate()
        ann = jam.annotations[0]
        gini = polyphony_gini(ann, hop_size=hop_size)
        print(gini, expected_gini)
        assert np.allclose([gini], [expected_gini], atol=1e-5)

    event_time_lists = ([
        [],
        [(0, 1)],
        [(0, 5), (5, 10)],
        [(0, 10), (3, 7), (4, 6)]
    ])

    expected_ginis = [0, 0.1, 1, 0.75]

    for etl, g in zip(event_time_lists, expected_ginis):
        __test_gini_from_event_times(etl, g, hop_size=0.01)

    for etl, g in zip(event_time_lists, expected_ginis):
        __test_gini_from_event_times(etl, g, hop_size=1.0)


def test_is_real_number():

    non_reals = [None, 1j, 'yes']
    yes_reals = [-1e12, -1, -1.0, 0, 1, 1.0, 1e12]

    # test single value
    for nr in non_reals:
        assert not is_real_number(nr)
    for yr in yes_reals:
        assert is_real_number(yr)


def test_is_real_array():

    non_reals = [None, 1j, 'yes']
    yes_reals = [-1e12, -1, -1.0, 0, 1, 1.0, 1e12]

    # non-list non-array types must return false
    for x in non_reals + yes_reals:
        assert not is_real_array(x)

    # test array
    for nr in non_reals:
        assert not is_real_array([nr])
    for yr in yes_reals:
        assert is_real_array([yr])
