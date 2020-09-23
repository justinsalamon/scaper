# CREATED: 5/5/17 14:36 by Justin Salamon <justin.salamon@nyu.edu>

from scaper.audio import get_integrated_lufs, match_sample_length
from scaper.util import _close_temp_files
import numpy as np
import os
import pytest
from scaper.scaper_exceptions import ScaperError
from pkg_resources import resource_filename
import shutil
import soundfile as sf
import tempfile
import random

# fixtures
SIREN_FILE = 'tests/data/audio/foreground/siren/69-Siren-1.wav'
CARHORN_FILE = (
    'tests/data/audio/foreground/car_horn/17-CAR-Rolls-Royce-Horn.wav')
HUMANVOICE_FILE = (
    'tests/data/audio/foreground/human_voice/'
    '42-Human-Vocal-Voice-all-aboard_edit.wav')
DOGBARK_FILE = 'tests/data/lufs/dogbark.wav'

SIREN_LUFS_I = -23.071089944980127
CARHORN_LUFS_I = -13.66146520099299
HUMANVOICE_LUFS_I = -20.061513106500225 
DOGBARK_LUFS_I = -11.1952428800271  # for x4 concatenated file

def test_get_integrated_lufs():
    # test correct functionality
    audiofiles = [SIREN_FILE, CARHORN_FILE, HUMANVOICE_FILE, DOGBARK_FILE]
    lufsi = [SIREN_LUFS_I, CARHORN_LUFS_I, HUMANVOICE_LUFS_I, DOGBARK_LUFS_I]

    for af, li in zip(audiofiles, lufsi):
        audio, sr = sf.read(af)
        i = get_integrated_lufs(audio, sr)
        assert i == li

def change_format_and_subtype(audio_path):
    audio, sr = sf.read(audio_path)
    audio_info = sf.info(audio_path)

    formats = ['WAV', 'FLAC']
    if audio_info.format in formats:
        formats.remove(audio_info.format)
    _format = random.choice(formats)

    subtypes = sf.available_subtypes(_format)
    accepted_subtypes = ['PCM_16', 'PCM_32', 'PCM_24', 'FLOAT', 'DOUBLE']
    subtypes = [s for s in subtypes.keys() if s in accepted_subtypes]
    if audio_info.subtype in subtypes:
        subtypes.remove(audio_info.subtype)
    _subtype = random.choice(subtypes)
    
    sf.write(audio_path, audio, sr, subtype=_subtype, format=_format)

def test_match_sample_length():
    durations_to_match = [1, 2, 5, 7, 22500, 44100, 88200, 100001]
    invalid_durations_to_match = [0, -1, .5, 1.0]
    tmpfiles = []
    with _close_temp_files(tmpfiles):
        carhorn = tempfile.NamedTemporaryFile(suffix='.wav', delete=True)
        tmpfiles.append(carhorn)

        siren = tempfile.NamedTemporaryFile(suffix='.wav', delete=True)
        tmpfiles.append(siren)

        for _duration in durations_to_match:
            shutil.copyfile(SIREN_FILE, siren.name)
            shutil.copyfile(CARHORN_FILE, carhorn.name)

            change_format_and_subtype(siren.name)
            change_format_and_subtype(carhorn.name)

            prev_audio_info = sf.info(carhorn.name)
            match_sample_length(carhorn.name, _duration)
            carhorn_audio, _ = sf.read(carhorn.name)
            next_audio_info = sf.info(carhorn.name)
            assert carhorn_audio.shape[0] == _duration
            assert prev_audio_info.format == next_audio_info.format
            assert prev_audio_info.subtype == next_audio_info.subtype

            prev_audio_info = sf.info(siren.name)
            match_sample_length(siren.name, _duration)
            siren_audio, _ = sf.read(siren.name)
            next_audio_info = sf.info(siren.name)
            assert siren_audio.shape[0] == _duration
            assert prev_audio_info.format == next_audio_info.format
            assert prev_audio_info.subtype == next_audio_info.subtype

            # should be summable
            summed_events = sum([carhorn_audio, siren_audio])
            assert summed_events.shape[0] == _duration

        for _duration in invalid_durations_to_match:
            pytest.raises(ScaperError, match_sample_length, carhorn.name, _duration)
            pytest.raises(ScaperError, match_sample_length, siren.name, _duration)
