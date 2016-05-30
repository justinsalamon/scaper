

import sox, random, glob, os, warnings, jams
import pandas as pd
import numpy as np

SNR_MAX = 120
MAX_DB = -3
MIN_DURATION = 1

supported_bg_labels = ['car', 'crowd', 'music']
supported_fg_labels = ['horn', 'machinery', 'siren', 'voice']

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
        # self.fg_label = None
        # self.bg_label = None

        files = []
        bit_rates = []
        num_channels = []
        samp_rates = []

        # # rename audio files to exclude space and comma chars
        # self.rename_files(self.fg_path)
        # self.rename_files(self.bg_path)

        self.fgs = pd.DataFrame(columns=['file_name', 'bit_rate', 'num_channels', 'sample_rate'])
        self.bgs = pd.DataFrame(columns=['file_name', 'bit_rate', 'num_channels', 'sample_rate'])


    def generate_jams(self, list, type, jams_outfile):

        # for generating jams files of input and ouput files
        if type == 'file':
            file_jam = jams.JAMS()
            file_ann = jams.Annotation(namespace='tag_open')

            # everything goes into the value field as a tuple
            for ind, event in list.iterrows():
                file_ann.append(time=0, duration=1.0,
                                 value=(list['file_name'], list['bit_rate'],
                                        list['num_channels'], list['sample_rate']),
                                 confidence=1)

            # add annotation to jams file
            file_jam.annotations.append(file_ann)
            # dummy duration
            file_jam.file_metadata.duration = 1
            file_jam.save('./file_out.jams')

            print file_ann.data
            # file_jam.save(jams_outfile)

        # for generating jam files of scene
        elif type == 'scape':
            scene_jam = jams.JAMS()
            scene_ann = jams.Annotation(namespace='tag_open')

            # everything goes into the value field as a tuple
            for ind, event in list.iterrows():
                print list['label'][ind]
                scene_ann.append(time=list['start_time'][ind],
                                 duration=list['end_time'][ind] - list['start_time'][ind],
                                 value=(list['label'][ind], list['src_file'][ind],
                                        list['src_start'][ind], list['src_end'][ind],
                                        list['snr'][ind], list['role'][ind]),
                                 confidence=1)

            # add annotation to jams file
            scene_jam.annotations.append(scene_ann)

            print scene_ann.data


            print '\n'
            scene_jam.file_metadata.duration = (list['end_time'][ind] - list['start_time'][ind])
            # scene_jam.save('./scene_out.jams')



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

        print '\n'
        print 'scape_file: '+scape_file
        print '\n'
        print bg_start_time
        print self.duration

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

            # normalize bg to desired dB to ensure SNR
            fg_gain = MAX_DB - self.snr

            # normalize fg to desired max dB
            fg = self.normalize_file(curr_fg_file, MAX_DB, fg_out_file)

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
        self.generate_jams(events, 'scape', 'scape.jams')

if __name__ == '__main__':


    sc = Scaper('audio/fg','audio/bg')
    sc.set_path('foreground', 'audio/sfg')
    sc.set_path('background', 'audio/bjg')

    fg_labels = ['voice', 'siren', 'horn']
    bg_labels = ['car']

    fg_label_paths = sc.set_label('foreground', fg_labels)
    bg_label_paths = sc.set_label('background', bg_labels)

    print '======'
    print 'return fg_label_paths'
    for each_label in fg_label_paths:
        print each_label

    print '======'
    print 'return bg_label_paths'
    for each_label in bg_label_paths:
        print each_label

    sc.set_snr(20)
    sc.set_duration(30)
    sc.generate_soundscapes(fg_label_paths, bg_label_paths, 'audio/output/this_scape.wav', fg_start=[5,10,15])

    # print sc.fgs