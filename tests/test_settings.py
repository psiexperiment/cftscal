'''
Tests for plugin settings classes in :mod:`cftscal.plugins.settings` and
per-plugin ``settings.py`` modules.

Focus on construction-time defaults — the kind of bug that hides behind
a stale local config file (``load_config()`` overwrites the bad default
before anyone notices) and only surfaces on a fresh install.
'''
import json
from pathlib import Path

import pytest

from cftscal.plugins.microphone.settings import MicrophoneCalibrationSettings
from cftscal.plugins.input_recording.settings import InputRecordingSettings
from cftscal.plugins.settings import CalibrationSettings, SensorDevice
from cftscal.plugins.workspace import WorkspaceSettings


class TestMicrophoneCalibrationSettingsDefaults:
    '''
    On a fresh install there is no persisted config, so
    ``load_config()``/``set_config()`` never run and ``selected_input``
    is whatever ``__init__`` left it as.  It must point at one of the
    freshly-built ``available_inputs`` entries (sensor=SensorDevice) —
    not the bare ``InputSettings()`` Atom default, whose ``sensor``
    defaults to ``SensorReference`` and has no ``available_devices``.
    '''

    def test_selected_input_defaults_to_first_available_input(self):
        settings = MicrophoneCalibrationSettings({'Ch 0': 'mic_ch_0'})
        assert settings.selected_input is settings.available_inputs[0]

    def test_selected_input_sensor_is_a_sensor_device(self):
        settings = MicrophoneCalibrationSettings({'Ch 0': 'mic_ch_0'})
        assert isinstance(settings.selected_input.sensor, SensorDevice)
        # Would raise AttributeError before the fix, since the bare
        # default's sensor was a SensorReference.
        assert settings.selected_input.sensor.available_devices == []


