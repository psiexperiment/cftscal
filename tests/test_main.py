'''
Light integration check that :func:`cftscal.main.main` seeds default
layout/preferences before starting the workbench event loop -- not a
full app-launch test (that would need a real Qt event loop/hardware
environment), just confirming the wiring and call order.
'''
import cftscal.main as main_module


def test_seeds_default_state_before_running_workbench(monkeypatch):
    calls = []
    monkeypatch.setattr(
        main_module, 'seed_all_default_state',
        lambda: calls.append('seed'),
    )
    monkeypatch.setattr(
        main_module.CalibrationWorkbench, 'run',
        lambda self, obj=None: calls.append('run'),
    )
    monkeypatch.setattr('sys.argv', ['cfts-cal'])

    main_module.main()

    assert calls == ['seed', 'run']



def test_icon_has_every_size_windows_uses():
    from cftscal.plugins.branding import load_app_icon
    assert len(load_app_icon().images) == 7  # 16 to 256 px, from the .ico


def test_application_icon_is_set(qt_app):
    from qtpy.QtWidgets import QApplication
    main_module.set_application_icon()
    sizes = {s.width() for s in QApplication.windowIcon().availableSizes()}
    assert {16, 32, 48, 256} <= sizes


def test_application_icon_set_before_window_shows(monkeypatch):
    # The taskbar takes its icon when the window first shows; set later,
    # it only appeared once a workspace was loaded.
    from types import SimpleNamespace
    calls = []
    ui = SimpleNamespace(show_window=lambda: calls.append('show'),
                         start_application=lambda: None,
                         invoke_command=lambda *args: None)
    monkeypatch.setattr(main_module, 'set_application_icon',
                        lambda: calls.append('icon'))
    monkeypatch.setattr(main_module, 'deferred_call', lambda *a, **k: None)
    monkeypatch.setattr(main_module.CalibrationWorkbench, 'register',
                        lambda self, m: None)
    monkeypatch.setattr(main_module.CalibrationWorkbench, 'unregister',
                        lambda self, m: None)
    monkeypatch.setattr(main_module.CalibrationWorkbench, 'get_plugin',
                        lambda self, name: ui)
    main_module.CalibrationWorkbench().run()
    assert calls == ['icon', 'show']


def _run(monkeypatch, obj):
    '''Run CalibrationWorkbench.run with stand-in plugins; return the
    deferred calls it made.'''
    from types import SimpleNamespace
    deferred = []
    ui = SimpleNamespace(show_window=lambda: None, start_application=lambda: None,
                         invoke_command=lambda *args: None)
    monkeypatch.setattr(main_module, 'set_application_icon', lambda: None)
    monkeypatch.setattr(main_module, 'deferred_call',
                        lambda f, *args: deferred.append(args))
    monkeypatch.setattr(main_module.CalibrationWorkbench, 'register',
                        lambda self, m: None)
    monkeypatch.setattr(main_module.CalibrationWorkbench, 'unregister',
                        lambda self, m: None)
    monkeypatch.setattr(main_module.CalibrationWorkbench, 'get_plugin',
                        lambda self, name: ui)
    main_module.CalibrationWorkbench().run(obj)
    return [args for args in deferred if args and args[0] ==
            'enaml.workbench.ui.select_workspace']


def test_opens_on_home(monkeypatch):
    assert _run(monkeypatch, None) == [
        ('enaml.workbench.ui.select_workspace', {'workspace': 'calibration.home'})]


def test_opens_workspace_named_on_command_line(monkeypatch):
    assert _run(monkeypatch, 'speaker') == [
        ('enaml.workbench.ui.select_workspace', {'workspace': 'speaker.workspace'})]


def test_web_engine_prepared_before_running(monkeypatch):
    # QtWebEngine has to be loaded before the Qt application exists.
    from cftscal.plugins import guide_view
    calls = []
    monkeypatch.setattr(main_module, 'seed_all_default_state', lambda: None)
    monkeypatch.setattr(guide_view, 'prepare_web_engine', lambda: calls.append('web'))
    monkeypatch.setattr(main_module.CalibrationWorkbench, 'run',
                        lambda self, obj=None: calls.append('run'))
    monkeypatch.setattr('sys.argv', ['cfts-cal'])
    main_module.main()
    assert calls == ['web', 'run']
