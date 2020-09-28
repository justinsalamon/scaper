"""
This is a profiling script to check the performance of
Scaper. It generates 100 soundscapes in sequence 
(no parallelization). Running it on 2019 Macbook Pro
currently takes 158.68 seconds (02:38).
"""

import scaper
import numpy as np
import tempfile
import os
import tqdm
import zipfile
import subprocess
import time
import csv
import platform
import psutil
import datetime
import math
import multiprocessing
import argparse
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--quick', action='store_true')
args = parser.parse_args()
cmd_line = ' '.join(sys.argv)
cmd_line = 'python ' + cmd_line

# Download the audio automatically
FIX_DIR = 'tests/data/'
QUICK_PITCH_TIME = args.quick

def get_git_commit_hash():
    process = subprocess.Popen(
        ['git', 'rev-parse', 'HEAD'], shell=False, stdout=subprocess.PIPE)
    git_head_hash = process.communicate()[0].strip().decode('utf-8')
    return git_head_hash

def convert_size(size_bytes):
   if size_bytes == 0:
       return "0B"
   size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
   i = int(math.floor(math.log(size_bytes, 1024)))
   p = math.pow(1024, i)
   s = round(size_bytes / p, 2)
   return "%s %s" % (s, size_name[i])

with tempfile.TemporaryDirectory() as tmpdir:  
    path_to_audio = os.path.join(FIX_DIR, 'audio/')
    # OUTPUT FOLDER
    outfolder = tmpdir

    # SCAPER SETTINGS
    fg_folder = os.path.join(path_to_audio, 'foreground')
    bg_folder = os.path.join(path_to_audio, 'background')

    # If we parallelize this script, change this accordingly
    n_workers = 1

    n_soundscapes = 100
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

    # generate a random seed for this Scaper object
    seed = 123

    # create a scaper that will be used below
    sc = scaper.Scaper(duration, fg_folder, bg_folder, random_state=seed)
    sc.protected_labels = []
    sc.ref_db = ref_db

    # Generate 100 soundscapes using a truncated normal distribution of start times
    start_time = time.time()

    for n in tqdm.trange(n_soundscapes):
        print('Generating soundscape: {:d}/{:d}'.format(n+1, n_soundscapes))

        # reset the event specifications for foreground and background at the 
        # beginning of each loop to clear all previously added events
        sc.reset_bg_event_spec()
        sc.reset_fg_event_spec()

        # add background
        sc.add_background(label=('choose', []),
                            source_file=('choose', []),
                            source_time=('const', 0))
        sc.fade_in_len = 0.01
        sc.fade_out_len = 0.01

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
                            time_stretch=(time_stretch_dist, time_stretch_min, time_stretch_max)
            )
        # generate
        audiofile = os.path.join(outfolder, "soundscape_unimodal{:d}.wav".format(n))
        jamsfile = os.path.join(outfolder, "soundscape_unimodal{:d}.jams".format(n))
        txtfile = os.path.join(outfolder, "soundscape_unimodal{:d}.txt".format(n))

        sc.generate(audiofile, jamsfile,
                    allow_repeated_label=True,
                    allow_repeated_source=True,
                    reverb=0.1,
                    disable_sox_warnings=True,
                    quick_pitch_time=QUICK_PITCH_TIME,
                    no_audio=False,
                    txt_path=txtfile)

    time_taken = time.time() - start_time
    uname = platform.uname()

    row = {
        'command': cmd_line,
        'time_of_run': str(datetime.datetime.now()),
        'scaper_version': scaper.__version__,
        'python_version': platform.python_version(),
        'system': uname.system,
        'machine': uname.machine,
        'processor': uname.processor,
        'n_cpu': multiprocessing.cpu_count(),
        'n_workers': n_workers,
        'memory': convert_size(psutil.virtual_memory().total),
        'n_soundscapes': n_soundscapes,        
        'execution_time': np.round(time_taken, 4),
        'git_commit_hash': get_git_commit_hash(),
    }

    fieldnames = list(row.keys())
    
    results_path = 'tests/profile_results.csv'
    write_header = not os.path.exists(results_path)

    with open(results_path, 'a') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)

    with open(results_path, 'r') as f:
        csv_f = csv.reader(f)
        for row in csv_f:
            print('{:<30}  {:<15}  {:<15}  {:<10} {:<10} {:<10} {:<5} {:<10} {:<10} {:<15} {:<10} {:}'.format(*row))
