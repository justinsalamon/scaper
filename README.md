# scaper

<img src="http://www.justinsalamon.com/uploads/4/3/9/4/4394963/scaper-logo_orig.png" width="400" height="108">

A library for soundscape synthesis and augmentation

[![PyPI](https://img.shields.io/pypi/v/scaper.svg)](https://pypi.python.org/pypi/scaper)
[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)
[![Build Status](https://travis-ci.org/justinsalamon/scaper.svg?branch=master)](https://travis-ci.org/justinsalamon/scaper)
[![Coverage Status](https://coveralls.io/repos/github/justinsalamon/scaper/badge.svg?branch=master)](https://coveralls.io/github/justinsalamon/scaper?branch=master)
[![Documentation Status](https://readthedocs.org/projects/scaper/badge/?version=latest)](http://scaper.readthedocs.io/en/latest/?badge=latest)
[![PyPI](https://img.shields.io/badge/python-2.7%2C%203.4%2C%203.5%2C%203.6-blue.svg)]()

Please refer to the [documentation](http://scaper.readthedocs.io/) for details.

For the motivation behind scaper and its applications check out the scaper-paper:

[Scaper: A library for soundscape synthesis and augmentation](http://www.justinsalamon.com/uploads/4/3/9/4/4394963/salamon_scaper_waspaa_2017.pdf)<br />
J. Salamon, D. MacConnell, M. Cartwright, P. Li, and J. P. Bello<br />
In IEEE Workshop on Applications of Signal Processing to Audio and Acoustics (WASPAA), New Paltz, NY, USA, Oct. 2017.

## Installation

### Non-python dependencies
Scaper has two non-python dependencies:
- SoX: http://sox.sourceforge.net/
- FFmpeg: https://ffmpeg.org/

#### Linux/macOS
If you're using [Anaconda](https://www.anaconda.com/distribution/) (or [miniconda](https://docs.conda.io/en/latest/miniconda.html)) to manage your python environment (recommended), you can install these dependencies using `conda` on macOS/Linux:

```
conda install -c conda-forge sox ffmpeg
```

#### macOS
On macOS these can be installed using [homebrew](https://brew.sh/):

```
brew install sox
brew install ffmpeg
```

#### Linux
On linux you can use your distribution's package manager, e.g. on Ubuntu (15.04 "Vivid Vervet" or newer):

```
sudo apt-get install sox
sudo apt-get install ffmpeg
```
NOTE: on earlier versions of Ubuntu [ffmpeg may point to a Libav binary](http://stackoverflow.com/a/9477756/2007700) which is not the correct binary. If you are using Anaconda, you can install the correct version as described earlier by calling `conda install -c conda-forge ffmpeg`. Otherwise, you can [obtain a static binary from the ffmpeg website](https://ffmpeg.org/download.html).

#### Windows
On windows you can use the provided installation binaries:
- SoX: https://sourceforge.net/projects/sox/files/sox/
- FFmpeg: https://ffmpeg.org/download.html#build-windows

### Installing Scaper

The simplest way to install scaper is by using `pip`, which will also install the required python dependencies if needed. To install scaper using pip, simply run:

```
pip install scaper
```

To install the latest version of scaper from source, clone or pull the lastest version:

```
git clone git@github.com:justinsalamon/scaper.git
```

Then enter the source folder and install using pip to handle python dependencies:

```
cd scaper
pip install -e .
```
## Tutorial

To help you get started with scaper, please see this [step-by-step tutorial](http://scaper.readthedocs.io/en/latest/tutorial.html).

## Example

```python
import scaper
import numpy as np

# OUTPUT FOLDER
outfolder = 'audio/soundscapes/'

# SCAPER SETTINGS
fg_folder = 'audio/soundbank/foreground/'
bg_folder = 'audio/soundbank/background/'

n_soundscapes = 1000
ref_db = -50
duration = 10.0 

min_events = 1
max_events = 9

event_time_dist = 'truncnorm'
event_time_mean = 5.0
event_time_std = 2.0
event_time_min = 0.0
event_time_max = 10.0

source_time_dist = 'const'
source_time = 0.0

event_duration_dist = 'uniform'
event_duration_min = 0.5
event_duration_max = 4.0

snr_dist = 'uniform'
snr_min = 6
snr_max = 30

pitch_dist = 'uniform'
pitch_min = -3.0
pitch_max = 3.0

time_stretch_dist = 'uniform'
time_stretch_min = 0.8
time_stretch_max = 1.2
    
# Generate 1000 soundscapes using a truncated normal distribution of start times

for n in range(n_soundscapes):
    
    print('Generating soundscape: {:d}/{:d}'.format(n+1, n_soundscapes))
    
    # create a scaper
    sc = scaper.Scaper(duration, fg_folder, bg_folder)
    sc.protected_labels = []
    sc.ref_db = ref_db
    
    # add background
    sc.add_background(label=('const', 'noise'), 
                      source_file=('choose', []), 
                      source_time=('const', 0))

    # add random number of foreground events
    n_events = np.random.randint(min_events, max_events+1)
    for _ in range(n_events):
        sc.add_event(label=('choose', []), 
                     source_file=('choose', []), 
                     source_time=(source_time_dist, source_time), 
                     event_time=(event_time_dist, event_time_mean, event_time_std, event_time_min, event_time_max), 
                     event_duration=(event_duration_dist, event_duration_min, event_duration_max), 
                     snr=(snr_dist, snr_min, snr_max),
                     pitch_shift=(pitch_dist, pitch_min, pitch_max),
                     time_stretch=(time_stretch_dist, time_stretch_min, time_stretch_max))
    
    # generate
    audiofile = os.path.join(outfolder, "soundscape_unimodal{:d}.wav".format(n))
    jamsfile = os.path.join(outfolder, "soundscape_unimodal{:d}.jams".format(n))
    txtfile = os.path.join(outfolder, "soundscape_unimodal{:d}.txt".format(n))
    
    sc.generate(audiofile, jamsfile,
                allow_repeated_label=True,
                allow_repeated_source=False,
                reverb=0.1,
                disable_sox_warnings=True,
                no_audio=False,
                txt_path=txtfile)
```
