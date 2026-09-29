import logging
log = logging.getLogger(__name__)

import os

# Enable ASIO host-API support in PortAudio BEFORE anything imports
# sounddevice. sounddevice reads this environment variable the first time it
# loads the PortAudio library, so it must be set as early as possible --
# hence here, at the top of the package's __init__ (the earliest module
# imported for any `cftscal.*` access), rather than next to the sounddevice
# import in cftscal/plugins/workspace.py. Without it, cftscal's device picker
# would omit ASIO devices entirely, so the user could never select one; and
# the ASIO devices it enumerates must agree with the psi calibration
# subprocess, which force-enables ASIO the same way (see
# psi.controller.engines.soundcard) and resolves the "<name>, <host API>"
# device string we hand it. Match psiexperiment's unconditional set (not
# setdefault) so the two host-API lists agree.
os.environ['SD_ENABLE_ASIO'] = '1'

import pyqtgraph as pg
pg.setConfigOptions(antialias=False)

from psi import register_defaults

from .config_defaults import DEFAULTS

register_defaults(DEFAULTS)

# There is deliberately no module-level CAL_ROOT any more. It was captured
# at import and never reassigned, so changing the calibration folder in the
# GUI left every later reader on the old path until the process restarted.
# Read `get_config('CFTSCAL_ROOT')` at the point of use instead.
