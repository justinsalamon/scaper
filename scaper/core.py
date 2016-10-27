import sox
import random
import os
import warnings
import jams
from collections import namedtuple
import logging
import tempfile
import numpy as np
import shutil
from .scaper_exceptions import ScaperError
from .scaper_warnings import ScaperWarning
from .util import _close_temp_files
from .util import _set_temp_logging_level
from .util import _get_sorted_files
from .util import _validate_folder_path
from .util import _populate_label_list
from .util import _trunc_norm
from .util import max_polyphony

SUPPORTED_DIST = {"const": lambda x: x,
                  "choose": lambda x: random.choice(x),
                  "uniform": random.uniform,
                  "normal": random.normalvariate,
                  "truncnorm": _trunc_norm}

# Define single event spec as namedtuple
EventSpec = namedtuple(
    'EventSpec',
    ['label', 'source_file', 'source_time', 'event_time', 'event_duration',
     'snr', 'role'], verbose=False)


def trim(audio_infile, jams_infile, audio_outfile, jams_outfile, start_time,
         end_time, strict=False):
    '''
    Given an input audio file and corresponding jams file, trim both the audio
    and all annotations in the jams file to the time range [`trim_start`,
    `trim_end`] and save the result to audio_outfile and jams_outfile
    respectively. This function uses `jams.trim()` for trimming the jams file.

    Parameters
    ----------
    audio_infile : str
        Path to input audio file
    jams_infile : str
        Path to input jams file
    audio_outfile : str
        Path to output trimmed audio file
    jams_outfile : str
        Path to output trimmed jams file
    start_time : float
        Start time for trimmed audio/jams
    end_time : float
        End time for trimmed audio/jams
    strict : bool
        Passed to `jams.trim()`, when `True` the time range defined by
        [`start_time`, `end_time`] must be a contained within the time range
        spanned by every annotation in the jams file (otherwise raises an
        error). When `False`, each annotation in the jams file will be trimmed
        to the time range given by the intersection of [`start_time`,
        `end_time`] and the time range spanned by the annotation. This can
        result in some annotations spanning a different time range compared to
        the trimmed audio file. See the `jams.trim` documentation for further
        details.

    '''
    # First trim jams (might raise an error)
    jam = jams.load(jams_infile)
    jam_trimmed = jam.trim(start_time, end_time, strict=strict)

    # Save result to output jams file
    jam_trimmed.save(jams_outfile)

    # Next, trim audio
    tfm = sox.Transformer()
    tfm.trim(start_time, end_time)
    if audio_outfile != audio_infile:
        tfm.build(audio_infile, audio_outfile)
    else:
        # must use temp file in order to save to same file
        tmpfiles = []
        with _close_temp_files(tmpfiles):
            # Create tmp file
            tmpfiles.append(
                tempfile.NamedTemporaryFile(
                    suffix='.wav', delete=True))
            # Save trimmed result to temp file
            tfm.build(audio_infile, tmpfiles[-1].name)
            # Copy result back to original file
            shutil.copyfile(tmpfiles[-1].name, audio_outfile)


def _get_value_from_dist(dist_tuple):
    '''
    Given a distribution tuple, validate its format/values and then sample
    and return a single value from the distribution specified by the tuple.

    Parameters
    ----------
    dist_tuple : tuple
        Distribution tuple to be validated. See Scaper.add_event for details
        about the expected format and item values.

    Returns
    -------
    value
        A value from the specified distribution.

    See Also
    --------
    _validate_distribution : Check whether a tuple specifying a parameter
    distribution has a valid format, if not raise an error.

    '''
    # Make sure it's a valid distribution tuple
    _validate_distribution(dist_tuple)
    return SUPPORTED_DIST[dist_tuple[0]](*dist_tuple[1:])


