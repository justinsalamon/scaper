

import sox, random, glob, os, warnings, jams
import pandas as pd
import numpy as np

SNR_MAX = 120
MAX_DB = -3
MIN_DURATION = 1

class ScaperSpec(object):

    def __init__(self, bg_label, bg_duration=10):

        print '~~~'
        print 'ScaperSpec Created:'

        # this is the spec
        self.spec = []

        # no background label provided, chose randomly
        if bg_label == None:
            available_labels = os.listdir(sc.bg_path)
            available_labels = [the_label for the_label in available_labels if not (the_label.startswith('.'))]
            self.bg_label = available_labels[(int(round(random.random() * len(available_labels))))]

        # if list not provided
        if type(bg_label) is not list:
            warnings.warn('Warning, Labels should be provided in list format.')
            labels = [bg_label]

        # validate background labels
        # FIX: change name..
        self.bg_label, self.bg_file  = self.validate_label_paths(sc.bg_path,bg_label,1)
        print '~~~'
        print self.bg_label
        print self.bg_file

        # invalid background element duration, use default.. or random?
        if bg_duration == None or bg_duration <= 0:
            self.bg_duration = 10
            warnings.warn('Warning, scape must have global duration > 0. Setting duration to default: 10 seconds')
        else:
            self.bg_duration = bg_duration

        bg_spec = {'bg_label'       : self.bg_label,
                   'bg_duration'    : self.bg_duration,
                   'bg_source_file' : self.bg_file}

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
                    warnings.warn('Warning, the supplied label does not exist in audio directory. Choosing label randomly')
                    available_labels = os.listdir(path)
                    # just ignores .DS_Store file
                    available_labels = [the_label for the_label in available_labels if not (the_label.startswith('.'))]
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
                        warnings.warn('Warning, no audio files present in label directory ' +
                                      str(tmp) + ' . Choosing new label randomly')
                        available_labels = os.listdir(path)
                        available_labels = [the_label for the_label in available_labels if not (the_label.startswith('.'))]
                        validated_labels[ndx] = available_labels[(int(round(random.random() * len(available_labels))))]

                # chose audio file paths for corresponding labels
                filepaths = []
                for n in range(0, num):
                    files = os.listdir(os.path.join(path, validated_labels[ndx]))
                    files = [file for file in files if not (file.startswith('.'))]
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
            available_labels = [the_label for the_label in available_labels if not(the_label.startswith('.'))]
            labels = available_labels[(int(round(random.random() * len(available_labels))))]

        # if list not provided
        if type(labels) is not list:
            warnings.warn('Warning, Labels should be provided in list format.')
            labels = [labels]

        # validate foreground labels
        self.labels, self.filepaths = self.validate_label_paths(sc.fg_path,labels,num_events)

        print '~~~'
        print self.labels
        print self.filepaths

        # invalid number of events
        if num_events == None or num_events <= 0:
            self.num_events = 1
            warnings.warn('Warning, number of events not provided. Setting number of events to default: 1')
        # multiple events, have to make fg_start_times, fg_durations, snrs into a list
        else:
            self.num_events = num_events

        # FIX invalid foreground element durations, use default.. or random?
        if fg_durations == None or fg_durations <= 0:
            # currently sets durations to rnadom value between 1 and (bg_duration/2)+1
            tmp = round(random.random() * (self.bg_duration / 2) + 1)
            self.fg_durations = [tmp] * self.num_events
            warnings.warn('Warning, event must have duration > 0. Setting duration to default: 2 seconds')
        else:
            self.fg_durations = fg_durations

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

        # event duration value checks
        for ndx, each_time in enumerate(self.fg_start_times):
            if (each_time + self.fg_durations[ndx] > self.bg_duration):
                self.fg_durations[ndx] = (self.bg_duration - self.fg_start_times[ndx])
                warnings.warn('Warning, event durations exceed background duration for provided start times. '
                              'Event duration trunctated to ' + str(self.fg_durations[ndx]) + ' seconds.')

        for ndx,each_label in enumerate(self.labels):
            s = {'label'        : each_label,
                'fg_start_time' : self.fg_start_times,
                'fg_duration'   : self.fg_durations,
                'source_files'  : self.filepaths,
                'snr'           : self.snrs,
                'num_events'    : self.num_events}

        # add these events to the spec object
        self.spec.append(s)
        print '~~~'

    def generate_jams(self, spec, outfile):

        jams.schema.add_namespace('namespaces/event.json')
        scene_jam = jams.JAMS()
        scene_ann = jams.Annotation(namespace='event')

        # everything goes into the value field as a tuple
        for ndx, events in enumerate(spec):

            # background file
            if 'bg_duration' in events:
                # add background annotation
                scene_ann.append(value=(['background', events['bg_label'][ndx],
                                        events['bg_source_file']]
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
                                             events['fg_start_time'][n],
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

    def __init__(self, fpath, bpath):

        # check if background/foreground directories exist
        if not (os.path.isdir(fpath)):
            warnings.warn('Warning, foreground path not valid. Using default directory audio/fg ')
            self.fg_path = 'audio/fg'
        else:
            self.fg_path = fpath

        if not (os.path.isdir(bpath)):
            warnings.warn('Warning, background path not valid. Using default directory audio/bg ')
            self.bg_path = 'audio/bg'
        else:
            self.bg_path = bpath


    def generate_soundscapes(self, jams=None):

        # print jams
        print "ding dong"



if __name__ == '__main__':

    sc = Scaper('audio/fg','audio/bg')

    # init spec with background label and duration
    sp = ScaperSpec(['crowd'],10)

    # add foreground events
    # add_to_spec(labels, fg_start_times, fg_durations, snrs, num_events)
    sp.add_events(['horn'],None ,None, None, 3)
    sp.add_events(['voice'], None, [7,1], None, 2)
    # sp.add_events(['machinery'], [8,9,10,18], [1,1], [61,20], 4)

    jams_outfile = './output_jams.jams'
    returned_jams = sp.generate_jams(sp.spec, jams_outfile)

    sc.generate_soundscapes(returned_jams)
    # print returned_jams



    # sc.generate_soundscapes(fg_label_paths, bg_label_paths, 'audio/output/this_scape.wav', fg_start=[5,10,15])
