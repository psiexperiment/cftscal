'''
Input Recording's "Emulate Measure Sound" mode: Measure Sound's calculations
(cftscal/plugins/input_recording/measure_sound.py) and how the plot manager
and view use them.
'''
from pathlib import Path
from types import SimpleNamespace

import enaml
import numpy as np
import pytest
from scipy import signal

from psiaudio.calibration import FlatCalibration

from cftscal.plugins.input_recording import measure_sound as ms


def _tone(frequency, fs, seconds=1, level=94):
    '''A tone at ``level`` dB SPL, in pascals.'''
    t = np.arange(int(seconds * fs)) / fs
    return np.sqrt(2) * 20e-6 * 10 ** (level / 20) * np.sin(2 * np.pi * frequency * t)


################################################################################
# The calculations
################################################################################
def test_correction_factors():
    assert [ms.correction_factor(i) for i in range(4)] == [1.165, 1.187, 1, 1]


@pytest.mark.parametrize('frequency, expected', [
    (50, -30.27), (125, -16.19), (1000, 0.0), (4000, 0.96), (16000, -6.71),
])
def test_a_weighting_power_is_the_curve_as_a_power_ratio(frequency, expected):
    assert 10 * np.log10(ms.a_weighting_power(np.array([frequency]))[0]) == \
        pytest.approx(expected, abs=0.01)


#: dBA of 94 dB SPL tones, from Measure Sound's own estimateLevel and
#: filterA run in MATLAB R2026b.
MATLAB_DBA = {
    (65536, 50): 30.45, (65536, 1000): 90.99, (65536, 4000): 92.92,
    (65536, 16000): 77.58, (131072, 50): 33.46, (131072, 1000): 94.00,
    (131072, 4000): 95.93, (131072, 16000): 80.59,
}


@pytest.mark.parametrize('fs, frequency', sorted(MATLAB_DBA))
def test_dba_matches_measure_sound_in_matlab(fs, frequency):
    assert ms.dba(_tone(frequency, fs), fs) == \
        pytest.approx(MATLAB_DBA[fs, frequency], abs=0.01)