def _validate_distribution(dist_tuple):
    '''
    Check whether a tuple specifying a parameter distribution has a valid
    format, if not raise an error.

    Parameters
    ----------
    dist_tuple : tuple
        Tuple specifying a distribution to sample from. See Scaper.add_event
        for details about the expected format of the tuple and allowed values.

    Raises
    ------
    ScaperError
        If the tuple does not have a valid format.

    See Also
    --------
    Scaper.add_event : Add a foreground sound event to the foreground
    specification.
    '''
    # Make sure it's a tuple
    if not isinstance(dist_tuple, tuple):
        raise ScaperError('Distribution tuple must be of type tuple.')

    # Make sure the tuple contains at least 2 items
    if len(dist_tuple) < 2:
        raise ScaperError('Distribution tuple must be at least of length 2.')

    # Make sure the first item is one of the supported distribution names
    if dist_tuple[0] not in SUPPORTED_DIST.keys():
        raise ScaperError(
            "Unsupported distribution name: {:s}".format(dist_tuple[0]))

    # If it's a constant distribution, tuple must be of length 2
    if dist_tuple[0] == 'const':
        if len(dist_tuple) != 2:
            raise ScaperError('"const" distribution tuple must be of length 2')
    # If it's a choose, tuple must be of length 2 and second item of type list
    elif dist_tuple[0] == 'choose':
        if len(dist_tuple) != 2 or not isinstance(dist_tuple[1], list):
            raise ScaperError(
                'The "choose" distribution tuple must be of length 2 where '
                'the second item is a list.')
    # If it's a uniform distribution, tuple must be of length 3, 2nd item must
    # be a real number and 3rd item must be real and greater/equal to the 2nd.
    elif dist_tuple[0] == 'uniform':
        if (len(dist_tuple) != 3 or
                not np.isrealobj(dist_tuple[1]) or
                not np.isrealobj(dist_tuple[2]) or
                dist_tuple[1] > dist_tuple[2]):
            raise ScaperError(
                'The "uniform" distribution tuple be of length 2, where the '
                '2nd item is a real number and the 3rd item is a real number '
                'and greater/equal to the 2nd item.')
    # If it's a normal distribution, tuple must be of length 3, 2nd item must
    # be a real number and 3rd item must be a non-negative real
    elif dist_tuple[1] == 'normal':
        if (len(dist_tuple) != 3 or
                not np.isrealobj(dist_tuple[1]) or
                not np.isrealobj(dist_tuple[2]) or
                dist_tuple[2] < 0):
            raise ScaperError(
                'The "normal" distribution tuple must be of length 3, where '
                'the 2nd item (mean) is a real number and the 3rd item (std '
                'dev) is real and non-negative.')
    elif dist_tuple[1] == 'truncnorm':
        if (len(dist_tuple) != 5 or
                not np.isrealobj(dist_tuple[1]) or
                not np.isrealobj(dist_tuple[2]) or
                not np.isrealobj(dist_tuple[3]) or
                not np.isrealobj(dist_tuple[4]) or
                dist_tuple[2] < 0 or
                dist_tuple[4] < dist_tuple[3]):
            raise ScaperError(
                'The "truncnorm" distribution tuple must be of length 5, '
                'where the 2nd item (mean) is a real number, the 3rd item '
                '(std dev) is real and non-negative, the 4th item (trunc_min) '
                'is a real number and the 5th item (trun_max) is a real '
                'number that is equal to or greater than trunc_min.')


def _validate_label(label, allowed_labels):
    '''
    Validate that a label tuple is in the right format and that it's values
    are valid.

    Parameters
    ----------
    label : tuple
        Label tuple (see ```Scaper.add_event``` for required format).
    allowed_labels : list
        List of allowed labels.

    Raises
    ------
    ScaperError
        If the validation fails.

    '''
    # Make sure it's a valid distribution tuple
    _validate_distribution(label)

    # Make sure it's one of the allowed distributions for a label and that the
    # label value is one of the allowed labels.
    if label[0] == "const":
        if not label[1] in allowed_labels:
            raise ScaperError(
                'Label value must match one of the available labels: '
                '{:s}'.format(str(allowed_labels)))
    elif label[0] == "choose":
        if label[1]:  # list is not empty
            if not set(label[1]).issubset(set(allowed_labels)):
                raise ScaperError(
                    'Label list provided must be a subset of the available '
                    'labels: {:s}'.format(str(allowed_labels)))
    else:
        raise ScaperError(
            'Label must be specified using a "const" or "choose" tuple.')


