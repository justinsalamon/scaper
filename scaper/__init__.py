#!/usr/bin/env python
"""Top-level module for scaper"""

from .core import *
import jams
from pkg_resources import resource_filename

__version__ = '0.0.1'

# Add sound_event namesapce
namespace_file = resource_filename(__name__, 'namespaces/sound_event.json')
jams.schema.add_namespace(namespace_file)
