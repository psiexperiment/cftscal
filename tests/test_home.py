'''
The Home workspace (cftscal/plugins/home_view.enaml and its wiring in
cftscal/plugins/manifest.enaml): a tile per available calibration
workspace, shown at startup.
'''
import importlib
from types import SimpleNamespace

import enaml
import pytest

with enaml.imports():
    from cftscal.plugins import manifest as manifest_module
    from cftscal.plugins.home_view import (
        TILE_LINES, TILE_WRAP, WORKSPACES_POINT, list_tiles, tile_text,
    )
    from cftscal.plugins.manifest import (
        HOME_WORKSPACE, TO_REGISTER, CalibrationManifest, workspace_settings,
    )


def _plugin_classes():
    with enaml.imports():
        return [getattr(importlib.import_module(m), c) for m, c in TO_REGISTER]


@pytest.fixture
def workbench():
    '''
    A workbench with the calibration and UI manifests registered (the UI
    plugin itself is never started) and the Speaker and Input Recording
    plugins, registered out of menu order.
    '''
    from enaml.workbench.api import Workbench
    with enaml.imports():
        from enaml.workbench.core.core_manifest import CoreManifest
        from enaml.workbench.ui.ui_manifest import UIManifest
        from cftscal.plugins.input_recording.manifest import InputRecordingManifest
        from cftscal.plugins.speaker.manifest import SpeakerManifest
    wb = Workbench()
    wb.register(CoreManifest())
    wb.register(UIManifest())
    wb.register(CalibrationManifest())
    wb.register(InputRecordingManifest(rank=3))
    wb.register(SpeakerManifest(rank=2))
    return wb


################################################################################
# Tiles
################################################################################
def test_tile_text_wraps_and_pads_to_same_height():
    short = tile_text('Title', 'One line.')
    long = tile_text('Title', 'word ' * 40)
    assert short.split('\n') == ['Title', 'One line.'] + [''] * (TILE_LINES - 1)
    # Every tile has the title plus TILE_LINES lines, long or short.
    assert len(short.split('\n')) == len(long.split('\n')) == TILE_LINES + 1
    assert all(len(line) <= TILE_WRAP for line in long.split('\n')[1:])


def test_list_tiles_in_menu_order_without_home(workbench):
    tiles = list_tiles(workbench, 'calibration')
    assert [t['title'] for t in tiles] == ['Speaker Calibration', 'Input Recording']
    assert [t['workspace'] for t in tiles] == ['speaker.workspace',
                                               'input-recording.workspace']
    assert all(t['icon'] is not None for t in tiles)
    assert tiles[0]['text'].startswith('Speaker Calibration\nMeasure a speaker')


class TestHomeView:

    @pytest.fixture
    def home(self, qt_app, workbench):
        with enaml.imports():
            from enaml.widgets.api import Window
            from cftscal.plugins.home_view import HomeView
        window = Window()
        view = HomeView(window, workbench=workbench)
        window.show()
        yield view, workbench
        window.close()

    def _tiles(self, view):
        return [b.text.split('\n')[0] for b in view.traverse()
                if type(b).__name__ == 'PushButton']

    def test_shows_a_tile_per_workspace(self, home):
        view, wb = home
        assert self._tiles(view) == ['Speaker Calibration', 'Input Recording']

    def test_tiles_follow_plugins(self, home):
        view, wb = home
        with enaml.imports():
            from cftscal.plugins.ir_sensor.manifest import IRSensorManifest
        wb.register(IRSensorManifest(rank=4))
        assert self._tiles(view)[-1] == 'IR Sensor Calibration'
        wb.unregister('ir-sensor')
        assert 'IR Sensor Calibration' not in self._tiles(view)

    def test_clicking_a_tile_opens_its_workspace(self, home, monkeypatch):
        view, wb = home
        core = wb.get_plugin('enaml.workbench.core')
        invoked = []
        # An Atom object: its methods can only be replaced on the class.
        monkeypatch.setattr(type(core), 'invoke_command',
                            lambda self, command, params=None, trigger=None:
                                invoked.append((command, params)))
        button = [b for b in view.traverse() if type(b).__name__ == 'PushButton'][1]
        button.clicked(False)
        assert invoked == [('enaml.workbench.ui.select_workspace',
                            {'workspace': 'input-recording.workspace'})]

    def test_closed_home_stops_listening(self, home):
        # Once another workspace replaces Home, plugin changes mustn't
        # reach the closed view (whose names enaml has cleared).
        view, wb = home
        view.destroy()
        with enaml.imports():
            from cftscal.plugins.ir_sensor.manifest import IRSensorManifest
        wb.register(IRSensorManifest(rank=4))
        point = wb.get_extension_point(WORKSPACES_POINT)
        wb.unregister('ir-sensor')
        assert point is not None

    def test_says_what_to_do_with_no_workspaces(self, qt_app):
        from enaml.workbench.api import Workbench
        with enaml.imports():
            from enaml.widgets.api import Window
            from enaml.workbench.ui.ui_manifest import UIManifest
            from cftscal.plugins.home_view import HomeView
        wb = Workbench()
        wb.register(UIManifest())
        window = Window()
        view = HomeView(window, workbench=wb)
        window.show()
        try:
            labels = [w.text for w in view.traverse() if type(w).__name__ == 'Label']
            assert any('Workspace > Settings' in text for text in labels)
        finally:
            window.close()


