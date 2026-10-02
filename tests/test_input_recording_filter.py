'''
Input Recording's plot filter (InputRecordingPlotManager._y_transform):
what is applied to a recording before it is plotted and its level measured.
'''
import enaml
import numpy as np
import pytest

FS = 10000


@pytest.fixture
def manager(qt_app):
    with enaml.imports():
        from cftscal.plugins.input_recording.view import InputRecordingPlotManager
    return InputRecordingPlotManager()


def _tone(frequency, seconds=4):
    t = np.arange(int(seconds * FS)) / FS
    return np.sin(2 * np.pi * frequency * t)


def _gain_db(manager, frequency):
    # Level ratio in the middle of the recording, away from the edges.
    y = _tone(frequency)
    out = manager._y_transform(y, FS)
    middle = slice(len(y) // 4, -len(y) // 4)
    return 20 * np.log10(np.std(out[middle]) / np.std(y[middle]))


def test_high_pass_20_hz_is_the_default(manager):
    assert manager.filter_mode == 'High-pass'
    assert manager.highpass_fc == 20
    assert manager.highpass_order == 3


def test_high_pass_removes_rumble_and_keeps_the_signal(manager):
    assert _gain_db(manager, 5) < -35
    assert abs(_gain_db(manager, 1000)) < 0.01


def test_high_pass_matches_12aq(manager):
    # GRAS 12AQ HP filter: 3-pole Butterworth, -3 dB at 20 Hz, so
    # |H|^2 = 1 / (1 + (fc/f)^6): -18.1 dB an octave below.
    assert _gain_db(manager, 20) == pytest.approx(-3.01, abs=0.1)
    assert _gain_db(manager, 10) == pytest.approx(-18.13, abs=0.2)


def test_high_pass_follows_cutoff(manager):
    manager.highpass_fc = 100
    assert _gain_db(manager, 100) == pytest.approx(-3.01, abs=0.1)
    assert _gain_db(manager, 20) < -35


def test_higher_order_cuts_more_steeply(manager):
    low_order = _gain_db(manager, 10)
    manager.highpass_order = 4
    assert _gain_db(manager, 10) < low_order - 5


def test_high_pass_has_no_spike_from_dc_offset(manager):
    # A tone riding on a DC offset: starting the filter from rest would
    # turn the offset into a step, ringing at the start of the plot.
    y = 0.5 + _tone(1000)
    out = manager._y_transform(y, FS)
    assert np.abs(out[:FS // 10]).max() < 1.05


def test_unfiltered_is_untouched(manager):
    manager.filter_mode = 'Unfiltered'
    y = _tone(5)
    assert manager._y_transform(y, FS) is y


@pytest.mark.parametrize('member, value', [('highpass_fc', 50), ('highpass_order', 4)])
def test_changing_high_pass_redraws(manager, monkeypatch, member, value):
    calls = []
    monkeypatch.setattr(type(manager), '_update_all', lambda self: calls.append(1))
    setattr(manager, member, value)
    assert calls == [1]


def test_band_pass_bandwidth(manager):
    # 1000 Hz center, 4 octaves wide: 250 Hz to 4 kHz, the band-pass in the
    # lab's older MATLAB tool. Run forwards and backwards, so -6 dB at the
    # band edges.
    manager.filter_mode = 'Band-pass'
    manager.filter_bw = 4
    assert abs(_gain_db(manager, 1000)) < 0.1
    assert _gain_db(manager, 250) == pytest.approx(-6.02, abs=0.2)
    assert _gain_db(manager, 4000) == pytest.approx(-6.02, abs=0.2)
    assert _gain_db(manager, 60) < -40


def test_band_pass_defaults_to_one_third_octave(manager):
    assert manager.filter_bw == pytest.approx(1 / 3)
    manager.filter_mode = 'Band-pass'
    # 1/3 octave around 1 kHz is about 891 to 1122 Hz.
    assert _gain_db(manager, 1000) > -0.1
    assert _gain_db(manager, 500) < -40


################################################################################
# Analysis table measurements
################################################################################
#: Sampling rate for the level tests -- typical of real recordings. At
#: 10 kHz the digital A-weighting filter is already 0.2 dB off at 1 kHz
#: (see a_weighting_sos).
LEVEL_FS = 100000


def _peak_tone(frequency, seconds=1):
    '''A 1 Pa-peak cosine: unlike a sine, its samples land on the peaks.'''
    t = np.arange(int(seconds * LEVEL_FS)) / LEVEL_FS
    return np.cos(2 * np.pi * frequency * t)


def _levels(y, y_unfiltered=None):
    with enaml.imports():
        from cftscal.plugins.input_recording.view import region_levels
    return region_levels(y, y if y_unfiltered is None else y_unfiltered, LEVEL_FS)


def test_pure_tone_levels():
    # A 1 kHz tone with a 1 Pa peak: RMS 1/sqrt(2) Pa = 90.97 dB SPL.
    levels = _levels(_peak_tone(1000))
    assert levels['rms'] == pytest.approx(90.97, abs=0.01)
    # peSPL is the RMS of a sine with the same peak-to-peak, so a pure
    # tone's peSPL is its RMS level...
    assert levels['pe'] == pytest.approx(levels['rms'], abs=0.01)
    # ...while Peak SPL (half the peak-to-peak) is 3 dB above it.
    assert levels['peak'] == pytest.approx(levels['rms'] + 3.01, abs=0.01)
    assert levels['max_pa'] == pytest.approx(1, abs=1e-3)
    assert levels['min_pa'] == pytest.approx(-1, abs=1e-3)


def test_dba_matches_spl_at_1_khz_and_drops_at_low_frequencies():
    tone = _levels(_peak_tone(1000))
    assert tone['dba'] == pytest.approx(tone['rms'], abs=0.1)
    # A-weighting is -30.2 dB at 50 Hz.
    low = _levels(_peak_tone(50))
    assert low['rms'] - low['dba'] == pytest.approx(30.2, abs=0.3)


def test_dba_ignores_the_filter_setting():
    # dBA comes from the unfiltered region, whatever the Filter is.
    raw = _peak_tone(1000)
    assert _levels(raw * 0.1, raw)['dba'] == pytest.approx(_levels(raw)['dba'])


def test_asymmetric_waveform_max_and_min():
    y = _peak_tone(1000) + 0.5
    levels = _levels(y)
    assert levels['max_pa'] == pytest.approx(1.5, abs=1e-3)
    assert levels['min_pa'] == pytest.approx(-0.5, abs=1e-3)
    # Peak-to-peak is unchanged by the offset.
    assert levels['peak'] == pytest.approx(_levels(_peak_tone(1000))['peak'], abs=0.01)


def test_view_has_new_columns_and_band_pass_controls(qt_app, tmp_path, monkeypatch):
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
        table, = [w for w in view.traverse() if type(w).__name__ == 'ListDictTable']
        canvas, = [w for w in view.traverse() if type(w).__name__ == 'PGCanvas']
        # Transposed: a row per measurement, a column per channel.
        canvas.manager.analysis = [
            {'color': 'red', 'recording': '2026-06-16 10:15:44',
             'channel': 'Right Input', 'duration': 4, 'rms': 104.6,
             'dba': 105.8, 'pe': 104.4, 'peak': 107.4, 'max_pa': 6.511,
             'min_pa': -6.402},
        ]
        assert [table.get_row_label(i) for i in range(len(table.data))] == \
            ['', 'Dur (s)', 'dB SPL', 'dBA', 'peSPL', 'Peak SPL', 'Max (Pa)',
             'Min (Pa)']
        assert table.get_columns() == ['c0']
        assert table.column_info['c0']['label'] == 'Right Input\n2026-06-16 10:15:44'
        assert [row['c0'] for row in table.data] == \
            ['', '4.00', '104.6', '105.8', '104.4', '107.4', '6.511', '-6.402']
        assert table.get_cell_color(0, 0) == 'red'
        assert table.get_cell_color(2, 0) == 'white'
        canvas.manager.filter_mode = 'Band-pass'
        QApplication = __import__('qtpy.QtWidgets', fromlist=['QApplication']).QApplication
        QApplication.processEvents()
        combos = [w for w in view.traverse() if type(w).__name__ == 'ObjectCombo'
                  and w.proxy_is_active and w.items and w.items[0] == 1 / 3]
        combo, = combos
        assert [combo.to_string(i) for i in combo.items] == \
            ['1/3', '1/2', '1', '2', '3', '4']
        combo.selected = 4
        assert canvas.manager.filter_bw == 4
    finally:
        window.close()


#: A-weighting in dB at standard frequencies (IEC 61672-1).
A_WEIGHTING = {31.5: -39.4, 63: -26.2, 125: -16.1, 250: -8.6, 500: -3.2,
               1000: 0.0, 2000: 1.2, 4000: 1.0, 8000: -1.1}


@pytest.mark.parametrize('frequency, expected', sorted(A_WEIGHTING.items()))
def test_dba_follows_the_a_weighting_curve(manager, frequency, expected):
    # Both the dBA Filter setting and the dBA column. The A-weighting used
    # to be applied forwards and backwards, which doubled it (e.g. -78.8
    # dB at 31.5 Hz); only 1 kHz, where it is 0 dB, came out right.
    y = _peak_tone(frequency, seconds=2)
    manager.filter_mode = 'dBA'
    out = manager._y_transform(y, LEVEL_FS)
    middle = slice(len(y) // 4, -len(y) // 4)
    mode_db = 20 * np.log10(np.std(out[middle]) / np.std(y[middle]))
    assert mode_db == pytest.approx(expected, abs=0.2)
    levels = _levels(y)
    assert levels['dba'] - levels['rms'] == pytest.approx(expected, abs=0.2)


def _entry(channel, recording, **levels):
    entry = {'color': 'red', 'recording': recording, 'channel': channel,
             'duration': 4.0}
    entry.update(dict.fromkeys(('rms', 'dba', 'pe', 'peak', 'max_pa', 'min_pa'), 90.0))
    entry.update(levels)
    return entry


def test_transpose_puts_channels_side_by_side():
    with enaml.imports():
        from cftscal.plugins.input_recording.view import transpose_analysis
    rows, info = transpose_analysis([
        _entry('Right Input', '2026-06-16 10:15:44', dba=105.8),
        _entry('Left Input', '2026-06-16 10:12:47', dba=107.6),
    ])
    assert list(info) == ['c0', 'c1']
    assert info['c1']['label'] == 'Left Input\n2026-06-16 10:12:47'
    # The dBA row (index 3) holds both channels' values.
    assert rows[3] == {'c0': '105.8', 'c1': '107.6'}


def test_transpose_empty_region_shows_dashes():
    with enaml.imports():
        from cftscal.plugins.input_recording.view import transpose_analysis
    nan = float('nan')
    rows, info = transpose_analysis([
        _entry('Ch 0', '2026-01-01 00:00:00', rms=nan, dba=nan, pe=nan,
               peak=nan, max_pa=nan, min_pa=nan, duration=0)])
    assert [r['c0'] for r in rows] == \
        ['', '0.00', '–', '–', '–', '–', '–', '–']


def test_transpose_nothing_plotted():
    with enaml.imports():
        from cftscal.plugins.input_recording.view import transpose_analysis
    assert transpose_analysis([]) == ([], {})
