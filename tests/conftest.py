import os

import pytest

from .fakes import FakeEvent


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    '''
    Give every test its own empty configuration file.

    cftscal reads and writes ordinary psi settings now rather than a
    workspace.json of its own, so a test that builds a settings object
    would otherwise read the developer's real configuration and
    save_config() would write into it. Only the settings tests used to
    redirect it, and only by remembering to.

    The environment overrides both the defaults and the file, so every
    setting set there is removed too: e.g., a machine with CFTSCAL_IO set
    to the keyboard manifest failed every test of which IO manifest is
    picked.
    '''
    from psi import config as psi_config

    settings = set(psi_config.setting_names())
    for name in list(os.environ):
        if name in settings or name.startswith(('PSI_', 'CFTSCAL_')):
            monkeypatch.delenv(name)
    monkeypatch.setenv('PSI_CONFIG_FILE', str(tmp_path / 'config.toml'))
    # The folder cftscal kept its settings in before config.toml. Pointed
    # somewhere empty so that starting cftscal in a test does not migrate
    # the developer's own old settings files (see
    # cftscal.migrate_settings).
    monkeypatch.setenv('PSI_CONFIG', str(tmp_path / 'legacy'))
    psi_config.reload_config()
    yield
    psi_config.reload_config()


@pytest.fixture
def event(monkeypatch):
    '''
    A workbench event for a paradigm's initialization handler, with an
    empty environment so a test only sees the variables it sets itself.
    '''
    monkeypatch.setattr(os, 'environ', {})
    return FakeEvent()


@pytest.fixture(scope='session')
def qt_app():
    '''
    A single QtApplication for tests that render widgets.  Skips the
    Qt tests (rather than failing) on a headless box where
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
