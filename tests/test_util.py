# CREATED: 10/15/16 7:52 PM by Justin Salamon <justin.salamon@nyu.edu>

'''
Tests for functions in util.py
'''

from scaper.util import _close_temp_files
from scaper.util import _set_temp_logging_level
import tempfile
import os
import logging


def test_close_temp_files():
    '''
    Create a bunch of temp files and then make sure they've been closed and
    deleted.

    '''
    tmpfiles = []

    with _close_temp_files(tmpfiles):
        for _ in range(5):
            tmpfiles.append(
                tempfile.NamedTemporaryFile(suffix='.wav', delete=True))

    for tf in tmpfiles:
        assert tf.file.closed
        assert not os.path.isfile(tf.name)


def test_set_temp_logging_level():
    '''
    Ensure temp logging level is set as expected


    '''
    logger = logging.getLogger()
    logger.setLevel('DEBUG')
    with _set_temp_logging_level('CRITICAL'):
        assert logging.getLevelName(logger.level) == 'CRITICAL'
    assert logging.getLevelName(logger.level) == 'DEBUG'
