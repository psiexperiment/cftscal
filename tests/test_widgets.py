'''
Tests for :mod:`cftscal.plugins.widgets`.
'''
import enaml
import pytest

with enaml.imports():
    from cftscal.plugins.widgets import BasePlotManager, SensorView, _remove_selected

import pyqtgraph as pg


class TestCreatePlot:
    '''
    create_plot() must build a ``pg.PlotDataItem``, not a bare
    ``pg.PlotCurveItem`` -- autoDownsample/clipToView/downsampleMethod are
    only ever read by PlotDataItem's own getData()/updateItems(), which
    decimates to the current view range/pixel width before handing the
    reduced data down to the PlotCurveItem it wraps internally. A bare
    PlotCurveItem accepts those same constructor kwargs into self.opts but
    never looks at them again, so every point still goes straight into
    the painted path on every repaint regardless -- silently a no-op that
    made every plot built via create_plot() (input_recording foremost,
    but also inear/input_amplifier/ir_sensor/microphone/speaker/starship)
    unusably slow for a several-second, 100 kHz recording.
    '''

    def test_returns_a_plot_data_item(self):
        manager = BasePlotManager()
        color, plot = manager.create_plot()
        assert isinstance(plot, pg.PlotDataItem)
        assert not isinstance(plot, pg.PlotCurveItem)

    def test_downsampling_options_are_set(self):
        manager = BasePlotManager()
        color, plot = manager.create_plot()
        assert plot.opts['autoDownsample'] is True
        assert plot.opts['clipToView'] is True
        # 'peak' (min/max envelope per pixel bucket), not the default
        # naive 'subsample', so transients don't visually disappear.
        assert plot.opts['downsampleMethod'] == 'peak'
        assert plot.opts['skipFiniteCheck'] is True

    def test_create_empty_plots_wraps_a_plot_data_item(self):
        # create_empty_plots() is what TimePSDPlotManager.get_plots()
        # actually calls (input_recording, inear, etc.) -- lock in that
        # the same fix applies through that path too.
        manager = BasePlotManager()
        color, plots = manager.create_empty_plots()
        assert len(plots) == 1
        assert isinstance(plots[0], pg.PlotDataItem)


@pytest.fixture(scope='module')
def qt_app():
    '''
    A single QtApplication for the rendering tests below.  Skips the
    whole module's Qt tests (rather than failing) on a headless box where
    a QtApplication can't be created -- the rest of the suite is
    deliberately Qt-free, so we don't want to introduce a hard display
    dependency.
    '''
    try:
        from enaml.qt.qt_application import QtApplication
        app = QtApplication.instance() or QtApplication()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f'QtApplication unavailable: {exc}')
    return app


def _find(widget, type_name):
    '''Recursively collect descendant widgets whose type name matches.'''
    found = []
    for child in widget.children:
        if type(child).__name__ == type_name:
            found.append(child)
        found.extend(_find(child, type_name))
    return found


def _build_sensor_view(qt_app, sensor, mode):
    with enaml.imports():
        from enaml.widgets.api import Window, Container
    win = Window()
    container = Container(win)
    view = SensorView(container, sensor=sensor, mode=mode, label='X')
    # show() forces the declarative children (incl. the Conditional
    # branches) to materialize so _find() can see the resolved widgets.
    win.show()
    return view


class TestSensorViewRoles:
    '''
    SensorView renders both sensor roles: a SensorDevice (free-form
    device-ID picker bound to ``available_devices``) and a
    SensorReference (existing-calibration picker bound to
    ``available_references``).  The two branches are mutually exclusive,
    keyed on ``hasattr(sensor, 'available_devices')`` -- a regression
    here (e.g. the reference branch trying to read ``available_devices``
    off a device sensor, or vice versa) is exactly what broke when the
    generic-microphone/measurement-microphone plugins moved off their
    hand-rolled device combos onto this shared widget.
    '''

    def test_device_mode_binds_available_devices(self, qt_app):
        from cftscal.plugins.settings import SensorDevice
        dev = SensorDevice()
        dev.available_devices = ['SN001', 'SN002']
        dev.name = 'SN001'

        view = _build_sensor_view(qt_app, dev, mode='device')
        combos = _find(view, 'ObjectCombo')
        assert combos, 'device-mode SensorView rendered no combo'
        # First combo is the device picker; it must reflect
        # available_devices, not a reference list.
        device_combo = combos[0]
        assert list(device_combo.items) == ['SN001', 'SN002']
        assert device_combo.selected == 'SN001'

    def test_device_mode_has_add_remove_buttons(self, qt_app):
        from cftscal.plugins.settings import SensorDevice
        dev = SensorDevice()
        dev.available_devices = ['SN001']
        dev.name = 'SN001'

        view = _build_sensor_view(qt_app, dev, mode='device')
        buttons = _find(view, 'PushButton')
        labels = sorted(b.text for b in buttons)
        assert labels == ['+', '-'], labels

    def test_device_remove_writes_back_to_model(self, qt_app):
        # The "-" button routes through _remove_selected(device_select),
        # whose two-way `items :=` binding must propagate back to the
        # sensor's available_devices list.
        from cftscal.plugins.settings import SensorDevice
        dev = SensorDevice()
        dev.available_devices = ['SN001', 'SN002']
        dev.name = 'SN001'

        view = _build_sensor_view(qt_app, dev, mode='device')
        device_combo = _find(view, 'ObjectCombo')[0]
        _remove_selected(device_combo)
        assert dev.available_devices == ['SN002']
        assert dev.name == 'SN002'

    def test_static_reference_has_no_add_remove(self, qt_app):
        # A static reference picker exposes no +/- buttons and, crucially,
        # never touches available_devices (which it doesn't have).
        from cftscal.plugins.settings import MeasurementMicrophoneReference
        ref = MeasurementMicrophoneReference()
        assert not hasattr(ref, 'available_devices')

        view = _build_sensor_view(qt_app, ref, mode='static')
        assert _find(view, 'PushButton') == []
        # Instance combo still renders (bound to available_references).
        assert _find(view, 'ObjectCombo')
