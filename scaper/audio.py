# CREATED: 4/23/17 15:37 by Justin Salamon <justin.salamon@nyu.edu>

'''
Utility functions for audio processing using FFMPEG (beyond sox). Based on:
https://github.com/mathos/neg23/
'''

import subprocess
from .scaper_exceptions import ScaperError


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
    except:
        return False
    return stats_dict


def get_integrated_lufs(filepath):
    '''Returns the integrated lufs for an audiofile'''

    loudness_stats = r128stats(filepath)
    if not loudness_stats:
        raise ScaperError(
            'Unable to obtain LUFS state for {:s}'.format(filepath))
    return loudness_stats['I']


def linear_gain(i_lufs, goal_lufs=-23):
    """ takes a floating point value for i_lufs, returns the necessary
    multiplier for audio gain to get to the goal_lufs value """
    gain_log = -(i_lufs - goal_lufs)
    return 10 ** (gain_log / 20.0)


def ff_apply_gain(inpath, outpath, linear_amount):
    """ creates a file from inpath at outpath, applying a filter
    for audio volume, multiplying by linearAmount """
    ffargs = ['ffmpeg', '-y', '-f', 'wav', '-i', inpath,
              '-af', 'volume=' + str(linear_amount),
              '-f', 'wav']
    if outpath[-4:].lower() == '.mp3':
        ffargs += ['-acodec', 'libmp3lame', '-aq', '0']
    ffargs += [outpath]
    try:
        subprocess.Popen(ffargs, stderr=subprocess.PIPE)
    except:
        return False
    return True


def normalize_audio_lufs(infile, outfile, goal_lufs=-23):
    '''
    Take infile, normalize to goal_lufs, and save to outfile.
    Parameters
    ----------
    infile : str
        Path to input audio file
    outfile : str
        Path to output audio file
    goal_lufs : float
        Desired LUFS level after normalization

    Returns
    -------

    '''

    loudness_stats = r128stats(infile)
    if not loudness_stats:
        raise ScaperError(
            'Unable to obtain LUFS state for {:s}'.format(infile))

    gain_amount = linear_gain(loudness_stats['I'], goal_lufs=goal_lufs)
    ff_gain_success = ff_apply_gain(infile, outfile, gain_amount)
    if not ff_gain_success:
        raise ScaperError(
            'Unable to apply gain of {:.2f} (goal LUFS={:.2f}) for input={:s} '
            'output={:s}'.format(gain_amount, goal_lufs, infile, outfile))