class TestInputRecordingSettings:
    '''
    InputRecordingSettings has ``n_active_inputs`` independent slots
    ("Input 0", "Input 1", ...), each of which can point at *any* real
    hardware channel via ``channel_for_slot``/``assign_slot`` -- not
    tied to hardware order, and not a single ``selected_input`` or a
    per-channel checkbox.
    '''

    def _make_settings(self):
        return InputRecordingSettings({
            'Ch 0': 'ai0', 'Ch 1': 'ai1', 'Ch 2': 'ai2',
        })

    def test_no_selected_input_attribute(self):
        settings = self._make_settings()
        assert not hasattr(settings, 'selected_input')

    def test_n_active_inputs_defaults_to_one(self):
        settings = self._make_settings()
        assert settings.n_active_inputs == 1

    def test_slots_default_to_hardware_order(self):
        settings = self._make_settings()
        assert settings.channel_for_slot(0).input_name == 'ai0'
        assert settings.channel_for_slot(1).input_name == 'ai1'
        assert settings.channel_for_slot(2).input_name == 'ai2'

    def test_assign_slot_reassigns_arbitrary_channel(self):
        # e.g. slot 0 -> the third channel, slot 1 -> the first --
        # exactly the "Input 10 first, Input 5 second" use case.
        settings = self._make_settings()
        settings.assign_slot(0, settings.available_inputs[2])
        settings.assign_slot(1, settings.available_inputs[0])
        assert settings.channel_for_slot(0).input_name == 'ai2'
        assert settings.channel_for_slot(1).input_name == 'ai0'
        # Unassigned slots are untouched.
        assert settings.channel_for_slot(2).input_name == 'ai2'

    def test_active_channels_uses_current_slot_assignment(self):
        settings = self._make_settings()
        settings.n_active_inputs = 2
        settings.assign_slot(0, settings.available_inputs[2])
        settings.assign_slot(1, settings.available_inputs[0])
        assert [c.input_name for c in settings.active_channels()] == [
            'ai2', 'ai0',
        ]

    def test_run_input_recording_raises_without_sensor(self):
        settings = self._make_settings()
        with pytest.raises(ValueError, match='Ch 0'):
            settings.run_input_recording()

    def test_run_input_recording_raises_when_n_active_inputs_is_zero(self):
        # The dropdown's minimum item is 1 (view.enaml) -- a hand-edited
        # or corrupted config could still persist 0, so
        # run_input_recording() must reject it itself.
        settings = self._make_settings()
        settings.n_active_inputs = 0
        with pytest.raises(ValueError, match='No input channels'):
            settings.run_input_recording()

    def test_run_input_recording_raises_on_duplicate_slot_assignment(self):
        # Two slots pointing at the same real channel can't actually
        # record independently different settings -- gain/calibration
        # are properties of the physical channel, not of the slot (see
        # active_input_channels()'s docstring in cftscal/paradigms/
        # __init__.py) -- and psi's own Input.name uniqueness check
        # would separately reject it too. Rejected here rather than
        # left to surface as a confusing psi-side error.
        settings = self._make_settings()
        settings.n_active_inputs = 2
        settings.assign_slot(0, settings.available_inputs[0])
        settings.assign_slot(1, settings.available_inputs[0])
        for i in settings.available_inputs:
            i.sensor.name = f'cal-{i.input_name}'
        with pytest.raises(ValueError, match='more than one slot'):
            settings.run_input_recording()

    def test_run_input_recording_happy_path(self, monkeypatch):
        # The sensor's default sensor_type ('Meas. Mic.') resolves
        # through measurement_microphone_manager, not input_manager --
        # see MultiTypeSensorReference.
        monkeypatch.setattr(
            'cftscal.plugins.settings.measurement_microphone_manager.get_object',
            lambda name: _StubCalObject(),
        )

        settings = self._make_settings()
        settings.n_active_inputs = 1
        # Slot 0 -> the third real channel (ai2), not the first -- makes
        # sure run_input_recording() follows the slot assignment rather
        # than hardware order.
        settings.assign_slot(0, settings.available_inputs[2])
        settings.available_inputs[2].sensor.name = 'MMM0'
        settings.available_inputs[2].sensor.gain = 20
        # ai0/ai1 are outside the active slots -- their env/metadata
        # entries must not appear.

        captured = {}

        def _fake_run_cal(self, pathname, experiment, env=None, metadata=None):
            captured['pathname'] = pathname
            captured['experiment'] = experiment
            captured['env'] = env
            captured['metadata'] = metadata

        monkeypatch.setattr(InputRecordingSettings, '_run_cal', _fake_run_cal)

        settings.run_input_recording()

        assert captured['experiment'] == 'cftscal.paradigms.input_recording'
        assert captured['env']['CFTS_INPUT_CHANNELS'] == 'ai2'
        assert captured['env']['CFTS_INPUT_AI2_GAIN'] == '20.0'
        assert captured['env']['CFTS_INPUT_AI2'] == 'stub-cal-string'
        assert 'CFTS_INPUT_AI0_GAIN' not in captured['env']
        assert 'CFTS_INPUT_AI1_GAIN' not in captured['env']
        assert captured['metadata'] == {
            'generator': settings.generator.name,
            'sensors': {'ai2': {'label': 'Ch 2', 'sensor': 'MMM0'}},
        }

    def test_slot_channels_persists_and_round_trips(self):
        # slot_channels is a plain Dict (not a List[PersistentSettings])
        # tagged persist=True -- CalibrationSettings.get_config() only
        # special-cases empty lists / lists of PersistentSettings, so
        # this locks in that the Dict passthrough path actually works.
        settings = self._make_settings()
        settings.n_active_inputs = 2
        settings.assign_slot(0, settings.available_inputs[2])
        settings.assign_slot(1, settings.available_inputs[0])

        config = settings.get_config()
        assert config['n_active_inputs'] == 2
        assert config['slot_channels'] == {'0': 'ai2', '1': 'ai0', '2': 'ai2'}

        restored = self._make_settings()
        restored.set_config(config)
        assert restored.n_active_inputs == 2
        assert [c.input_name for c in restored.active_channels()] == [
            'ai2', 'ai0',
        ]


