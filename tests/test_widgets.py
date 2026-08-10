'''
Tests for :mod:`cftscal.plugins.widgets` -- currently just
``BasePlotManager.create_plot()``.
'''
import enaml

with enaml.imports():
    from cftscal.plugins.widgets import BasePlotManager

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
