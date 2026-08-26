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

from pathlib import Path
import json


DEFAULT_CAL_ROOT = os.path.expanduser('~/Documents/cftscal')
CAL_ROOT = Path(os.environ.get('CFTSCAL_ROOT', DEFAULT_CAL_ROOT))

try:
    from psi import get_config_folder
    config_file = get_config_folder() / 'cfts' / 'workspace.json'
    if config_file.exists():
        config = json.loads(config_file.read_text())
        if 'data_path' in config:
            CAL_ROOT = Path(config['data_path'])
except ImportError:
    pass

log.info('Base folder for calibrations is %s', CAL_ROOT)
