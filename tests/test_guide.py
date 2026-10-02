'''
The user guide inside the app: Home's User Guide panel and each
workspace's Help tab (cftscal/plugins/guide_view.py, help_tab.enaml), the
offline copy bundled into the package (tools/build_guide.py), and the
workspace icons on Home's tiles.

A real QWebEngineView starts a Chromium process, so the web view is
replaced by a plain widget that records what it was asked to load.
'''
import importlib
import importlib.util
from pathlib import Path
import sys
import tarfile
from types import ModuleType
import zipfile

import enaml
import pytest

from cftscal.plugins import guide_view
from cftscal.plugins.guide_view import GUIDE_URL, guide_url

REPO = Path(__file__).parents[1]


@pytest.fixture
def fake_web_engine(monkeypatch, qt_app):
    '''Replace QtWebEngineWidgets with a QWebEngineView that only records.'''
    from qtpy.QtWidgets import QWidget

    class FakeWebView(QWidget):
        def load(self, url):
            self.loaded = url.toString()

    module = ModuleType('qtpy.QtWebEngineWidgets')
    module.QWebEngineView = FakeWebView
    monkeypatch.setitem(sys.modules, 'qtpy.QtWebEngineWidgets', module)
    return FakeWebView


@pytest.fixture
def bundled(tmp_path, monkeypatch):
    '''A bundled guide with a home page and one plugin page.'''
    guide = tmp_path / 'guide'
    (guide / 'plugins').mkdir(parents=True)
    (guide / 'index.html').write_text('<html></html>')
    (guide / 'plugins' / 'speaker.html').write_text('<html></html>')
    monkeypatch.setattr(guide_view, 'files', lambda package: tmp_path)
    return guide


@pytest.fixture
def not_bundled(tmp_path, monkeypatch):
    monkeypatch.setattr(guide_view, 'files', lambda package: tmp_path)


################################################################################
# Where the guide opens
################################################################################
def test_bundled_copy_is_preferred(bundled, qt_app):
    assert guide_url() == (bundled / 'index.html').as_uri()
    assert guide_url('plugins/speaker') == (bundled / 'plugins' / 'speaker.html').as_uri()


def test_website_when_page_not_bundled(bundled, qt_app):
    assert guide_url('plugins/starship') == GUIDE_URL + 'plugins/starship/'


def test_website_when_nothing_bundled(not_bundled, qt_app):
    assert guide_url() == GUIDE_URL
    assert guide_url('concepts') == GUIDE_URL + 'concepts/'


def _show(browser_kwargs):
    with enaml.imports():
        from enaml.widgets.api import Container, Window
    window = Window()
    browser = guide_view.GuideBrowser(Container(window), **browser_kwargs)
    window.show()
    return window, browser


def test_browser_loads_the_page(fake_web_engine, bundled):
    window, browser = _show({'page': 'plugins/speaker'})
    try:
        assert isinstance(browser.view, fake_web_engine)
        assert browser.view.loaded == (bundled / 'plugins' / 'speaker.html').as_uri()
    finally:
        window.close()


def test_link_when_web_engine_is_missing(monkeypatch, qt_app):
    # E.g. a packaged build that leaves QtWebEngine out.
    monkeypatch.setitem(sys.modules, 'qtpy.QtWebEngineWidgets', None)
    window, browser = _show({})
    try:
        assert type(browser.view).__name__ == 'QLabel'
        assert GUIDE_URL in browser.view.text()
        assert browser.view.openExternalLinks()
    finally:
        window.close()


def test_prepare_web_engine_fails_soft(monkeypatch):
    monkeypatch.setitem(sys.modules, 'qtpy.QtWebEngineWidgets', None)
    guide_view.prepare_web_engine()


################################################################################
# Help tab on every workspace
################################################################################
def _plugin_manifests():
    with enaml.imports():
        from cftscal.plugins.manifest import TO_REGISTER
        for module_name, class_name in TO_REGISTER:
            yield getattr(importlib.import_module(module_name), class_name)()


