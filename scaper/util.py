# CREATED: 10/14/16 12:35 PM by Justin Salamon <justin.salamon@nyu.edu>
'''
Utility functions
=================
'''

from contextlib import contextmanager
import logging
import os
import glob
from .scaper_exceptions import ScaperError
import scipy
import numpy as np


@contextmanager
def _close_temp_files(tmpfiles):
    '''
    Utility function for creating a context and closing all temporary files
    once the context is exited. For correct functionality, all temporary file
    handles created inside the context must be appended to the ```tmpfiles```
    list.

    Parameters
    ----------
    tmpfiles : list
        List of temporary file handles

    '''

    yield
    for t in tmpfiles:
        try:
            t.close()
            os.unlink(t.name)
        except:
            pass


@contextmanager
def _set_temp_logging_level(level):
    '''
    Utility function for temporarily changing the logging level using contexts.

    Parameters
    ----------
    level : str or int
        The desired temporary logging level. For allowed values see:
        https://docs.python.org/2/library/logging.html#logging-levels

    '''
    logger = logging.getLogger()
    current_level = logger.level
    logger.setLevel(level)
    yield
    logger.setLevel(current_level)


def _get_sorted_files(folder_path):
    '''
    Return a list of absolute paths to all valid files contained within the
    folder specified by ```folder_path```.

    Parameters
    ----------
    folder_path : str
        Path to the folder to scan for files.

    Returns
    -------
    files : list
        List of absolute paths to all valid files contained within
        ```folder_path```.

    '''

    # Ensure path points to valid folder
    _validate_folder_path(folder_path)

    # Get folder contents and filter for valid files
    # Note, we sort the list to ensure consistent behavior across operating
    # systems.
    files = sorted(glob.glob(os.path.join(folder_path, "*")))
    files = [f for f in files if os.path.isfile(f)]

    return files


def _validate_folder_path(folder_path):
    '''
    Validate that a provided path points to a valid folder.

    Parameters
    ----------
    folder_path : str
        Path to a folder.

    Raises
    ------
    ScaperError
        If ```folder_path``` does not point to a valid folder.

    '''

    if not os.path.isdir(folder_path):
        raise ScaperError(
            'Folder path "{:s}" does not point to a valid folder'.format(
                str(folder_path)))


def _populate_label_list(folder_path, label_list):
    '''
    Given a path to a folder and a list, add the names of all subfolders
    contained in this folder (excluding folders whose name starts with '.') to
    the provided list. This is used in scaper to populate the lists of valid
    foreground and background labels, which are determined by the names of the
    folders contained in ```fg_path`` and ```bg_path``` provided during
    initialization.

    Parameters
    ----------
    folder_path : str
        Path to a folder
    label_list : list
        List to which label (subfolder) names will be added.

    See Also
    --------
    _validate_folder_path : Validate that a provided path points to a valid
    folder.

    '''

    # Make sure folder path is valid
    _validate_folder_path(folder_path)

    folder_names = os.listdir(folder_path)
    for fname in folder_names:
        if (os.path.isdir(os.path.join(folder_path, fname)) and
                fname[0] != '.'):
            label_list.append(fname)
    # ensure consistent ordering of labels
    label_list.sort()


def _trunc_norm(mu, sigma, trunc_min, trunc_max):
    '''
    Return a random value sampled from a truncated normal distribution with
    mean ```mu``` and standard deviation ```sigma``` whose values are limited
    between ```trunc_min``` and ```trunc_max```.

    Parameters
    ----------
    mu : float
        The mean of the truncated normal distribution
    sig : float
        The standard deviation of the truncated normal distribution
    trunc_min : float
        The minimum value allowed for the distribution (lower boundary)
    trunc_max : float
        The maximum value allowed for the distribution (upper boundary)

    Returns
    -------
    value : float
        A random value sampled from the truncated normal distribution defined
        by ```mu```, ```sigma```, ```trunc_min``` and ```trunc_max```.

    '''

    # By default truncnorm expects a (lower boundary) and b (upper boundary)
    # values for a standard normal distribution (mu=0, sigma=1), so we need
    # to recompute a and b given the user specified parameters.
    a, b = (trunc_min - mu) / float(sigma), (trunc_max - mu) / float(sigma)
    return scipy.stats.truncnorm.rvs(a, b, mu, sigma)