class TestInputRecordingReadyToRecord:
    '''
    ready_to_record() backs the Record button's `enabled <<` binding
    (input_recording/view.enaml). The binding used to inline this same
    logic directly (a method call plus set/generator comprehensions), all
    of which Enaml's `<<` tracer can't see through -- it only tracks plain
    `obj.attr` reads executed directly in the traced expression's own
    bytecode, not reads inside a called method or inside comprehensions/
    generator expressions (those compile to a separate code object with
    its own locals, which the tracer explicitly skips). That meant the
    button could go stale -- e.g. a channel/sensor change wouldn't
    re-enable it -- unless something *else* in the expression happened to
    also be a direct dependency. `_readiness_tick` exists to fix that: it
    must get bumped on every input that affects ready_to_record()'s
    result, so the view's dependency-forcing read of it (see the comment
    at the Record button) actually re-triggers on all of them.
    '''

    def _make_settings(self):
        return InputRecordingSettings({
            'Ch 0': 'ai0', 'Ch 1': 'ai1', 'Ch 2': 'ai2',
        })

    def test_false_with_no_generator(self):
        settings = self._make_settings()
        settings.available_inputs[0].sensor.name = 'MMM0'
        assert settings.generator.name == ''
        assert settings.ready_to_record() is False

    def test_false_with_missing_sensor(self):
        settings = self._make_settings()
        settings.generator.name = 'chirp'
        assert settings.ready_to_record() is False

    def test_false_with_duplicate_slot_assignment(self):
        settings = self._make_settings()
        settings.generator.name = 'chirp'
        settings.n_active_inputs = 2
        settings.assign_slot(0, settings.available_inputs[0])
        settings.assign_slot(1, settings.available_inputs[0])
        for i in settings.available_inputs:
            i.sensor.name = f'cal-{i.input_name}'
        assert settings.ready_to_record() is False

    def test_true_when_fully_configured(self):
        settings = self._make_settings()
        settings.generator.name = 'chirp'
        settings.available_inputs[0].sensor.name = 'MMM0'
        assert settings.ready_to_record() is True

    def test_tick_bumps_on_slot_reassignment(self):
        settings = self._make_settings()
        before = settings._readiness_tick
        settings.assign_slot(0, settings.available_inputs[1])
        assert settings._readiness_tick > before

    def test_tick_bumps_on_n_active_inputs_change(self):
        settings = self._make_settings()
        before = settings._readiness_tick
        settings.n_active_inputs = 2
        assert settings._readiness_tick > before

    def test_tick_bumps_on_generator_name_change(self):
        settings = self._make_settings()
        before = settings._readiness_tick
        settings.generator.name = 'chirp'
        assert settings._readiness_tick > before

    def test_tick_bumps_on_any_channel_sensor_name_change(self):
        # Not just the currently-active channel's sensor -- any channel
        # could become active via a later slot reassignment.
        settings = self._make_settings()
        before = settings._readiness_tick
        settings.available_inputs[2].sensor.name = 'MMM0'
        assert settings._readiness_tick > before


class TestWorkspaceSettingsEnabledPlugins:
    '''
    WorkspaceSettings.enabled_plugins forces specific plugins to load in
    view-only mode regardless of hardware detection (see
    _CalibrationPluginManifest._get_available in
    cftscal/plugins/manifest.enaml). Unlike per-plugin settings,
    WorkspaceSettings hand-rolls save_config()/load_config() with an
    explicit key list rather than the tagged-member persistence pattern
    -- this locks in that enabled_plugins is actually included.
    '''

    def _make_settings(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            'cftscal.plugins.workspace.get_config_folder', lambda: tmp_path,
        )
        return WorkspaceSettings()

    def test_defaults_to_empty(self, tmp_path, monkeypatch):
        settings = self._make_settings(tmp_path, monkeypatch)
        assert settings.enabled_plugins == []

    def test_round_trips_through_save_and_load(self, tmp_path, monkeypatch):
        settings = self._make_settings(tmp_path, monkeypatch)
        settings.enabled_plugins = ['input-recording', 'starship']
        settings.save_config()

        restored = self._make_settings(tmp_path, monkeypatch)
        assert restored.enabled_plugins == ['input-recording', 'starship']


