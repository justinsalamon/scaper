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

REF_DB = -12
N_CHANNELS = 1
SUPPORTED_DIST = ["uniform", "normal"]

# # overload my warnings
# def _warning(
#     message,
#     category=UserWarning,
#     filename='',
#     lineno=-1): print(message)
# warnings.showwarning = _warning

# Define single event spec as namedtuple
EventSpec = namedtuple(
    'EventSpec',
    ['label', 'source_file', 'source_time', 'event_time', 'event_duration',
     'snr', 'role'], verbose=False)


def _get_value_from_dist(*args):
    '''

    Parameters
    ----------
    args

    Returns
    -------

    '''
    # first arg must always be a distribution tuple
    if len(args) < 1 or not isinstance(args[0], tuple):
        raise ScaperError("No distribution tuple provided.")

    # if user specified a value
    if args[0][0] == "const":
        if len(args[0]) != 2:
            raise ScaperError('"const" tuple should include exactly 2 items.')
        else:
            return args[0][1]
    # choose randomly out of a list of options
    elif args[0][0] == "random":
        # second arg must be list of options
        if len(args) < 2 or not isinstance(args[1], list):
            raise ScaperError("No list provided for random selection.")
        else:
            # nb: random.randint range *includes* upper bound.
            idx = random.randint(0, len(args[1]) - 1)
            return args[1][idx]
    else:
        # for all other distributions we run validation
        _validate_distribution(args[0])
        if args[0][0] == "uniform":
            return random.uniform(args[0][1], args[0][2])
        elif args[0][0] == "normal":
            return random.normalvariate(args[0][1], args[0][2])


def _validate_distribution(dist_tuple):
    '''
    Check whether a tuple specifying a parameter distribution has a valid
    format, if not raise an error.

    Parameters
    ----------
    dist_tuple : tuple
        Tuple specifying a distribution to sample from

    Raises
    ------
    ScaperError
        If the tuple does not have a valid format.
    '''
    if len(dist_tuple) < 2:
        raise ScaperError('Distribution tuple must be at least of length 2.')

    if dist_tuple[0] not in SUPPORTED_DIST:
        raise ScaperError(
            "Unsupported distribution type: {:s}".format(dist_tuple[0]))

    if dist_tuple[0] == "uniform":
        if ((not np.isrealobj(dist_tuple[1])) or
                (not np.isrealobj(dist_tuple[2])) or
                (dist_tuple[1] >= dist_tuple[2])):
            raise ScaperError('Uniform must specify min and max values with '
                              'max > min.')
    elif dist_tuple[1] == "normal":
        if ((not np.isrealobj(dist_tuple[1])) or
                (not np.isrealobj(dist_tuple[2])) or
                (dist_tuple[2] <= 0)):
            raise ScaperError('Normal must specify mean and positive stddev.')


def _validate_label(label, allowed_labels):
    '''
    Validate that a label tuple is in the right format and that if a label
    value is provided using "const" that it is one of the allowed labels.

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
    if label[0] == "const":
        if len(label) != 2 or not label[1] in allowed_labels:
            raise ScaperError(
                'Label value must be specified when using "const" and must '
                'match one of the available background labels: '
                '{:s}'.format(str(allowed_labels)))
    else:
        if label[0] != "random":
            raise ScaperError(
                'Label must be specified using "const" or "random".')


def _validate_source_file(source_file, label):
    '''
    Validate that a source_file tuple is in the right format and that if a
    source_file is provided using "const" that its parent folder matches the
    provided label.

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
    # If source file is specified
    if source_file[0] == "const":
        # 1. it must specify a filepath
        if not len(source_file) == 2:
            raise ScaperError(
                'Source file must be provided when using "const".')
        # 2. the filepath must point to an existing file
        if not os.path.isfile(source_file[1]):
            raise ScaperError(
                "Source file not found: {:s}".format(source_file[1]))
        # 3. the label must match the files parent folder name
        parent_name = os.path.basename(os.path.dirname(source_file[1]))
        if len(label) != 2 or label[0] != "const" or label[1] != parent_name:
            raise ScaperError(
                "Label does not match source file parent folder name.")
    # Otherwise it must be set to "random"
    else:
        if source_file[0] != "random":
            raise ScaperError(
                'Source file must be specified using "const" or "random".')


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
    Check that event parameter values are valid. See ```add_event()```
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
    _validate_label(label)

    # SOURCE TIME
    _validate_time(source_time)

    # EVENT TIME
    _validate_time(event_time)

    # EVENT DURATION
    _validate_duration(event_duration)

    # SNR
    _validate_snr(snr)


