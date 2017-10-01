#!/usr/bin/env python
"""Top-level module for scaper"""

from .core import Scaper
from .core import generate_from_jams
from .core import trim
import jams
from pkg_resources import resource_filename
from .version import version as __version__

# Add sound_event namesapce
namespace_file = resource_filename(__name__, 'namespaces/sound_event.json')
jams.schema.add_namespace(namespace_file)
