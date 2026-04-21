import logging
log = logging.getLogger(__name__)

import pyqtgraph as pg
pg.setConfigOptions(antialias=False)

import os
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