class Scaper(object):

    def __init__(self, duration, fg_path=None, bg_path=None):
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

        # Duration must be positive
        # TODO : check for type?
        if duration > 0:
            self.duration = duration
        else:
            raise ScaperError('Duration must be positive')

        # Start with empty specifications
        self.fg_spec = []
        self.bg_spec = []

        # Only set folder paths if they point to valid folders
        if fg_path is not None and os.path.isdir(fg_path):
            self.fg_path = fg_path
        else:
            self.fg_path = None
            warnings.warn(
                'fg_path "{:s}" unset or does not point to a valid '
                'folder'.format(str(fg_path)))

        if bg_path is not None and os.path.isdir(bg_path):
            self.bg_path = bg_path
        else:
            self.bg_path = None
            warnings.warn(
                'bg_path "{:s}" unset or does not point to a valid '
                'folder'.format(str(bg_path)))

        # Populate label lists from folder paths
        self.fg_labels = []
        self.bg_labels = []

        if self.fg_path is not None:
            folder_names = os.listdir(self.fg_path)
            for fname in folder_names:
                if (os.path.isdir(os.path.join(self.fg_path, fname)) and
                        fname[0] != '.'):
                    self.fg_labels.append(fname)

        if self.bg_path is not None:
            folder_names = os.listdir(self.bg_path)
            for fname in folder_names:
                if (os.path.isdir(os.path.join(self.bg_path, fname)) and
                        fname[0] != '.'):
                    self.bg_labels.append(fname)

    def add_background(self, label, source_file, source_time):
        '''
        Add a background recording. The duration will be equal to the duration
        of the soundscape specified when initializing the Scaper object
        ```self.duration```. If the source file is shorter than this duration
        then it will be concatenated to itself as many times as necessary to
        produce the specified duration.

        Parameters
        ----------
        label : tuple
            Specifies the label of the background sound. To set a specific
            value, the first item must be "const" and the second item the label
            value (string). The value must match one of the labels in the
            Scaper's background label list ```bg_labels```.
            If ```source_file``` is specified using "const", then the value of
            ```label``` must also be specified using "const" and its value must
            match the source file's parent folder's name.
            To randomly set a value, see the Random Options documentation
            below.
        source_file: tuple
            Specifies the audio file to use as the source. To set a specific
            value the first item must be "const" and the second item the path to
            the audio file (string).
            If ```source_file``` is specified using "const", then the value of
            ```label``` must match the source file's parent folder's name.
            To randomly set a value, see the Random Options documentation
            below.
        source_time : tuple
            Specifies the desired start time in the source file. To set a
            specific value, the first item must be "const" and the second the
            desired value in seconds (float). The value must be equal to or
            smaller than the source file's duration - ```self.duration```
            (i.e. the soundscape's duration specified during initialization).
            To randomly set a value, see the Random Options documentation
            below.

        Random Options
        --------------
        ```source_time``` can either be set to a specific
        value using "const" as the first item in the tuple, or it can be
        randomly chosen from a distribution. To achieve this, instead of "const"
        the first item must be one of the supported distribution names,
        followed by the distribution's parameters (which are distribution-
        specific).
        The supported distributions (and their parameters) are:
        - ("uniform", min_value, max_value)
        - ("normal", mean, stddev)
        The ```label``` and ```source_file``` parameters only support the
        following distribution (in addition to "const"):
        - ("random")
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
            Specifies the label of the sound event. To set a specific value,
            the first item must be "const" and the second item the label value
            (string). The value must match one of the labels in the Scaper's
            foreground label list ```fg_labels```.
            If ```source_file``` is specified using "const", then the value of
            ```label``` must match the source file's parent folder's name.
            To randomly set a value, see the Random Options documentation
            below.
        source_file : tuple
            Specifies the audio file to use as the source. To set a specific
            value the first item must be "const" and the second item the path to
            the audio file (string).
            If ```source_file``` is specified using "const", then the value of
            ```label``` must also be specified using "const" and its value must
            match the source file's parent folder's name.
            To randomly set a value, see the Random Options documentation
            below.
        source_time : tuple
            Specifies the desired start time in the source file. To set a
            specific value, the first item must be "const" and the second the
            desired value in seconds (float). The value must be equal to or
            smaller than the  source file's duration - ```event_duration```.
            To randomly set a value, see the Random Options documentation
            below.
        event_time : tuple
            Specifies the desired start time of the event in the soundscape.
            To set a specific value, the first item must be "const" and the
            second the desired value in seconds (float). The value must be
            equal to or smaller than the soundscapes's duration -
            ```event_duration```.
            To randomly set a value, see the Random Options documentation
            below.
        event_duration : tuple
            Specifies the desired duration of the event. To set a
            specific value, the first item must be "const" and the second the
            desired value in seconds (float). The value must be equal to or
            smaller than the source file's duration.
            To randomly set a value, see the Random Options documentation
            below.
        snr : float
            Specifies the desired signal to noise ratio (snr) between the event
            and the background.
            To set a specific value, the first item must be "const" and the
            second the desired value in dB (float).
            To randomly set a value, see the Random Options documentation
            below.

        Random Options
        --------------
        All of the aforementioned parameters can either be set to a specific
        value using "const" as the first item in the tuple, or they can be
        randomly chosen from a distribution. To achieve this, instead of "const"
        the first item must be one of the supported distribution names,
        followed by the distribution's parameters (which are distribution-
        specific).
        The supported distributions (and their parameters) are:
        - ("uniform", min_value, max_value)
        - ("normal", mean, stddev)
        All of the parameters can take any of the aforementioned distributions
        with the exception of ```label``` and ```source_file``` that only
        support the following distribution (in addition to "const"):
        - ("random")
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
            source_files = glob.glob(os.path.join(self.bg_path, label, '*'))
            source_files = [sf for sf in source_files if os.path.isfile(sf)]
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
            value = value._asdict()

            ann.append(time=event_time,
                       duration=event_duration,
                       value=value,
                       confidence=1.0)

        # Add foreground events
        for event in self.fg_spec:

            # determine label
            label = _get_value_from_dist(event.label, self.fg_labels)

            # determine source file
            source_files = glob.glob(os.path.join(self.fg_path, label, '*'))
            source_files = [sf for sf in source_files if os.path.isfile(sf)]
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
            value = value._asdict()

            ann.append(time=event_time,
                       duration=event_duration,
                       value=value,
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
            logger = logging.getLogger()
            logger.setLevel('CRITICAL')  # only critical messages please

        # array for storing all tmp files (one for every event)
        tmpfiles = []

        try:
            for event in ann.data.iterrows():

                # first item is index, second is event dictionary
                e = event[1]

                if e.value['role'] == 'background':
                    # Concatenate background if necessary. Right now we always
                    # concatenate the background at least once, since the pysox
                    # combiner raises an error if you try to call build using
                    # an input_file_list with less than 2 elements. In the
                    # future if the combiner is updated to accept a list of
                    # length 1, then the max(..., 2) statement can be removed
                    # from the calculation of ntiles.
                    source_duration = (
                        sox.file_info.duration(e.value['source_file']))
                    ntiles = int(max(self.duration // source_duration + 1, 2))

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
                        [e.value['source_file']] * ntiles, tmpfiles[-1].name,
                        'concatenate')

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
                    tfm.fade(fade_in_len=0.01, fade_out_len=0.01)
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
                        'Unsupported event role: {:s}'.format(e.value['role']))

            # Finally combine all the files
            cmb = sox.Combiner()
            # TODO: do we want to normalize the final output?
            cmb.build([t.name for t in tmpfiles], audio_path, 'mix')

        finally:
            # Close all open temp files
            for t in tmpfiles:
                t.close()

        if disable_sox_warnings:
            # set back to warning
            logger = logging.getLogger()
            logger.setLevel('WARNING')

        # Finally save JAMS to disk too
        jam.save(jams_path)
