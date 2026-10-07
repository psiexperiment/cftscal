'''
Reading B&K PULSE recordings saved as ``.mat`` files (the files the older
MATLAB program, measure_sound, read and wrote), and listing them in Input
Recording beside cftscal's own recordings.
'''
import datetime as dt
import json
import os
from pathlib import Path

import enaml
import numpy as np
import pytest
from scipy import io
from scipy.io import wavfile

from cftscal.mat_recording import (
    MatFileError, MatRecording, read_mat_header,
)
from cftscal.objects import (
    CalibrationManager, CFTSInputRecordingLoader, InputRecording,
    MatInputRecording, MatInputRecordingLoader,
)

FS = 65536


def write_pulse_mat(path, channels, fs=FS, **header):
    '''
    Write a ``.mat`` file laid out like a PULSE export (and like the files
    measure_sound's Save button wrote): text fields in File_Header, one
    Channel_<n>_Data vector per channel.

    Parameters
    ----------
    path : Path
        File to write; its folder is created if need be.
    channels : dict
        Maps channel number to its samples.
    fs : float
        Sampling rate, written as text as PULSE does.
    **header
        Extra File_Header fields, or ``Channel_<n>_Header`` structs.
    '''
    path.parent.mkdir(parents=True, exist_ok=True)
    channel_headers = {k: v for k, v in header.items() if k.startswith('Channel_')}
    file_header = {k: v for k, v in header.items() if k not in channel_headers}
    first = next(iter(channels.values()))
    contents = {
        'File_Header': {
            'SampleFrequency': str(fs),
            'NumberOfChannels': str(len(channels)),
            'NumberOfSamplesPerChannel': str(len(first)),
            **file_header,
        },
        **{f'Channel_{n}_Data': np.asarray(y)[:, np.newaxis]
           for n, y in channels.items()},
        **channel_headers,
    }
    io.savemat(path, contents)
    return path


def _tone(seconds=0.5, frequency=1000, amplitude=1.0):
    t = np.arange(int(seconds * FS)) / FS
    return amplitude * np.sin(2 * np.pi * frequency * t)


################################################################################
# Reading the file
################################################################################
def test_header(tmp_path):
    path = write_pulse_mat(tmp_path / 'rec.mat', {1: _tone(), 2: _tone()})
    header = read_mat_header(path)
    assert header['fs'] == FS
    assert header['channels'] == {
        'Channel_1_Data': {'label': 'Channel 1', 'unit': 'Pa'},
        'Channel_2_Data': {'label': 'Channel 2', 'unit': 'Pa'},
    }
    # No Date in File_Header: when the file was written, from the
    # MAT-file's own header (savemat writes the current time).
    assert abs(header['datetime'] - dt.datetime.now()) < dt.timedelta(minutes=1)


def test_channels_in_numeric_order(tmp_path):
    channels = {n: _tone(0.01) for n in (10, 2, 1)}
    path = write_pulse_mat(tmp_path / 'rec.mat', channels)
    assert list(read_mat_header(path)['channels']) == \
        ['Channel_1_Data', 'Channel_2_Data', 'Channel_10_Data']


def test_date_time_and_unit_from_the_file(tmp_path):
    path = write_pulse_mat(
        tmp_path / 'rec.mat', {1: _tone(0.01)},
        Date='16-Jun-2026', Time='10:15:44',
        Channel_1_Header={'Unit': 'V'},
    )
    header = read_mat_header(path)
    assert header['datetime'] == dt.datetime(2026, 6, 16, 10, 15, 44)
    assert header['channels']['Channel_1_Data']['unit'] == 'V'


def test_real_pulse_header_fields(tmp_path):
    # As in a real PULSE export: SignalName names the channel, Unit is
    # padded with spaces, and the date has no time of day.
    path = write_pulse_mat(
        tmp_path / 'rec.mat', {1: _tone(0.01), 2: _tone(0.01)},
        fs='65536.000000', Date='15/MAR/2011',
        Channel_1_Header={'Unit': 'Pa                  ', 'SignalName': 'LeftEar',
                          'Correction': '0.020827', 'MaxLevel': '682.446029'},
        Channel_2_Header={'Unit': 'Pa                  ', 'SignalName': 'RightEar'},
    )
    header = read_mat_header(path)
    assert header['fs'] == 65536
    assert header['channels'] == {
        'Channel_1_Data': {'label': 'LeftEar', 'unit': 'Pa'},
        'Channel_2_Data': {'label': 'RightEar', 'unit': 'Pa'},
    }
    # savemat writes today's date in the MAT header, so it isn't the
    # recording's date: midnight on the recorded date.
    assert header['datetime'] == dt.datetime(2011, 3, 15)


