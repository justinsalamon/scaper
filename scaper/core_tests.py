import unittest
import core


class Scaper_Tests(unittest.TestCase):

    def test_Scaper_args(self):

        # fgpath, bgpath
        self.failUnless(core.Scaper())
        self.failUnless(core.Scaper('audio/fg'))
        self.failUnless(core.Scaper(bpath='audio/bg', fpath='audio/fg'))

    def test_ScaperSpec_args(self):

        sc = core.Scaper()

        # scape, label, duration
        self.failUnless(core.ScaperSpec(sc))
        self.failUnless(core.ScaperSpec(sc, 'music', -2))
        self.failUnless(core.ScaperSpec(sc, ['music', 'crowd'], 8))
        self.failUnless(core.ScaperSpec(scape=sc, labels=['crowd'], duration=12 ))

    def test_add_events_args(self):

        sc = core.Scaper()
        sp = core.ScaperSpec(sc)
        sp.add_events()

        sp.add_events(['horn'], [1, 2], [2, 2], None, 2)
        sp.add_events(['voice'], [3,4,5], [1,2,3], None, 2)


        # def testTwo(self):
    #     self.failIf(IsOdd(2))

def main():
    unittest.main()

if __name__ == '__main__':
    main()

    # jams_outfile = './output_jams.jams'
    # returned_jams = sp.generate_jams(sp.spec, jams_outfile)
    #
    # print "======================="
    # sc.generate_soundscapes(jams_outfile, './audio/output/output_audio.wav')
