'''
Exporting and playing Input Recording's selected region
(cftscal/plugins/input_recording/region.py and the view's buttons).
'''
import datetime as dt
from pathlib import Path
import sys
from types import SimpleNamespace

import enaml
import numpy as np
import pytest
from scipy.io import wavfile

from cftscal.plugins.export import read_calibration_wav_metadata
from cftscal.plugins.input_recording import region as region_module
from cftscal.plugins.input_recording.region import (
    PLAYBACK_FULL_SCALE_PA, Player, clipping_peak, export_region,
    playback_samples, region_filename,
)

FS = 1000


class FakeRecording:
    '''The parts of a CFTSInputRecording the region code reads. Hashable,
    like the real one: the plot manager keys its data by recording.'''

    def __init__(self, name):
        self.filename = Path('C:/data/input-recording/BK-4123') / name
        self.sensors = {'ai0': {'label': 'Left Input', 'sensor': 'HATS-Left'},
                        'ai1': {'label': 'Right Input', 'sensor': 'HATS-Right'}}
        self.generator = 'BK-4123'
        self.datetime = dt.datetime(2026, 6, 16, 10, 15, 44)


def _item(name='20260616-101544'):
    return FakeRecording(name)


def test_region_filename():
    assert region_filename('20260616-101544', 18, 22.5) == \
        '20260616-101544_18.000-22.500s.wav'


def test_export_region_writes_pascals_interleaved(tmp_path):
    left = np.linspace(-1, 1, 100)
    right = np.linspace(2, -2, 100)
    path = export_region(tmp_path, 'rec', [left, right], FS,
                         {'region': (1, 1.1), 'filter': {'mode': 'High-pass'}})
    assert path.name == 'rec_1.000-1.100s.wav'
    with pytest.warns(wavfile.WavFileWarning):  # scipy skips the CFTS chunk
        fs, data = wavfile.read(path)
    assert fs == FS
    np.testing.assert_allclose(data[:, 0], left, rtol=1e-6)
    np.testing.assert_allclose(data[:, 1], right, rtol=1e-6)
    assert read_calibration_wav_metadata(path)['filter'] == {'mode': 'High-pass'}


def test_export_region_never_overwrites(tmp_path):
    y = np.zeros(10)
    meta = {'region': (0, 1)}
    first = export_region(tmp_path, 'rec', [y], FS, meta)
    second = export_region(tmp_path, 'rec', [y], FS, meta)
    third = export_region(tmp_path, 'rec', [y], FS, meta)
    assert [p.name for p in (first, second, third)] == \
        ['rec_0.000-1.000s.wav', 'rec_0.000-1.000s_2.wav', 'rec_0.000-1.000s_3.wav']


def test_clipping_peak():
    assert clipping_peak(np.array([0.5, -19.9])) is None
    assert clipping_peak(np.array([0.5, -25.0])) == 25.0
    assert clipping_peak(np.array([])) is None


def test_playback_uses_a_fixed_scale_and_clips():
    y = np.array([0, 10, -20, 40])
    samples, fs = playback_samples(y, 48000)
    assert fs == 48000
    np.testing.assert_allclose(samples, [0, 0.5, -1, 1])
    assert samples.dtype == np.float32


def test_playback_resamples_for_the_device():
    y = np.sin(2 * np.pi * 1000 * np.arange(100000) / 100000)
    samples, fs = playback_samples(y, 100000, device_fs=48000)
    assert fs == 48000
    assert len(samples) == 48000


class FakeSounddevice:
    '''Stands in for the sounddevice module.'''

    def __init__(self, supported=(48000,)):
        self.supported = supported
        self.played = []
        self.stopped = 0

    def check_output_settings(self, samplerate):
        if samplerate not in self.supported:
            raise ValueError('Invalid sample rate')

    def query_devices(self, kind):
        return {'default_samplerate': self.supported[0]}

    def play(self, samples, fs):
        self.played.append((samples, fs))

    def stop(self):
        self.stopped += 1


@pytest.fixture
def fake_sd(monkeypatch):
    sd = FakeSounddevice()
    monkeypatch.setitem(sys.modules, 'sounddevice', sd)
    timers = []
    import enaml.application
    monkeypatch.setattr(enaml.application, 'timed_call',
                        lambda ms, f, *args: timers.append((ms, f, args)))
    return sd, timers


def test_player_plays_scaled_and_finishes(fake_sd):
    sd, timers = fake_sd
    player = Player()
    y = np.full(48000, PLAYBACK_FULL_SCALE_PA / 2)
    player.play(y, 48000)
    assert player.playing
    samples, fs = sd.played[0]
    assert fs == 48000
    np.testing.assert_allclose(samples, 0.5)
    # Marked finished once the sound has had time to end (1 s + margin).
    ms, finished, args = timers[0]
    assert ms == 1200
    finished(*args)
    assert not player.playing


def test_player_resamples_when_device_cannot_play_rate(fake_sd):
    sd, timers = fake_sd
    Player().play(np.zeros(100000), 100000)
    samples, fs = sd.played[0]
    assert fs == 48000
    assert len(samples) == 48000


def test_player_stop_and_stale_timer(fake_sd):
    sd, timers = fake_sd
    player = Player()
    player.play(np.zeros(4800), 48000)
    player.stop()
    assert not player.playing
    assert sd.stopped == 1
    player.play(np.zeros(4800), 48000)
    # The first sound's timer mustn't end the second one.
    _, finished, args = timers[0]
    finished(*args)
    assert player.playing


