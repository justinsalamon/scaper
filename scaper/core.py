

import sox, random, glob, os, warnings, jams
import pandas as pd
import numpy as np

SNR_MAX = 120
MAX_DB = -3
MIN_DURATION = 1

class ScaperSpec(object):

    def __init__(self, *args, **kwargs):

        # argument checks
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
            if key == "labels":
                bg_label = val
            elif key == "duration":
                bg_duration = val
            elif key == "scape":
                sc = val

        print '~~~'
        print 'ScaperSpec Created:'

        # this is the spec
        self.spec = []
        self.sc = sc

        available_labels = os.listdir(sc.bg_path)
        available_labels = [the_label for the_label in available_labels if not (the_label.startswith('.'))]

        # no background label provided, chose randomly
        if bg_label == None:
            bg_label = available_labels[(int(round(random.random() * (len(available_labels)-1))))]

        # if list not provided
        if type(bg_label) is not list:
            self.bg_label = [bg_label]

        # list provided
        else:
            # specific path provided
            if len(bg_label) == 1:
                if os.path.exists(bg_label[0]):
                    print "not yet implemented! fix"

                # FIX

            # list of labels provided
            else:
                bg_label = bg_label[(int(round(random.random() * (len(bg_label) - 1))))]

        self.bg_label, self.bg_file = self.validate_label_paths(sc.bg_path, bg_label, 1)

        # invalid background element duration
        if bg_duration == None or bg_duration <= 0 or not isinstance(bg_duration, int):
            self.bg_duration = 10
            warnings.warn('Warning, scape must have global duration > 0. Setting duration to default: 10 seconds')
        else:
            self.bg_duration = bg_duration

        bg_spec = {'bg_label'       : self.bg_label,
                   'bg_duration'    : self.bg_duration,
                   'bg_source_file' : self.bg_file}

        # append to spec
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

        validated_labels = [None] * len(labels)

        available_labels = os.listdir(path)
        available_labels = [the_label for the_label in available_labels if not (the_label.startswith('.'))]

        # if a list of labels is passed
        for ndx in range(0, len(labels)):

            # check if label directory exists
            if not (os.path.isdir(os.path.join(path, labels[ndx]))):
                warnings.warn('Warning, the supplied label does not exist in audio directory. Choosing label randomly')
                validated_labels[ndx] = available_labels[(int(round(random.random() * (len(available_labels)-1))))]
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
                    warnings.warn('Warning, no audio files present in label directory ' + str(tmp) + ' . Choosing new label randomly')
                    validated_labels[ndx] = available_labels[(int(round(random.random() * (len(available_labels) - 1))))]

            # chose audio file paths for corresponding labels

            files = os.listdir(os.path.join(path, validated_labels[ndx]))
            filepaths = [file for file in files if not (file.startswith('.'))]

            for n, each_label in enumerate(validated_labels):
                # print os.path.join(path, validated_labels[ndx])
                this_path = os.path.join(path, validated_labels[ndx])
                for n, each_file in enumerate(filepaths):
                    filepaths[n] = os.path.join(this_path, each_file)

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
            available_labels = os.listdir(self.sc.fg_path)
            available_labels = [the_label for the_label in available_labels if not(the_label.startswith('.'))]
            labels = available_labels[(int(round(random.random() * (len(available_labels)-1))))]

        # if list not provided
        if type(labels) is not list:
            warnings.warn('Warning, Labels should be provided in list format.')
            labels = [labels]

        # validate foreground labels
        self.labels, self.filepaths = self.validate_label_paths(self.sc.fg_path,labels,num_events)

        # invalid number of events
        if num_events == None or num_events <= 0:
            self.num_events = 1
            warnings.warn('Warning, number of events not provided. Setting number of events to default: 1')
        # multiple events, have to make fg_start_times, fg_durations, snrs into a list
        else:
            self.num_events = num_events


        # invalid foreground element durations, use random
        if fg_durations == None or fg_durations <= 0:
            # random value between 1 and (bg_duration/2)+1
            tmp = round(random.random() * (self.bg_duration / 2) + 1)
            self.fg_durations = [tmp] * self.num_events
            warnings.warn('Warning, event must have duration > 0. Setting duration to default: 2 seconds')
        else:
            self.fg_durations = fg_durations
        # more durations provided than events
        if (len(self.fg_durations) > self.num_events):
            self.fg_durations = self.fg_durations[0:self.num_events]
            warnings.warn('Warning, more event durations provided than events. Using the following durations: ' + str(self.fg_durations))


        # FIX invalid SNR value, use default... or random?
        if snrs == None or snrs < 0:
            self.snrs = 10
            warnings.warn('Warning, SNR value not provided or out of range. Setting SNR to default: 10 dB')
        else:
            self.snrs = snrs

        if type(self.snrs) is list:
            # extend SNR list if too short
            if len(self.snrs) < num_events:
                for ndx in range(len(self.snrs),num_events):
                    self.snrs.append(self.snrs[num_events%ndx-1])

        # invalid start times - generate randomly
        if fg_start_times == None or fg_start_times < 0:
            warnings.warn('Warning, start times not provided, or less than 0. Setting start times randomly.')
            self.fg_start_times = []
            for ndx in range(0, self.num_events):
                self.fg_start_times.append(round(random.random() * (self.bg_duration - self.fg_durations[(ndx % self.num_events)- 1])))
        # multiple events
        else:
            self.fg_start_times = fg_start_times
            # more durations provided than events
        if (len(self.fg_start_times) > self.num_events):
            self.fg_start_times = self.fg_start_times[0:self.num_events]
            warnings.warn('Warning, more event start times provided than events. Using the following start times: ' + str(self.fg_start_times))

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
                self.fg_durations.append(self.fg_durations[(ndx % self.num_events)- 1])  # FIX MOD

        # lists passed, but must ensure they are correct length (same as num_events)
        if type(self.fg_start_times) is list and (len(self.fg_start_times) != self.num_events):
            for ndx in range(len(self.fg_start_times), num_events):
                self.fg_start_times.append(self.fg_start_times[(ndx % self.num_events)- 1])  # FIX MOD

        # event duration value checks
        for ndx, each_time in enumerate(self.fg_start_times):
            if (each_time + self.fg_durations[ndx] > self.bg_duration):
                self.fg_durations[ndx] = (self.bg_duration - self.fg_start_times[ndx])
                warnings.warn('Warning, event durations exceed background duration for provided start times. '
                              'Event duration trunctated to ' + str(self.fg_durations[ndx]) + ' seconds.')

        print "\n"
        print "-----------------------------------"


        chosen_files = []
        for ndx, this_durr in enumerate(self.fg_durations):

            # duration and start time larger than file duration
            if (this_durr + self.fg_start_times[ndx]) > sox.file_info.duration(self.filepaths[ndx]):

                for each_file in self.filepaths:
                    if sox.file_info.duration(each_file) >= (this_durr + self.fg_start_times[ndx]):

                        warnings.warn("Warning, the file \""+ str(self.filepaths[ndx]) + "\" is shorter than the "
                                        "provided start time and duration. Using \"" + str(each_file) + "\" instead.")
                        chosen_files.append(each_file)
                        break

            # duration and start time are ok, add this filepath
            elif (this_durr + self.fg_start_times[ndx]) <= sox.file_info.duration(self.filepaths[ndx]):
                chosen_files.append(self.filepaths[ndx])

        # set the filepaths member to be the updated list of chosen files
        self.filepaths = chosen_files

        print "\n"
        print "Add Events:"

        print "-----------------------------------"
        for eachfile in chosen_files:
            print eachfile
        print "-----------------------------------"

        for ndx,each_label in enumerate(self.labels):
            s = {'label'        : each_label,
                'fg_start_time' : self.fg_start_times,
                'fg_duration'   : self.fg_durations,
                'source_files'  : self.filepaths,
                'snr'           : self.snrs,
                'num_events'    : self.num_events}

        # add these events to the spec object
        self.spec.append(s)

    def generate_jams(self, spec, outfile):

        jams.schema.add_namespace('namespaces/event.json')
        scene_jam = jams.JAMS()
        scene_ann = jams.Annotation(namespace='event')

        # everything goes into the value field as a tuple
        for ndx, events in enumerate(spec):

            # background file
            if 'bg_duration' in events:
                # add background annotation
                scene_ann.append(value=(['background', events['bg_label'][0],
                                        events['bg_source_file'][0]]
                                        ),
                                 time=0.0,
                                 duration=events['bg_duration'],
                                 confidence=1)

                # every jam must have a duration
                scene_jam.file_metadata.duration = events['bg_duration']

            elif 'fg_duration' in events:
                # append annotation for each event
                for n in range(0,events['num_events']):
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

        return scene_jam