class TestWorkspaceSettingsHwConfiguration:
    '''
    ``hw_configuration`` -- the string actually passed to psi's ``--io``
    argument (see ``_run_cal`` in cftscal/plugins/settings.py) and to
    ``load_io_manifest()`` (see ``io_manifest()`` in cftscal/util.py) -- is
    a computed Property derived from ``hw_mode`` and, in custom mode,
    ``custom_io_path``/``custom_io_class``. Neither of those two readers
    changed: this locks in that the derivation still produces what they
    expect, and that old ``workspace.json`` files (which persisted
    ``hw_configuration`` directly, picked from a flat list of every
    discovered IO file/module path) still load correctly.
    '''

    def _make_settings(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            'cftscal.plugins.workspace.get_config_folder', lambda: tmp_path,
        )
        return WorkspaceSettings()

    def test_sound_card_mode(self, tmp_path, monkeypatch):
        settings = self._make_settings(tmp_path, monkeypatch)
        settings.hw_mode = 'Sound Card'
        assert settings.hw_configuration == 'Sound Card'

    def test_custom_mode_composes_path_and_class(self, tmp_path, monkeypatch):
        settings = self._make_settings(tmp_path, monkeypatch)
        settings.hw_mode = 'Custom (Enaml IO manifest)'
        settings.custom_io_path = 'C:/rig/io.enaml'
        settings.custom_io_class = 'MyManifest'
        assert settings.hw_configuration == 'C:/rig/io.enaml::MyManifest'

    def test_custom_mode_defaults_class_to_iomanifest(self, tmp_path, monkeypatch):
        settings = self._make_settings(tmp_path, monkeypatch)
        settings.hw_mode = 'Custom (Enaml IO manifest)'
        settings.custom_io_path = 'C:/rig/io.enaml'
        assert settings.custom_io_class == 'IOManifest'
        assert settings.hw_configuration == 'C:/rig/io.enaml::IOManifest'

    def test_custom_mode_blank_class_falls_back_to_iomanifest(self, tmp_path, monkeypatch):
        settings = self._make_settings(tmp_path, monkeypatch)
        settings.hw_mode = 'Custom (Enaml IO manifest)'
        settings.custom_io_path = 'C:/rig/io.enaml'
        settings.custom_io_class = '   '
        assert settings.hw_configuration == 'C:/rig/io.enaml::IOManifest'

    def test_custom_mode_without_path_is_empty(self, tmp_path, monkeypatch):
        settings = self._make_settings(tmp_path, monkeypatch)
        settings.hw_mode = 'Custom (Enaml IO manifest)'
        assert settings.hw_configuration == ''

    def test_round_trips_through_save_and_load(self, tmp_path, monkeypatch):
        settings = self._make_settings(tmp_path, monkeypatch)
        settings.hw_mode = 'Custom (Enaml IO manifest)'
        settings.custom_io_path = 'C:/rig/io.enaml'
        settings.custom_io_class = 'MyManifest'
        settings.save_config()

        restored = self._make_settings(tmp_path, monkeypatch)
        assert restored.hw_mode == 'Custom (Enaml IO manifest)'
        assert restored.custom_io_path == 'C:/rig/io.enaml'
        assert restored.custom_io_class == 'MyManifest'
        assert restored.hw_configuration == 'C:/rig/io.enaml::MyManifest'

    def test_loads_legacy_sound_card_config(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            'cftscal.plugins.workspace.get_config_folder', lambda: tmp_path,
        )
        config_file = tmp_path / 'cfts' / 'workspace.json'
        config_file.parent.mkdir(parents=True)
        config_file.write_text(json.dumps({'hw_configuration': 'Sound Card'}))

        settings = WorkspaceSettings()
        assert settings.hw_mode == 'Sound Card'
        assert settings.hw_configuration == 'Sound Card'

    def test_loads_legacy_custom_config_with_class(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            'cftscal.plugins.workspace.get_config_folder', lambda: tmp_path,
        )
        config_file = tmp_path / 'cfts' / 'workspace.json'
        config_file.parent.mkdir(parents=True)
        config_file.write_text(json.dumps({
            'hw_configuration': 'C:/rig/io.enaml::MyManifest',
        }))

        settings = WorkspaceSettings()
        assert settings.hw_mode == 'Custom (Enaml IO manifest)'
        assert settings.custom_io_path == 'C:/rig/io.enaml'
        assert settings.custom_io_class == 'MyManifest'

    def test_loads_legacy_custom_config_without_class(self, tmp_path, monkeypatch):
        # e.g. an old STANDARD_IO dotted module path, which never carried
        # an explicit '::ClassName' suffix -- defaults to IOManifest, same
        # as load_io_manifest() itself does for a bare '.enaml' path.
        monkeypatch.setattr(
            'cftscal.plugins.workspace.get_config_folder', lambda: tmp_path,
        )
        config_file = tmp_path / 'cfts' / 'workspace.json'
        config_file.parent.mkdir(parents=True)
        config_file.write_text(json.dumps({
            'hw_configuration': 'some_pkg.io.CustomManifest',
        }))

        settings = WorkspaceSettings()
        assert settings.hw_mode == 'Custom (Enaml IO manifest)'
        assert settings.custom_io_path == 'some_pkg.io.CustomManifest'
        assert settings.custom_io_class == 'IOManifest'


