'''
Tests for :mod:`cftscal.migrate_settings`, which moves cftscal's old JSON
settings files into ``config.toml`` on machines that have no ``config.py``
to run ``psi-config migrate`` on.

``conftest.isolated_config`` already points ``PSI_CONFIG_FILE`` and
``PSI_CONFIG`` (the legacy folder) at the test's own temporary directory.
'''
import json
from pathlib import Path

import pytest

from psi import get_config, save_config
from psi.config import load_config

from cftscal.migrate_settings import (
    MARKER_FILENAME, get_legacy_folder, migrate_legacy_settings,
    plan_migration,
)


WORKSPACE = {
    'data_path': 'C:/Calibration',
    'hw_mode': 'Sound Card',
    'custom_io_path': '',
    'custom_io_class': 'IOManifest',
    'selected_device_name': 'ASIO Fireface USB',
    'selected_device_hostapi': 'ASIO',
    'sample_rate': 96000.0,
    'enabled_plugins': ['speaker'],
}


@pytest.fixture
def legacy():
    '''The legacy folder, as a cftscal-only machine would have it.'''
    folder = get_legacy_folder()
    (folder / 'cfts' / 'calibration').mkdir(parents=True)
    return folder


def write_workspace(folder, data):
    path = folder / 'cfts' / 'workspace.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    return path


def write_plugin(folder, name, data):
    path = folder / 'cfts' / 'calibration' / name
    path.write_text(json.dumps(data), encoding='utf-8')
    return path


def test_legacy_folder_follows_psi_config(tmp_path):
    assert get_legacy_folder() == tmp_path / 'legacy'


def test_legacy_folder_defaults_to_home(monkeypatch):
    monkeypatch.delenv('PSI_CONFIG')
    assert get_legacy_folder() == Path('~/psi').expanduser()


def test_nothing_to_migrate(tmp_path):
    assert migrate_legacy_settings() == {}
    assert not (tmp_path / 'config.toml').exists()
    assert not (get_legacy_folder() / 'cfts').exists()


def test_migrates_workspace_and_plugins(legacy):
    write_workspace(legacy, WORKSPACE)
    write_plugin(legacy, 'speaker.json', {'output': 'speaker_1'})
    write_plugin(legacy, 'microphone-measurement.json', {'gain': 20})

    migrate_legacy_settings()

    assert get_config('CFTSCAL_ROOT') == Path('C:/Calibration')
    assert get_config('CFTSCAL_DEVICE_NAME') == 'ASIO Fireface USB'
    assert get_config('CFTSCAL_DEVICE_HOSTAPI') == 'ASIO'
    assert get_config('CFTSCAL_SAMPLE_RATE') == 96000.0
    assert get_config('CFTSCAL_ENABLED_PLUGINS') == ['speaker']
    # Keyed by the filename, which is what CalibrationSettings.load_config
    # looks up.
    assert get_config('CFTSCAL_PLUGIN') == {
        'speaker.json': {'output': 'speaker_1'},
        'microphone-measurement.json': {'gain': 20},
    }


def test_plugins_only(legacy):
    # A machine where the workspace was never configured, but plugins were
    # used.
    write_plugin(legacy, 'speaker.json', {'output': 'speaker_1'})
    migrate_legacy_settings()
    assert get_config('CFTSCAL_PLUGIN') == {
        'speaker.json': {'output': 'speaker_1'},
    }


def test_legacy_workspace_keys(legacy):
    # A workspace.json from before hw_mode and the device host API.
    write_workspace(legacy, {
        'data_path': 'C:/Calibration',
        'hw_configuration': 'C:/io/rig.enaml::RigIO',
        'selected_device': 'Lynx',
    })
    migrate_legacy_settings()
    assert get_config('CFTSCAL_IO') == 'C:/io/rig.enaml::RigIO'
    assert get_config('CFTSCAL_DEVICE_NAME') == 'Lynx'


def test_existing_settings_are_kept(legacy):
    save_config({
        'CFTSCAL_ROOT': 'D:/Newer',
        'CFTSCAL_PLUGIN': {'speaker.json': {'output': 'newer'}},
    })
    write_workspace(legacy, WORKSPACE)
    write_plugin(legacy, 'speaker.json', {'output': 'older'})
    write_plugin(legacy, 'starship.json', {'gain': 40})

    migrate_legacy_settings()

    assert get_config('CFTSCAL_ROOT') == Path('D:/Newer')
    assert get_config('CFTSCAL_DEVICE_NAME') == 'ASIO Fireface USB'
    assert get_config('CFTSCAL_PLUGIN') == {
        'speaker.json': {'output': 'newer'},
        'starship.json': {'gain': 40},
    }
    note = (legacy / 'cfts' / MARKER_FILENAME).read_text(encoding='utf-8')
    assert 'CFTSCAL_ROOT is already in' in note
    assert 'CFTSCAL_PLUGIN."speaker.json" is already in' in note


def test_other_settings_in_config_file_survive(legacy):
    save_config({'PSI_DATA_ROOT': 'D:/data'})
    write_workspace(legacy, WORKSPACE)
    migrate_legacy_settings()
    assert load_config()['PSI_DATA_ROOT'] == 'D:/data'


def test_writes_marker_and_leaves_old_files(legacy, tmp_path):
    workspace = write_workspace(legacy, WORKSPACE)
    migrate_legacy_settings()
    note = (legacy / 'cfts' / MARKER_FILENAME).read_text(encoding='utf-8')
    assert str(tmp_path / 'config.toml') in note
    assert 'workspace.json: data_path -> CFTSCAL_ROOT' in note
    assert json.loads(workspace.read_text()) == WORKSPACE


def test_runs_only_once(legacy):
    write_workspace(legacy, WORKSPACE)
    migrate_legacy_settings()

    # A setting removed from config.toml on purpose must not come back.
    save_config({'CFTSCAL_ROOT': None})
    assert migrate_legacy_settings() == {}
    assert 'CFTSCAL_ROOT' not in load_config()
    assert plan_migration() == ({}, [])


def test_unreadable_workspace_is_recorded_not_retried(legacy):
    (legacy / 'cfts' / 'workspace.json').write_text('{not json')
    write_plugin(legacy, 'speaker.json', {'output': 'speaker_1'})

    migrate_legacy_settings()

    assert get_config('CFTSCAL_PLUGIN') == {
        'speaker.json': {'output': 'speaker_1'},
    }
    note = (legacy / 'cfts' / MARKER_FILENAME).read_text(encoding='utf-8')
    assert 'workspace.json: could not be read' in note


def test_plan_writes_nothing(legacy, tmp_path):
    write_workspace(legacy, WORKSPACE)
    updates, notes = plan_migration()
    assert updates['CFTSCAL_ROOT'] == 'C:/Calibration'
    assert notes
    assert not (tmp_path / 'config.toml').exists()
    assert not (legacy / 'cfts' / MARKER_FILENAME).exists()


def test_workspace_settings_load_migrated_values(legacy):
    '''
    End to end: the values land where WorkspaceSettings reads them.
    '''
    from cftscal.plugins.workspace import WorkspaceSettings

    write_workspace(legacy, WORKSPACE)
    migrate_legacy_settings()

    settings = WorkspaceSettings()
    settings.load_config()
    assert settings.data_path == Path('C:/Calibration')
    assert settings.hw_mode == 'sound-card'
    assert settings.selected_device_name == 'ASIO Fireface USB'
    assert settings.enabled_plugins == ['speaker']