class Scaper(object):

    def __init__(self, *args, **kwargs):

        print '~~~'
        print 'Scaper Created:'

        # argument checks
        if len(args) == 0:
            warnings.warn('Warning, no audio paths provided. Using default directories: audio/fg     audio/bg')
            fpath = 'audio/fg'
            bpath = 'audio/bg'
        elif len(args) == 1:
            warnings.warn('Warning, no background path provided. Using default directory: audio/bg ')
            fpath = args[0]
            bpath = 'audio/bg'
        else:
            fpath = args[0]
            bpath = args[1]

        # if args are key value pairs
        for key, val in kwargs.iteritems():
            if key == "fpath":
                fpath = val
            elif key == "bpath":
                bpath = val

        # filepath checks
        if not (os.path.isdir(fpath)):
            warnings.warn('Warning, foreground path not valid. Using default directory: audio/fg ')
            self.fg_path = 'audio/fg'
        else:
            self.fg_path = fpath

        if not (os.path.isdir(bpath)):
            warnings.warn('Warning, background path not valid. Using default directory: audio/bg ')
            self.bg_path = 'audio/bg'
        else:
            self.bg_path = bpath



    def generate_soundscapes(self, j_file=None, s_file=None):

        # check jams file
        if j_file == None or not os.path.isfile(j_file):
            warnings.warn("Warning, no jams file, or invalid jams file provided. Generate_soundscapes() process terminated.")
            return

        # check output scaper file
        if os.path.exists(s_file):
            warnings.warn("Warning, output file " +str(s_file)+ " already exists. Continuing will overwrite.")

            while True:
                response = raw_input("Proceed: y/n?")
                if response == "y":
                    warnings.warn("Overwriting file " + str(s_file))
                    break
                if response == "n":
                    warnings.warn("File " +str(s_file)+ " will not be overwritten. Generate_soundscapes() process terminated.")
                    return
                warnings.warn("Warning, invalid response. Please select \"y\" or \"no\" :")

        elif os.access(os.path.dirname(s_file), os.W_OK):
            print "Output file " + str(s_file)+ "selected."
        else:
            warnings.warn("Warning, provided scaper output file is invalid. Generate_soundscapes() process terminated.")
            return


        # load jams file, extract elements
        jam = jams.load(j_file)
        events = jam.search(namespace='event')[0]

        # print events
        print "\n"
        for ndx, value in enumerate(events.data.value):

            if value[0] == 'background':

                bg_filepath = value[2]
                bg_start_time = events.data.time[ndx].total_seconds()
                bg_duration = events.data.duration[ndx].total_seconds()

                tmp_bg_filepath = 'audio/output/tmp/bg_tmp.wav'
                # create pysox transformer for background
                bg = sox.Transformer(bg_filepath, tmp_bg_filepath)

                # trim background to user selected duration
                bg.trim(bg_start_time, (bg_start_time + bg_duration))

                # normalize background audio to MAX_DB
                bg.norm(MAX_DB)

                # save trimmed and normalized background
                bg.build()

            if value[0] == 'foreground':

                print "\n"

                curr_fg_filepath = value[2]
                curr_fg_start_time = events.data.time[ndx].total_seconds()
                curr_fg_duration = events.data.duration[ndx].total_seconds()
                curr_fg_snr = value[3]

                # print curr_fg_filepath
                # print curr_fg_start_time
                # print curr_fg_duration
                # print sox.file_info.duration(curr_fg_filepath)
                # # print curr_fg_snr

                # FIX: PYSOX: have to store these intermediate files, at the moment
                tmp_out_file = 'audio/output/tmp/fg_tmp_' + str(ndx) + '.wav'

                # create pysox transformer for foreground
                curr_fg = sox.Transformer(curr_fg_filepath, tmp_out_file)

                # trim foreground from start_time to start_time + duration
                curr_fg.trim(curr_fg_start_time, (curr_fg_start_time + curr_fg_duration))

                # normalize background audio to MAX_DB
                curr_fg.norm(curr_fg_snr)

                # save trimmed and normalized background
                curr_fg.build()

        print "\n"

        tmp_audio_path = 'audio/output/tmp'

        files_to_mix =  [file for file in os.listdir(tmp_audio_path) if not (file.startswith('.'))]
        for ndx,file in enumerate(files_to_mix):
            files_to_mix[ndx] = os.path.join(tmp_audio_path, files_to_mix[ndx])

        print files_to_mix

        mix = sox.Combiner(files_to_mix, s_file, 'mix')

        # create the output file
        mix.build()

#
# if __name__ == '__main__':
#
#     # init scaper
#     sc = Scaper('audio/fg','audio/bg')
#
#     # init spec with background label and duration
#     # sp = ScaperSpec(sc,['audio/bg/music/14-indian-stredet-music.wav'],10)
#     sp = ScaperSpec(sc)
#
#     # add foreground events
#     sp.add_events(['horn'],[1,2] ,[2,2], None, 2)
#     sp.add_events(['voice'], [3,4,5], [1,2,3], None, 2)
#
#     jams_outfile = './output_jams.jams'
#     returned_jams = sp.generate_jams(sp.spec, jams_outfile)
#
#     print "======================="
#     sc.generate_soundscapes(jams_outfile, './audio/output/output_audio.wav')
