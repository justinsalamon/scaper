import sox
from sox.core import sox as _sox_func
from sox import file_info
from sox.log import logger
import soundfile as sf
import time
from subprocess import PIPE, Popen
import shlex
import numpy as np

ENCODINGS_MAPPING = {
    np.int16: 's16',
    np.float32: 'f32',
    np.float64: 'f64',
}

PIPE_CHAR = '-'

def sox_func(args, samplerate, encoding, channels):
    cmd_suffix = ' '.join([
        '-t ' + ENCODINGS_MAPPING[encoding],
        '-r ' + str(samplerate),
        '-c ' + str(channels),
        PIPE_CHAR,
    ])

    cmd = 'sox ' + ' '.join(list(map(str, args))) + ' ' +  cmd_suffix

    print(cmd)

    stdout, stderr = Popen(shlex.split(cmd, posix=False), stdout=PIPE, stderr=PIPE).communicate()
    
    if stderr:
        raise RuntimeError(stderr.decode())
    elif stdout:
        outsound = np.fromstring(stdout, dtype=encoding)
        if channels > 1:
            outsound = outsound.reshape(
                (channels, int(len(outsound) / channels_out)), order='F')
        return outsound


class Transformer(sox.Transformer):
    def __init__(self):
        super().__init__()

    def build(self, input_filepath, samplerate, channels, encoding=np.float32):
        '''Builds the output_file by executing the current set of commands.
        Parameters
        ----------
        input_filepath : str
            Path to input audio file.
        '''
        file_info.validate_input_file(input_filepath)

        args = []
        args.extend(self.globals)
        args.extend(self.input_format)
        args.append(input_filepath)
        args.extend(self.effects)

        start_time = time.time()
        outsound = sox_func(args, samplerate, encoding, channels)
        time_taken = time.time() - start_time
        print(f'Took {time_taken} for {args}')
        print(outsound)
        return outsound

class Combiner(sox.Combiner):
    def __init__(self):
        super().__init__()
