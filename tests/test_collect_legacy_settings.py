'''
Tests for `cftscal.migrate_settings.collect_legacy_settings`, which reads
the settings files cftscal kept in the legacy psi configuration folder.

It runs two ways: on cftscal's own startup (`migrate_legacy_settings`),
and from ``psi-config migrate`` through cftscal's ``psi.migrations`` entry
point. These tests moved here from psiexperiment along with the code.

``conftest.isolated_config`` already points ``PSI_CONFIG_FILE`` at the
test's own temporary directory.
'''
import json

import pytest

from psi import get_config
from psi.config import load_config

from cftscal.migrate_settings import collect_legacy_settings


@pytest.fixture
def folder(tmp_path):
    '''A legacy configuration folder.'''
    folder = tmp_path / 'psi'
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


def migrate_with_psi(folder, monkeypatch):
    '''
    Run ``psi-config migrate`` on a config.py in `folder`, with cftscal's
    conversion as the one installed package migration.
    '''
    import importlib.metadata
    from types import SimpleNamespace

    from psi.config_migrate import migrate

    entry = SimpleNamespace(name='cftscal',
                            load=lambda: collect_legacy_settings)
    monkeypatch.setattr(importlib.metadata, 'entry_points',
                        lambda group=None: [entry])
    source = folder / 'config.py'
    source.write_text("CAL_ROOT = 'C:/Calibration/from_config_py'\n",
                      encoding='utf-8')
    return migrate(source)


def test_empty_folder(tmp_path):
    assert collect_legacy_settings(tmp_path) == ({}, [])


def test_without_config_py(folder):
    # A machine that only ever ran cftscal has its settings and no
    # config.py, so they must be collectable from the folder alone.
    write_workspace(folder, {'data_path': 'C:/cal'})
    write_plugin(folder, 'speaker.json', {'a': 1})
    updates, _ = collect_legacy_settings(folder)
    assert updates == {
        'CFTSCAL_ROOT': 'C:/cal',
        'CFTSCAL_PLUGIN': {'speaker.json': {'a': 1}},
    }


def test_declared_as_a_psi_migration():
    from importlib.metadata import entry_points
    entries = {e.name: e for e in entry_points(group='psi.migrations')}
    assert entries['cftscal'].load() is collect_legacy_settings


class TestPluginTables:

    def test_keyed_by_the_name_cftscal_reads(self, folder):
        '''
        CalibrationSettings.settings_filename is 'microphone.json', and it
        is used verbatim as the key. Keying by the stem wrote a table
        nothing read.
        '''
        write_plugin(folder, 'microphone-measurement.json', {'gain': 20})
        updates, _ = collect_legacy_settings(folder)
        assert 'microphone-measurement.json' in updates['CFTSCAL_PLUGIN']
        assert 'microphone-measurement' not in updates['CFTSCAL_PLUGIN']

    def test_every_plugin_survives_psi_config_migrate(self, folder,
                                                      monkeypatch):
        for name in ('microphone-measurement.json', 'speaker.json',
                     'starship.json'):
            write_plugin(folder, name, {'name': name})
        migrate_with_psi(folder, monkeypatch)
        table = get_config('CFTSCAL_PLUGIN')
        assert set(table) == {
            'microphone-measurement.json', 'speaker.json', 'starship.json'}
        # The exact lookup in CalibrationSettings.load_config.
        assert table['speaker.json'] == {'name': 'speaker.json'}

    def test_unreadable_plugin_is_skipped_not_fatal(self, folder):
        write_plugin(folder, 'good.json', {'a': 1})
        bad = folder / 'cfts' / 'calibration' / 'bad.json'
        bad.write_text('{not json', encoding='utf-8')
        updates, notes = collect_legacy_settings(folder)
        assert 'good.json' in updates['CFTSCAL_PLUGIN']
        assert any('bad.json' in n and 'skipped' in n for n in notes)


class TestNullValues:
    '''
    A launcher writes these on a fresh install, where no device has been
    chosen yet. They used to abort the whole migration.
    '''

    def test_none_in_the_workspace_is_dropped(self, folder, monkeypatch):
        write_workspace(folder, {'data_path': 'C:/cal', 'sample_rate': None})
        updates, _ = collect_legacy_settings(folder)
        # Reported as the old file held it; dropping it is the writer's job.
        assert updates['CFTSCAL_SAMPLE_RATE'] is None

        migrate_with_psi(folder, monkeypatch)
        assert 'CFTSCAL_SAMPLE_RATE' not in load_config()

    def test_none_in_a_plugin_table_is_dropped(self, folder, monkeypatch):
        write_plugin(folder, 'microphone.json', {'gain': 20, 'device': None})
        migrate_with_psi(folder, monkeypatch)
        assert get_config('CFTSCAL_PLUGIN')['microphone.json'] == {'gain': 20}


