import sox
import random
import os
import warnings
import jams
import glob
from collections import namedtuple
import numbers

SNR_MAX = 120
MAX_DB = -31
MIN_DURATION = 1
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
     'snr'], verbose=False)


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
        raise ValueError("No distribution tuple provided.")

    # if user specified a value
    if args[0][0] == "set":
        if len(args[0]) != 2:
            raise ValueError('"set" tuple should include exactly 2 items.')
        else:
            return args[0][1]
    # choose randomly out of a list of options
    elif args[0][0] == "random":
        # second arg must be list of options
        if len(args) < 2 or not isinstance(args[1], list):
            raise ValueError("No list provided for random selection.")
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
    ValueError
        If the tuple does not have a valid format.
    '''
    if len(dist_tuple) < 2:
        raise ValueError('Distribution tuple must be at least of length 2.')

    if dist_tuple[0] not in SUPPORTED_DIST:
        raise ValueError(
            "Unsupported distribution type: {:s}".format(dist_tuple[0]))

    if dist_tuple[0] == "uniform":
        if ((not isinstance(dist_tuple[1], numbers.Number)) or
                (not isinstance(dist_tuple[2], numbers.Number)) or
                (dist_tuple[1] >= dist_tuple[2])):
            raise ValueError('Uniform must specify min and max values with '
                             'max > min.')
    elif dist_tuple[1] == "normal":
        if ((not isinstance(dist_tuple[1], numbers.Number)) or
                (isinstance(dist_tuple[2], numbers.Number)) or
                (dist_tuple[2] <= 0)):
            raise ValueError('Normal must specify mean and positive stddev.')


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
    ValueError
        If any of the input parameters has an invalid format or value.
    '''
    # ALL PARAMS except for the allowed_labels
    args = locals()
    for key in args:
        if key == 'allowed_labels':
            if not isinstance(args[key], list):
                raise ValueError('allowed_labels must be of type list.')
        else:
            if not isinstance(args[key], tuple) or len(args[key]) < 1:
                raise ValueError(
                    "Parameter {:s} must be non-empty tuple.".format(key))

    # SOURCE FILE
    # If source file is specified
    if source_file[0] == "set":
        # 1. it must specify a filepath
        if not len(source_file) == 2:
            raise ValueError(
                'Source file must be provided when using "set".')
        # 2. the filepath must point to an existing file
        if not os.path.isfile(source_file[1]):
            raise RuntimeError(
                "Source file not found: {:s}".format(source_file[1]))
        # 3. the label must match the files parent folder name
        parent_name = os.path.basename(os.path.dirname(source_file[1]))
        if len(label) != 2 or label[0] != "set" or label[1] != parent_name:
            raise ValueError(
                "Label does not match source file parent folder name.")
    # Otherwise it must be set to "random"
    else:
        if source_file[0] != "random":
            raise ValueError(
                'Source file must be specified using "set" or "random".')

    # LABEL
    if label[0] == "set":
        if len(label) != 2 or not label[1] in allowed_labels:
            raise ValueError(
                'Label value must be specified when using "set" and must '
                'match one of the available background labels: '
                '{:s}'.format(str(allowed_labels)))
    else:
        if label[0] != "random":
            raise ValueError(
                'Label must be specified using "set" or "random".')

    # SOURCE TIME
    if source_time[0] == "set":
        if ((len(source_time) != 2) or
                (not isinstance(source_time[1], numbers.Number)) or
                (source_time[1] < 0)):
            raise ValueError(
                'Source time must be specified when using "set" and must '
                'be non-negative.')
    else:
        _validate_distribution(source_time)

    # EVEN TIME
    if event_time[0] == "set":
        if ((len(event_time) != 2) or
                (not isinstance(event_time[1], numbers.Number)) or
                (event_time[1] < 0)):
            raise ValueError(
                'Event time must be specified when using "set" and must '
                'be non-negative zero.')
    else:
        _validate_distribution(event_time)

    # EVENT DURATION
    if event_duration[0] == "set":
        if ((len(event_duration) != 2) or
                (not isinstance(event_duration[1], numbers.Number)) or
                (event_duration[1] <= 0)):
            raise ValueError(
                'Event duration must be specified when using "set" and '
                'must be greater than zero.')
    else:
        _validate_distribution(event_duration)

    # SNR
    if snr[0] == "set":
        if ((len(snr) != 2) or
                (not isinstance(snr[1], numbers.Number))):
            raise ValueError(
                'SNR must be specified when using "set".')
    else:
        _validate_distribution(snr)


