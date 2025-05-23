import logging
log = logging.getLogger(__name__)

import os
from pathlib import Path


DEFAULT_CAL_ROOT = os.path.expanduser('~/Documents/cftscal')
CAL_ROOT = Path(os.environ.get('CFTSCAL_ROOT', DEFAULT_CAL_ROOT))
log.info('Base folder for calibrations is %s', CAL_ROOT)