def _validate_source_file(source_file_tuple, label_tuple):
    '''
    Validate that a source_file tuple is in the right format a that it's values
    are valid.

    Parameters
    ----------
    source_file : tuple
        Source file tuple (see ```Scaper.add_event``` for required format).
    label : str
        Label tuple (see ```Scaper.add_event``` for required format).

    Raises
    ------
    ScaperError
        If the validation fails.

    '''
    # Make sure it's a valid distribution tuple
    _validate_distribution(source_file_tuple)
    _validate_distribution(label_tuple)

    # If source file is specified explicitly
    if source_file_tuple[0] == "const":
        # 1. the filepath must point to an existing file
        if not os.path.isfile(source_file_tuple[1]):
            raise ScaperError(
                "Source file not found: {:s}".format(source_file_tuple[1]))
        # 2. the label must match the file's parent folder name
        parent_name = os.path.basename(os.path.dirname(source_file_tuple[1]))
        if label_tuple[0] != "const" or label_tuple[1] != parent_name:
            raise ScaperError(
                "Source file's parent folder name does not match label.")
    # Otherwise it must be specified using "choose"
    elif source_file_tuple[0] == "choose":
        if source_file_tuple[1]:  # list is not empty
            if not all(os.path.isfile(x) for x in source_file_tuple[1]):
                raise ScaperError(
                    'Source file list must either be empty or all paths in '
                    'the list must point to valid files.')
    else:
        raise ScaperError(
            'Source file must be specified using a "const" or "choose" tuple.')


def _validate_time(time_tuple):
    '''
    Validate that a time tuple has the right format and that the
    specified distribution cannot result in a negative time.

    Parameters
    ----------
    time_tuple : tuple
        Time tuple (see ```Scaper.add_event``` for required format).

    Raises
    ------
    ScaperError
        If the validation fails.

    '''
    # Make sure it's a valid distribution tuple
    _validate_distribution(time_tuple)

    # Ensure the values are valid for time
    if time_tuple[0] == "const":
        if not np.isrealobj(time_tuple[1]) or time_tuple[1] < 0:
            raise ScaperError(
                'Time must be a real non-negative number.')
    elif time_tuple[0] == "choose":
        if (not time_tuple[1] or
                not np.isrealobj(time_tuple[1]) or
                not all(x >= 0 for x in time_tuple[1])):
            raise ScaperError(
                'Time list must be a non-empty list of non-negative real '
                'numbers.')
    elif time_tuple[0] == "uniform":
        if time_tuple[1] < 0:
            raise ScaperError(
                'A "uniform" distribution tuple for time must have '
                'min_value >= 0')
    elif time_tuple[0] == "normal":
        warnings.warn(
            'A "normal" distribution tuple for time can result in '
            'negative values, in which case the distribution will be '
            're-sampled until a positive value is returned: this can result '
            'in an infinite loop!',
            ScaperWarning)
    elif time_tuple[0] == "truncnorm":
        if time_tuple[3] < 0:
            raise ScaperError(
                'A "truncnorm" distirbution tuple for time must specify a non-'
                'negative trunc_min value.')


def _validate_duration(duration_tuple):
    '''
    Validate that a duration tuple has the right format and that the
    specified distribution cannot result in a negative or zero value.

    Parameters
    ----------
    duration : tuple
        Duration tuple (see ```Scaper.add_event``` for required format).

    Raises
    ------
    ScaperError
        If the validation fails.

    '''
    # Make sure it's a valid distribution tuple
    _validate_distribution(duration_tuple)

    # Ensure the values are valid for duration
    if duration_tuple[0] == "const":
        if not np.isrealobj(duration_tuple[1]) or duration_tuple[1] <= 0:
            raise ScaperError(
                'Duration must be a real number greater than zero.')
    elif duration_tuple[0] == "choose":
        if (not duration_tuple[1] or
                not np.isrealobj(duration_tuple[1]) or
                not all(x > 0 for x in duration_tuple[1])):
            raise ScaperError(
                'Duration list must be a non-empty list of positive real '
                'numbers.')
    elif duration_tuple[0] == "uniform":
        if duration_tuple[1] <= 0:
            raise ScaperError(
                'A "uniform" distribution tuple for duration must have '
                'min_value > 0')
    elif duration_tuple[0] == "normal":
        warnings.warn(
            'A "normal" distribution tuple for duration can result in '
            'non-positives values, in which case the distribution will be '
            're-sampled until a positive value is returned: this can result '
            'in an infinite loop!',
            ScaperWarning)
    elif duration_tuple[0] == "truncnorm":
        if duration_tuple[3] <= 0:
            raise ScaperError(
                'A "truncnorm" distirbution tuple for time must specify a '
                'positive trunc_min value.')