################################################################################
# The plot manager and the view
################################################################################
@pytest.fixture
def manager(qt_app, monkeypatch):
    from psiaudio.calibration import FlatCalibration
    with enaml.imports():
        from cftscal.plugins.input_recording.view import InputRecordingPlotManager
    # The data below has no plot lines to redraw when the filter changes.
    monkeypatch.setattr(InputRecordingPlotManager, '_update_all', lambda self: None)
    manager = InputRecordingPlotManager()
    manager.component  # builds the plots, as showing the view does
    manager.filter_mode = 'Unfiltered'
    item = _item()
    x = np.arange(10 * FS) / FS
    manager.data = {
        (item, 'ai0'): {'x': x, 'y': x.copy(), 'fs': FS,
                        'calibration': FlatCalibration.unity()},
        (item, 'ai1'): {'x': x, 'y': -x, 'fs': FS,
                        'calibration': FlatCalibration.unity()},
    }
    manager.region_select.setRegion((2, 3))
    return manager, item


def test_region_signals_are_the_selected_region(manager):
    manager, item = manager
    entry, = manager.region_signals()
    assert entry['item'] is item
    assert entry['region'] == (2, 3)
    (ch0, y0), (ch1, y1) = entry['channels']
    assert (ch0, ch1) == ('ai0', 'ai1')
    assert len(y0) == FS
    assert y0[0] == pytest.approx(2) and y1[0] == pytest.approx(-2)


def test_region_signals_are_filtered(manager):
    manager, item = manager
    manager.filter_mode = 'High-pass'
    (ch, y), _ = manager.region_signals()[0]['channels']
    # A ramp is almost all low frequency: the high-pass removes most of it.
    assert np.abs(y).max() < 0.5


def test_channel_region(manager):
    manager, item = manager
    y, fs = manager.channel_region((item, 'ai1'))
    assert fs == FS and y[0] == pytest.approx(-2)
    manager.region_select.setRegion((20, 30))
    assert manager.channel_region((item, 'ai1')) is None


@pytest.mark.parametrize('mode, expected', [
    ('High-pass', {'mode': 'High-pass', 'cutoff_hz': 20, 'order': 3}),
    ('Unfiltered', {'mode': 'Unfiltered'}),
    ('Band-pass', {'mode': 'Band-pass', 'center_hz': 1000,
                   'width_octaves': pytest.approx(1 / 3), 'order': 4}),
])
def test_filter_settings(manager, mode, expected):
    manager, item = manager
    manager.filter_mode = mode
    assert manager.filter_settings() == expected


def test_export_regions_with_metadata(manager, tmp_path):
    manager, item = manager
    manager.filter_mode = 'High-pass'
    with enaml.imports():
        from cftscal.plugins.input_recording.view import export_regions
    path, = export_regions(tmp_path, manager.region_signals(),
                           manager.filter_settings())
    assert path.name == '20260616-101544_2.000-3.000s.wav'
    meta = read_calibration_wav_metadata(path)
    assert meta['region'] == [2, 3]
    assert meta['filter'] == {'mode': 'High-pass', 'cutoff_hz': 20, 'order': 3}
    assert meta['channels'] == ['ai0', 'ai1']
    assert meta['sensors']['ai1']['label'] == 'Right Input'
    assert meta['units'] == 'Pa'
    with pytest.warns(wavfile.WavFileWarning):
        assert wavfile.read(path)[1].shape == (FS, 2)


def test_buttons_follow_region_and_playback(qt_app, tmp_path, monkeypatch):
    monkeypatch.setenv('CFTSCAL_ROOT', str(tmp_path))
    with enaml.imports():
        from enaml.widgets.api import Window
        from cftscal.plugins.input_recording.view import InputRecordingView
    from cftscal.plugins.input_recording.settings import InputRecordingSettings
    view = InputRecordingView(settings=InputRecordingSettings({'Ch 0': 'ai0'}))
    window = Window()
    view.set_parent(window)
    window.show()
    try:
        buttons = {w.text: w for w in view.traverse()
                   if type(w).__name__ == 'PushButton'}
        play, export = buttons['Play region'], buttons['Export region\u2026']
        assert not play.enabled and not export.enabled
        canvas, = [w for w in view.traverse() if type(w).__name__ == 'PGCanvas']
        canvas.manager.analysis = [{'duration': 1.0, 'color': 'red',
                                    'recording': 'r', 'channel': 'c'}]
        assert play.enabled and export.enabled
        view.player.playing = True
        assert play.text == 'Stop'
    finally:
        window.close()


################################################################################
# Initial time window
################################################################################
def _with_length(manager, seconds):
    from psiaudio.calibration import FlatCalibration
    x = np.arange(int(seconds * FS)) / FS
    manager.data = {(_item(f'rec{seconds}'), 'ai0'): {
        'x': x, 'y': x, 'fs': FS, 'calibration': FlatCalibration.unity()}}


def test_long_recording_opens_on_first_90_s(manager):
    manager, item = manager
    _with_length(manager, 300)
    manager._show_initial_window()
    (x0, x1), _ = manager.time_vb.viewRange()
    assert (x0, x1) == pytest.approx((0, 90))


def test_short_recording_fills_the_plot(manager):
    manager, item = manager
    _with_length(manager, 300)
    manager._show_initial_window()
    _with_length(manager, 30)
    manager._show_initial_window()
    # Back on auto-range, so the 30 s recording isn't squeezed into 90 s.
    assert manager.time_vb.autoRangeEnabled()[0]


def test_initial_window_is_adjustable(manager):
    manager, item = manager
    manager.initial_window = 20
    _with_length(manager, 60)
    manager._show_initial_window()
    (x0, x1), _ = manager.time_vb.viewRange()
    assert (x0, x1) == pytest.approx((0, 20))