@pytest.mark.parametrize('date, time, created_on, expected', [
    # The file was written on the recording day: its time is used.
    ('15/MAR/2011', None, dt.datetime(2011, 3, 15, 12, 52, 13),
     dt.datetime(2011, 3, 15, 12, 52, 13)),
    # Written later (e.g. re-saved by measure_sound): only the date is known.
    ('15/MAR/2011', None, dt.datetime(2012, 1, 1, 9, 0, 0),
     dt.datetime(2011, 3, 15)),
    # An explicit time wins.
    ('15/MAR/2011', '10:15:44', dt.datetime(2011, 3, 15, 12, 52, 13),
     dt.datetime(2011, 3, 15, 10, 15, 44)),
    # Day first, as PULSE writes it.
    ('03/04/2011', None, None, dt.datetime(2011, 4, 3)),
    # No date at all: when the file was written.
    (None, None, dt.datetime(2011, 3, 15, 12, 52, 13),
     dt.datetime(2011, 3, 15, 12, 52, 13)),
    (None, None, None, None),
])
def test_recording_datetime(date, time, created_on, expected):
    from types import SimpleNamespace
    from cftscal.mat_recording import _parse_datetime
    header = SimpleNamespace(**{k: v for k, v in
                                (('Date', date), ('Time', time)) if v})
    assert _parse_datetime(header, created_on) == expected


def test_created_on_from_the_mat_header():
    from cftscal.mat_recording import _created_on
    header = b'MATLAB 5.0 MAT-file, Platform: PCWIN, Created on: Tue Mar 15 12:52:13 2011'
    assert _created_on(header) == dt.datetime(2011, 3, 15, 12, 52, 13)
    assert _created_on(b'MATLAB 5.0 MAT-file, Platform: PCWIN, Created on: Tue Mar  1 02:03:04 2011')         == dt.datetime(2011, 3, 1, 2, 3, 4)
    assert _created_on(b'MATLAB 5.0 MAT-file') is None
    assert _created_on(None) is None


def test_unparseable_date_is_ignored(tmp_path):
    path = write_pulse_mat(tmp_path / 'rec.mat', {1: _tone(0.01)},
                           Date='not a date')
    # Falls back to when the file was written.
    when = read_mat_header(path)['datetime']
    assert abs(when - dt.datetime.now()) < dt.timedelta(minutes=1)


@pytest.mark.parametrize('contents, message', [
    ({'x': np.zeros(3)}, 'Not a B&K PULSE recording'),
    ({'File_Header': {'SampleFrequency': '1000'}}, 'Not a B&K PULSE recording'),
    ({'File_Header': {'SampleFrequency': 'abc'}, 'Channel_1_Data': np.zeros(3)},
     'no valid SampleFrequency'),
    ({'File_Header': {'Title': 'x'}, 'Channel_1_Data': np.zeros(3)},
     'no valid SampleFrequency'),
])
def test_not_a_pulse_recording(tmp_path, contents, message):
    path = tmp_path / 'other.mat'
    io.savemat(path, contents)
    with pytest.raises(MatFileError, match=message):
        read_mat_header(path)


def test_unreadable_file(tmp_path):
    path = tmp_path / 'broken.mat'
    path.write_bytes(b'not a mat file at all')
    with pytest.raises(MatFileError, match='Could not read'):
        read_mat_header(path)


def test_recording_reads_samples_on_demand(tmp_path):
    left, right = _tone(), _tone(amplitude=0.5)
    path = write_pulse_mat(tmp_path / 'rec.mat', {1: left, 2: right})
    recording = MatRecording(path)
    signal = recording.Channel_2_Data
    assert signal._data is None
    assert signal.fs == FS
    np.testing.assert_allclose(signal[0], right)
    assert signal.shape == (1, len(right))
    assert signal.duration == pytest.approx(0.5)
    # Already in pascals.
    np.testing.assert_allclose(signal.get_calibration().get_level(signal[0]), right)
    with pytest.raises(AttributeError):
        recording.Channel_3_Data


################################################################################
# Listing them in Input Recording
################################################################################
@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv('CFTSCAL_ROOT', str(tmp_path))
    return tmp_path / 'input-recording'


def _manager():
    manager = CalibrationManager(InputRecording)
    manager.loaders.extend([CFTSInputRecordingLoader(), MatInputRecordingLoader()])
    return manager


def _listing(manager):
    return {
        (obj.folder, obj.name): sorted(c.filename.name for c in cals)
        for obj, cals in manager.list_objects_and_calibrations()
    }


def test_mat_files_are_listed_with_cftscal_recordings(root):
    write_pulse_mat(root / 'BK-4123' / 'noise.mat', {1: _tone(0.01)})
    write_pulse_mat(root / 'Lab' / 'BK-4189' / 'tone.mat', {1: _tone(0.01)})
    write_pulse_mat(root / 'loose.mat', {1: _tone(0.01)})
    cfts = root / 'BK-4123' / '20260616-101544_bk-4123'
    cfts.mkdir(parents=True)
    (cfts / 'metadata.json').write_text(json.dumps(
        {'datetime': '2026-06-16T10:15:44', 'generator': 'BK-4123',
         'sensors': {}}))
    assert _listing(_manager()) == {
        # A folder can hold both kinds.
        ('', 'BK-4123'): ['20260616-101544_bk-4123', 'noise.mat'],
        ('Lab', 'BK-4189'): ['tone.mat'],
        # A file directly in the Input Recording folder is its own object.
        ('', 'loose'): ['loose.mat'],
    }


