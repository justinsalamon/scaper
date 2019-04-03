# CREATED: 5/5/17 14:36 by Justin Salamon <justin.salamon@nyu.edu>

from scaper.audio import r128stats, get_integrated_lufs, match_sample_length
from scaper.util import _close_temp_files
import numpy as np
import os
import pytest
from scaper.scaper_exceptions import ScaperError
from pkg_resources import resource_filename
import shutil
import soundfile as sf
import tempfile

# fixtures
SIREN_FILE = 'tests/data/audio/foreground/siren/69-Siren-1.wav'
CARHORN_FILE = (
    'tests/data/audio/foreground/car_horn/17-CAR-Rolls-Royce-Horn.wav')
HUMANVOICE_FILE = (
    'tests/data/audio/foreground/human_voice/'
    '42-Human-Vocal-Voice-all-aboard_edit.wav')
DOGBARK_FILE = 'tests/data/lufs/dogbark.wav'

SIREN_LUFS_I = -23.0
CARHORN_LUFS_I = -13.3
HUMANVOICE_LUFS_I = -20.0
DOGBARK_LUFS_I = -11.0  # for x4 concatenated file

SIREN_LUFS_DICT = {'I': -23.0, 'I Threshold': -33.1, 'LRA': 8.8,
                   'LRA High': -18.8, 'LRA Low': -27.6, 'LRA Threshold': -43.5}
CARHORN_LUFS_DICT = {'I': -13.3, 'I Threshold': -23.3, 'LRA': 0.0,
                     'LRA High': 0.0, 'LRA Low': 0.0, 'LRA Threshold': 0.0}
HUMANVOICE_LUFS_DICT = {'I': -20.0, 'I Threshold': -30.0, 'LRA': 0.0,
                        'LRA High': 0.0, 'LRA Low': 0.0, 'LRA Threshold': 0.0}
# for x4 concatenated file
DOGBARK_LUFS_DICT = {'I': -11.0, 'I Threshold': -21.0, 'LRA': 0.0,
                     'LRA High': 0.0, 'LRA Low': 0.0, 'LRA Threshold': 0.0}


def test_get_integrated_lufs():

    # should get error if can't return lufs
    fakefile = 'tests/data/audio/foreground/siren/fakefile.wav'
    pytest.raises(ScaperError, get_integrated_lufs, fakefile)

    # test correct functionality
    audiofiles = [SIREN_FILE, CARHORN_FILE, HUMANVOICE_FILE, DOGBARK_FILE]
    lufsi = [SIREN_LUFS_I, CARHORN_LUFS_I, HUMANVOICE_LUFS_I, DOGBARK_LUFS_I]

    for af, li in zip(audiofiles, lufsi):

        i = get_integrated_lufs(af)
        assert i == li


def test_match_sample_length():
    durations_to_match = [1, 2, 5, 7, 22500, 44100, 88200, 100001]
    invalid_durations_to_match = [0, -1, .5, 1.0]
    tmpfiles = []
    with _close_temp_files(tmpfiles):
        carhorn = tempfile.NamedTemporaryFile(suffix='.wav', delete=True)
        shutil.copyfile(CARHORN_FILE, carhorn.name)
        tmpfiles.append(carhorn)

        siren = tempfile.NamedTemporaryFile(suffix='.wav', delete=True)
        shutil.copyfile(SIREN_FILE, siren.name)
        tmpfiles.append(siren)

        for _duration in durations_to_match:
            match_sample_length(carhorn.name, _duration)
            carhorn_audio, _ = sf.read(carhorn.name)
            assert carhorn_audio.shape[0] == _duration

            match_sample_length(siren.name, _duration)
            siren_audio, _ = sf.read(siren.name)
            assert siren_audio.shape[0] == _duration

            # should be summable
            summed_events = sum([carhorn_audio, siren_audio])
            assert summed_events.shape[0] == _duration

        for _duration in invalid_durations_to_match:
            pytest.raises(ScaperError, match_sample_length, carhorn.name, _duration)
            pytest.raises(ScaperError, match_sample_length, siren.name, _duration)


def test_r128stats():

    # should return false if can't get data
    fakefile = 'tests/data/audio/foreground/siren/fakefile.wav'
    pytest.raises(ScaperError, r128stats, fakefile)

    # test correct functionality
    audiofiles = [SIREN_FILE, CARHORN_FILE, HUMANVOICE_FILE]
    lufs_dicts = [SIREN_LUFS_DICT, CARHORN_LUFS_DICT, HUMANVOICE_LUFS_DICT]

    for af, ld in zip(audiofiles, lufs_dicts):
        d = r128stats(af)
        assert d == ld