def _validate_snr(snr_tuple):
    '''
    Validate that an snr distribution tuple has the right format.

    Parameters
    ----------
    snr : tuple
        SNR tuple (see ```Scaper.add_event``` for required format).

    Raises
    ------
    ScaperError
        If the validation fails.

    '''
    # Make sure it's a valid distribution tuple
    _validate_distribution(snr_tuple)

    # Ensure the values are valid for SNR
    if snr_tuple[0] == "const":
        if not np.isrealobj(snr_tuple[1]):
            raise ScaperError(
                'SNR must be a real number.')
    elif snr_tuple[0] == "choose":
        if not snr_tuple[1] or not np.isrealobj(snr_tuple[1]):
            raise ScaperError(
                'SNR list must be a non-empty list of real numbers.')

    # No need to check for "uniform" and "normal" since they must produce a
    # real number and technically speaking any real number is a valid SNR.
    # TODO: do we want to impose limits on the possible SNR values?


def _validate_event(label, source_file, source_time, event_time,
                    event_duration, snr, allowed_labels):
    '''
    Check that event parameter values are valid. See ```Scaper.add_event```
    for a detailed description of the expected format of each parameter.

    Parameters
    ----------
    label : tuple
    source_file : tuple
    source_time : tuple
    event_time : tuple
    event_duration : tuple
    snr : tuple
    allowed_labels : list
        List of allowed labels for the event.

    Raises
    ------
    ScaperError
        If any of the input parameters has an invalid format or value.

    See Also
    --------
    Scaper.add_event : Add a foreground sound event to the foreground
    specification.
    '''
    # allowed_labels must be a list. All other parameters will be validated
    # individually.
    if not isinstance(allowed_labels, list):
        raise ScaperError('allowed_labels must be of type list.')

    # SOURCE FILE
    _validate_source_file(source_file, label)

    # LABEL
    _validate_label(label, allowed_labels)

    # SOURCE TIME
    _validate_time(source_time)

    # EVENT TIME
    _validate_time(event_time)

    # EVENT DURATION
    _validate_duration(event_duration)

    # SNR
    _validate_snr(snr)


