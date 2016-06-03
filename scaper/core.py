

import sox, random, glob, os, warnings, jams
import pandas as pd
import numpy as np

SNR_MAX = 120
MAX_DB = -3
MIN_DURATION = 1

# supported_bg_labels = ['car', 'crowd', 'music']
# supported_fg_labels = ['horn', 'machinery', 'siren', 'voice']


class ScaperSpec(object):

    def __init__(self, bg_label, bg_duration=10):

        print "ScaperSpec Created:"
        print "~~~"


        # no background label provided, chose randomly
        if bg_label == None:
            available_labels = os.listdir(sc.bg_path)
            available_labels = [the_label for the_label in available_labels if not (the_label.startswith("."))]
            self.bg_label = available_labels[(int(round(random.random() * len(available_labels))))]

        # if list not provided
        if type(bg_label) is not list:
            warnings.warn("Warning, Labels should be provided in list format.")
            labels = [bg_label]

        # evaluate background labels
        self.bg_label, self.bg_file  = self.validate_label_paths(sc.bg_path,bg_label,1)
        print "~~~"
        print self.bg_label
        print self.bg_file

        # invalid background element duration, use default.. or random?
        if bg_duration == None or bg_duration <= 0:
            self.bg_duration = 10
            warnings.warn("Warning, scape must have global duration > 0. Setting duration to default: 10 seconds")
        else:
            self.bg_duration = bg_duration

        bg_spec = {"bg_label"       : self.bg_label,
                    "bg_duration"   : self.bg_duration,
                   "bg_source_file"      : self.bg_file}

        self.spec = []
        self.spec.append(bg_spec)

    def validate_label_paths(self, path, labels, num):

        # validate provided labels
        """

        Parameters
        ----------
        path        : foreground or background path where label subdirectories are located
        labels      : the labels, whose corresponding directory paths will be validated

        Returns
        -------
        validated_labels : the labels that have been validated, or assigned in case of failure

        """

        # if a list of labels is passed
        for ndx in range(0, len(labels)):

                # check if label directory exists
                if not (os.path.isdir(os.path.join(path, labels[ndx]))):
                    warnings.warn("Warning, the supplied label does not exist in audio directory. Choosing label randomly")
                    available_labels = os.listdir(path)
                    # just ignores .DS_Store file
                    available_labels = [the_label for the_label in available_labels if not (the_label.startswith("."))]
                    validated_labels[ndx] = available_labels[(int(round(random.random() * len(available_labels))))]
                    # FIX currently this can assign same class.. desired?

                # label exists, check if it contains any audio files
                else:
                    tmp = os.path.join(path, labels[ndx])
                    for filename in os.listdir(tmp):
                        if filename.endswith('.wav'):
                            # an audio file is present, set labels and break
                            validated_labels = labels
                            break
                    else:
                        # no audio files in the provided label directory, chose random label that exists
                        warnings.warn("Warning, no audio files present in label directory " + str(
                            tmp) + " . Choosing new label randomly")
                        available_labels = os.listdir(path)
                        available_labels = [the_label for the_label in available_labels if not (the_label.startswith("."))]
                        validated_labels[ndx] = available_labels[(int(round(random.random() * len(available_labels))))]

                # chose audio file paths for corresponding labels
                filepaths = []
                for n in range(0, num):
                    files = os.listdir(os.path.join(path, validated_labels[ndx]))
                    files = [file for file in files if not (file.startswith("."))]
                    filepaths.append(os.path.join(path, random.choice(files)))
                    # print os.path.join(path, random.choice(os.listdir(os.path.join(path, validated_labels[ndx]))))


        return validated_labels, filepaths


    def add_events(self, labels=None, fg_start_times=None, fg_durations=None, snrs=None, num_events=None):

        """

        Parameters
        ----------
        labels          : foreground event labels
        fg_start_times  : start time of events
        fg_durations    : durations of events
        snrs            : SNR of events
        num_events      : number of this type of event to insert

        """

        # no labels provided, chose randomly
        if labels == None:
            available_labels = os.listdir(sc.fg_path)
            available_labels = [the_label for the_label in available_labels if not(the_label.startswith("."))]
            labels = available_labels[(int(round(random.random() * len(available_labels))))]

        # if list not provided
        if type(labels) is not list:
            warnings.warn("Warning, Labels should be provided in list format.")
            labels = [labels]

        # validate foreground labels
        self.labels, self.filepaths = self.validate_label_paths(sc.fg_path,labels,num_events)


        print "~~~"
        print self.labels
        print self.filepaths

        # invalid foreground element durations, use default.. or random?
        if fg_durations == None or fg_durations <= 0:
            self.fg_durations = [2]
            warnings.warn("Warning, event must have duration > 0. Setting duration to default: 2 seconds")
        else:
            self.fg_durations = fg_durations

        # invalid SNR value, use default... or random?
        if snrs == None or snrs < 0:
            self.snrs = 10
            warnings.warn("Warning, SNR value not provided or out of range. Setting SNR to default: 10 dB")
        else:
            self.snrs = snrs

        if type(self.snrs) is list:
            # extend SNR list if too short
            if len(self.snrs) < num_events:
                for ndx in range(len(self.snrs),num_events):
                    self.snrs.append(self.snrs[num_events%ndx-1])

        # invalid number of events
        if num_events == None or num_events <= 0:
            self.num_events = 1
            warnings.warn("Warning, number of events not provided. Setting number of events to default: 1")

        # multiple events, have to make fg_start_times, fg_durations, snrs into a list
        else:
            self.num_events = num_events

        # invalid start times - generate randomly
        if fg_start_times == None or fg_start_times < 0:
            warnings.warn("Warning, start times not provided, or less than 0. Setting start times randomly.")
            self.fg_start_times = []
            for ndx in range(0, self.num_events):
                self.fg_start_times.append(round(random.random() * (self.bg_duration - self.fg_durations[ndx])))

        # start times passed as list
        elif type(fg_start_times) is list:
            self.fg_start_times = fg_start_times
        # start time passed as int
        elif type(fg_start_times) is int:
            self.fg_start_times = fg_start_times

        # no lists are passed
        if self.num_events > 1 and type(self.fg_durations) is not list:
            tmp = self.fg_durations
            self.fg_durations = [tmp] * self.num_events
        if self.num_events > 1 and type(self.fg_start_times) is not list:
            tmp = self.fg_start_times
            self.fg_start_times = [tmp] * self.num_events
        if self.num_events > 1 and type(self.snrs) is not list:
            tmp = self.snrs
            self.snrs = [tmp] * self.num_events

        # lists passed, but must ensure they are correct length (same as num_events)
        if type(self.fg_durations) is list and (len(self.fg_durations) != self.num_events):
            for ndx in range(len(self.fg_durations), num_events):
                self.fg_durations.append(self.fg_durations[num_events % ndx - 1])  # FIX MOD

        # lists passed, but must ensure they are correct length (same as num_events)
        if type(self.fg_start_times) is list and (len(self.fg_start_times) != self.num_events):
            for ndx in range(len(self.fg_start_times), num_events):
                self.fg_start_times.append(self.fg_start_times[num_events % ndx - 1])  # FIX MOD

        for ndx,each_label in enumerate(self.labels):
            s = {"label"        : each_label,
                "fg_start_time" : self.fg_start_times,
                "fg_duration"   : self.fg_durations,
                "source_files"  : self.filepaths,
                "snr"           : self.snrs,
                "num_events"    : self.num_events}

        # add these events to the spec object
        self.spec.append(s)


    def generate_jams(self, spec):

        # print spec

        scene_jam = jams.JAMS()
        scene_ann = jams.Annotation(namespace='tag_open')

        # everything goes into the value field as a tuple



        print '\n'
        for ndx, event in enumerate(spec):

            # background file
            if "bg_duration" in event:
                print event
                print ":HAS BG DURATION"

                scene_ann.append(time=0.0,
                                 duration=event["bg_duration"],
                                 value=(event["bg_label"]),
                                 confidence=1)
                scene_jam.annotations.append(scene_ann)

                print 'new gen jams'
                print scene_ann.data
                print '\n'

        print '\n'
        #
        # for ind, event in list.iterrows():
        #     print list['label'][ind]
        #     scene_ann.append(time=list['start_time'][ind],
        #                      duration=list['end_time'][ind] - list['start_time'][ind],
        #                      value=(list['label'][ind], list['src_file'][ind],
        #                             list['src_start'][ind], list['src_end'][ind],
        #                             list['snr'][ind], list['role'][ind]),
        #                      confidence=1)

        # add annotation to jams file
        # scene_jam.annotations.append(scene_ann)


        # scene_jam.file_metadata.duration = (list['end_time'][ind] - list['start_time'][ind])
        # scene_jam.save('./scene_out.jams')


