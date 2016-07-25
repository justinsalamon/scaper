import pytest
import core


def test_Scaper_args():

    sc = core.Scaper()
    assert sc.bg_path == 'audio/bg'
    assert sc.fg_path == 'audio/fg'

    sc = core.Scaper(bg_path='audio/bsg', fg_path='audio/fg')
    assert sc.bg_path == 'audio/bg'
    assert sc.fg_path == 'audio/fg'

    sc = core.Scaper( fg_path='audio/fg', bg_path='audio/bg')
    assert sc.bg_path == 'audio/bg'
    assert sc.fg_path == 'audio/fg'

    # foreground comes first when not named
    sc = core.Scaper('audio/fg','audio/bg')
    assert sc.bg_path == 'audio/bg'
    assert sc.fg_path == 'audio/fg'


def test_ScaperSpec_args():

    sc = core.Scaper()
    sp = core.ScaperSpec(sc, bg_label=['music'], bg_duration = 9)
    assert sp.bg_label == ['music']
    assert sp.bg_duration == 9

    sp = core.ScaperSpec(scape=None, bg_label=None, bg_duration=None)
    assert sp.sc != None
    assert sp.bg_label != None
    assert sp.bg_duration != None

    sp = core.ScaperSpec()
    assert sp.sc != None
    assert sp.bg_label != None
    assert sp.bg_duration != None

    sp = core.ScaperSpec(scape=sc, bg_label='dummy', bg_duration=0)
    assert sp.bg_label != 'dummy'
    assert sp.bg_duration >= 0

def test_add_events():

    sc = core.Scaper()
    sp = core.ScaperSpec(sc)
    sp.add_events(labels=['horn', 'siren'], fg_start_times=[3,2], fg_durations=[1,1], snrs=[-2,-5], num_events=2)
    assert sp.labels == ['horn', 'siren']
    assert sp.fg_start_times == [3,2]
    assert sp.fg_durations == [1,1]
    assert sp.snrs == [-2,-5]
    assert sp.num_events == 2

    sp = core.ScaperSpec(sc)
    sp.add_events(labels=['horn', 'siren'], fg_start_times=[3,2], fg_durations=[1,1], snrs=[-2,-5], num_events=4)
    assert len(sp.labels) == 4
    assert len(sp.fg_start_times) == 4
    assert len(sp.fg_durations) == 4
    assert len(sp.snrs) == 4
    assert sp.num_events == 4

    sp = core.ScaperSpec(sc)
    sp.add_events(labels=['foo', 'bar'], fg_start_times=[-200,-200,0], fg_durations=[-1,0,3], snrs=[1,4], num_events=2)
    assert sp.labels != ['foo', 'bar']
    assert sp.fg_start_times != [-200,-200]
    assert len(sp.fg_start_times) == 2
    assert sp.fg_durations != [-1,0]
    assert sp.snrs != None
    assert sp.num_events == 2

    # full default - no arguments passed
    sp = core.ScaperSpec()
    sp.add_events()
    assert sp.labels != None
    assert sp.fg_start_times != None
    assert sp.fg_durations != None
    assert sp.snrs != None
    assert sp.num_events != None
    assert len(sp.labels) == len(sp.fg_durations) == len(sp.fg_start_times) == len(sp.snrs) == sp.num_events

    # list extension
    sp = core.ScaperSpec(sc)
    sp.add_events(labels='crowd', fg_start_times=2, fg_durations=3, snrs=1, num_events=3)
    assert len(sp.labels) == len(sp.fg_durations) == len(sp.fg_start_times) == len(sp.snrs) == sp.num_events

    # duration checks
    sp = core.ScaperSpec(sc, bg_label=['music'], bg_duration=10)
    sp.add_events(labels=['music'], fg_start_times=[5,6,7,8], fg_durations=[6], snrs=[-1,-3], num_events=4)
    assert sp.fg_durations == [5,4,3,2]

def test_generate_jams():

    sc = core.Scaper()
    sp = core.ScaperSpec(sc, bg_label=['crowd'], bg_duration=10)
    sp.add_events(labels=['horn', 'siren'], fg_start_times=[3,2], fg_durations=[1,1], snrs=[-2,-5], num_events=2)
    the_jam = sp.generate_jams(sp.spec, 'test/dummy_outfile.jams')
    assert the_jam


def test_generate_soundscapes():

    # file path checks
    sc = core.Scaper()
    sp = core.ScaperSpec(sc, bg_label=['crowd'], bg_duration=10)
    sp.add_events(labels=['horn', 'siren'], fg_start_times=[3, 2], fg_durations=[1, 1], snrs=[-2, -5], num_events=2)
    the_jam = sp.generate_jams(sp.spec, 'test/dummy_outfile.jams')
    sc.generate_soundscapes('test/incorrec_name.jams', 'test/dummy_output_audio.wav')
    assert the_jam

    the_jam = sp.generate_jams(sp.spec, 'test/test_jams.jams')
    sc.generate_soundscapes('test/test_jams.jams', 'test/dummy_output_audio.wav')
    # assert the_jam == 1


if __name__ == "__main__":
    import doctest
    doctest.testmod()


    # # # labels, start times, durations, snrs, num events
    # # sp.add_events(labels=['horn', 'siren'], fg_start_times=[3,2], fg_durations=[1,1], snrs=[-2,-5], num_events=4)
    # # thejam = sp.generate_jams(sp.spec, 'jammyjamm.jams')
    # # sc.generate_soundscapes('./jams/jammyjamm.jams','./output_audio/output_audio.wav')