class TestRunCalMetadataMerge:
    '''
    ``_run_cal`` writes cftscal's own metadata.json into the calibration
    folder after ``psi`` returns. psi/psidata may have already written
    their own metadata.json there for run provenance (hostname/timestamp/
    version) -- ``_run_cal`` must merge cftscal's fields on top rather
    than clobbering that file, mirroring the equivalent fix in
    migrate_metadata.py for historical calibrations.
    '''

    def _make_settings(self, tmp_path, monkeypatch):
        # WorkspaceSettings() is constructed internally by _run_cal; point
        # its config folder at a scratch dir like TestPersistEnabledPlugins
        # does, so it doesn't touch the real ~/.config.
        monkeypatch.setattr(
            'cftscal.plugins.workspace.get_config_folder', lambda: tmp_path,
        )
        settings = CalibrationSettings()
        settings.data_path = tmp_path
        return settings

    def _run(self, settings, tmp_path, monkeypatch, psi_side_effect):
        def fake_check_output(args, env=None):
            psi_side_effect(Path(args[2]))
            return b''

        monkeypatch.setattr(
            'cftscal.plugins.settings.subprocess.check_output',
            fake_check_output,
        )
        pathname = tmp_path / 'cal' / '{date_time}'
        settings._run_cal(
            pathname, 'cftscal.paradigms.fake',
            metadata={'pistonphone': 'PP1'},
        )
        return next((tmp_path / 'cal').iterdir(), None)

    def test_merges_with_preexisting_psi_metadata(self, tmp_path, monkeypatch):
        settings = self._make_settings(tmp_path, monkeypatch)

        def psi_writes_provenance_metadata(out_dir):
            out_dir.mkdir(parents=True)
            (out_dir / 'data.csv').write_text('...')
            (out_dir / 'metadata.json').write_text(json.dumps({
                'hostname': 'rig1',
                'version': {'psi': '0.6.4'},
            }))

        out_dir = self._run(
            settings, tmp_path, monkeypatch, psi_writes_provenance_metadata,
        )
        meta = json.loads((out_dir / 'metadata.json').read_text())
        assert meta['pistonphone'] == 'PP1'
        assert meta['hostname'] == 'rig1'
        assert meta['version'] == {'psi': '0.6.4'}
        assert 'datetime' in meta

    def test_writes_when_psi_wrote_no_metadata(self, tmp_path, monkeypatch):
        settings = self._make_settings(tmp_path, monkeypatch)

        def psi_writes_only_data(out_dir):
            out_dir.mkdir(parents=True)
            (out_dir / 'data.csv').write_text('...')

        out_dir = self._run(
            settings, tmp_path, monkeypatch, psi_writes_only_data,
        )
        meta = json.loads((out_dir / 'metadata.json').read_text())
        assert meta['pistonphone'] == 'PP1'
        assert 'datetime' in meta

    def test_empty_output_dir_pruned_not_written(self, tmp_path, monkeypatch):
        # User aborted before any data was acquired -- no metadata.json
        # should appear, and the empty dir psi created is removed.
        settings = self._make_settings(tmp_path, monkeypatch)

        def psi_aborted(out_dir):
            out_dir.mkdir(parents=True)

        self._run(settings, tmp_path, monkeypatch, psi_aborted)
        assert list((tmp_path / 'cal').iterdir()) == []


class _StubCalibration:
    def to_string(self):
        return 'stub-cal-string'


class _StubCalObject:
    def get_current_calibration(self):
        return _StubCalibration()
