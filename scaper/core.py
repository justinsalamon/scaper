
class Scaper(object):

    def __init__(self,  fpath1, fpath2, snr=10):
        """

        Parameters
        ----------
        fpath1:     path to foreground audio
        fpath2:     path to background soundscape audio
        snr:        signal to noie ratio
        """

        self.fpath1 = fpath1          # foreground
        self.fpath2 = fpath2
        self.snr = snr

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

    def generate_soundscape(self):
        print self.fpath1
        print self.fpath2
        print self.snr




sc = Scaper('./1.txt','./2.txt', 40)
sc.set_fg_path('./3.txt')
sc.generate_soundscape(10)