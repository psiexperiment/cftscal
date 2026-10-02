'''
Selecting the analysis region on a time plot (RegionSelectViewBox and
RegionSelectItem in cftscal.plugins.widgets).

pyqtgraph hands a drag to the item under the mouse: the region's middle,
one of its edges, or (anywhere else) the view box. These tests send drag
events straight to each of those, the way pyqtgraph's scene does.
'''
import enaml
import pytest

from qtpy.QtCore import QPointF, Qt
from qtpy.QtWidgets import QApplication


class FakeDrag:
    '''The parts of a pyqtgraph MouseDragEvent these handlers use.'''

    def __init__(self, vb, x0, x, start=False, finish=False, ctrl=False):
        self._down = vb.mapViewToScene(QPointF(x0, 0.5))
        self._pos = vb.mapViewToScene(QPointF(x, 0.5))
        self._start, self._finish = start, finish
        self._modifiers = Qt.ControlModifier if ctrl else Qt.NoModifier
        self.accepted = False

    def button(self):
        return Qt.MouseButton.LeftButton

    def modifiers(self):
        return self._modifiers

    def isStart(self):
        return self._start

    def isFinish(self):
        return self._finish

    def buttonDownScenePos(self):
        return self._down

    def scenePos(self):
        return self._pos

    def accept(self):
        self.accepted = True

    def ignore(self):
        self.accepted = False


@pytest.fixture
def plot(qt_app):
    import pyqtgraph as pg
    with enaml.imports():
        from cftscal.plugins.widgets import RegionSelectItem, RegionSelectViewBox
    vb = RegionSelectViewBox()
    widget = pg.PlotWidget(viewBox=vb)
    widget.resize(600, 300)
    vb.setRange(xRange=(0, 20), yRange=(0, 1), padding=0)
    region = RegionSelectItem(values=(2, 18), movable=True)
    vb.addItem(region, ignoreBounds=True)
    vb.region_select = region
    finished = []
    region.sigRegionChangeFinished.connect(lambda r: finished.append(r.getRegion()))
    widget.show()
    QApplication.processEvents()
    yield vb, region, finished
    widget.close()


def _drag(handler, vb, x0, x1, ctrl):
    '''Send a three-event drag from x0 to x1 to ``handler``.'''
    events = [
        FakeDrag(vb, x0, x0 + (x1 - x0) / 2, start=True, ctrl=ctrl),
        FakeDrag(vb, x0, x1, ctrl=ctrl),
        FakeDrag(vb, x0, x1, finish=True, ctrl=ctrl),
    ]
    for ev in events:
        handler(ev)
    return events


def _region(region):
    return tuple(round(v, 3) for v in sorted(region.getRegion()))


@pytest.mark.parametrize('target', ['middle', 'left edge', 'right edge'])
def test_ctrl_drag_on_region_draws_new_region(plot, target):
    # Before RegionSelectItem, a Ctrl+drag starting on the region moved or
    # resized it instead, so a new region couldn't be drawn inside it.
    vb, region, finished = plot
    handler = {
        'middle': region.mouseDragEvent,
        'left edge': region.lines[0].mouseDragEvent,
        'right edge': region.lines[1].mouseDragEvent,
    }[target]
    events = _drag(handler, vb, 8, 12, ctrl=True)
    assert _region(region) == (8, 12)
    assert all(ev.accepted for ev in events)
    # The analysis recomputes once, at the end of the drag.
    assert len(finished) == 1


def test_ctrl_drag_elsewhere_draws_new_region(plot):
    vb, region, finished = plot
    region.setRegion((2, 4))
    finished.clear()
    _drag(vb.mouseDragEvent, vb, 10, 16, ctrl=True)
    assert _region(region) == (10, 16)
    assert len(finished) == 1


def test_releasing_ctrl_mid_drag_keeps_drawing(plot):
    vb, region, finished = plot
    start = FakeDrag(vb, 8, 9, start=True, ctrl=True)
    later = FakeDrag(vb, 8, 12, ctrl=False)
    end = FakeDrag(vb, 8, 12, finish=True, ctrl=False)
    for ev in (start, later, end):
        region.mouseDragEvent(ev)
    assert _region(region) == (8, 12)


@pytest.mark.parametrize('target, index', [('middle', None), ('edge', 1)])
def test_plain_drag_on_region_uses_normal_handling(plot, monkeypatch, target, index):
    # Without Ctrl, a drag on the middle still moves the region and one on
    # an edge still resizes it: the original handlers get every event.
    import pyqtgraph as pg
    vb, region, finished = plot
    seen = []
    drawn = []
    monkeypatch.setattr(type(vb), 'draw_region', lambda self, ev: drawn.append(ev))
    if target == 'middle':
        monkeypatch.setattr(pg.LinearRegionItem, 'mouseDragEvent',
                            lambda self, ev: seen.append(ev))
        handler = region.mouseDragEvent
    else:
        # The edge's own handler was wrapped when the region was made;
        # build a fresh region so the wrapper picks up the spy.
        monkeypatch.setattr(pg.InfiniteLine, 'mouseDragEvent',
                            lambda self, ev: seen.append(ev))
        with enaml.imports():
            from cftscal.plugins.widgets import RegionSelectItem
        region = RegionSelectItem(values=(2, 18), movable=True)
        vb.addItem(region, ignoreBounds=True)
        handler = region.lines[index].mouseDragEvent
    events = _drag(handler, vb, 8, 12, ctrl=False)
    assert seen == events
    assert drawn == []
