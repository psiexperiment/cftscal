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