@pytest.mark.parametrize('manifest', list(_plugin_manifests()), ids=lambda m: m.id)
def test_every_workspace_has_help_tab(manifest, fake_web_engine, tmp_path, monkeypatch):
    monkeypatch.setenv('CFTSCAL_ROOT', str(tmp_path))
    with enaml.imports():
        from enaml.widgets.api import DockArea, Window
        from cftscal.plugins.help_tab import HelpDockItem
        from cftscal.plugins.manifest import workspace_factory
    space = workspace_factory(None, manifest)
    area, = [w for w in space.content.traverse() if isinstance(w, DockArea)]
    tab, = [w for w in area.children if isinstance(w, HelpDockItem)]
    assert tab.title == 'Help' and not tab.closable
    assert tab.page == manifest.help_page
    # A dock bar (a tab on the left edge), not a column of the layout.
    main, = [layout for layout in area.layout.items if not layout.floating]
    bars = [(bar.position, list(bar.items)) for bar in main.dock_bars]
    assert ('left', ['help']) in [(p, [i.name for i in items]) for p, items in bars]

    window = Window()
    space.content.set_parent(window)
    window.show()
    try:
        browser, = [w for w in tab.traverse() if type(w).__name__ == 'GuideBrowser']
        assert browser.page == manifest.help_page
    finally:
        window.close()


@pytest.mark.parametrize('manifest', list(_plugin_manifests()), ids=lambda m: m.id)
def test_help_page_is_in_the_guide(manifest):
    assert (REPO / 'docs' / f'{manifest.help_page}.md').is_file()


def test_no_help_tab_without_dock_area(qt_app):
    with enaml.imports():
        from enaml.widgets.api import Container
        from cftscal.plugins.help_tab import add_help_tab
    assert add_help_tab(Container(), 'plugins/speaker') is None


################################################################################
# Bundling the guide into releases
################################################################################
@pytest.fixture
def build_guide():
    spec = importlib.util.spec_from_file_location(
        'build_guide', REPO / 'tools' / 'build_guide.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _wheel(path, names):
    with zipfile.ZipFile(path, 'w') as z:
        for name in names:
            z.writestr(name, '')


def _sdist(path, names):
    with tarfile.open(path, 'w:gz') as t:
        for name in names:
            info = tarfile.TarInfo(f'cftscal-1.0/{name}')
            t.addfile(info)


def test_check_passes_when_both_packages_have_the_guide(build_guide, tmp_path):
    names = ['cftscal/__init__.py', 'cftscal/guide/index.html']
    _wheel(tmp_path / 'cftscal-1.0-py3-none-any.whl', names)
    _sdist(tmp_path / 'cftscal-1.0.tar.gz', names)
    assert build_guide.check(tmp_path) == 0


def test_check_counts_packages_missing_the_guide(build_guide, tmp_path):
    _wheel(tmp_path / 'cftscal-1.0-py3-none-any.whl', ['cftscal/__init__.py'])
    _sdist(tmp_path / 'cftscal-1.0.tar.gz', ['cftscal/guide/index.html'])
    assert build_guide.check(tmp_path) == 1


def test_check_fails_with_no_packages(build_guide, tmp_path):
    assert build_guide.check(tmp_path) == 1


def test_release_workflow_builds_and_checks_the_guide():
    workflow = (REPO / '.github' / 'workflows' / 'publish-to-pypi.yml').read_text()
    build = workflow.index('python tools/build_guide.py\n')
    package = workflow.index('--sdist')
    check = workflow.index('tools/build_guide.py --check dist')
    assert build < package < check


def test_sdist_includes_the_guide():
    # setuptools_scm leaves untracked files (the built guide) out of the
    # sdist without this.
    assert 'graft cftscal/guide' in (REPO / 'MANIFEST.in').read_text()


################################################################################
# Workspace icons
################################################################################
@pytest.mark.parametrize('manifest', list(_plugin_manifests()), ids=lambda m: m.id)
def test_every_workspace_icon_loads(manifest, qt_app):
    from cftscal.plugins.branding import load_workspace_icon
    icon = load_workspace_icon(manifest.icon)
    assert icon is not None and icon.images


def test_unknown_icon(qt_app):
    from cftscal.plugins.branding import load_workspace_icon
    assert load_workspace_icon('no-such-icon') is None


def test_icons_are_drawn_in_navy(qt_app):
    from qtpy.QtGui import QColor, QImage
    from cftscal.plugins.branding import WORKSPACE_ICON_COLOR, load_workspace_icon
    image = QImage()
    image.loadFromData(load_workspace_icon('microphone').images[0].image.data, 'PNG')
    assert image.width() == 96
    opaque = {image.pixelColor(x, y).name() for x in range(96) for y in range(96)
              if image.pixelColor(x, y).alpha() == 255}
    assert opaque == {QColor(WORKSPACE_ICON_COLOR).name()}


def test_icon_license_is_bundled():
    assert (REPO / 'cftscal' / 'icons' / 'workspaces' / 'LICENSE').is_file()
