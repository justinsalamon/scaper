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

        s1 = core.ScaperSpec(labels=['crowd'], duration=12, scape=sc)
        s2 = core.ScaperSpec(sc, ['crowd'], 12)
        self.assertEqual(s1.bg_label, s2.bg_label)
        self.assertEqual(s1.bg_duration, s2.bg_duration)
        self.assertEqual(s1.bg_file, s2.bg_file)

        self.assertIsInstance(s1, core.ScaperSpec, "Not an instance")
        self.assertIsInstance(s2, core.ScaperSpec, "Not an instance")

        self.assertRaises(Exception)


    def test_add_events_args(self):

        sc = core.Scaper()
        sp1 = core.ScaperSpec(sc)
        sp2 = core.ScaperSpec(sc)
        # sp.add_events()

        sp1.add_events(['horn','voice'], [1, 2], [2, 2], None, 2)
        sp2.add_events(labels=['horn','voice'], fg_start_times=[1,2], fg_durations=[2,2], snrs=None, num_events=2)

        self.assertEqual(sp1.labels, sp2.labels)
        self.assertEqual(sp1.fg_durations, sp2.fg_durations)
        self.assertEqual(sp1.snrs, sp2.snrs)
        self.assertEqual(sp1.num_events, sp2.num_events)
        self.assertEqual(sp1.fg_start_times, sp2.fg_start_times)

        self.assertIsInstance(sp1, core.ScaperSpec, "Not an instance")
        self.assertIsInstance(sp2, core.ScaperSpec, "Not an instance")

        # sp.add_events(['voice'], [3,4,5], [1,2,3], None, 2)

        # sp.add_events(['crowd','voice'])


        # def testTwo(self):
    #     self.failIf(IsOdd(2))

def main():
    unittest.main()

if __name__ == '__main__':
    main()
