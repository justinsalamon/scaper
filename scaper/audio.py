# CREATED: 4/23/17 15:37 by Justin Salamon <justin.salamon@nyu.edu>

'''
Utility functions for audio processing using FFMPEG (beyond sox). Based on:
https://github.com/mathos/neg23/
'''

import subprocess
import sox
import numpy as np
import soundfile
import tempfile
from .scaper_exceptions import ScaperError
from .util import _close_temp_files


def r128stats(filepath):
    """ takes a path to an audio file, returns a dict with the loudness
    stats computed by the ffmpeg ebur128 filter """
    ffargs = ['ffmpeg',
              '-nostats',
              '-i',
              filepath,
              '-filter_complex',
              'ebur128',
              '-f',
              'null',
              '-']
    try:
        proc = subprocess.Popen(ffargs, stderr=subprocess.PIPE,
                                universal_newlines=True)
        stats = proc.communicate()[1]
        summary_index = stats.rfind('Summary:')

        if summary_index == -1:
            raise ScaperError(
                'Unable to find LUFS summary, stats string:\n{:s}'.format(
                    stats))

        summary_list = stats[summary_index:].split()
        i_lufs = float(summary_list[summary_list.index('I:') + 1])
        i_thresh = float(summary_list[summary_list.index('I:') + 4])
        lra = float(summary_list[summary_list.index('LRA:') + 1])
        lra_thresh = float(summary_list[summary_list.index('LRA:') + 4])
        lra_low = float(summary_list[summary_list.index('low:') + 1])
        lra_high = float(summary_list[summary_list.index('high:') + 1])
        stats_dict = {'I': i_lufs, 'I Threshold': i_thresh, 'LRA': lra,
                      'LRA Threshold': lra_thresh, 'LRA Low': lra_low,
                      'LRA High': lra_high}
    except Exception as e:
        raise ScaperError(
            'Unable to obtain LUFS data for {:s}, error message:\n{:s}'.format(
                filepath, e.__str__()))

    return stats_dict


def get_integrated_lufs(filepath, min_duration=0.5):
    """
    Returns the integrated LUFS for an audiofile.

    For files shorter than 400 ms ffmpeg returns a constant integrated LUFS
    value of -70.0. To avoid this, files shorter than min_duration (by default
    500 ms) are self-concatenated until min_duration is reached and the
    LUFS value is computed for the concatenated file.

    Parameters
    ----------
    filepath : str
        Path to audio file for computing LUFS
    min_duration : float
        Minimum required duration for computing LUFS value. Files shorter than
        this are self-concatenated until their duration reaches this value
        for the purpose of computing the integrated LUFS. Caution: if you set
        min_duration < 0.4, a constant LUFS value of -70.0 will be returned for
        all files shorter than 400 ms.

    Returns
    -------

    """
    try:
        duration = sox.file_info.duration(filepath)
    except Exception as e:
        raise ScaperError(
            'Unable to obtain LUFS for {:s}, error message:\n{:s}'.format(
                filepath, e.__str__()))

    if duration < min_duration:
        # compute how many concatenations we require
        n_tiles = int(np.ceil(min_duration / duration))

        # Concatenate audio to itself, save to temp file and get LUFS
        tmpfiles = []
        with _close_temp_files(tmpfiles):
            concat_file = tempfile.NamedTemporaryFile(suffix='.wav',
                                                      delete=False)
            tmpfiles.append(concat_file)

            cbn = sox.Combiner()
            cbn.build([filepath] * n_tiles, concat_file.name, 'concatenate')

            loudness_stats = r128stats(concat_file.name)
    else:
        loudness_stats = r128stats(filepath)

    return loudness_stats['I']


def match_sample_length(audio_path, duration_in_samples):
    '''
    Takes a path to an audio file and a duration defined in samples. The audio
    is loaded from the specifid audio_path and padded or trimmed such that it
    matches the duration_in_samples. The modified audio is then saved back to
    audio_path. This ensures that the durations match exactly. If the audio
    needed to be padded, it is padded with zeros to the end of the audio file.
    If the audio needs to be trimmed, the function will trim samples from the end of 
    the audio file. The sample rate of the saved audio is the same as the sample 
    rate of the input file.

    Parameters
    ----------
    audio_path : str
        Path to the audio file that will be modified.
    duration_in_samples : int
        Duration that the audio will be padded or trimmed to.

    '''
    if duration_in_samples <= 0:
        raise ScaperError(
            'Duration in samples must be > 0.')
    if not isinstance(duration_in_samples, int):
        raise ScaperError(
            'Duration in samples must be an integer.')

    audio, sr = soundfile.read(audio_path)
    audio_info = soundfile.info(audio_path)
    current_duration = audio.shape[0]

    if duration_in_samples < current_duration:
        audio = audio[:duration_in_samples]
    elif duration_in_samples > current_duration:
        n_pad = duration_in_samples - current_duration

        pad_width = [(0, 0) for _ in range(len(audio.shape))]
        pad_width[0] = (0, n_pad)

        audio = np.pad(audio, pad_width, 'constant')

    soundfile.write(audio_path, audio, sr, 
        subtype=audio_info.subtype, format=audio_info.format)
