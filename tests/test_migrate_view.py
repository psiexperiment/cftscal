'''
Tests for the GUI side of importing old settings: the dialog that asks,
the check cftscal runs once its window is up, and the Workspace > Settings
import. The decisions themselves are tested in test_migrate_settings.py.
'''
import json
from pathlib import Path

import enaml
import pytest

from psi import get_config, save_config

from cftscal.migrate_settings import (
    IMPORT, LATER, NEVER, get_legacy_folder, is_migrated
)

with enaml.imports():
    from cftscal.plugins import manifest as manifest_module
    from cftscal.plugins.migrate_view import ImportSettingsDialog


@pytest.fixture
def legacy():
    folder = get_legacy_folder()
    cfts = folder / 'cfts'
    (cfts / 'calibration').mkdir(parents=True)
    (cfts / 'workspace.json').write_text(
        json.dumps({'data_path': 'C:/Calibration'}), encoding='utf-8')
    return folder


def _buttons(dlg):
    return {w.text: w for w in dlg.traverse()
            if type(w).__name__ == 'PushButton'}


class TestDialog:

    @pytest.fixture
    def dialog(self, qt_app, legacy):
        dialogs = []

        def make(**kwargs):
            dlg = ImportSettingsDialog(**kwargs)
            dlg.show()
            dialogs.append(dlg)
            return dlg

        yield make
        for dlg in dialogs:
            dlg.destroy()

    @pytest.mark.parametrize('label, answer', [
        ('Import', IMPORT), ('Not now', LATER), ("Don't ask again", NEVER),
    ])
    def test_startup_buttons(self, dialog, label, answer):
        dlg = dialog()
        _buttons(dlg)[label].clicked(False)
        assert dlg.answer == answer

    def test_question_has_real_line_breaks(self, dialog):
        # Escapes in an f-string inside an enaml file come out literally.
        dlg = dialog()
        (label,) = [w for w in dlg.traverse() if type(w).__name__ == 'Label']
        assert '\\n' not in label.text
        assert label.text.count('\n') == 4

    def test_startup_has_no_replace_option(self, dialog):
        dlg = dialog()
        assert not [w for w in dlg.traverse()
                    if type(w).__name__ == 'CheckBox']

    def test_manual_has_no_dont_ask(self, dialog):
        dlg = dialog(manual=True)
        assert set(_buttons(dlg)) == {'Cancel', 'Import'}

    def test_import_disabled_when_nothing_new(self, dialog):
        save_config({'CFTSCAL_ROOT': 'D:/Newer'})
        dlg = dialog(manual=True)
        assert not _buttons(dlg)['Import'].enabled

    def test_replace_enables_import(self, dialog):
        save_config({'CFTSCAL_ROOT': 'D:/Newer'})
        dlg = dialog(manual=True)
        dlg.replace = True
        assert _buttons(dlg)['Import'].enabled
        assert dlg.plan[0] == {'CFTSCAL_ROOT': 'C:/Calibration'}

    def test_manual_ignores_marker(self, dialog):
        (get_legacy_folder() / 'cfts' / 'MIGRATED.txt').write_text('done')
        dlg = dialog(manual=True)
        assert dlg.plan[0] == {'CFTSCAL_ROOT': 'C:/Calibration'}


class TestCheckLegacySettings:

    def test_reloads_plugins_after_import(self, legacy, monkeypatch):
        reloaded = []
        monkeypatch.setattr(manifest_module, 'reload_plugins',
                            reloaded.append)
        monkeypatch.setattr(
            'cftscal.plugins.migrate_view.ask_to_import',
            lambda updates, notes: IMPORT)
        manifest_module.check_legacy_settings('workbench')
        assert reloaded == ['workbench']
        assert get_config('CFTSCAL_ROOT') == Path('C:/Calibration')

    def test_no_reload_when_not_imported(self, legacy, monkeypatch):
        reloaded = []
        monkeypatch.setattr(manifest_module, 'reload_plugins',
                            reloaded.append)
        monkeypatch.setattr(
            'cftscal.plugins.migrate_view.ask_to_import',
            lambda updates, notes: LATER)
        manifest_module.check_legacy_settings('workbench')
        assert reloaded == []

    def test_failure_does_not_raise(self, legacy, monkeypatch):
        def fail(ask):
            raise RuntimeError('boom')

        monkeypatch.setattr('cftscal.migrate_settings.startup_check', fail)
        manifest_module.check_legacy_settings('workbench')


class TestWorkspaceImport:

    def test_imports_and_reloads(self, legacy):
        from cftscal.plugins.workspace import WorkspaceSettings

        reloaded = []
        settings = WorkspaceSettings()
        settings._on_save = lambda: reloaded.append(True)
        updates = settings.import_legacy_settings()
        assert updates == {'CFTSCAL_ROOT': 'C:/Calibration'}
        assert settings.data_path == Path('C:/Calibration')
        assert reloaded == [True]
        assert is_migrated()

    def test_replace(self, legacy):
        from cftscal.plugins.workspace import WorkspaceSettings

        save_config({'CFTSCAL_ROOT': 'D:/Newer'})
        settings = WorkspaceSettings()
        settings.load_config()
        assert settings.import_legacy_settings() == {}
        assert settings.data_path == Path('D:/Newer')
        settings.import_legacy_settings(replace=True)
        assert settings.data_path == Path('C:/Calibration')


class TestWorkspaceSettingsButton:

    def _labels(self, qt_app):
        with enaml.imports():
            from cftscal.plugins.workspace_view import WorkspaceSettingsView
        from cftscal.plugins.workspace import WorkspaceSettings

        view = WorkspaceSettingsView(settings=WorkspaceSettings())
        view.show()
        try:
            return {w.text for w in view.traverse()
                    if type(w).__name__ == 'PushButton'}
        finally:
            view.destroy()

    def test_shown_with_old_files(self, qt_app, legacy):
        assert 'Import old settings...' in self._labels(qt_app)

    def test_hidden_without_old_files(self, qt_app):
        assert 'Import old settings...' not in self._labels(qt_app)


def _close_modal_soon():
    '''
    Close whichever modal dialog is up once its event loop is running, so a
    test can go through the real, blocking exec_() call.
    '''
    from qtpy.QtCore import QTimer
    from qtpy.QtWidgets import QApplication

    def close():
        widget = QApplication.activeModalWidget()
        if widget is None:
            QTimer.singleShot(10, close)
        else:
            widget.close()

    QTimer.singleShot(0, close)


class TestModal:
    '''
    Through the real exec_(), which the tests above bypass by calling
    show() -- and which is how the dialog is actually used.
    '''

    def test_ask_to_import(self, qt_app, legacy):
        with enaml.imports():
            from cftscal.plugins.migrate_view import ask_to_import
        _close_modal_soon()
        assert ask_to_import({}, []) == LATER

    def test_workspace_settings_button(self, qt_app, legacy):
        with enaml.imports():
            from cftscal.plugins.workspace_view import WorkspaceSettingsView
        from cftscal.plugins.workspace import WorkspaceSettings

        view = WorkspaceSettingsView(settings=WorkspaceSettings())
        view.show()
        try:
            button = [w for w in view.traverse()
                      if type(w).__name__ == 'PushButton'
                      and w.text == 'Import old settings...'][0]
            _close_modal_soon()
            button.clicked(False)
        finally:
            view.destroy()
        # Closed without choosing Import, so nothing was imported.
        assert not is_migrated()
