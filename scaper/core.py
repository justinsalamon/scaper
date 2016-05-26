

import sox, glob, os, jams

class Scaper(object):

    def __init__(self, fg_path, bg_path, fg_class, bg_class, num_scapes=1, snr=10, duration=10):
        """

        Parameters
        ----------

        fg_path:    path to foreground audio
        bg_path:    path to background soundscape audio
        fg_class:   background class
        fg_class:   foreground class
        num_scapes: number of soundscapes to generate
        snr:        signal to noise ratio
        duration:   duration of output file

        """

        self.MAX_DB = -3

        self.bg_class = bg_class
        self.fg_class = fg_class

        self.duration = duration
        self.num_scapes = num_scapes
        self.fg_path = fg_path            # foregrounds
        self.bg_path = bg_path            # backgrounds
        self.snr = snr

        jam = jams.JAMS()
        self.fgs = {}                        # init dicts
        self.bgs = {}

        # rename audio files to exclude space and comma chars
        self.rename_files(self.fg_path)
        self.rename_files(self.bg_path)

        # create dictionary file lists
        # FIX: only file and bitrate stored in dictionaries
        for file in glob.glob(self.fg_path+"/"+fg_class+"/*"):
            self.fgs[file] = sox.file_info.bitrate(file)
        for file in glob.glob(self.bg_path+"/"+bg_class+"/*"):
            self.bgs[file] = sox.file_info.bitrate(file)

    def normalize_file(self, file, max_db, out_file):

        """

        Parameters
        ----------
        file :  object
        max_db: normalize reference

        """

        # tmp = 10 + len(the_class)
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

    def set_fg_path(self, new_path):
        """

        Parameters
        ----------
        new_path:   path to foreground audio
        """

        self.fpath1 = new_path

    def set_bg_path(self, new_path):
        """

        Parameters
        ----------
        new_path:   path background soundscape audio
        """
        self.fpath2 = new_path

    def set_snr(self, snr):
        """

        Parameters
        ----------
        snr:        signal to noise ratio
        """
        self.snr = snr

    def generate_soundscapes(self, fgs, bgs):


        # be in generate_soundscape()?
        for n in range(0, self.num_scapes):

            print n
            curr_fg_file = fgs.keys()[n]
            curr_bg_file = bgs.keys()[n]

            scp = sox.Transformer(curr_bg_file, './audio/output/temp1.wav')

            # trim bg to user selected duration
            scp.trim(0, self.duration)
            scp.build()

            # output file names for temp storage of normalized files
            tmp = 10 + len(self.fg_class)
            fg_out_file = 'audio/output/' + curr_fg_file[tmp:-4] + '_norm_out.wav'
            tmp = 10 + len(self.bg_class)
            bg_out_file = 'audio/output/' + curr_bg_file[tmp:-4] + '_norm_out.wav'

            # normalize fg to desired max dB
            self.fg = self.normalize_file(curr_fg_file, self.MAX_DB, fg_out_file)

            # normalize bg to desired dB to ensure SNR
            bg_gain = self.MAX_DB - self.snr
            self.bg = self.normalize_file(curr_bg_file, bg_gain, bg_out_file)

            # have to expicitly write these?
            self.fg.build()
            self.bg.build()

            scape_out = sox.Combiner([fg_out_file, bg_out_file], 'audio/output/mixed_with_norm.wav', 'mix')
            scape_out.build()

            # MAYBE THIS CAN ALL BE DONE WITH COMBINER?
            # scape2_out = sox.Combiner([curr_fg_file, curr_bg_file], 'audio/output/mixed_just_comb.wav', 'mix',[-3,-13])
            # scape2_out.build()






sc = Scaper('audio/fg','audio/bg', 'machinery', 'street', 2, 20, 10)
sc.generate_soundscapes(sc.fgs, sc.bgs)