def test_mat_recording_properties(root):
    path = write_pulse_mat(root / 'BK-4123' / 'cage 3 noise.mat',
                           {1: _tone(0.01), 2: _tone(0.01)},
                           Date='16-Jun-2026', Time='10:15:44')
    cal = MatInputRecording('BK-4123', path)
    assert cal.problem is None
    assert cal.generator == 'cage 3 noise'
    assert cal.datetime == dt.datetime(2026, 6, 16, 10, 15, 44)
    assert cal.sensors == {
        'Channel_1_Data': {'label': 'Channel 1', 'sensor': '.mat file (Pa)'},
        'Channel_2_Data': {'label': 'Channel 2', 'sensor': '.mat file (Pa)'},
    }
    # Survives the trip through a string, as calibrations sent to
    # experiments do.
    copy = MatInputRecording.from_string(cal.to_string())
    assert copy.filename == cal.filename and copy.name == cal.name


def test_datetime_falls_back_to_when_the_file_was_modified(root):
    path = write_pulse_mat(root / 'BK-4123' / 'noise.mat', {1: _tone(0.01)})
    # Blank out the MAT-file header's "Created on" time, so the file says
    # nothing about when it was made.
    data = path.read_bytes()
    start = data.index(b'Created on:')
    # The header text is the first 116 bytes, padded with spaces or nulls.
    end = data.find(bytes(1), start, 116)
    if end == -1:
        end = 116
    path.write_bytes(data[:start] + b' ' * (end - start) + data[end:])
    when = dt.datetime(2020, 1, 2, 3, 4, 5)
    os.utime(path, (when.timestamp(), when.timestamp()))
    assert MatInputRecording('BK-4123', path).datetime == when


def test_unreadable_mat_file_is_listed_with_a_problem(root):
    path = root / 'BK-4123' / 'broken.mat'
    path.parent.mkdir(parents=True)
    path.write_bytes(b'garbage')
    (cal,), = [cals for _, cals in _manager().list_objects_and_calibrations()]
    assert 'Could not read' in cal.problem
    # Still sortable, by the file's modification time.
    assert cal.sort_datetime.year >= 2026


def test_export_as_wav(root, tmp_path):
    from cftscal.plugins.export import export_calibration
    left, right = _tone(), _tone(amplitude=0.25)
    path = write_pulse_mat(root / 'BK-4123' / 'noise.mat', {1: left, 2: right})
    out = tmp_path / 'out.wav'
    export_calibration(MatInputRecording('BK-4123', path), out)
    with pytest.warns(wavfile.WavFileWarning):  # scipy skips the CFTS chunk
        fs, samples = wavfile.read(out)
    assert fs == FS
    np.testing.assert_allclose(samples[:, 0], left, atol=1e-6)
    np.testing.assert_allclose(samples[:, 1], right, atol=1e-6)


def test_plotted_and_measured_like_a_cftscal_recording(root, qt_app):
    # A 1 Pa-peak, 1 kHz tone: 90.97 dB SPL.
    from types import SimpleNamespace
    with enaml.imports():
        from cftscal.plugins.input_recording.view import InputRecordingPlotManager
    path = write_pulse_mat(root / 'BK-4123' / 'tone.mat',
                           {1: np.cos(2 * np.pi * 1000 * np.arange(FS) / FS)})
    cal = MatInputRecording('BK-4123', path)
    manager = InputRecordingPlotManager(apply_calibration=True)
    manager.component  # builds the plots, as showing the view does
    manager.filter_mode = 'Unfiltered'
    plot = SimpleNamespace(setData=lambda *args: None)
    data = manager._plot('Channel_1_Data', cal.load(), [plot], [plot])
    manager.data = {(cal, 'Channel_1_Data'): {**data, 'color': 'red'}}
    manager.region_select.setRegion((0.25, 0.75))
    manager._update_analysis()
    entry, = manager.analysis
    assert entry['channel'] == 'Channel 1'
    assert entry['rms'] == pytest.approx(90.97, abs=0.01)


def test_exported_region_is_named_without_the_extension(root):
    with enaml.imports():
        from cftscal.plugins.input_recording.view import recording_stem
    path = write_pulse_mat(root / 'BK-4123' / 'noise.mat', {1: _tone(0.01)})
    assert recording_stem(path) == 'noise'
    folder = root / 'BK-4123' / '20260616-101544_bk-4123'
    folder.mkdir()
    assert recording_stem(folder) == '20260616-101544_bk-4123'


def test_delete_removes_a_file_or_a_folder(tmp_path, qt_app):
    with enaml.imports():
        from cftscal.plugins.fast_tree_view import delete_calibration_path
    path = write_pulse_mat(tmp_path / 'noise.mat', {1: _tone(0.01)})
    delete_calibration_path(path)
    assert not path.exists()
    folder = tmp_path / '20260616-101544_x'
    folder.mkdir()
    (folder / 'metadata.json').write_text('{}')
    delete_calibration_path(folder)
    assert not folder.exists()
