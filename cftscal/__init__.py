import os
from pathlib import Path
import textwrap


try:
    #CAL_ROOT = Path(get_config('CAL_ROOT', os.environ['CAL_ROOT']))
    CAL_ROOT = Path(os.environ['CAL_ROOT'])
except KeyError as e:
    mesg = '''
    Could not determine the location of calibration data. To specify the
    location, set an environment variable, `CAL_ROOT` with the full path to the
    root of the calibration data. If you do not have any calibration data,
    create a folder where you would like the calibration data stored and set
    CAL_ROOT accordingly. If you are using a conda environment, you can use
    `conda env config vars set CAL_ROOT=<path>`.
    '''
    mesg = textwrap.dedent(mesg).replace('\n', ' ').strip()
    raise KeyError(mesg) from e
