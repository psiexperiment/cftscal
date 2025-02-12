import os
from pathlib import Path


DEFAULT_CAL_ROOT = os.path.expanduser('~/Documents/cftscal')
CAL_ROOT = Path(os.environ.get('CAL_ROOT', DEFAULT_CAL_ROOT))