################################################################################
# Wiring in the calibration manifest
################################################################################
def test_home_is_a_registered_workspace(workbench):
    point = workbench.get_extension_point(WORKSPACES_POINT)
    assert HOME_WORKSPACE in [e.qualified_id for e in point.extensions]


def test_home_factory(qt_app, workbench):
    space = manifest_module.home_factory(workbench)
    assert space.window_title == 'Home'
    assert type(space.content).__name__ == 'HomeView'


def test_home_menu_item():
    items = [item for ext in CalibrationManifest().extensions
             for item in ext.children if getattr(item, 'path', '') == '/workspace/home']
    item, = items
    assert item.label == 'Home'
    assert item.parameters == {'workspace': HOME_WORKSPACE}


@pytest.mark.parametrize('cls', _plugin_classes(), ids=lambda c: c.__name__)
def test_every_plugin_has_a_description(cls):
    assert cls().description


@pytest.mark.parametrize('workspace, expected', [
    (None, None),
    (SimpleNamespace(content=None), None),
    (SimpleNamespace(content=SimpleNamespace()), None),  # Home, view-only
    (SimpleNamespace(content=SimpleNamespace(settings='s')), 's'),
])
def test_workspace_settings(workspace, expected):
    assert workspace_settings(workspace) == expected


@pytest.mark.parametrize('content', [None, SimpleNamespace()])
def test_set_defaults_does_nothing_without_settings(content):
    # Home and view-only workspaces: Set Defaults (Ctrl+D) used to raise.
    ui = SimpleNamespace(workspace=SimpleNamespace(content=content))
    event = SimpleNamespace(workbench=SimpleNamespace(get_plugin=lambda name: ui))
    manifest_module.set_defaults(event)


def test_set_defaults_saves_settings():
    saved = []
    settings = SimpleNamespace(save_config=lambda: saved.append(True))
    ui = SimpleNamespace(workspace=SimpleNamespace(content=SimpleNamespace(settings=settings)))
    event = SimpleNamespace(workbench=SimpleNamespace(get_plugin=lambda name: ui))
    manifest_module.set_defaults(event)
    assert saved == [True]


class _FakeWorkbench:

    def __init__(self, workspace):
        self.ui = SimpleNamespace(workspace=workspace)
        self.invoked = []
        self.core = SimpleNamespace(
            invoke_command=lambda command, params: self.invoked.append(params))

    def get_plugin(self, name):
        return self.ui if name.endswith('.ui') else self.core


def test_reload_shows_home_when_open_workspace_was_closed(monkeypatch):
    # Its plugin went away, leaving the empty workspace close_workspace()
    # puts in its place: show Home rather than an empty window.
    monkeypatch.setattr(manifest_module, 'TO_REGISTER', [])
    wb = _FakeWorkbench(SimpleNamespace(window_title='', content=None))
    manifest_module.reload_plugins(wb)
    assert wb.invoked == [{'workspace': HOME_WORKSPACE}]


def test_reload_leaves_home_alone(monkeypatch):
    monkeypatch.setattr(manifest_module, 'TO_REGISTER', [])
    wb = _FakeWorkbench(SimpleNamespace(window_title='Home', content=object()))
    manifest_module.reload_plugins(wb)
    assert wb.invoked == []
