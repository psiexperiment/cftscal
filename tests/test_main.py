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
        main_module, 'migrate_legacy_settings',
        lambda: calls.append('migrate'),
    )
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

    assert calls == ['migrate', 'seed', 'run']


def test_failed_migration_does_not_stop_startup(monkeypatch):
    def fail():
        raise RuntimeError('boom')

    calls = []
    monkeypatch.setattr(main_module, 'migrate_legacy_settings', fail)
    monkeypatch.setattr(main_module, 'seed_all_default_state', lambda: None)
    monkeypatch.setattr(
        main_module.CalibrationWorkbench, 'run',
        lambda self, obj=None: calls.append('run'),
    )
    monkeypatch.setattr('sys.argv', ['cfts-cal'])

    main_module.main()

    assert calls == ['run']
