import sox
import random
import os
import warnings
import jams
import glob

SNR_MAX = 120
MAX_DB = -31
MIN_DURATION = 1


# overload my warnings
def _warning(
    message,
    category=UserWarning,
    filename='',
    lineno=-1): print(message)
warnings.showwarning = _warning


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

    def __init__(self, fg_path=None, bg_path=None):

        '''
        Parameters
        ----------
        :param fg_path: str
            Path to folder containing foreground sounds
        :param bg_path: str
            Path to folder containing background sounds
        '''

        # print('-----------------------------------')
        # print('Scaper Created:')
        # print('fg path: ', fg_path)
        # print('bg path: ', bg_path)

        # file path checks
        # if not (os.path.isdir(fg_path)):
        #     warnings.warn('Warning, foreground path not valid. Using default '
        #                   'directory: ../audio/fg ')
        #     self.fg_path = '../audio/fg'
        # else:
        #     self.fg_path = fg_path
        #
        # if not (os.path.isdir(bg_path)):
        #     warnings.warn('Warning, background path not valid. Using default '
        #                   'directory: ../audio/bg ')
        #     self.bg_path = '../audio/bg'
        # else:
        #     self.bg_path = bg_path

        # Validate folder paths
        if fg_path is not None and not os.path.isdir(fg_path):
            warnings.warn(
                'fg_path "{:s}" does not point to a valid '
                'folder'.format(fg_path))
        if bg_path is not None and not os.path.isdir(bg_path):
            warnings.warn(
                'bg_path "{:s}" does not point to a valid '
                'folder'.format(bg_path))

        self.fg_path = fg_path
        self.bg_path = bg_path

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