@pytest.mark.parametrize('frequency, expected', [
    # Measure Sound's filter applies a first-order band-pass twice: its
    # band edges (250 Hz and 4 kHz for 1 kHz, 4 octaves) are 6 dB down.
    (250, -6.02), (1000, 0.0), (4000, -6.02), (125, -14.65), (8000, -15.75),
])
def test_band_pass(frequency, expected):
    fs = 48000
    y = np.sin(2 * np.pi * frequency * np.arange(4 * fs) / fs)
    out = ms.band_pass(y, fs, 1000, 4)
    middle = slice(len(y) // 4, -len(y) // 4)
    gain = 20 * np.log10(np.std(out[middle]) / np.std(y[middle]))
    assert gain == pytest.approx(expected, abs=0.05)


def test_band_pass_pads_as_matlab_does():
    # MATLAB's filtfilt pads 3 * (filter length - 1) samples; SciPy's
    # default is 3 * filter length.
    fs = 48000
    y = np.random.default_rng(0).normal(size=fs)
    b, a = signal.butter(1, [250 / (fs / 2), 4000 / (fs / 2)], 'bandpass')
    np.testing.assert_allclose(ms.band_pass(y, fs, 1000, 4),
                               signal.filtfilt(b, a, y, padlen=6))
    assert np.isnan(ms.band_pass(y[:5], fs, 1000, 4)).all()


def test_levels_limit_max_and_min_at_zero():
    # Measure Sound looks for the maximum and minimum with everything
    # outside the window set to 0.
    levels = ms.levels(np.array([0.5, 1.0, 0.75]), 48000)
    assert levels['max_pa'] == 1.0 and levels['min_pa'] == 0
    # Its equivalent RMS: ((|max| + |min|) / 2) / sqrt(2).
    assert levels['pe'] == pytest.approx(20 * np.log10(0.5 / np.sqrt(2) / 20e-6))


#: The recording the numbers in the user guide's worked example come from.
REAL_RECORDING = Path(r'C:\Users\buran\Downloads\anechoic chamber recordings'
                      r'\iPad3 60 dB Calibrated PART 1kHz-1.mat')


@pytest.mark.skipif(not REAL_RECORDING.exists(), reason='recording not available')
def test_real_recording_matches_measure_sound():
    # The values Measure Sound shows for this recording's left channel.
    from cftscal.objects import MatInputRecording
    sig = MatInputRecording('x', REAL_RECORDING).load().Channel_1_Data
    levels = ms.levels(sig[0] * ms.correction_factor(0), sig.fs)
    assert levels['rms'] == pytest.approx(61.7285, abs=1e-4)
    assert levels['dba'] == pytest.approx(34.4108, abs=1e-4)
    assert levels['pe'] == pytest.approx(73.0518, abs=1e-4)
    assert levels['max_pa'] == pytest.approx(0.12492, abs=1e-5)
    assert levels['min_pa'] == pytest.approx(-0.12928, abs=1e-5)


################################################################################
# The plot manager
################################################################################
FS = 48000


class Recording:
    '''The parts of a recording the plot manager reads.'''
    sensors = {'ai0': {'label': 'Left'}, 'ai1': {'label': 'Right'},
               'ai2': {'label': 'Third'}}
    datetime = '2026-10-08 12:00:00'


@pytest.fixture
def manager(qt_app):
    with enaml.imports():
        from cftscal.plugins.input_recording.view import InputRecordingPlotManager
    manager = InputRecordingPlotManager(apply_calibration=True)
    manager.component  # builds the plots, as showing the view does
    item = Recording()
    plot = SimpleNamespace(setData=lambda *args: None)
    y = _tone(1000, FS, seconds=2)
    manager.data = {
        (item, channel): {
            'x': np.arange(len(y)) / FS, 'y': y, 'fs': FS, 'color': 'red',
            'calibration': FlatCalibration.unity(), 'channel': channel,
            'time_plot': [plot], 'psd_plot': [plot],
            'ms_factor': ms.correction_factor(i),
        }
        for i, channel in enumerate(item.sensors)
    }
    manager.region_select.setRegion((0.5, 1.5))
    return manager, item


def _rms(manager):
    manager._update_analysis()
    return {entry['channel']: entry['rms'] for entry in manager.analysis}


def test_emulation_applies_the_correction_factors(manager):
    manager, item = manager
    # Unfiltered, as emulation switches the default High-pass to.
    manager.filter_mode = 'Unfiltered'
    standard = _rms(manager)
    manager.emulate_measure_sound = True
    emulated = _rms(manager)
    assert emulated['Left'] - standard['Left'] == pytest.approx(20 * np.log10(1.165))
    assert emulated['Right'] - standard['Right'] == pytest.approx(20 * np.log10(1.187))
    assert emulated['Third'] == pytest.approx(standard['Third'])


def test_emulation_offers_only_measure_sounds_filters(manager):
    manager, item = manager
    manager.filter_mode = 'dBA'
    manager.emulate_measure_sound = True
    assert manager.filter_mode == 'Unfiltered'
    manager.emulate_measure_sound = False
    assert manager.filter_mode == 'dBA'
    # A Band-pass is kept, and kept when emulation is turned off.
    manager.filter_mode = 'Band-pass'
    manager.emulate_measure_sound = True
    assert manager.filter_mode == 'Band-pass'
    manager.emulate_measure_sound = False
    assert manager.filter_mode == 'Band-pass'


def test_emulation_leaves_the_users_settings_alone(manager):
    manager, item = manager
    manager.emulate_measure_sound = True
    manager.emulate_measure_sound = False
    assert manager.zero_phase is False
    assert manager.exact_a_weighting is False
    assert manager.filter_order == 4


def test_emulated_band_pass_filters_the_whole_recording(manager):
    # As Measure Sound does: filter everything, then measure the window.
    manager, item = manager
    manager.filter_mode = 'Band-pass'
    manager.filter_bw = 4
    manager.emulate_measure_sound = True
    d = manager.data[(item, 'ai0')]
    expected = ms.band_pass(d['y'], FS, 1000, 4) * 1.165
    np.testing.assert_allclose(d['displayed'], expected)
    m = (d['x'] >= 0.5) & (d['x'] < 1.5)
    manager._update_analysis()
    left = manager.analysis[0]
    assert left['rms'] == pytest.approx(ms.levels(expected[m], FS)['rms'])
    assert left['dba'] == pytest.approx(ms.dba(expected[m], FS))


def test_play_and_export_use_the_emulated_signal(manager):
    manager, item = manager
    manager.filter_mode = 'Band-pass'
    manager.emulate_measure_sound = True
    entry, = manager.region_signals()
    d = manager.data[(item, 'ai1')]
    m = (d['x'] >= 0.5) & (d['x'] < 1.5)
    (_, left), (_, right), (_, third) = entry['channels']
    np.testing.assert_allclose(right, d['displayed'][m])
    assert entry['correction_factors'] == {'ai0': 1.165, 'ai1': 1.187, 'ai2': 1.0}
    y, fs = manager.channel_region((item, 'ai1'))
    np.testing.assert_allclose(y, right)
    assert manager.filter_settings() == {
        'mode': 'Band-pass', 'emulate_measure_sound': True, 'center_hz': 1000,
        'width_octaves': pytest.approx(1 / 3), 'order': 1, 'zero_phase': True,
    }
    with enaml.imports():
        from cftscal.plugins.input_recording.view import region_metadata
    item.sensors = Recording.sensors
    item.generator, item.filename = 'gen', Path('rec')
    item.datetime = SimpleNamespace(isoformat=lambda: '2026-10-08T12:00:00')
    meta = region_metadata(entry, manager.filter_settings())
    assert meta['correction_factors'] == entry['correction_factors']


################################################################################
# The view
################################################################################
def test_view_controls(qt_app, tmp_path, monkeypatch):
    monkeypatch.setenv('CFTSCAL_ROOT', str(tmp_path))
    from qtpy.QtWidgets import QApplication
    with enaml.imports():
        from enaml.widgets.api import Window
        from cftscal.plugins.input_recording.view import InputRecordingView
    from cftscal.plugins.input_recording.settings import InputRecordingSettings
    view = InputRecordingView(settings=InputRecordingSettings({'Ch 0': 'ai0'}))
    window = Window()
    view.set_parent(window)
    window.show()
    try:
        manager, = [w.manager for w in view.traverse()
                    if type(w).__name__ == 'PGCanvas']
        boxes = {w.text: w for w in view.traverse() if type(w).__name__ == 'CheckBox'}
        combo, = [w for w in view.traverse() if type(w).__name__ == 'ObjectCombo'
                  and w.items and 'Unfiltered' in w.items]
        manager.filter_mode = 'Band-pass'
        QApplication.processEvents()
        order, = [w for w in view.traverse() if type(w).__name__ == 'IntField'
                  and w.proxy_is_active]
        assert order.value == 4 and order.enabled

        boxes['Emulate Measure Sound'].checked = True
        QApplication.processEvents()
        assert manager.emulate_measure_sound
        assert combo.items == ['Unfiltered', 'Band-pass']
        # Zero-phase shows ticked (Measure Sound's filter is zero-phase)
        # without changing the setting.
        assert boxes['Zero-phase'].checked and not boxes['Zero-phase'].enabled
        assert manager.zero_phase is False
        assert not boxes['Exact A-weighting'].enabled
        assert order.value == 1 and not order.enabled
        assert manager.filter_order == 4

        boxes['Emulate Measure Sound'].checked = False
        QApplication.processEvents()
        assert combo.items == ['High-pass', 'Unfiltered', 'dBA', 'Band-pass']
        assert not boxes['Zero-phase'].checked and boxes['Zero-phase'].enabled
        assert boxes['Exact A-weighting'].enabled
        assert order.value == 4 and order.enabled
        assert manager.zero_phase is False and manager.filter_order == 4
    finally:
        window.close()