def max_polyphony(ann):
    '''
    Given an annotation of sound events, compute the maximum polyphony, i.e.
    the maximum number of simultaneous events at any given point in time. Only
    foreground events are taken into consideration for computing the polyphony.

    Parameters
    ----------
    ann : JAMS.Annotation

    Returns
    -------
    polyphony : int
        Maximum number of simultaneous events at any point in the annotation.
    '''

    # If there are no foreground events the polyphony is 0
    roles = [obs.value['role'] for obs in ann.data]
    if 'foreground' not in roles:
        return 0
    else:
        # Keep only foreground events
        int_time, int_val = ann.to_interval_values()
        int_time_clean = []
        for t, v in zip(int_time, int_val):
            if v['role'] == 'foreground':
                int_time_clean.append(t)
        int_time_clean = np.asarray(int_time_clean)

        # Sort and reshape
        arrivals = np.sort(int_time_clean[:, 0]).reshape(-1, 1)
        departures = np.sort(int_time_clean[:, 1]).reshape(-1, 1)

        # Onsets are +1, offsets are -1
        arrivals = np.concatenate(
            (arrivals, np.ones(arrivals.shape)), axis=1)
        departures = np.concatenate(
            (departures, -np.ones(departures.shape)), axis=1)

        # Merge arrivals and departures and sort
        entry_log = np.concatenate((arrivals, departures), axis=0)
        entry_log_sorted = entry_log[entry_log[:, 0].argsort()]

        # Get maximum number of simultaneously occurring events
        polyphony = np.max(np.cumsum(entry_log_sorted[:, 1]))

        return int(polyphony)


def polyphony_gini(ann, hop_size=0.01):
    '''
    Compute the gini coefficient of the annotation's polyphony time series.

    Useful as an estimate of the polyphony "flatness" or entropy. The
    coefficient is in the range [0,1] and roughly inverse to entropy: a
    distribution that's close to uniform will have a low gini coefficient
    (high entropy), vice versa.
    https://en.wikipedia.org/wiki/Gini_coefficient

    Parameters
    ----------
    ann : jams.Annotation
        Annotation for which to compute the normalized polyphony entropy. Must
        be of the scaper namespace.
    hop_size : float
        The hop size for sampling the polyphony time series.

    Returns
    -------
    polyphony_gini: float
        Gini coefficient computed from the annotation's polyphony time series.

    Raises
    ------
    ScaperError
        If the annotation does not have a duration value or if its namespace is
        not scaper.

    '''

    if not ann.duration:
        raise ScaperError('Annotation does not have a duration value set.')

    if ann.namespace != 'scaper':
        raise ScaperError(
            'Annotation namespace must be scaper, found {:s}.'.format(
                ann.namespace))

    # If there are no foreground events the gini coefficient is 0
    roles = [obs.value['role'] for obs in ann.data]
    if 'foreground' not in roles:
        return 0

    # Sample the polyphony using the specified hop size
    n_samples = int(np.floor(ann.duration / float(hop_size)) + 1)
    times = np.linspace(0, (n_samples-1) * hop_size, n_samples)
    values = np.zeros_like(times)

    # for idx in ann.data.index:
    for obs in ann.data:
        # if ann.data.loc[idx, 'value']['role'] == 'foreground':
        if obs.value['role'] == 'foreground':
            start_time = obs.time
            end_time = start_time + obs.duration
            start_idx = np.argmin(np.abs(times - start_time))
            end_idx = np.argmin(np.abs(times - end_time)) - 1
            values[start_idx:end_idx + 1] += 1
    values = values[:-1]

    # DEBUG
    # vstring = ('{:d} ' * len(values)).format(*tuple([int(v) for v in values]))
    # print(vstring)
    # print(' ')

    # Compute gini as per:
    # http://www.statsdirect.com/help/default.htm#nonparametric_methods/gini.htm
    values += 1e-6  # all values must be positive
    values = np.sort(values)  # sort values
    n = len(values)
    i = np.arange(n) + 1
    gini = np.sum((2*i - n - 1) * values) / (n * np.sum(values))
    return (1 - gini)


def is_real_number(num):
    '''
    Check if a value is a real scalar by aggregating several numpy checks.

    Parameters
    ----------
    num : any type
        The parameter to check

    Returns
    ------
    check : bool
        True if ```num``` is a real scalar, False otherwise.

    '''

    if (not np.isreal(num) or
            not np.isrealobj(num) or
            not np.isscalar(num)):
        return False
    else:
        return True


def is_real_array(array):
    '''
    Check if a value is a list or array of real scalars by aggregating several
    numpy checks.

    Parameters
    ----------
    array: any type
        The parameter to check

    Returns
    ------
    check : bool
        True if ```array``` is a list or array of a real scalars, False
        otherwise.

    '''

    if not (type(array) is list or type(array) is np.ndarray):
        return False
    else:
        if (not np.all([np.isreal(x) for x in array]) or
                not np.isrealobj(array) or
                not np.asarray(list(map(np.isscalar, array))).all()):
            return False
        else:
            return True
