# CREATED: 5/5/17 14:36 by Justin Salamon <justin.salamon@nyu.edu>

from scaper.audio import r128stats, get_integrated_lufs
import numpy as np
import os
import pytest
from scaper.scaper_exceptions import ScaperError
from pkg_resources import resource_filename

# fixtures
SIREN_FILE = 'tests/data/audio/foreground/siren/69-Siren-1.wav'
CARHORN_FILE = (
    'tests/data/audio/foreground/car_horn/17-CAR-Rolls-Royce-Horn.wav')
HUMANVOICE_FILE = (
    'tests/data/audio/foreground/human_voice/'
    '42-Human-Vocal-Voice-all-aboard_edit.wav')

SIREN_LUFS_I = -23.0
CARHORN_LUFS_I = -13.3
HUMANVOICE_LUFS_I = -20.0

SIREN_LUFS_DICT = {'I': -23.0, 'I Threshold': -33.1, 'LRA': 8.8,
                   'LRA High': -18.8, 'LRA Low': -27.6, 'LRA Threshold': -43.5}
CARHORN_LUFS_DICT = {'I': -13.3, 'I Threshold': -23.3, 'LRA': 0.0,
                     'LRA High': 0.0, 'LRA Low': 0.0, 'LRA Threshold': 0.0}
HUMANVOICE_LUFS_DICT = {'I': -20.0, 'I Threshold': -30.0, 'LRA': 0.0,
                        'LRA High': 0.0, 'LRA Low': 0.0, 'LRA Threshold': 0.0}


def test_get_integrated_lufs():

    # should get error (from r1238stats) if can't return lufs
    fakefile = 'tests/data/audio/foreground/siren/fakefile.wav'
    pytest.raises(ScaperError, get_integrated_lufs, fakefile)

    # test correct functionality
    audiofiles = [SIREN_FILE, CARHORN_FILE, HUMANVOICE_FILE]
    lufsi = [SIREN_LUFS_I, CARHORN_LUFS_I, HUMANVOICE_LUFS_I]

    for af, li in zip(audiofiles, lufsi):

        i = get_integrated_lufs(af)
        assert i == li


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