class Scaper(object):

    def __init__(self, fg_path, bg_path, num_scapes=1, snr=10, duration=10, fg_start=1, bg_start=1):
        """

        Parameters
        ----------

        fg_path:    path to foreground audio
        bg_path:    path to background soundscape audio
        num_scapes: number of soundscapes to generate
        snr:        signal to noise ratio
        duration:   duration of output file

        """

        # THESE PROBABLY CAN BE None, Specific, Multiple
        self.num_scapes = num_scapes
        self.fg_path = fg_path              # foregrounds
        self.bg_path = bg_path              # backgrounds
        self.duration = duration
        self.fg_start = fg_start
        self.bg_start = bg_start
        self.snr = snr
        self.events = None


        # PATH AND LABELS here

        # # rename audio files to exclude space and comma chars
        # self.rename_files(self.fg_path)
        # self.rename_files(self.bg_path)
        #
        # self.fgs = pd.DataFrame(columns=['file_name', 'bit_rate', 'num_channels', 'sample_rate'])
        # self.bgs = pd.DataFrame(columns=['file_name', 'bit_rate', 'num_channels', 'sample_rate'])
        #

    # def generate_jams(self, list, type, jams_outfile):
    #
    #     # for generating jams files of input and ouput files
    #     if type == 'file':
    #         file_jam = jams.JAMS()
    #         file_ann = jams.Annotation(namespace='tag_open')
    #
    #         # everything goes into the value field as a tuple
    #         for ind, event in list.iterrows():
    #             file_ann.append(time=0, duration=1.0,
    #                              value=(list['file_name'], list['bit_rate'],
    #                                     list['num_channels'], list['sample_rate']),
    #                              confidence=1)
    #
    #         # add annotation to jams file
    #         file_jam.annotations.append(file_ann)
    #         # dummy duration
    #         file_jam.file_metadata.duration = 1
    #         file_jam.save('./file_out.jams')
    #
    #         print file_ann.data
    #         # file_jam.save(jams_outfile)
    #
    #     # for generating jam files of scene
    #     elif type == 'scape':
    #         scene_jam = jams.JAMS()
    #         scene_ann = jams.Annotation(namespace='tag_open')
    #
    #         # everything goes into the value field as a tuple
    #         for ind, event in list.iterrows():
    #             print list['label'][ind]
    #             scene_ann.append(time=list['start_time'][ind],
    #                              duration=list['end_time'][ind] - list['start_time'][ind],
    #                              value=(list['label'][ind], list['src_file'][ind],
    #                                     list['src_start'][ind], list['src_end'][ind],
    #                                     list['snr'][ind], list['role'][ind]),
    #                              confidence=1)
    #
    #         # add annotation to jams file
    #         scene_jam.annotations.append(scene_ann)
    #
    #         print scene_ann.data
    #         print '\n'
    #
    #         scene_jam.file_metadata.duration = (list['end_time'][ind] - list['start_time'][ind])
    #         # scene_jam.save('./scene_out.jams')


    def normalize_file(self, file, max_db, out_file):

        """

        Parameters
        ----------
        file :      file to normalize
        max_db:     normalize reference
        out_file:   file to save normalized output

        """

        nrm = sox.Transformer(file, out_file)
        nrm.norm(max_db)
        return nrm


    def rename_files(self, path):

        """

        Parameters
        ----------
        path: path to files for renaming

        """
        paths = (os.path.join(root, filename)
                 for root, _, filenames in os.walk(path)
                 for filename in filenames)
        for path in paths:
            newpath = path.replace(' ', '-')
            newname = newpath.replace(',', '')
            if newname != path:
                os.rename(path, newname)


    def set_num_scapes(self, num):

        """

        Parameters
        ----------
        num:    number of soundscapes to generate

        """
        if num < 1:
            warnings.warn('Warning, number of scapes to generate must be >= 1. User selected '+str(num)+' scapes, defaulting to 1')
            self.num_scapes = 1
        else:
            self.num_scapes = num


    def set_path(self, mode, new_path):

        """

        Parameters
        ----------
        new_path:   path to foreground audio

        """

        if mode == 'foreground':
            # check if directory exists
            if os.path.isdir(new_path):
                self.fg_path = new_path

            # if dir doesn't exist, use default
            else:
                self.fg_path = 'audio/fg'
                warnings.warn('Warning, foreground path is not a valid directory. Using default directory: audio/fg')

        elif mode == 'background':
            # check if directory exists
            if os.path.isdir(new_path):
                self.bg_path = new_path
            # if dir doesn't exist, use default
            else:
                self.bg_path = 'audio/bg'
                warnings.warn('Warning, background path is not a valid directory. Using default directory: audio/bg')


    def set_duration(self, duration):

        """

        Parameters
        ----------
        duration:   duration of output soundscape

        """

        if duration >= MIN_DURATION:
            self.duration = duration
        else:
            self.duration = 10
            warnings.warn('Warning, duration must be greater than 0. Using default duration: 10 seconds')


    def set_snr(self, snr):

        """

        Parameters
        ----------
        snr:        signal to noise ratio

        """
        if snr >= 0 and snr < SNR_MAX:
            self.snr = snr
        else:
            self.snr = 0
            warnings.warn('Warning, SNR value provided out of range. SNR set to 0 dB.')



    def set_label(self, mode, new_labels):

        # check if new_labels provided
        """

        Parameters
        ----------
        mode:       foreground or background mode
        new_labels: labels

        Returns
        -------

        """
        if len(new_labels) <= 0:
            warnings.warn('Warning, '+str(mode)+' labels not provided.')
            return  # return default label?

        if mode == 'foreground':

            # check if labels are in supported labels list
            for label in new_labels:
                if label not in supported_fg_labels:
                    warnings.warn('Warning, \''+ str(label) +'\' is not a supported '+str(mode)+' label.')
                    return  # return default label?

            # initialize foreground labels array
            # fg_labels = np.empty([len(new_labels),1], dtype="<U30")
            fg_labels = []

            # if passed a list of labels
            if type(new_labels) == list:
                for ndx, each_label in enumerate(new_labels):
                    fg_labels.append(self.fg_path + "/" + each_label)

            # if passed a single label
            elif type(new_labels) == str:
                fg_labels.append(self.fg_path + "/" + new_labels)

            return fg_labels

        elif mode == 'background':

            # check if labels are in supported labels list
            for label in new_labels:
                if label not in supported_bg_labels:
                    warnings.warn('Warning, \''+ str(label) +'\' is not a supported '+str(mode)+' label.')
                    return  # return default label?

            # initialize foreground labels array
            # bg_labels = np.empty([len(new_labels), 1], dtype="<U30")
            bg_labels = []

            # if passed a list of labels
            if type(new_labels) == list:
                for ndx, each_label in enumerate(new_labels):
                    bg_labels.append(self.bg_path + "/" + each_label)

            # if passed a single label
            elif type(new_labels) == str:
                bg_labels.append(self.bg_path + "/" + new_labels)

            return bg_labels


    def set_start_times(self, mode, times):

        """

        Parameters
        ----------
        mode
        times

        """
        if mode == 'foreground':
            self.fg_start = times

        elif mode == 'background':
            self.bg_start = times


    def generate_soundscapes(self, fgs, bgs, outfile, bg_start=None, fg_start=None):

        """

        Parameters
        ----------
        fgs:        foreground files
        bgs:        background files
        outfile:    save soundscape as
        bg_start:   background start times - needed?
        fg_start:   foreground start times

        """
        event_starts = np.array([])
        event_ends = np.array([])
        event_labels = np.array([])
        event_source = np.array([])
        event_source_start = np.array([])
        event_source_end = np.array([])
        event_snr = np.array([])
        event_role = np.array([])

        events = pd.DataFrame(columns=['start_time', 'end_time', 'label', 'src_file', 'src_start', 'src_end', 'snr', 'role'])

        # determine number of foreground elements to include
        if fg_start ==  None:
            num_events = 1
        elif type(fg_start) == int:
            num_events = 1
        else:
            num_events = len(fg_start)

        # choose background file for this soundscape
        # FIX: just uses fierst one if list passed.. random ?
        curr_bg_file = bgs[0] + '/' + random.choice([file for file in os.listdir(bgs[0]) if
                                      not file.startswith('.') and os.path.isfile(os.path.join(bgs[0], file))])

        print '\nbackground audio file chosen: ' + str(curr_bg_file) +'\n'

        # no background start time provided, chose randomly
        if bg_start == None:

            # duration > file length
            # set duration to length of file, and start to 0 - FIX: should this just use a different bg file?
            if self.duration > sox.file_info.duration(curr_bg_file):
                self.duration = sox.file_info.duration(curr_bg_file)
                bg_start_time = 0
                warnings.warn('Warning, provided duration exceeds length of background file. Duration set to ' +
                              str(sox.file_info.duration(curr_bg_file)))

            # use random start time within range
            else:
                print 'random bg start'
                bg_start_time = random.random() * (sox.file_info.duration(curr_bg_file) - self.duration)

        # background start time provided
        else:
            if type(bg_start) is list:
                # FIX -- this uses random bg files when list is passed
                randx = int(round(random.random()*len(bg_start)-1))
                bg_start_time = bg_start[randx]
            elif type(bg_start) is int:
                bg_start_time = bg_start

            if bg_start_time + self.duration > sox.file_info.duration(curr_bg_file):

                bg_start_time = sox.file_info.duration(curr_bg_file) - self.duration
                # if start time is now negative, set it to 0 and use duration as length of file
                if bg_start_time < 0:
                    bg_start_time = 0
                    duration = sox.file_info.duration(curr_bg_file)
                warnings.warn(
                    'Warning, provided start time and duration exceeds length of background file. Start time set to ' +
                    str(bg_start_time) + '. Durration set to ' + str(duration))

        scape_file = outfile[:-4] + '.wav'
        scape_file_out = outfile + str(0) + '.wav'

        # create pysox transformer for background
        bg = sox.Transformer(curr_bg_file, scape_file_out)

        # trim background to user selected duration
        bg.trim(bg_start_time, bg_start_time + self.duration)

        # normalize background audio to MAX_DB
        bg.norm(MAX_DB)

        # save trimmed and normalized background
        bg.build()

        for n in range(0, num_events):

            # choose foreground file for this soundscape
            curr_fg_file = fgs[n] + '/' + random.choice([file for file in os.listdir(fgs[n]) if
                                           not file.startswith('.') and os.path.isfile(os.path.join(fgs[n], file))])
            print '\nforeground audio file chosen: ' + str(curr_fg_file) + '\n'

            # no foreground start times provided, chose randomly
            if fg_start == None:
                fg_start_time = round(random.random() * (self.duration - sox.file_info.duration(curr_fg_file)))
            else:
                # choose start times from list provided -- FIX: currently picks according to loop
                if type(fg_start) is list:
                    print 'fg list'
                    fg_start_time = fg_start[n]
                # use single start time provided
                elif type(fg_start) is int:
                    fg_start_time = fg_start

            # keep track of event entries
            event_starts = np.append(event_starts, fg_start_time)
            event_ends = np.append(event_ends, (fg_start_time + sox.file_info.duration(curr_fg_file)))
            event_labels = np.append(event_labels, fgs[n])
            event_source = np.append(event_source, curr_fg_file)
            event_source_start = np.append(event_source_start, bg_start_time)
            event_source_end = np.append(event_source_end, sox.file_info.duration(curr_fg_file))
            event_snr = np.append(event_snr, self.snr)
            event_role = np.append(event_role, 'event')

            # output file names for temp storage of normalized files
            # tmp = 10 + len(self.fg_label)
            fg_out_file = curr_fg_file[:-4] + '_norm_out.wav'

            # normalize fg to desired max dB
            # this backwards
            fg_gain = MAX_DB - self.snr
            fg = self.normalize_file(curr_fg_file, fg_gain, fg_out_file)

            # pad to foreground start time
            fg.pad(fg_start_time,0)

            # # have to expicitly write these?
            fg.build()

            # combine the foreground and background files
            last_scape_file = outfile+str(n)+'.wav'
            scape_file_out = outfile+str(n+1)+'.wav'
            scape_out = sox.Combiner([fg_out_file, last_scape_file], scape_file_out, 'mix')
            print '-----------'
            print fg_out_file
            print scape_file_out
            print '-----------'
            scape_out.build()

            # MAYBE THIS CAN ALL BE DONE WITH COMBINER?
            # scape2_out = sox.Combiner([curr_fg_file, curr_bg_file], 'audio/output/mixed_just_comb.wav', 'mix',[-3,-13])
            # scape2_out.build()

        # foreground events
        print event_starts
        events['start_time'] = event_starts
        events['end_time'] = event_ends
        events['label'] = event_labels
        events['src_file'] = event_source
        events['src_start'] = event_source_start
        events['src_end'] = event_source_end
        events['snr'] = event_snr
        events['role'] = event_role

        print events

        # background
        events.loc[len(events)] = [0, self.duration, bgs[0], curr_bg_file, bg_start_time, bg_start_time + self.duration, 0, 'background']

        # generate jams file
        # self.generate_jams(events, 'scape', 'scape.jams')


if __name__ == '__main__':


    sc = Scaper('audio/fg','audio/bg')

    # init spec with background label and duration
    sp = ScaperSpec(['crowd'],10)

    # add foreground events
    # add_to_spec(labels, fg_start_times, fg_durations, snrs, num_events)
    sp.add_events(['horn'],1,None, None, 2)
    sp.add_events(['voice'], 3, [1, 2], [11, 20], 2)
    sp.add_events(['machinery'], [3,1], [6, 2], [61, 20], 7)

    print "\n"
    for entry in sp.spec:
        print entry
    print "\n"

    sp.generate_jams(sp.spec)


    # sc.generate_soundscapes(fg_label_paths, bg_label_paths, 'audio/output/this_scape.wav', fg_start=[5,10,15])
