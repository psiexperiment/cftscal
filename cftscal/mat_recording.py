'''
Read sound recordings saved as MATLAB ``.mat`` files by B&K PULSE.

These are the files the lab's older MATLAB program, measure_sound, read (and
wrote, with its *Save* button). Each file holds:

* ``File_Header``: a struct whose ``SampleFrequency`` field gives the
  sampling rate in Hz. It is stored as text (e.g. ``'65536'``), as are the
  other fields measure_sound read (``NumberOfChannels``,
  ``NumberOfSamplesPerChannel``).
* ``Channel_1_Data``, ``Channel_2_Data``, ...: one vector of samples per
  channel, already in pascals.

Optional extras are used when present: ``Date`` and ``Time`` fields in
``File_Header`` for when the recording was made, and a
``Channel_<n>_Header`` struct whose ``Unit`` field gives the channel's units.

The samples are used exactly as stored. measure_sound multiplied channel 1
by 1.165 and channel 2 by 1.187, correction factors for one particular
setup; those are *not* applied here.
'''
import datetime as dt
from pathlib import Path
import re

import numpy as np
import pandas as pd
from scipy import io

from psiaudio.calibration import FlatCalibration


#: Matches the variable holding a channel's samples; the group is its number.
CHANNEL_PATTERN = re.compile(r'^Channel_(\d+)_Data$')


class MatFileError(Exception):
    '''A ``.mat`` file isn't a recording this module can read.'''


def _field(struct, name, default=None):
    '''
    A field of a MATLAB struct loaded by `scipy.io.loadmat`, or `default`.
    Text fields come back as plain strings, and one-element arrays as their
    single value.
    '''
    value = getattr(struct, name, default)
    if isinstance(value, np.ndarray) and value.size == 1:
        value = value.item()
    return value


def _loadmat(filename, variable_names):
    try:
        return io.loadmat(filename, variable_names=variable_names,
                          squeeze_me=True, struct_as_record=False)
    except NotImplementedError as e:
        # scipy can't read MATLAB's HDF5-based v7.3 format.
        raise MatFileError(
            'This is a MATLAB v7.3 file, which cannot be read. Open it in '
            "MATLAB and save it again with save(filename, '-v7')."
        ) from e
    except Exception as e:
        raise MatFileError(f'Could not read the file: {e}') from e


def _parse_datetime(header):
    '''When the recording was made, from File_Header, or None.'''
    date = _field(header, 'Date')
    if not isinstance(date, str) or not date.strip():
        return None
    time = _field(header, 'Time')
    text = f'{date} {time}' if isinstance(time, str) else date
    try:
        return pd.to_datetime(text).to_pydatetime()
    except (ValueError, OverflowError):
        return None


def read_mat_header(filename):
    '''
    Read everything about a PULSE ``.mat`` recording except its samples.

    Parameters
    ----------
    filename : str or Path
        The ``.mat`` file.

    Returns
    -------
    header : dict
        ``fs``: sampling rate, in Hz. ``channels``: maps each channel's
        variable name (e.g. ``'Channel_1_Data'``), in channel order, to a
        dict with its ``label`` (e.g. ``'Channel 1'``) and ``unit`` (``'Pa'``
        unless the file says otherwise). ``datetime``: when the recording was
        made according to the file, or None if it doesn't say.

    Raises
    ------
    MatFileError
        If the file can't be read, or isn't laid out as described in the
        module docstring.
    '''
    try:
        variables = [name for name, _, _ in io.whosmat(filename)]
    except Exception as e:
        raise MatFileError(f'Could not read the file: {e}') from e
    numbers = sorted(int(m.group(1)) for v in variables
                     if (m := CHANNEL_PATTERN.match(v)))
    if 'File_Header' not in variables or not numbers:
        raise MatFileError(
            'Not a B&K PULSE recording: expected a File_Header and '
            'Channel_1_Data, Channel_2_Data, ... variables.'
        )
    channel_headers = [f'Channel_{n}_Header' for n in numbers]
    contents = _loadmat(filename, ['File_Header'] + [
        h for h in channel_headers if h in variables])
    header = contents['File_Header']
    try:
        fs = float(_field(header, 'SampleFrequency'))
    except (TypeError, ValueError):
        fs = 0
    if not fs > 0:
        raise MatFileError('File_Header has no valid SampleFrequency.')

    channels = {}
    for n, header_name in zip(numbers, channel_headers):
        unit = _field(contents.get(header_name), 'Unit')
        channels[f'Channel_{n}_Data'] = {
            'label': f'Channel {n}',
            'unit': unit if isinstance(unit, str) and unit else 'Pa',
        }
    return {'fs': fs, 'channels': channels, 'datetime': _parse_datetime(header)}


class MatSignal:
    '''
    One channel of a ``.mat`` recording, read the first time its samples are
    needed. Offers the parts of psidata's signals that cftscal uses: index
    it with ``[0]`` for the samples, and `fs` and `get_calibration`.
    '''

    def __init__(self, filename, variable, fs):
        self.filename = Path(filename)
        self.variable = variable
        self.fs = fs
        self._data = None

    @property
    def array(self):
        '''The samples, shaped (1, n) like psidata's signals.'''
        if self._data is None:
            contents = _loadmat(self.filename, [self.variable])
            data = np.asarray(contents[self.variable], dtype=float)
            self._data = data.reshape(1, -1)
        return self._data

    def __getitem__(self, index):
        return self.array[index]

    @property
    def shape(self):
        return self.array.shape

    @property
    def duration(self):
        return self.shape[-1] / self.fs

    def get_calibration(self):
        '''Unity: the samples are already in pascals.'''
        return FlatCalibration.unity()


class MatRecording:
    '''
    A ``.mat`` recording, offering its channels as attributes named after
    their variables (``recording.Channel_1_Data``) the way psidata's
    `Recording` offers a cftscal recording's channels.
    '''

    def __init__(self, filename, header=None):
        self.filename = Path(filename)
        if header is None:
            header = read_mat_header(filename)
        self._signals = {
            name: MatSignal(self.filename, name, header['fs'])
            for name in header['channels']
        }

    def __getattr__(self, name):
        try:
            return self.__dict__['_signals'][name]
        except KeyError:
            raise AttributeError(name) from None


def file_datetime(filename):
    '''When ``filename`` was last modified, as a datetime.'''
    return dt.datetime.fromtimestamp(Path(filename).stat().st_mtime)
