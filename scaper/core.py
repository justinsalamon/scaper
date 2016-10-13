import sox
import random
import os
import warnings
import jams
import glob
from collections import namedtuple
import logging
import tempfile
from .exceptions import ScaperError
import numpy as np
from contextlib import contextmanager

REF_DB = -12
N_CHANNELS = 1
SUPPORTED_DIST = {"const": lambda x: x,
                  "choose": lambda x: random.choice(x),
                  "uniform": random.uniform,
                  "normal": random.normalvariate}

# Define single event spec as namedtuple
EventSpec = namedtuple(
    'EventSpec',
    ['label', 'source_file', 'source_time', 'event_time', 'event_duration',
     'snr', 'role'], verbose=False)


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
        t.close()


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


def _get_value_from_dist(dist_tuple):
    '''

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
    return SUPPORTED_DIST[dist_tuple[0], dist_tuple[1:]]


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
        if not set(label[1]).issubset(set(allowed_labels)):
            raise ScaperError(
                'Label list provided must be a subset of the available labels: '
                '{:s}'.format(str(allowed_labels)))
    else:
        raise ScaperError(
            'Label must be specified using a "const" or "choose" tuple.')


def _validate_source_file(source_file, label):
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
    _validate_distribution(source_file)

    # If source file is specified explicitly
    if source_file[0] == "const":
        # 1. the filepath must point to an existing file
        if not os.path.isfile(source_file[1]):
            raise ScaperError(
                "Source file not found: {:s}".format(source_file[1]))
        # 2. the label must match the file's parent folder name
        parent_name = os.path.basename(os.path.dirname(source_file[1]))
        if label[0] != "const" or label[1] != parent_name:
            raise ScaperError(
                "Source file's parent folder name does not match label.")
    # Otherwise it must be specified using "choose"
    elif source_file[0] == "choose":
        pass
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
    if time_tuple[0] == "const":
        if ((len(time_tuple) != 2) or
                (not np.isrealobj(time_tuple[1])) or
                (time_tuple[1] < 0)):
            raise ScaperError(
                'Time must be specified when using "const" and must '
                'be non-negative.')
    else:
        _validate_distribution(time_tuple)


def _validate_duration(duration):
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
    if duration[0] == "const":
        if ((len(duration) != 2) or
                (not np.isrealobj(duration[1])) or
                (duration[1] <= 0)):
            raise ScaperError(
                'Event duration must be specified when using "const" and '
                'must be greater than zero.')
    else:
        _validate_distribution(duration)


def _validate_snr(snr):
    '''
    Validate that an snr tuple has the right format.

    Parameters
    ----------
    snr : tuple
        SNR tuple (see ```Scaper.add_event``` for required format).

    Raises
    ------
    ScaperError
        If the validation fails.

    '''
    if snr[0] == "const":
        if ((len(snr) != 2) or
                (not np.isrealobj(snr[1]))):
            raise ScaperError(
                'SNR must be specified when using "const".')
    else:
        _validate_distribution(snr)


def _validate_event(label, source_file, source_time, event_time,
                    event_duration, snr, allowed_labels):
    '''
    Check that event parameter values are valid. See ```Scaper.add_event```
    for detailed description of the expected format of each parameter.

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
    # ALL PARAMS except for the allowed_labels
    args = locals()
    for key in args:
        if key == 'allowed_labels':
            if not isinstance(args[key], list):
                raise ScaperError('allowed_labels must be of type list.')
        else:
            if not isinstance(args[key], tuple) or len(args[key]) < 1:
                raise ScaperError(
                    "Parameter {:s} must be non-empty tuple.".format(key))

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

    def _instantiate(self):
        '''
        Instantiate a specific soundscape in JAMS format based on the current
        specification. Any non-deterministic event values will be set randomly
        based on the allowed values.
        '''
        jam = jams.JAMS()
        ann = jams.Annotation(namespace='sound_event')

        # INSTANTIATE BACKGROUND AND FOREGROUND EVENTS AND ADD TO ANNOTATION
        # NOTE: logic for instantiating bg and fg events is NOT the same.

        # Add background sounds
        for event in self.bg_spec:

            # determine label
            label = _get_value_from_dist(event.label, self.bg_labels)

            # determine source file
            source_files = _get_sorted_files(os.path.join(self.bg_path, label))
            source_file = _get_value_from_dist(event.source_file,
                                               source_files)

            # event duration is fixed to self.duration
            event_duration = _get_value_from_dist(event.event_duration)
            source_duration = sox.file_info.duration(source_file)
            if (event_duration > source_duration):
                warnings.warn(
                    "{:s} background duration ({:.2f}) is greater that source "
                    "duration ({:.2f}), source will be concatenated to itself "
                    "to meet required background duration".format(
                        label, event_duration, source_duration))

            # determine source time
            source_time = _get_value_from_dist(event.source_time)
            if source_time + event_duration > source_duration:
                old_source_time = source_time
                source_time = max(0, source_duration - event_duration)
                warnings.warn(
                    '{:s} source time ({:.2f}) is too great given background '
                    'duration ({:.2f}) and source duration ({:.2f}), changed '
                    'to {:.2f}.'.format(
                        label, old_source_time, event_duration,
                        source_duration, source_time))

            # event time is fixed to 0
            event_time = _get_value_from_dist(event.event_time)

            # snr is fixed to 0
            snr = _get_value_from_dist(event.snr)

            # get role (which can only take "foreground" or "background") and
            # is set internally, not by the user.
            role = event.role

            # pack up values for JAMS
            value = EventSpec(label=label,
                              source_file=source_file,
                              source_time=source_time,
                              event_time=event_time,
                              event_duration=event_duration,
                              snr=snr,
                              role=role)

            ann.append(time=event_time,
                       duration=event_duration,
                       value=value._asdict(),
                       confidence=1.0)

        # Add foreground events
        for event in self.fg_spec:

            # determine label
            label = _get_value_from_dist(event.label, self.fg_labels)

            # determine source file
            source_files = _get_sorted_files(os.path.join(self.fg_path, label))
            source_file = _get_value_from_dist(event.source_file,
                                               source_files)

            # determine event duration
            event_duration = _get_value_from_dist(event.event_duration)
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
                        event_duration))

            # determine source time
            source_time = _get_value_from_dist(event.source_time)
            if source_time + event_duration > source_duration:
                old_source_time = source_time
                source_time = source_duration - event_duration
                warnings.warn(
                    '{:s} source time ({:.2f}) is too great given event '
                    'duration ({:.2f}) and source duration ({:.2f}), changed '
                    'to {:.2f}.'.format(
                        label, old_source_time, event_duration,
                        source_duration, source_time))

            # determine event time
            event_time = _get_value_from_dist(event.event_time)
            if event_time + event_duration > self.duration:
                old_event_time = event_time
                event_time = self.duration - event_duration
                warnings.warn(
                    '{:s} event time ({:.2f}) is too great given event '
                    'duration ({:.2f}) and soundscape duration ({:.2f}), '
                    'changed to {:.2f}.'.format(
                        label, old_event_time, event_duration,
                        self.duration, event_time))

            # determine snr
            snr = _get_value_from_dist(event.snr)

            # get role (which can only take "foreground" or "background") and
            # is set internally, not by the user.
            role = event.role

            # pack up values for JAMS
            value = EventSpec(label=label,
                              source_file=source_file,
                              source_time=source_time,
                              event_time=event_time,
                              event_duration=event_duration,
                              snr=snr,
                              role=role)

            ann.append(time=event_time,
                       duration=event_duration,
                       value=value._asdict(),
                       confidence=1.0)

        # ADD SPECIFICATIONS TO ANNOTATION SANDBOX
        ann.sandbox.scaper = jams.Sandbox(fg_spec=self.fg_spec,
                                          bg_spec=self.bg_spec)

        # Set annotation duration
        ann.duration = self.duration

        # Add annotation to jams
        jam.annotations.append(ann)

        # Set jam metadata
        jam.file_metadata.duration = self.duration

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
                        cmb.channels(N_CHANNELS)
                        # Then trim
                        cmb.trim(e.value['source_time'],
                                 e.value['source_time'] +
                                 e.value['event_duration'])
                        # After trimming, normalize background to reference DB.
                        cmb.norm(db_level=REF_DB)
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
                        tfm.channels(N_CHANNELS)
                        # Trim
                        tfm.trim(e.value['source_time'],
                                 e.value['source_time'] +
                                 e.value['event_duration'])
                        # Apply very short fade in and out
                        # (avoid unnatural sound onsets/offsets)
                        tfm.fade(fade_in_len=self.fade_in_len,
                                 fade_out_len=self.fade_out_len)
                        # Normalize to specified SNR with respect to REF_DB
                        tfm.norm(REF_DB + e.value['snr'])
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