def random_file(folder_path):
    '''
    Return path to a randomly chosen file contained within the provided folder.
    Note: any subfolders contained in the provided folder path will be ignored.

    Parameters
    ----------
    folder_path : str
        Path to folder containing files.

    Returns
    -------
    randfilepath : str
        Path to randomly chosen file contained in the provided folder.
    '''
    # Make sure folder_path is valid
    if not os.path.isdir(folder_path):
        raise ValueError("Path provided does not point to a valid folder.")

    files = glob.glob(os.path.join(folder_path, "*"))
    files = [f for f in files if os.path.isfile(f)]
    idx = random.randint(0, len(files))
    return files[idx]


class ScaperSpec(object):

    def __init__(self, *args, **kwargs):

        """

        Parameters
        ----------
        @param bg_label     : background audio class label
        bg_duration   : background audio duration
        scape      : scape object to be used with this spec

        """

        # avoid reference before assignment, in case no scaper object passed
        sc = None

        # number of argument checks
        if len(args) == 0:
            bg_label = None
            bg_duration = None
        elif len(args) == 1:
            sc = args[0]
            bg_label = None
            bg_duration = None
        elif len(args) == 2:
            sc = args[0]
            bg_label = args[1]
            bg_duration = None
        else:
            sc = args[0]
            bg_label = args[1]
            bg_duration = args[2]

        # if args are key value pairs
        for key, val in kwargs.iteritems():
            if key == 'bg_label':
                bg_label = val
            elif key == 'bg_duration':
                bg_duration = val
            elif key == 'scape':
                sc = val

        print('-----------------------------------')
        print('ScaperSpec Created:')
        print('bg_label: ', bg_label)
        print('duration: ', bg_duration)

        # None scape passed or invalid type
        if sc is None or not isinstance(sc, Scaper):
            # generate default scaper
            sc = Scaper()
            warnings.warn('Warning, No Scaper object provided to ScaperSpec '
                          'function. Using default Scaper object.')

        # this is the spec
        self.spec = []
        self.sc = sc

        # sum members aren't set initialized until later
        self.num_events = 0
        self.labels = None
        self.durations = None
        self.fg_start_times = None
        self.fg_durations = None
        self.snrs = None
        self.filepaths = None

        # acquire available labels
        available_labels = os.listdir(sc.bg_path)
        available_labels = (
            [the_label for the_label in available_labels if not
                (the_label.startswith('.'))])

        # no background label provided, chose randomly
        if bg_label is None:
            if len(available_labels) > 0:
                bg_label = (
                    available_labels[(int(round(random.random() *
                                                (len(available_labels)-1))))])
                warnings.warn('Warning, No background label provided, '
                              'choosing randomly.')
            else:
                # FIXME
                bg_label = 'car'
            self.bg_label = bg_label

        # list not provided
        elif type(bg_label) is not list:
            self.bg_label = [bg_label]

        # list provided
        elif type(bg_label) is list:
            # specific path provided
            if len(bg_label) == 1:
                self.bg_label = bg_label
            # list of labels provided, choose randomly
            else:
                self.bg_label = (
                    [bg_label[(int(round(random.random() *
                                         (len(bg_label) - 1))))]])

        # invalid background element duration
        if (bg_duration is None or bg_duration <= 0 or
                not isinstance(bg_duration, int)):
            self.bg_duration = 10
            warnings.warn('Warning, scape must have global duration > 0. '
                          'Setting duration to default: 10 seconds')
        else:
            self.bg_duration = bg_duration

        # validate background label
        self.bg_label, self.bg_file = (
            self.validate_label_paths(sc.bg_path, self.bg_label))

        # choose a file for background
        while True:
            # random index of available bg files
            rand_ndx = int(round(random.random() * (len(self.bg_file[0]) - 1)))
            thefile = self.bg_file[0][rand_ndx]

            # if the file satisfies the start times and durations
            if self.bg_duration <= sox.file_info.duration(thefile):
                self.bg_file = thefile
                break

        bg_spec = {'bg_label': self.bg_label,
                   'bg_duration': self.bg_duration,
                   'bg_source_file': self.bg_file}

        # append to spec
        self.spec.append(bg_spec)

    @staticmethod
    def validate_label_paths(path, labels):

        """

        Parameters
        ----------
        path : str
            Foreground or background path where label subdirectories are
            located.
        labels : list?
            The labels, whose corresponding directory paths will be validated

        Returns
        -------
        validated_labels : list?
            The labels that have been validated, or assigned in case of failure

        """

        fpaths = []
        validated_labels = [None] * len(labels)
        available_labels = os.listdir(path)
        available_labels = ([the_label for the_label in available_labels
                             if not (the_label.startswith('.'))])

        # if a list of labels is passed
        for ndx in range(0, len(labels)):

            # check if label directory does not exist
            if not (os.path.isdir(os.path.join(path, labels[ndx]))):

                warnings.warn('Warning, the supplied label does not exist in '
                              'audio directory. Choosing label randomly')
                validated_labels[ndx] = (
                    available_labels[(int(round(random.random() *
                                                (len(available_labels)-1))))])
                # FIXME currently this can assign same class..

            # label exists, check if it contains any audio files
            else:
                tmp = os.path.join(path, labels[ndx])
                # for each file in directory
                for filename in os.listdir(tmp):
                    # if not .DS_store
                    if ((not filename.startswith('.')) and
                            filename.endswith('.wav')):
                        # set labels and break
                        validated_labels[ndx] = labels[ndx]
                        break

            # chose audio file paths for corresponding labels
            files = os.listdir(os.path.join(path, validated_labels[ndx]))
            filepaths = (
                [thisfile for thisfile in files if not
                    (thisfile.startswith('.'))])
            this_path = os.path.join(path, validated_labels[ndx])
            for n, thefile in enumerate(filepaths):
                filepaths[n] = os.path.join(this_path, filepaths[n])
            fpaths.append(filepaths)

        return validated_labels, fpaths

    def add_events(self, *args, **kwargs):

        # """
        #
        # Parameters
        # ----------
        # @param labels          : foreground event labels
        # @param fg_start_times  : start time of events
        # @param fg_durations    : durations of events
        # @param snrs            : SNR of events
        # @param num_events      : number of this type of event to insert
        #
        # """

        # number of argument checks
        if len(args) == 0:
            labels = None
            fg_start_times = None
            fg_durations = None
            snrs = None
            num_events = None

        elif len(args) == 1:
            labels = args[0]
            fg_start_times = None
            fg_durations = None
            snrs = None
            num_events = None

        elif len(args) == 2:
            labels = args[0]
            fg_start_times = args[1]
            fg_durations = None
            snrs = None
            num_events = None

        elif len(args) == 3:
            labels = args[0]
            fg_start_times = args[1]
            fg_durations = args[2]
            snrs = None
            num_events = None

        elif len(args) == 4:
            labels = args[0]
            fg_start_times = args[1]
            fg_durations = args[2]
            snrs = args[3]
            num_events = None

        else:
            labels = args[0]
            fg_start_times = args[1]
            fg_durations = args[2]
            snrs = args[3]
            num_events = args[4]

        # if args are key value pairs
        for key, val in kwargs.iteritems():
            if key == 'labels':
                labels = val
            elif key == 'fg_start_times':
                fg_start_times = val
            elif key == 'fg_durations':
                fg_durations = val
            elif key == 'snrs':
                snrs = val
            elif key == 'num_events':
                num_events = val

        # ////////////////////////////////////////////////////////////////////
        # NUM EVENTS
        # num_events not provided,

        # FIXME choose randomly or default ?
        if num_events is None:
            warnings.warn('Warning, number of events not provided. Setting '
                          'number of events to default: 1')
            self.num_events = 1

        # invalid number of events
        # FIXME choose randomly or default ?
        if num_events <= 0:
            warnings.warn('Warning, invalid number of events provided. Setting '
                          'number of events to default: 1')
            self.num_events = 1
        else:
            self.num_events = num_events

        # ////////////////////////////////////////////////////////////////////
        # LABELS

        available_labels = os.listdir(self.sc.fg_path)
        available_labels = (
            [the_label for the_label in available_labels if not
                (the_label.startswith('.'))])

        # no labels provided, chose randomly
        if labels is None:
            labels = (
                [available_labels[(int(round(random.random() *
                                             (len(available_labels) - 1))))]])
            warnings.warn('Warning, labels not provided. Using randomly '
                          'generated labels: ' + str(labels))
            self.labels = labels

        # list not provided, single element passed
        elif type(labels) is not list:
            tmp = labels
            self.labels = [tmp] * self.num_events

        # list provided
        elif type(labels) is list:
            self.labels = labels

        # ////////////////////////////////////////////////////////////////////
        # FG DURATIONS
        # invalid foreground element durations, use random
        if fg_durations is None:
            # FIXME bg_duration/2 is arbitrary
            tmp = round(random.random() * (self.bg_duration / 2) + 1)
            fg_durations = [tmp] * self.num_events
            warnings.warn('Warning, no event durations provided. Setting '
                          'durations randomly: ' + str(fg_durations))
            self.fg_durations = fg_durations

        # list provided
        elif type(fg_durations) is list:
            for ndx, duration in enumerate(fg_durations):
                if duration <= 0:
                    # FIXME bg_duration/2 is arbitrary
                    tmp = round(random.random() * (self.bg_duration / 2) + 1)
                    fg_durations[ndx] = tmp
                    warnings.warn('Warning, events must have duration > 0. '
                                  'Setting durations randomly: ' +
                                  str(fg_durations))
            self.fg_durations = fg_durations

        # list not provided
        elif type(fg_durations) is not list:
            tmp = fg_durations
            self.fg_durations = [tmp] * self.num_events

        # ///////////////////////////////////////////////////////////////////
        # SNRS

        # no snrs provided
        if snrs is None:
            # FIXME default -10 to 0 is arbitary
            tmp = -round(random.random() * 10) + 1
            snrs = [tmp] * self.num_events
            self.snrs = snrs
            warnings.warn('Warning, no SNRs provided. Setting SNRS '
                          'randomly: ' + str(self.snrs))

        # list provided
        elif type(snrs) is list:
            for ndx, snr_val in enumerate(snrs):
                if snr_val > 0:
                    # FIXME default -10 to 0 is arbitary
                    tmp = -round(random.random() * 10) + 1
                    snrs[ndx] = tmp
                    warnings.warn('Warning, SNR value provided out of range '
                                  '(must be < 0). Setting SNR randomly: ' +
                                  str(snrs))
                self.snrs = snrs

        # list not provided
        elif type(snrs) is not list:
            tmp = snrs
            self.snrs = [tmp] * self.num_events

        # ////////////////////////////////////////////////////////////////////
        # FG START TIMES

        # no start times provided
        self.fg_start_times = []
        if fg_start_times is None:
            warnings.warn('Warning, start times not provided. Setting start '
                          'times randomly.')
            for ndx in range(0, self.num_events):
                rand_start_time = (
                    round(random.random() *
                          (self.bg_duration -
                           self.fg_durations[(ndx % self.num_events) - 1])))
                self.fg_start_times.append(rand_start_time)

        # list provided
        elif type(fg_start_times) is list:
            for ndx, start_time in enumerate(fg_start_times):
                if start_time < 0:
                    new_start_time = (
                        round(random.random() *
                              (self.bg_duration -
                               self.fg_durations[(ndx % self.num_events) - 1])))
                    warnings.warn(
                        'Warning, fg_start_time ' +
                        str(start_time) +
                        ' invalid. Start times must be >= 0.')
                    self.fg_start_times.append(new_start_time)
                else:
                    self.fg_start_times.append(start_time)
        # list not provided
        elif type(fg_start_times) is not list:
            tmp = fg_start_times
            self.fg_start_times = [tmp] * self.num_events

        # ////////////////////////////////////////////////////////////////////
        # check list length
        # lists passed, but must ensure they are correct length
        # (same as num_events)

        if type(self.snrs) is list and (len(self.snrs) != self.num_events):
            # not enough snrs
            if len(self.snrs) < self.num_events:
                for ndx in range(len(self.snrs), num_events):
                    # FIXME MOD
                    self.snrs.append(self.snrs[(ndx % self.num_events) - 1])
                warnings.warn('Warning, not enough SNRs provided. Using the '
                              'following SNRs: ' + str(self.snrs))
            # too many snrs
            elif len(self.snrs) > self.num_events:
                self.snrs = self.snrs[0:self.num_events]
                warnings.warn('Warning, more SNRs provided than events. Using '
                              'the following SNRs: ' + str(self.snrs))

        # lists passed, but must ensure they are correct length (same as
        # num_events)
        if type(self.fg_durations) is list and (len(self.fg_durations) !=
                                                self.num_events):
            # not enough durations
            if len(self.fg_durations) < self.num_events:
                for ndx in range(len(self.fg_durations), num_events):
                    # FIXME MOD or rand ?
                    self.fg_durations.append(
                        self.fg_durations[(ndx % self.num_events)-1])
                warnings.warn('Warning, not enough durations provided. Using '
                              'the following durations: ' +
                              str(self.fg_durations))
            # too many durations
            elif len(self.fg_durations) > self.num_events:
                self.fg_durations = self.fg_durations[0:self.num_events]
                warnings.warn('Warning, more durations provided than events. '
                              'Using the following durations: ' +
                              str(self.fg_durations))

        # lists passed, but must ensure they are correct length (same as num_
        # events)
        if type(self.fg_start_times) is list and (len(self.fg_start_times) !=
                                                  self.num_events):
            # not enough start times
            if len(self.fg_start_times) < self.num_events:
                for ndx in range(len(self.fg_start_times), self.num_events):
                    # FIXME MOD or rand ?
                    self.fg_start_times.append(
                        self.fg_start_times[(ndx % self.num_events) - 1])
                warnings.warn('Warning, not enough start times provided. Using '
                              'the following start times: ' +
                              str(self.fg_start_times))
            # too many start times
            elif len(self.fg_start_times) > self.num_events:
                self.fg_start_times = self.fg_start_times[0:self.num_events]
                warnings.warn('Warning, more start times provided than events. '
                              'Using the following start times: ' +
                              str(self.fg_start_times))

        # lists passed, but must ensure they are correct length (same as num_
        # events)
        if type(self.labels) is list and (len(self.labels) != self.num_events):
            # not enough labels
            if len(self.labels) < self.num_events:
                for ndx in range(len(self.labels), self.num_events):
                    # FIXME MOD or rand ?
                    self.labels.append(
                        self.labels[(ndx % self.num_events) - 1])
                warnings.warn('Warning, not enough labels provided. Using the '
                              'following labels: ' + str(self.labels))
            # too many labels
            elif len(self.labels) > self.num_events:
                self.labels = self.labels[0:self.num_events]
                warnings.warn('Warning, more labels provided than events. '
                              'Using the following labels: ' +
                              str(self.labels))

        # event duration value checks
        for ndx, each_time in enumerate(self.fg_start_times):
            # if fg_start_time + fg_duration is longer than bg_duration
            if each_time + self.fg_durations[ndx] > self.bg_duration:
                self.fg_durations[ndx] = (
                    self.bg_duration - self.fg_start_times[ndx])
                warnings.warn('Warning, event durations exceed background '
                              'duration for provided start times. ' +
                              'Event duration truncated to ' +
                              str(self.fg_durations[ndx]) + ' seconds.')

        # choose the source file for each event
        chosen_files = []
        for n in range(0, self.num_events):
            # if more events than labels provided
            if (n >= len(self.labels)):
                print "ever?"
                # choose a random label from the label list
                label = (
                    self.labels[int(round(random.random() *
                                          (len(self.labels)-1)))])
                # append this new label
                self.labels.append(label)

        # validate foreground labels
        self.labels, self.filepaths = (
            self.validate_label_paths(self.sc.fg_path, self.labels))

        # for each label, choose a file
        for ndx, this_label in enumerate(self.labels):
            for each_file in self.filepaths[ndx]:

                # random index for files corresponding to label
                rand_ndx = int(
                    round(random.random() * (len(self.filepaths[ndx]) - 1)))
                f = self.filepaths[ndx][rand_ndx]

                # if the file satisfies the start times and durations
                if self.fg_durations[ndx] <= sox.file_info.duration(f):
                    chosen_files.append(f)
                    break

        # set the filepaths member to be the updated list of chosen files
        self.filepaths = chosen_files

        print("chosen files: \n")
        print(chosen_files)

        print('\n')
        print('Add Events:')
        print('-----------------------------------')
        print('fg_labels', self.labels)
        print('fg_start_time', self.fg_start_times)
        print('fg_duration', self.fg_durations)
        print('source_files', self.filepaths)
        print('snr', self.snrs)
        print('num_events', self.num_events)

        s = None

        for ndx, each_label in enumerate(self.labels):
            s = {'label': each_label,
                 'fg_start_time': self.fg_start_times,
                 'fg_duration': self.fg_durations,
                 'source_files': self.filepaths,
                 'snr': self.snrs,
                 'num_events': self.num_events}

        # add these events to the spec object
        self.spec.append(s)

        # self.labels = ["horn"]
        # self.fg_durations = [1]
        # self.fg_start_times = [1]
        # self.num_events= 1
        # self.snrs = [1]

    @staticmethod
    def generate_jams(spec, outfile):

        """

        Parameters
        ----------
        spec        :   ScaperSpec object defining the soundscape
        outfile     :   location to save JAMS outfile

        Returns
        -------
        scene_jam   :   JAMS annotation

        """
        jams.schema.add_namespace('namespaces/event.json')
        scene_jam = jams.JAMS()
        scene_ann = jams.Annotation(namespace='event')

        # FIXME should sp.spec be passed or should spec = sp.spec be used here?

        # everything goes into the value field as a tuple
        for ndx, events in enumerate(spec):

            # background file
            if 'bg_duration' in events:
                # add background annotation
                scene_ann.append(value=(['background', events['bg_label'][0],
                                        events['bg_source_file']]
                                        ),
                                 time=0.0,
                                 duration=events['bg_duration'],
                                 confidence=1)

                # every jam must have a duration
                scene_jam.file_metadata.duration = events['bg_duration']

            elif 'fg_duration' in events:
                # append annotation for each event

                for n in range(0, events['num_events']):
                    scene_ann.append(value=(['foreground', events['label'],
                                            events['source_files'][n],
                                             # events['fg_start_time'][n],
                                             events['snr'][n]]
                                            #
                                            ),
                                     # time=1,
                                     # duration=2,
                                     time=events['fg_start_time'][n],
                                     duration=events['fg_duration'][n],
                                     confidence=1)

        # append annotation to jams, save jams
        scene_jam.annotations.append(scene_ann)
        scene_jam.save(outfile)

        print('-----------------------------------')
        print('Jams Created:')
        print(outfile)

        return scene_jam


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
            raise ValueError('Duration must be positive')

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
            value, the first item must be "set" and the second item the label
            value (string). The value must match one of the labels in the
            Scaper's background label list ```bg_labels```.
            If ```source_file``` is specified using "set", then the value of
            ```label``` must also be specified using "set" and its value must
            match the source file's parent folder's name.
            To randomly set a value, see the Random Options documentation
            below.
        source_file: tuple
            Specifies the audio file to use as the source. To set a specific
            value the first item must be "set" and the second item the path to
            the audio file (string).
            If ```source_file``` is specified using "set", then the value of
            ```label``` must match the source file's parent folder's name.
            To randomly set a value, see the Random Options documentation
            below.
        source_time : tuple
            Specifies the desired start time in the source file. To set a
            specific value, the first item must be "set" and the second the
            desired value in seconds (float). The value must be equal to or
            smaller than the source file's duration - ```self.duration```
            (i.e. the soundscape's duration specified during initialization).
            To randomly set a value, see the Random Options documentation
            below.

        Random Options
        --------------
        ```source_time``` can either be set to a specific
        value using "set" as the first item in the tuple, or it can be
        randomly chosen from a distribution. To achieve this, instead of "set"
        the first item must be one of the supported distribution names,
        followed by the distribution's parameters (which are distribution-
        specific).
        The supported distributions (and their parameters) are:
        - ("uniform", min_value, max_value)
        - ("normal", mean, stddev)
        The ```label``` and ```source_file``` parameters only support the
        following distribution (in addition to "set"):
        - ("random")
        '''

        # These values are fixed for the background sound
        event_time = ("set", 0)
        event_duration = ("set", self.duration)
        snr = ("set", 0)

        # Validate parameter format and values
        _validate_event(label, source_file, source_time, event_time,
                        event_duration, snr, self.bg_labels)

        # Create background sound event
        bg_event = EventSpec(label=label,
                             source_file=source_file,
                             source_time=source_time,
                             event_time=event_time,
                             event_duration=event_duration,
                             snr=snr)

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
            the first item must be "set" and the second item the label value
            (string). The value must match one of the labels in the Scaper's
            foreground label list ```fg_labels```.
            If ```source_file``` is specified using "set", then the value of
            ```label``` must match the source file's parent folder's name.
            To randomly set a value, see the Random Options documentation
            below.
        source_file : tuple
            Specifies the audio file to use as the source. To set a specific
            value the first item must be "set" and the second item the path to
            the audio file (string).
            If ```source_file``` is specified using "set", then the value of
            ```label``` must also be specified using "set" and its value must
            match the source file's parent folder's name.
            To randomly set a value, see the Random Options documentation
            below.
        source_time : tuple
            Specifies the desired start time in the source file. To set a
            specific value, the first item must be "set" and the second the
            desired value in seconds (float). The value must be equal to or
            smaller than the  source file's duration - ```event_duration```.
            To randomly set a value, see the Random Options documentation
            below.
        event_time : tuple
            Specifies the desired start time of the event in the soundscape.
            To set a specific value, the first item must be "set" and the
            second the desired value in seconds (float). The value must be
            equal to or smaller than the soundscapes's duration -
            ```event_duration```.
            To randomly set a value, see the Random Options documentation
            below.
        event_duration : tuple
            Specifies the desired duration of the event. To set a
            specific value, the first item must be "set" and the second the
            desired value in seconds (float). The value must be equal to or
            smaller than the source file's duration.
            To randomly set a value, see the Random Options documentation
            below.
        snr : float
            Specifies the desired signal to noise ratio (snr) between the event
            and the background.
            To set a specific value, the first item must be "set" and the
            second the desired value in dB (float).
            To randomly set a value, see the Random Options documentation
            below.

        Random Options
        --------------
        All of the aforementioned parameters can either be set to a specific
        value using "set" as the first item in the tuple, or they can be
        randomly chosen from a distribution. To achieve this, instead of "set"
        the first item must be one of the supported distribution names,
        followed by the distribution's parameters (which are distribution-
        specific).
        The supported distributions (and their parameters) are:
        - ("uniform", min_value, max_value)
        - ("normal", mean, stddev)
        All of the parameters can take any of the aforementioned distributions
        with the exception of ```label``` and ```source_file``` that only
        support the following distribution (in addition to "set"):
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
                          snr=snr)

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

            # pack up values for JAMS
            value = EventSpec(label=label,
                              source_file=source_file,
                              source_time=source_time,
                              event_time=event_time,
                              event_duration=event_duration,
                              snr=snr)
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

            # pack up values for JAMS
            value = EventSpec(label=label,
                              source_file=source_file,
                              source_time=source_time,
                              event_time=event_time,
                              event_duration=event_duration,
                              snr=snr)
            value = value._asdict()

            ann.append(time=event_time,
                       duration=event_duration,
                       value=value,
                       confidence=1.0)

        # ADD SPECIFICATIONS TO ANNOTATION SANDBOX
        ann.sandbox.scaper = jams.Sandbox(fg_spec=self.fg_spec,
                                          bg_spec=self.bg_spec)

        # Add annotation to jams
        jam.annotations.append(ann)

        # Return
        return jam

    def generate(self, audio_path, jams_path):
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
        soundscape_jams = self._instantiate()
        # TODO: synthesize the soundscape instance
        soundscape_audio = 0

        # TODO: save to disk

    @staticmethod
    def generate_soundscapes(*args, **kwargs):

        """
          Parameters
          ----------
          @param j_file      :   JAMS file describing soundscape
          @param s_file      :   audio output filepath

          Returns
          -------

          """

        # if args are key value pairs
        for key, val in kwargs.iteritems():
            if key == 'j_file':
                j_file = val
            elif key == 's_file':
                s_file = val

        # if no key value pairs for args
        # FIXME not the way to do this
        try:
            j_file
        except NameError:
            # argument checks
            if len(args) == 0:
                warnings.warn('Warning, no audio paths provided. Using default '
                              'directories: ../audio/fg  ../audio/bg')
                j_file = 'jams.jams'
                s_file = '../audio/output'
            elif len(args) == 1:
                warnings.warn('Warning, no background path provided. Using '
                              'default directory: ../audio/bg ')
                j_file = args[0]
                s_file = '../audio/output'
            else:
                j_file = args[0]
                s_file = args[1]

        if j_file is None or not os.path.isfile(j_file):
            warnings.warn('Warning, no jams file, or invalid jams file '
                          'provided. Generate_soundscapes()' +
                          ' process terminated.')
            return

        print("--", s_file)
        # check if output audio file already exists
        if os.path.exists(s_file):
            warnings.warn('Warning, output file %s already exists. Continuing '
                          'will overwrite.' % j_file)

            while True:
                response = raw_input('Proceed: y/n?')
                if response == 'y':
                    warnings.warn('Overwriting file %s' % str(s_file))
                    break
                if response == 'n':
                    warnings.warn('File %s will not be overwritten. Generate_'
                                  'soundscapes() terminated.' % s_file)
                    return
                warnings.warn('Warning, invalid response. Please select '
                              '\'y\' or \'no\' :')

        elif os.access(os.path.dirname(s_file), os.W_OK):
            print('Output file %s selected.' % s_file)
        else:
            warnings.warn('Warning, provided scaper output file is invalid. '
                          'Generate_soundscapes() process terminated.')
            return

        # load jams file, extract elements
        jam = jams.load(j_file)
        events = jam.search(namespace='event')[0]

        for ndx, value in enumerate(events.data.value):
            if value[0] == 'background':

                bg_filepath = value[2]
                bg_start_time = events.data.time[ndx].total_seconds()
                bg_duration = events.data.duration[ndx].total_seconds()
                tmp_bg_filepath = '../audio/output/tmp/bg_tmp.wav'

                # create pysox transformer for background
                # bg = sox.Transformer(bg_filepath, tmp_bg_filepath)
                bg = sox.Transformer()

                # trim background to user selected duration
                bg.trim(bg_start_time, (bg_start_time + bg_duration))

                # normalize background audio to MAX_DB
                bg.norm(MAX_DB)

                # save trimmed and normalized background
                bg.build(bg_filepath, tmp_bg_filepath)

            if value[0] == 'foreground':

                curr_fg_filepath = value[2]
                curr_fg_start_time = events.data.time[ndx].total_seconds()
                curr_fg_duration = events.data.duration[ndx].total_seconds()
                curr_fg_snr = value[3]

                # FIXME - sox: have to store these intermediate files,
                # at the moment
                tmp_out_file = (
                    '../audio/output/tmp/fg_tmp_' + str(ndx) + '.wav')

                # create pysox transformer for foreground
                # curr_fg = sox.Transformer(curr_fg_filepath, tmp_out_file)
                curr_fg = sox.Transformer()

                # trim foreground from start to end
                # FIX: needs duration checks
                curr_fg.trim(0, curr_fg_duration)

                # apply fade in and out
                curr_fg.fade(fade_in_len=0.1, fade_out_len=0.1)

                # pad with silence according to fg_start_times
                curr_fg.pad(curr_fg_start_time, 0)

                # normalize background audio to MAX_DB
                # FIXME: this is relative to FS ?
                curr_fg.norm(curr_fg_snr)

                # save trimmed and normalized background
                curr_fg.build(curr_fg_filepath, tmp_out_file)

        tmp_audio_path = '../audio/output/tmp'

        files_to_mix = (
            [eachfile for eachfile in os.listdir(tmp_audio_path) if not
                (eachfile.startswith('.'))])
        for ndx, thefile in enumerate(files_to_mix):
            files_to_mix[ndx] = os.path.join(tmp_audio_path, files_to_mix[ndx])

        # create the output file
        mix = sox.Combiner()
        mix.build(files_to_mix, s_file, 'mix')

        print('-----------------------------------')
        print('Soundscape Created:')
        print('Audio files: ', s_file)
        print('From Jams: ', j_file)