class Scaper(object):

    def __init__(self, duration, fg_path, bg_path):
        '''
        Initialization, need to provide desired duration, and paths to
        foreground and background folders.

        Parameters
        ----------
        duration : float
            Duration of soundscape, in seconds.
        fg_path : str
            Path to foreground folder.
        bg_path : str
            Path to background folder.

        '''
        # Duration must be a positive real number
        if np.isrealobj(duration) and duration > 0:
            self.duration = duration
        else:
            raise ScaperError('Duration must be a positive real value')

        # Initialize parameters
        self.ref_db = -12
        self.n_channels = 1
        self.fade_in_len = 0.01  # 10 ms
        self.fade_out_len = 0.01  # 10 ms

        # Start with empty specifications
        self.fg_spec = []
        self.bg_spec = []

        # Populate label lists from folder paths
        self.fg_labels = []
        self.bg_labels = []

        # Validate paths and set
        _validate_folder_path(fg_path)
        _validate_folder_path(bg_path)
        self.fg_path = fg_path
        self.bg_path = bg_path

        _populate_label_list(self.fg_path, self.fg_labels)
        _populate_label_list(self.bg_path, self.bg_labels)

    def add_background(self, label, source_file, source_time):
        '''
        Add a background recording. The duration will be equal to the duration
        of the soundscape ```Scaper.duration``` specified when initializing
        the Scaper object. If the source file is shorter than this duration
        then it will be concatenated to itself as many times as necessary to
        produce the specified duration when calling ```Scaper.generate```.

        Parameters
        ----------
        label : tuple
            Specifies the label of the background. See Notes below for the
            expected format of this tuple and the allowed values.
            NOTE: The label specified by this tuple must match one
            of the labels in the Scaper's background label list
            ```Scaper.bg_labels```. Furthermore, if ```source_file``` is
            specified using "const" (see Notes), then ```label``` must also be
            specified using "const" and its ```value ``` (see Notes) must
            match the source file's parent folder's name.
        source_file : tuple
            Specifies the audio file to use as the source. See Notes below for
            the expected format of this tuple and the allowed values.
            NOTE: If ```source_file``` is specified using "const" (see Notes),
            then ```label``` must also be specified using "const" and its
            ```value``` (see Notes) must match the source file's parent
            folder's name.
        source_time : tuple
            Specifies the desired start time in the source file. See Notes
            below for the expected format of this tuple and the allowed values.
            NOTE: the source time specified by this tuple should be equal to or
            smaller than ```<source file duration> - <soundscape duration>```.
            Larger values will be automatically changed to fulfill this
            requirement when calling ```Scaper.generate```.

        Notes
        -----
        Each parameter of this function is set by passing a distribution
        tuple, whose first item is always the distribution name and subsequent
        items are distribution specific. The supported distribution tuples are:
            * ```("const", value)``` : a constant, given by ```value```.
            * ```("choose", valuelist)``` : choose a value from
              ```valuelist``` at random (uniformly). The ```label``` and
              ```source_file``` parameters also support providing an empty
              ```valuelist``` i.e. ```("choose", [])```, in which case the
              value will be chosen at random from all available labels or files
              as determined automatically by Scaper by examining the file
              structure of ```bg_path``` provided during initialization.
            * ```("uniform", min_value, max_value)``` : sample a random
              value from a uniform distribution between ```min_value```
              and ```max_value```.
            * ```("normal", mean, stddev)``` : sample a random value from a
              normal distribution defined by its mean ```mean``` and
              standard deviation ```stddev```.
        IMPORTANT: not all parameters support all distribution tuples. In
        particular, ```label``` and ```source_file``` only support "const" and
        "choose", whereas ```source_time``` supports all distribution
        tuples. As noted above, only ```label``` and ```source_file``` support
        providing an empty ```valuelist``` with "choose".

        '''
        # These values are fixed for the background sound
        event_time = ("const", 0)
        event_duration = ("const", self.duration)
        snr = ("const", 0)

        # Validate parameter format and values
        _validate_event(label, source_file, source_time, event_time,
                        event_duration, snr, self.bg_labels)

        # Create background sound event
        bg_event = EventSpec(label=label,
                             source_file=source_file,
                             source_time=source_time,
                             event_time=event_time,
                             event_duration=event_duration,
                             snr=snr,
                             role='background')

        # Add event to background spec
        self.bg_spec.append(bg_event)

    def add_event(self, label, source_file, source_time, event_time,
                  event_duration, snr):
        '''
        Add a foreground sound event to the foreground specification.

        Parameters
        ----------
        label : tuple
            Specifies the label of the sound event. See Notes below for the
            expected format of this tuple and the allowed values.
            NOTE: The label specified by this tuple must match one
            of the labels in the Scaper's foreground label list
            ```Scaper.fg_labels```. Furthermore, if ```source_file``` is
            specified using "const" (see Notes), then ```label``` must also be
            specified using "const" and its ```value ``` (see Notes) must
            match the source file's parent folder's name.
        source_file : tuple
            Specifies the audio file to use as the source. See Notes below for
            the expected format of this tuple and the allowed values.
            NOTE: If ```source_file``` is specified using "const" (see Notes),
            then ```label``` must also be specified using "const" and its
            ```value``` (see Notes) must match the source file's parent
            folder's name.
        source_time : tuple
            Specifies the desired start time in the source file. See Notes
            below for the expected format of this tuple and the allowed values.
            NOTE: the source time specified by this tuple should be equal to or
            smaller than ```<source file duration> - event_duration```. Larger
            values will be automatically changed to fulfill this requirement
            when calling ```Scaper.generate```.
        event_time : tuple
            Specifies the desired start time of the event in the soundscape.
            See Notes below for the expected format of this tuple and the
            allowed values.
            NOTE: The value specified by this tuple should be equal to or
            smaller than ```<soundscapes duration> - event_duration```, and
            larger values will be automatically changed to fulfill this
            requirement when calling ```Scaper.generate```.
        event_duration : tuple
            Specifies the desired duration of the event. See Notes below for
            the expected format of this tuple and the allowed values.
            NOTE: The value specified by this tuple should be equal to or
            smaller than the source file's duration, and larger values will be
            automatically changed to fulfill this requirement when calling
            ```Scaper.generate```.
        snr : float
            Specifies the desired signal to noise ratio (SNR) between the event
            and the background. See Notes below for the expected format of
            this tuple and the allowed values.

        Notes
        -----
        Each parameter of this function is set by passing a distribution
        tuple, whose first item is always the distribution name and subsequent
        items are distribution specific. The supported distribution tuples are:
            * ```("const", value)``` : a constant, given by ```value```.
            * ```("choose", valuelist)``` : choose a value from
              ```valuelist``` at random (uniformly). The ```label``` and
              ```source_file``` parameters also support providing an empty
              ```valuelist``` i.e. ```("choose", [])```, in which case the
              value will be chosen at random from all available labels or
              source files as determined automatically by Scaper by examining
              the file structure of ```fg_path``` provided during
              initialization.
            * ```("uniform", min_value, max_value)``` : sample a random
              value from a uniform distribution between ```min_value```
              and ```max_value``` (including ```max_value```).
            * ```("normal", mean, stddev)``` : sample a random value from a
              normal distribution defined by its mean ```mean``` and
              standard deviation ```stddev```.
        IMPORTANT: not all parameters support all distribution tuples. In
        particular, ```label``` and ```source_file``` only support "const" and
        "choose", whereas the remaining parameters support all distribution
        tuples. As noted above, only ```label``` and ```source_file``` support
        providing an empty ```valuelist``` with "choose".

        See Also
        --------
        _validate_event : Check that event parameter values are valid.

        '''

        # SAFETY CHECKS
        _validate_event(label, source_file, source_time, event_time,
                        event_duration, snr, self.fg_labels)

        # Create event
        event = EventSpec(label=label,
                          source_file=source_file,
                          source_time=source_time,
                          event_time=event_time,
                          event_duration=event_duration,
                          snr=snr,
                          role='foreground')

        # Add event to foreground specification
        self.fg_spec.append(event)

    def _instantiate_event(self, event, isbackground=False):
        '''
        Given an event specification containing distribution tuples,
        instantiate the event, i.e. samples values for the label, source_file,
        source_time, event_time, event_duration and snr from their respective
        distribution tuples, and return the sampled values in as a new event
        specification.

        Parameters
        ----------
        event : EventSpec
            Event specification containing distribution tuples.
        isbackground : bool
            Flag indicating whether the event to instantiate is a background
            event or not (False implies it is a foreground event).

        Returns
        -------
        instantiated_event : EventSpec
            Event specification containing values sampled from the distribution
            tuples of the input event specification.

        '''
        # set paths and labels depending on whether its a foreground/background
        # event
        if isbackground:
            file_path = self.bg_path
            allowed_labels = self.bg_labels
        else:
            file_path = self.fg_path
            allowed_labels = self.fg_labels

        # determine label
        if event.label[0] == "choose" and not event.label[1]:
            label_tuple = list(event.label)
            label_tuple[1] = allowed_labels
            label_tuple = tuple(label_tuple)
        else:
            label_tuple = event.label
        label = _get_value_from_dist(label_tuple)

        # determine source file
        if event.source_file[0] == "choose" and not event.source_file[1]:
            source_files = _get_sorted_files(
                os.path.join(file_path, label))
            source_file_tuple = list(event.source_file)
            source_file_tuple[1] = source_files
            source_file_tuple = tuple(source_file_tuple)
        else:
            source_file_tuple = event.source_file
        source_file = _get_value_from_dist(source_file_tuple)

        # determine event duration
        # For background events the duration is fixed to self.duration
        # (which must be > 0), but for foreground events it could potentially
        # be non-positive, hence the loop.
        event_duration = -np.Inf
        while event_duration <= 0:
            event_duration = _get_value_from_dist(event.event_duration)
        # Check if chosen event duration is longer than the duration of the
        # selected source file, if so adjust the event duration.
        source_duration = sox.file_info.duration(source_file)
        if (event_duration > source_duration or
                event_duration > self.duration):
            old_duration = event_duration  # for warning
            event_duration = min(source_duration, self.duration)
            warnings.warn(
                "{:s} event duration ({:.2f}) is greater that source "
                "duration ({:.2f}) or soundscape duration ({:.2f}), "
                "changed to {:.2f}".format(
                    label, old_duration, source_duration, self.duration,
                    event_duration),
                ScaperWarning)

        # determine source time
        source_time = -np.Inf
        while source_time < 0:
            source_time = _get_value_from_dist(event.source_time)
        # Make sure source time + event duration is not greater than the
        # source duration, if it is, adjust the source time (i.e. duration
        # takes precedences over start time).
        if source_time + event_duration > source_duration:
            old_source_time = source_time
            source_time = source_duration - event_duration
            warnings.warn(
                '{:s} source time ({:.2f}) is too great given event '
                'duration ({:.2f}) and source duration ({:.2f}), changed '
                'to {:.2f}.'.format(
                    label, old_source_time, event_duration,
                    source_duration, source_time),
                ScaperWarning)

        # determine event time
        # for background events the event time is fixed to 0, but for
        # foreground events it's not.
        event_time = -np.Inf
        while event_time < 0:
            event_time = _get_value_from_dist(event.event_time)
        # Make sure the selected event time + event duration are is not greater
        # than the total duration of the soundscape, if it is adjust the event
        # time. This means event duration takes precedence over the event
        # start time.
        if event_time + event_duration > self.duration:
            old_event_time = event_time
            event_time = self.duration - event_duration
            warnings.warn(
                '{:s} event time ({:.2f}) is too great given event '
                'duration ({:.2f}) and soundscape duration ({:.2f}), '
                'changed to {:.2f}.'.format(
                    label, old_event_time, event_duration,
                    self.duration, event_time),
                ScaperWarning)

        # determine snr
        snr = _get_value_from_dist(event.snr)

        # get role (which can only take "foreground" or "background" and
        # is set internally, not by the user).
        role = event.role

        # pack up instantiated values in an EventSpec
        instantiated_event = EventSpec(label=label,
                                       source_file=source_file,
                                       source_time=source_time,
                                       event_time=event_time,
                                       event_duration=event_duration,
                                       snr=snr,
                                       role=role)
        # Return
        return instantiated_event

    def _instantiate(self):
        '''
        Instantiate a specific soundscape in JAMS format based on the current
        specification. Any non-deterministic event values (i.e. distribution
        tuples) will be sampled randomly from based on the distribution
        parameters.

        Parameters
        ----------
        crop : float or None
            Crop the instantiated soundscape to the center ```crop``` seconds.
            By default set to ```None``` which means no cropping is performed.
            IMPORTANT: since soundscape instantiation occurs independently of
            cropping, there is no guarantee that all the foreground events
            added to the scaper will be present in the cropped soundscape.
            Both the output audio file and JAMS file will reflect the cropped
            soundscape.
        '''
        jam = jams.JAMS()
        ann = jams.Annotation(namespace='sound_event')

        # Set annotation duration (might be changed later due to cropping)
        ann.duration = self.duration

        # INSTANTIATE BACKGROUND AND FOREGROUND EVENTS AND ADD TO ANNOTATION
        # NOTE: logic for instantiating bg and fg events is NOT the same.

        # Add background sounds
        for event in self.bg_spec:
            value = self._instantiate_event(event, isbackground=True)
            ann.append(time=value.event_time,
                       duration=value.event_duration,
                       value=value._asdict(),
                       confidence=1.0)

        # Add foreground events
        for event in self.fg_spec:
            value = self._instantiate_event(event, isbackground=False)
            ann.append(time=value.event_time,
                       duration=value.event_duration,
                       value=value._asdict(),
                       confidence=1.0)

        # Compute max polyphony
        poly = max_polyphony(ann)

        # Add specs and other info to sandbox
        ann.sandbox.scaper = jams.Sandbox(fg_spec=self.fg_spec,
                                          bg_spec=self.bg_spec,
                                          max_polyphony=poly)

        # Add annotation to jams
        jam.annotations.append(ann)

        # Set jam metadata
        jam.file_metadata.duration = ann.duration

        # Return
        return jam

    def generate(self, audio_path, jams_path, disable_sox_warnings=True):
        '''
        Generate a soundscape based on the current specification and save to
        disk as both an audio file and a JAMS file describing the soundscape.

        Parameters
        ----------
        audio_path : str
            Path for saving soundscape audio
        jams_path : str
            Path for saving soundscape jams
        disable_sox_warnings : bool
            When True (default), warnings from the pysox module are suppressed
            unless their level is 'CRITICAL'.
        '''
        # Create specific instance of a soundscape based on the spec
        jam = self._instantiate()
        ann = jam.annotations.search(namespace='sound_event')[0]

        # disable sox warnings
        if disable_sox_warnings:
            temp_logging_level = 'CRITICAL'  # only critical messages please
        else:
            temp_logging_level = logging.getLogger().level

        with _set_temp_logging_level(temp_logging_level):

            # Array for storing all tmp files (one for every event)
            tmpfiles = []
            with _close_temp_files(tmpfiles):

                for event in ann.data.iterrows():

                    # first item is index, second is event dictionary
                    e = event[1]

                    if e.value['role'] == 'background':
                        # Concatenate background if necessary. Right now we
                        # always concatenate the background at least once,
                        # since the pysox combiner raises an error if you try
                        # to call build using an input_file_list with less than
                        # 2 elements. In the future if the combiner is updated
                        # to accept a list of length 1, then the max(..., 2)
                        # statement can be removed from the calculation of
                        # ntiles.
                        source_duration = (
                            sox.file_info.duration(e.value['source_file']))
                        ntiles = int(
                            max(self.duration // source_duration + 1, 2))

                        # Create combiner
                        cmb = sox.Combiner()
                        # First ensure files has predefined number of channels
                        cmb.channels(self.n_channels)
                        # Then trim
                        cmb.trim(e.value['source_time'],
                                 e.value['source_time'] +
                                 e.value['event_duration'])
                        # After trimming, normalize background to reference DB.
                        cmb.norm(db_level=self.ref_db)
                        # Finally save result to a tmp file
                        tmpfiles.append(
                            tempfile.NamedTemporaryFile(
                                suffix='.wav', delete=True))
                        cmb.build(
                            [e.value['source_file']] * ntiles,
                            tmpfiles[-1].name, 'concatenate')

                    elif e.value['role'] == 'foreground':
                        # Create transformer
                        tfm = sox.Transformer()
                        # First ensure files has predefined number of channels
                        tfm.channels(self.n_channels)
                        # Trim
                        tfm.trim(e.value['source_time'],
                                 e.value['source_time'] +
                                 e.value['event_duration'])
                        # Apply very short fade in and out
                        # (avoid unnatural sound onsets/offsets)
                        tfm.fade(fade_in_len=self.fade_in_len,
                                 fade_out_len=self.fade_out_len)
                        # Normalize to specified SNR with respect to
                        # self.ref_db
                        tfm.norm(self.ref_db + e.value['snr'])
                        # Pad with silence before/after event to match the
                        # soundscape duration
                        prepad = e.value['event_time']
                        postpad = self.duration - (e.value['event_time'] +
                                                   e.value['event_duration'])
                        tfm.pad(prepad, postpad)
                        # Finally save result to a tmp file
                        tmpfiles.append(
                            tempfile.NamedTemporaryFile(
                                suffix='.wav', delete=True))
                        tfm.build(e.value['source_file'], tmpfiles[-1].name)

                    else:
                        raise ScaperError(
                            'Unsupported event role: {:s}'.format(
                                e.value['role']))

                # Finally combine all the files
                cmb = sox.Combiner()
                # TODO: do we want to normalize the final output?
                cmb.build([t.name for t in tmpfiles], audio_path, 'mix')

        # Finally save JAMS to disk too
        jam.save(jams_path)
