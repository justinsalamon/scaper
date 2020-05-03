import os
import scaper
import jams

os.chdir('..')

# FIXTURES
# Paths to files for testing
FG_PATH = 'tests/data/audio/foreground'
BG_PATH = 'tests/data/audio/background'

ALT_FG_PATH = 'tests/data/audio_alt_path/foreground'
ALT_BG_PATH = 'tests/data/audio_alt_path/background'

REG_NAME = 'soundscape_20200501'
# REG_NAME = 'soundscape_20190326_22050'
# REG_WAV_PATH = 'tests/data/regression/soundscape_20170928.wav'
# REG_JAM_PATH = 'tests/data/regression/soundscape_20170928.jams'
# REG_TXT_PATH = 'tests/data/regression/soundscape_20170928.txt'

REG_BGONLY_NAME = 'bgonly_soundscape_20200501'
# REG_BGONLY_NAME = 'bgonly_soundscape_20190326_22050'
# REG_BGONLY_WAV_PATH = 'tests/data/regression/bgonly_soundscape_20170928.wav'
# REG_BGONLY_JAM_PATH = 'tests/data/regression/bgonly_soundscape_20170928.jams'
# REG_BGONLY_TXT_PATH = 'tests/data/regression/bgonly_soundscape_20170928.txt'

REG_REVERB_NAME = 'reverb_soundscape_20200501'
# REG_REVERB_NAME = 'reverb_soundscape_20190326_22050'
# REG_REVERB_WAV_PATH = 'tests/data/regression/reverb_soundscape_20170928.wav'
# REG_REVERB_JAM_PATH = 'tests/data/regression/reverb_soundscape_20170928.jams'
# REG_REVERB_TXT_PATH = 'tests/data/regression/reverb_soundscape_20170928.txt'

# fg and bg labels for testing
FB_LABELS = ['car_horn', 'human_voice', 'siren']
BG_LABELS = ['park', 'restaurant', 'street']

SAMPLE_RATES = [22050, 44100]


def test_names(name, rate, exts=('wav', 'jams', 'txt')):
    return [os.path.join('tests/data/regression', '{}_{}.{}'.format(name, rate, ext)) for ext in exts]


for rate in SAMPLE_RATES:
    test_names(REG_NAME, rate)

    print("==========USING BELOW FOR TESTS==============")
    VAR_NAMES_PARTIAL = ('REG', 'REG_BGONLY', 'REG_REVERB')
    FILE_BASENAMES = (REG_NAME, REG_BGONLY_NAME, REG_REVERB_NAME)
    FILE_TYPES = ('WAV', 'JAM', 'TXT')

    for var, name in zip(VAR_NAMES_PARTIAL, FILE_BASENAMES):
        for type, path in zip(FILE_TYPES, test_names(name, rate)):
            print("{}_{}_PATH = '{}'".format(var, type, path))
        print()
    print("==========USING ABOVE FOR TESTS==============")

    sc = scaper.Scaper(10.0, fg_path=FG_PATH, bg_path=BG_PATH)
    sc.ref_db = -50
    sc.sr = rate

    # background
    sc.add_background(
        label=('const', 'park'),
        source_file=(
            'const',
            'tests/data/audio/background/park/'
            '268903__yonts__city-park-tel-aviv-israel.wav'),
        source_time=('const', 0))

    # foreground events
    sc.add_event(
        label=('const', 'siren'),
        source_file=('const',
                     'tests/data/audio/foreground/'
                     'siren/69-Siren-1.wav'),
        source_time=('const', 5),
        event_time=('const', 2),
        event_duration=('const', 5),
        snr=('const', 5),
        pitch_shift=None,
        time_stretch=None)

    sc.add_event(
        label=('const', 'car_horn'),
        source_file=('const',
                     'tests/data/audio/foreground/'
                     'car_horn/17-CAR-Rolls-Royce-Horn.wav'),
        source_time=('const', 0),
        event_time=('const', 5),
        event_duration=('const', 2),
        snr=('const', 20),
        pitch_shift=('const', 1),
        time_stretch=None)

    sc.add_event(
        label=('const', 'human_voice'),
        source_file=('const',
                     'tests/data/audio/foreground/'
                     'human_voice/42-Human-Vocal-Voice-taxi-2_edit.wav'),
        source_time=('const', 0),
        event_time=('const', 7),
        event_duration=('const', 2),
        snr=('const', 10),
        pitch_shift=None,
        time_stretch=('const', 1.2))

    wav_file, jam_file, txt_file = test_names(REG_NAME, rate)
    sc.generate(wav_file, jam_file, txt_path=txt_file, disable_instantiation_warnings=True)
    print('Wrote:', wav_file, jam_file, txt_file)

    wav_file, jam_file, txt_file = test_names(REG_REVERB_NAME, rate)
    sc.generate(wav_file, jam_file, txt_path=txt_file, reverb=0.2, disable_instantiation_warnings=True)
    print('Wrote:', wav_file, jam_file, txt_file)

    jams.load(jam_file)

    # soundscape with only one event will use transformer (regression test)
    sc = scaper.Scaper(10.0, fg_path=FG_PATH, bg_path=BG_PATH)
    sc.ref_db = -20
    sc.sr = rate

    # background
    sc.add_background(
        label=('const', 'park'),
        source_file=('const',
                     'tests/data/audio/background/park/'
                     '268903__yonts__city-park-tel-aviv-israel.wav'),
        source_time=('const', 0))

    wav_file, jam_file, txt_file = test_names(REG_BGONLY_NAME, rate)
    sc.generate(wav_file, jam_file, txt_path=txt_file, reverb=0.2, disable_instantiation_warnings=True)
    print('Wrote:', wav_file, jam_file, txt_file)