class TestWorkspace:

    def test_wins_over_cal_root_in_config_py(self, folder, monkeypatch):
        '''
        Both name the calibration folder, and workspace.json is the one
        cftscal actually used, so it must not be clobbered by CAL_ROOT.
        '''
        write_workspace(folder, {'data_path': 'C:/Calibration/real'})
        migrate_with_psi(folder, monkeypatch)
        assert str(get_config('CFTSCAL_ROOT')) == r'C:\Calibration\real'

    def test_device_identity_is_carried_over(self, folder):
        write_workspace(folder, {'selected_device_name': 'Fireface',
                                 'selected_device_hostapi': 'ASIO',
                                 'sample_rate': 96000})
        updates, _ = collect_legacy_settings(folder)
        assert updates['CFTSCAL_DEVICE_NAME'] == 'Fireface'
        assert updates['CFTSCAL_DEVICE_HOSTAPI'] == 'ASIO'
        assert updates['CFTSCAL_SAMPLE_RATE'] == 96000

    def test_unreadable_workspace_is_not_fatal(self, folder):
        # A truncated workspace.json must not abort the conversion of
        # everything else -- the plugin reader already behaves this way.
        (folder / 'cfts' / 'workspace.json').write_text(
            '{not json', encoding='utf-8')
        write_plugin(folder, 'speaker.json', {'a': 1})
        updates, notes = collect_legacy_settings(folder)
        assert 'speaker.json' in updates['CFTSCAL_PLUGIN']
        assert any('workspace.json' in n for n in notes)


class TestWorkspaceIO:
    '''
    hw_mode, custom_io_path and custom_io_class chose the IO manifest
    between them. They are the one setting CFTSCAL_IO now.
    '''

    def collect_io(self, folder, data):
        write_workspace(folder, data)
        return collect_legacy_settings(folder)

    def test_sound_card(self, folder):
        updates, _ = self.collect_io(folder, {
            'hw_mode': 'Sound Card', 'custom_io_path': 'C:/io/stale.enaml'})
        assert updates['CFTSCAL_IO'] == 'sound-card'

    def test_custom_file(self, folder):
        updates, _ = self.collect_io(folder, {
            'hw_mode': 'Custom (Enaml IO manifest)',
            'custom_io_path': 'C:/io/rig.enaml', 'custom_io_class': 'RigIO'})
        assert updates['CFTSCAL_IO'] == 'C:/io/rig.enaml::RigIO'

    def test_custom_file_blank_class(self, folder):
        updates, _ = self.collect_io(folder, {
            'hw_mode': 'Custom (Enaml IO manifest)',
            'custom_io_path': 'C:/io/rig.enaml', 'custom_io_class': ' '})
        assert updates['CFTSCAL_IO'] == 'C:/io/rig.enaml::IOManifest'

    def test_custom_module_ignores_class(self, folder):
        # A dotted module path names its class itself; appending
        # ::IOManifest made a reference psi could not load.
        updates, _ = self.collect_io(folder, {
            'hw_mode': 'Custom (Enaml IO manifest)',
            'custom_io_path': 'pkg.io.Rig', 'custom_io_class': 'IOManifest'})
        assert updates['CFTSCAL_IO'] == 'pkg.io.Rig'

    def test_custom_without_file_is_left_to_default(self, folder):
        updates, notes = self.collect_io(folder, {
            'hw_mode': 'Custom (Enaml IO manifest)'})
        assert 'CFTSCAL_IO' not in updates
        assert any('no file was selected' in n for n in notes)

    def test_old_keys_are_not_written(self, folder):
        updates, _ = self.collect_io(folder, {'hw_mode': 'Sound Card'})
        assert not any(k.startswith(('CFTSCAL_HW', 'CFTSCAL_CUSTOM'))
                       for k in updates)

    def test_sound_card_warns_when_a_hostname_manifest_exists(
            self, folder, monkeypatch):
        import psi.application
        monkeypatch.setattr(psi.application, 'get_default_io',
                            lambda: 'C:/io/rig1.enaml')
        _, notes = self.collect_io(folder, {'hw_mode': 'Sound Card'})
        assert any('C:/io/rig1.enaml' in n for n in notes)


class TestLegacyWorkspaceKeys:
    '''
    Keys from before cftscal split them up. A machine that has not been
    updated since still depends on them.
    '''

    def test_sound_card(self, folder):
        write_workspace(folder, {'hw_configuration': 'Sound Card'})
        updates, _ = collect_legacy_settings(folder)
        assert updates['CFTSCAL_IO'] == 'sound-card'

    def test_custom_manifest(self, folder):
        # It was exactly what psi's --io was given.
        write_workspace(folder, {'hw_configuration': 'C:/io/rig.enaml::RigIO'})
        updates, _ = collect_legacy_settings(folder)
        assert updates['CFTSCAL_IO'] == 'C:/io/rig.enaml::RigIO'

    def test_selected_device(self, folder):
        write_workspace(folder, {'selected_device': 'Fireface'})
        updates, _ = collect_legacy_settings(folder)
        assert updates['CFTSCAL_DEVICE_NAME'] == 'Fireface'

    def test_current_keys_win(self, folder):
        write_workspace(folder, {
            'selected_device': 'Old',
            'selected_device_name': 'New',
            'hw_configuration': 'C:/io/rig.enaml',
            'hw_mode': 'Sound Card',
        })
        updates, notes = collect_legacy_settings(folder)
        assert updates['CFTSCAL_DEVICE_NAME'] == 'New'
        assert updates['CFTSCAL_IO'] == 'sound-card'
        assert any('superseded' in n for n in notes)
