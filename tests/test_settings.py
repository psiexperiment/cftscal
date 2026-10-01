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
from cftscal.plugins.microphone_generic.settings import MicrophoneComparisonSettings
from cftscal.plugins.input_recording.settings import InputRecordingSettings
from cftscal.plugins.ir_sensor.settings import IRSensorSettings
from cftscal.plugins.speaker.settings import SpeakerCalibrationSettings
from cftscal.plugins.starship.settings import StarshipCalibrationSettings
from psi import get_all_config, get_config, save_config

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
        # The sensor's default device_type ('Meas. Mic.') resolves
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

        settings.generator.name = 'Bench speaker #3 (Lab B)'
        monkeypatch.setattr(InputRecordingSettings, '_run_cal', _fake_run_cal)

        settings.run_input_recording()

        assert captured['experiment'] == 'cftscal.paradigms.input_recording'
        # No target folder picked, so the folder is auto-created from the
        # slugified generator name...
        assert captured['pathname'] == (
            settings.data_path / 'input-recording'
            / 'bench-speaker-3-lab-b' / '{date_time}'
        )
        assert captured['env']['CFTSCAL_INPUT_CHANNELS'] == 'ai2'
        assert captured['env']['CFTSCAL_INPUT_AI2_GAIN'] == '20.0'
        assert captured['env']['CFTSCAL_INPUT_AI2'] == 'stub-cal-string'
        assert 'CFTSCAL_INPUT_AI0_GAIN' not in captured['env']
        assert 'CFTSCAL_INPUT_AI1_GAIN' not in captured['env']
        # ...while the metadata keeps the text exactly as typed.
        assert captured['metadata'] == {
            'generator': 'Bench speaker #3 (Lab B)',
            'sensors': {'ai2': {'label': 'Ch 2', 'sensor': 'MMM0', 'gain': 20.0}},
        }

    def test_run_input_recording_happy_path_unity(self, monkeypatch):
        # Regression test for the Unity pin bug: no manager/get_object
        # monkeypatching here at all -- if get_env_vars() still routed
        # 'Unity' through resolve_object()/get_current_calibration(),
        # this would raise LookupError (unity_manager's object has no
        # on-disk directory to pin a "current" calibration in).
        settings = self._make_settings()
        settings.n_active_inputs = 1
        settings.assign_slot(0, settings.available_inputs[2])
        settings.available_inputs[2].sensor.switch_type('Unity')

        captured = {}

        def _fake_run_cal(self, pathname, experiment, env=None, metadata=None):
            captured['env'] = env
            captured['metadata'] = metadata

        settings.generator.name = 'Bench speaker #3 (Lab B)'
        monkeypatch.setattr(InputRecordingSettings, '_run_cal', _fake_run_cal)
        settings.run_input_recording()

        assert captured['env']['CFTSCAL_INPUT_AI2'] == 'cftscal.objects.UnityInputCalibration'
        assert captured['metadata']['sensors']['ai2']['sensor'] == 'unity'

    def test_run_input_recording_happy_path_nominal(self, monkeypatch):
        settings = self._make_settings()
        settings.n_active_inputs = 1
        settings.assign_slot(0, settings.available_inputs[2])
        settings.available_inputs[2].sensor.switch_type('Nominal')
        settings.available_inputs[2].sensor.sensitivity = 12.3

        captured = {}

        def _fake_run_cal(self, pathname, experiment, env=None, metadata=None):
            captured['env'] = env
            captured['metadata'] = metadata

        settings.generator.name = 'Bench speaker #3 (Lab B)'
        monkeypatch.setattr(InputRecordingSettings, '_run_cal', _fake_run_cal)
        settings.run_input_recording()

        assert captured['env']['CFTSCAL_INPUT_AI2'] == (
            'cftscal.objects.NominalInputCalibration::12.3'
        )
        assert captured['metadata']['sensors']['ai2']['sensor'] == (
            'Nominal (12.3 mV/Pa)'
        )

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

    def test_true_with_unity_device_type_and_no_name(self):
        # Unity is "configured" the instant it's picked -- there's no
        # instance name to also fill in (see MultiTypeSensorReference.
        # is_configured()).
        settings = self._make_settings()
        settings.generator.name = 'chirp'
        settings.available_inputs[0].sensor.switch_type('Unity')
        assert settings.available_inputs[0].sensor.name == ''
        assert settings.ready_to_record() is True

    def test_false_with_nominal_device_type_and_zero_sensitivity(self):
        settings = self._make_settings()
        settings.generator.name = 'chirp'
        settings.available_inputs[0].sensor.switch_type('Nominal')
        settings.available_inputs[0].sensor.sensitivity = 0
        assert settings.ready_to_record() is False

    def test_true_with_nominal_device_type_and_positive_sensitivity(self):
        settings = self._make_settings()
        settings.generator.name = 'chirp'
        settings.available_inputs[0].sensor.switch_type('Nominal')
        settings.available_inputs[0].sensor.sensitivity = 12.3
        assert settings.ready_to_record() is True

    def test_tick_bumps_on_sensitivity_change(self):
        settings = self._make_settings()
        before = settings._readiness_tick
        settings.available_inputs[0].sensor.sensitivity = 5.0
        assert settings._readiness_tick > before


class TestSelectedItemPersistenceRoundTrip:
    '''
    "available list + currently selected item" must persist via the
    List member's ``selected='selected_x'`` tag (see
    ``CalibrationSettings.get_config``/``set_config``), not by
    independently tagging both the list and the singular ``selected_x``
    member persist -- the latter shape lets the *separate* ``selected_x``
    snapshot get applied onto whatever ``selected_x`` still
    object-identically points at post-``__init__`` (``available_x[0]``)
    instead of the entry it was actually pointing at when saved, silently
    corrupting that first entry's own data and resetting the UI's
    selection on every reload. Regression coverage for that bug across
    every plugin it was found in.
    '''

    @pytest.fixture(autouse=True)
    def _isolate_cal_root(self, tmp_path, monkeypatch):
        # Constructing these settings classes builds SensorReference/
        # StarshipSettings sub-objects whose __init__ unconditionally
        # calls refresh_available(), which queries a real
        # CalibrationManager/CFTSBaseLoader -- redirect CAL_ROOT so that
        # never touches the real calibration tree.
        monkeypatch.setenv('CFTSCAL_ROOT', str(tmp_path))

    def test_starship_selected_input(self):
        settings = StarshipCalibrationSettings(
            {'A': 'starship_A'}, {'Ch 0': 'ai0', 'Ch 1': 'ai1'},
        )
        settings.selected_input = settings.available_inputs[1]
        settings.selected_input.sensor.name = 'MMM1'
        settings.available_inputs[0].sensor.name = 'MMM0'

        restored = StarshipCalibrationSettings(
            {'A': 'starship_A'}, {'Ch 0': 'ai0', 'Ch 1': 'ai1'},
        )
        restored.set_config(settings.get_config())

        assert restored.selected_input is restored.available_inputs[1]
        assert restored.selected_input.sensor.name == 'MMM1'
        # Would be 'MMM1' before the fix -- the selected entry's
        # snapshot got misapplied onto available_inputs[0].
        assert restored.available_inputs[0].sensor.name == 'MMM0'

    def test_speaker_selected_input_and_output(self):
        settings = SpeakerCalibrationSettings(
            {'Ch 0': 'ao0', 'Ch 1': 'ao1'}, {'Ch 0': 'ai0', 'Ch 1': 'ai1'},
        )
        settings.selected_input = settings.available_inputs[1]
        settings.selected_input.sensor.name = 'MMM1'
        settings.available_inputs[0].sensor.name = 'MMM0'
        settings.selected_output = settings.available_outputs[1]
        settings.selected_output.generator.name = 'SPK1'
        settings.available_outputs[0].generator.name = 'SPK0'

        restored = SpeakerCalibrationSettings(
            {'Ch 0': 'ao0', 'Ch 1': 'ao1'}, {'Ch 0': 'ai0', 'Ch 1': 'ai1'},
        )
        restored.set_config(settings.get_config())

        assert restored.selected_input is restored.available_inputs[1]
        assert restored.selected_input.sensor.name == 'MMM1'
        assert restored.available_inputs[0].sensor.name == 'MMM0'
        assert restored.selected_output is restored.available_outputs[1]
        assert restored.selected_output.generator.name == 'SPK1'
        assert restored.available_outputs[0].generator.name == 'SPK0'

    def test_ir_sensor_selected_input_and_output(self):
        settings = IRSensorSettings(
            {'Ch 0': 'ai0', 'Ch 1': 'ai1'}, {'Ch 0': 'ao0', 'Ch 1': 'ao1'},
        )
        settings.selected_input = settings.available_inputs[1]
        settings.available_inputs[1].group_path = 'Lab1'
        settings.available_inputs[0].group_path = 'Lab0'
        settings.selected_output = settings.available_outputs[1]
        settings.available_outputs[1].group_path = 'Lab1'
        settings.available_outputs[0].group_path = 'Lab0'

        restored = IRSensorSettings(
            {'Ch 0': 'ai0', 'Ch 1': 'ai1'}, {'Ch 0': 'ao0', 'Ch 1': 'ao1'},
        )
        restored.set_config(settings.get_config())

        assert restored.selected_input is restored.available_inputs[1]
        assert restored.selected_input.group_path == 'Lab1'
        assert restored.available_inputs[0].group_path == 'Lab0'
        assert restored.selected_output is restored.available_outputs[1]
        assert restored.selected_output.group_path == 'Lab1'
        assert restored.available_outputs[0].group_path == 'Lab0'

    def test_microphone_generic_all_three_selections(self):
        settings = MicrophoneComparisonSettings(
            measurement_inputs={'Ch 0': 'ai0', 'Ch 1': 'ai1'},
            generic_inputs={'Ch 0': 'ai2', 'Ch 1': 'ai3'},
            speaker_outputs={'Ch 0': 'ao0', 'Ch 1': 'ao1'},
        )
        settings.measurement_input = settings.measurement_inputs[1]
        settings.measurement_input.sensor.name = 'MMM1'
        settings.measurement_inputs[0].sensor.name = 'MMM0'

        settings.generic_input = settings.generic_inputs[1]
        settings.generic_input.sensor.name = 'GEN1'
        settings.generic_inputs[0].sensor.name = 'GEN0'

        settings.speaker_output = settings.speaker_outputs[1]
        settings.speaker_output.generator.name = 'SPK1'
        settings.speaker_outputs[0].generator.name = 'SPK0'

        restored = MicrophoneComparisonSettings(
            measurement_inputs={'Ch 0': 'ai0', 'Ch 1': 'ai1'},
            generic_inputs={'Ch 0': 'ai2', 'Ch 1': 'ai3'},
            speaker_outputs={'Ch 0': 'ao0', 'Ch 1': 'ao1'},
        )
        restored.set_config(settings.get_config())

        assert restored.measurement_input is restored.measurement_inputs[1]
        assert restored.measurement_input.sensor.name == 'MMM1'
        assert restored.measurement_inputs[0].sensor.name == 'MMM0'

        assert restored.generic_input is restored.generic_inputs[1]
        assert restored.generic_input.sensor.name == 'GEN1'
        assert restored.generic_inputs[0].sensor.name == 'GEN0'

        assert restored.speaker_output is restored.speaker_outputs[1]
        assert restored.speaker_output.generator.name == 'SPK1'
        assert restored.speaker_outputs[0].generator.name == 'SPK0'


class TestStarshipAvailableCouplers:
    '''
    available_couplers is a plain, purely user-managed persisted list
    (same shape as SensorDevice.available_devices) -- unlike
    SensorReference.available_references (never persisted, always
    re-derived from real calibration data), there's no calibration
    manager behind coupler labels at all, so the "+"-added entries are
    the only source of truth and must survive a reload on their own.
    '''

    @pytest.fixture(autouse=True)
    def _isolate_cal_root(self, tmp_path, monkeypatch):
        monkeypatch.setenv('CFTSCAL_ROOT', str(tmp_path))

    def test_starts_empty(self):
        settings = StarshipCalibrationSettings(
            {'A': 'starship_A'}, {'Ch 0': 'ai0'},
        )
        assert settings.available_couplers == []
        assert settings.calibration_coupler == ''

    def test_added_couplers_persist_across_reload(self):
        settings = StarshipCalibrationSettings(
            {'A': 'starship_A'}, {'Ch 0': 'ai0'},
        )
        settings.available_couplers = ['tube-2mm', 'tube-0mm', '3D-basic']
        settings.calibration_coupler = 'tube-0mm'

        restored = StarshipCalibrationSettings(
            {'A': 'starship_A'}, {'Ch 0': 'ai0'},
        )
        restored.set_config(settings.get_config())

        # get_config()/set_config() round-trip a plain list as a direct
        # passthrough (no sorting) -- insertion order is preserved.
        assert restored.available_couplers == ['tube-2mm', 'tube-0mm', '3D-basic']
        assert restored.calibration_coupler == 'tube-0mm'


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

    def test_defaults_to_empty(self):
        settings = WorkspaceSettings()
        assert settings.enabled_plugins == []

    def test_round_trips_through_save_and_load(self):
        settings = WorkspaceSettings()
        settings.enabled_plugins = ['input-recording', 'starship']
        settings.save_config()

        restored = WorkspaceSettings()
        assert restored.enabled_plugins == ['input-recording', 'starship']


class TestWorkspaceSettingsIO:
    '''
    The view edits a mode plus, for any other manifest, a path and class.
    They are saved as the one CFTSCAL_IO setting, ``io_reference``, which
    `cftscal.util.resolve_io` turns into what psi is run with.
    '''

    def test_keyword_modes(self):
        settings = WorkspaceSettings()
        settings.hw_mode = 'sound-card'
        assert settings.io_reference == 'sound-card'
        settings.hw_mode = 'default'
        assert settings.io_reference == 'default'

    def test_custom_file_composes_path_and_class(self):
        settings = WorkspaceSettings()
        settings.hw_mode = 'custom'
        settings.custom_io_path = 'C:/rig/io.enaml'
        settings.custom_io_class = 'MyManifest'
        assert settings.io_reference == 'C:/rig/io.enaml::MyManifest'

    def test_custom_file_blank_class_falls_back_to_iomanifest(self):
        settings = WorkspaceSettings()
        settings.hw_mode = 'custom'
        settings.custom_io_path = 'C:/rig/io.enaml'
        settings.custom_io_class = '   '
        assert settings.io_reference == 'C:/rig/io.enaml::IOManifest'

    def test_custom_module_ignores_class(self):
        # Appending ::IOManifest to a dotted module path made a reference
        # psi could not load.
        settings = WorkspaceSettings()
        settings.hw_mode = 'custom'
        settings.custom_io_path = 'some_pkg.io.CustomManifest'
        assert settings.io_reference == 'some_pkg.io.CustomManifest'

    def test_custom_without_path_is_empty(self):
        settings = WorkspaceSettings()
        settings.hw_mode = 'custom'
        assert settings.io_reference == ''

    def test_round_trips_as_one_setting(self):
        settings = WorkspaceSettings()
        settings.hw_mode = 'custom'
        settings.custom_io_path = 'C:/rig/io.enaml'
        settings.custom_io_class = 'MyManifest'
        settings.save_config()
        assert get_config('CFTSCAL_IO') == 'C:/rig/io.enaml::MyManifest'

        restored = WorkspaceSettings()
        assert restored.hw_mode == 'custom'
        assert restored.custom_io_path == 'C:/rig/io.enaml'
        assert restored.custom_io_class == 'MyManifest'

    def test_saved_keyword_is_loaded(self):
        save_config({'CFTSCAL_IO': 'sound-card'})
        assert WorkspaceSettings().hw_mode == 'sound-card'

    def test_environment_override_disables_every_io_control(
            self, monkeypatch):
        monkeypatch.setenv('CFTSCAL_IO', 'default')
        overridden = WorkspaceSettings().overridden_settings()
        for member in ('hw_mode', 'custom_io_path', 'custom_io_class'):
            assert overridden[member] == 'CFTSCAL_IO'


class TestResolveIO:
    '''
    `resolve_io` is the one place CFTSCAL_IO is interpreted, for cftscal's
    own calibrations and for every launcher built on it.
    '''

    def test_sound_card(self):
        from cftscal.util import SOUND_CARD_MANIFEST, resolve_io
        save_config({
            'CFTSCAL_IO': 'sound-card',
            'CFTSCAL_DEVICE_NAME': 'ASIO Fireface USB',
            'CFTSCAL_DEVICE_HOSTAPI': 'ASIO',
            'CFTSCAL_SAMPLE_RATE': 96000.0,
        })
        manifest, env = resolve_io()
        assert manifest == SOUND_CARD_MANIFEST
        assert env == {
            'PSI_SOUND_DEVICE_NAME': 'ASIO Fireface USB, ASIO',
            'PSI_SOUND_DEVICE_FS': '96000',
        }

    def test_default_is_this_machines_manifest(self, monkeypatch):
        from cftscal import util
        monkeypatch.setattr(util, 'get_default_io', lambda: 'C:/io/rig1.enaml')
        save_config({'CFTSCAL_IO': 'default'})
        assert util.resolve_io() == ('C:/io/rig1.enaml', {})

    def test_anything_else_is_passed_through(self):
        from cftscal.util import resolve_io
        save_config({'CFTSCAL_IO': 'C:/io/rig.enaml::RigIO'})
        assert resolve_io() == ('C:/io/rig.enaml::RigIO', {})

    def test_empty_is_an_error(self):
        from cftscal.util import resolve_io
        save_config({'CFTSCAL_IO': ''})
        with pytest.raises(ValueError, match='No IO manifest is selected'):
            resolve_io()

    def test_default_setting_follows_the_hostname_manifest(self, monkeypatch):
        import psi.application
        monkeypatch.setattr(psi.application, 'get_default_io',
                            lambda: 'C:/io/rig1.enaml')
        assert get_config('CFTSCAL_IO') == 'default'

        def missing():
            raise ValueError('no manifest')

        monkeypatch.setattr(psi.application, 'get_default_io', missing)
        assert get_config('CFTSCAL_IO') == 'sound-card'


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
        settings = CalibrationSettings()
        settings.data_path = tmp_path
        return settings

    def _run(self, settings, tmp_path, monkeypatch, psi_side_effect):
        def fake_check_output(args, env=None, **kwargs):
            # **kwargs swallows stdin/stderr (and anything else
            # _run_cal's real subprocess.check_output call passes) --
            # this stub only cares about args/env, so it shouldn't need
            # updating every time _run_cal's call is tweaked, the way it
            # broke last time stdin=subprocess.DEVNULL was added.
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


import types


class _FakeSD:
    '''
    Stand-in for the ``sounddevice`` module used by
    :mod:`cftscal.plugins.workspace`, so device-selection tests can run
    against a fixed, deterministic device list on any machine (no real
    audio hardware required).

    ``devices`` is the list returned by ``query_devices()`` (position ==
    PortAudio index); each entry's ``hostapi`` keys into ``hostapis``.
    '''

    def __init__(self, devices, hostapis, default_input=0):
        self._devices = devices
        self._hostapis = hostapis
        self.default = types.SimpleNamespace(device=(default_input, 0))

    def query_devices(self, device=None):
        if device is None:
            return [dict(d) for d in self._devices]
        return dict(self._devices[device])

    def query_hostapis(self, index):
        return self._hostapis[index]

    def check_input_settings(self, device=None, samplerate=None):
        # Accept every standard rate -- these tests don't exercise
        # rate filtering.
        pass


# Two of these share the bare name 'RME Babyface' and differ only by host
# API -- the exact ambiguity the name+host-API identity is meant to resolve.
_DEVICES = [
    {'name': 'Speakers', 'hostapi': 0,
     'max_input_channels': 0, 'max_output_channels': 2},
    {'name': 'RME Babyface', 'hostapi': 0,
     'max_input_channels': 2, 'max_output_channels': 2},
    {'name': 'RME Babyface', 'hostapi': 1,
     'max_input_channels': 8, 'max_output_channels': 8},
]
_HOSTAPIS = [{'name': 'MME'}, {'name': 'ASIO'}]


class TestWorkspaceSettingsDeviceSelection:
    '''
    The audio device is selected/persisted/handed off by its durable
    identity -- name + host API -- never by the unstable PortAudio index.
    ``selected_device_query`` is the fully-qualified ``"<name>, <host API>"``
    string handed to the psi subprocess (via PSI_SOUND_DEVICE_NAME), which
    sounddevice matches exactly. See WorkspaceSettings in
    cftscal/plugins/workspace.py.
    '''

    def _make_settings(self, tmp_path, monkeypatch, devices=None,
                       hostapis=None, default_input=0):
        fake = _FakeSD(devices if devices is not None else _DEVICES,
                       hostapis if hostapis is not None else _HOSTAPIS,
                       default_input=default_input)
        monkeypatch.setattr('cftscal.plugins.workspace.sd', fake)
        return WorkspaceSettings()

    def test_fresh_install_seeds_identity_from_default_device(
            self, tmp_path, monkeypatch):
        settings = self._make_settings(tmp_path, monkeypatch, default_input=0)
        assert settings.selected_device_name == 'Speakers'
        assert settings.selected_device_hostapi == 'MME'
        assert settings.selected_device_query == 'Speakers, MME'

    def test_selecting_device_populates_identity_and_query(
            self, tmp_path, monkeypatch):
        settings = self._make_settings(tmp_path, monkeypatch)
        settings.selected_device = settings.available_devices[2]
        assert settings.selected_device_name == 'RME Babyface'
        assert settings.selected_device_hostapi == 'ASIO'
        assert settings.selected_device_query == 'RME Babyface, ASIO'

    def test_query_disambiguates_same_name_by_host_api(
            self, tmp_path, monkeypatch):
        settings = self._make_settings(tmp_path, monkeypatch)
        settings.selected_device = settings.available_devices[1]
        assert settings.selected_device_query == 'RME Babyface, MME'
        settings.selected_device = settings.available_devices[2]
        assert settings.selected_device_query == 'RME Babyface, ASIO'

    def test_query_matches_sounddevices_full_string_format(
            self, tmp_path, monkeypatch):
        # The ", " separator and ordering must match what sounddevice builds
        # internally (device name + ', ' + host API name) so the query is an
        # exact match, not just a substring.
        settings = self._make_settings(tmp_path, monkeypatch)
        settings.selected_device = settings.available_devices[2]
        d = _DEVICES[2]
        expected = d['name'] + ', ' + _HOSTAPIS[d['hostapi']]['name']
        assert settings.selected_device_query == expected

    def test_round_trip_persists_identity_not_index(
            self, tmp_path, monkeypatch):
        settings = self._make_settings(tmp_path, monkeypatch)
        settings.selected_device = settings.available_devices[2]
        settings.save_config()

        assert get_config('CFTSCAL_DEVICE_NAME') == 'RME Babyface'
        assert get_config('CFTSCAL_DEVICE_HOSTAPI') == 'ASIO'
        # Persisted by identity only -- no positional index leaks into the
        # configuration file.
        assert 'CFTSCAL_DEVICE_INDEX' not in get_all_config()

    def test_reresolves_device_after_device_list_reorder(
            self, tmp_path, monkeypatch):
        settings = self._make_settings(tmp_path, monkeypatch)
        settings.selected_device = settings.available_devices[2]  # ASIO RME
        settings.save_config()

        # Next launch: the ASIO device now sits at a different position.
        reordered = [_DEVICES[2], _DEVICES[0], _DEVICES[1]]
        restored = self._make_settings(
            tmp_path, monkeypatch, devices=reordered)
        # Re-found by identity regardless of its new position in the list.
        assert restored.selected_device is restored.available_devices[0]
        assert restored.selected_device_hostapi == 'ASIO'
        assert restored.selected_device_query == 'RME Babyface, ASIO'

    def test_absent_device_preserves_identity_for_handoff(
            self, tmp_path, monkeypatch):
        settings = self._make_settings(tmp_path, monkeypatch)
        settings.selected_device = settings.available_devices[2]
        settings.save_config()

        # Device unplugged: only the two others remain.
        remaining = [_DEVICES[0], _DEVICES[1]]
        restored = self._make_settings(
            tmp_path, monkeypatch, devices=remaining)
        # No live device matches, but the durable identity (and thus the query
        # we hand off) survives so the run still targets the right device if it
        # reappears.
        assert restored.selected_device is None
        assert restored.selected_device_query == 'RME Babyface, ASIO'
        assert restored.selected_device_info == ''

    def test_name_without_host_api_resolves_by_name(
            self, tmp_path, monkeypatch):
        # A blank host API is still a supported state -- it is what a
        # device identity looks like before one has been recorded -- so a
        # name on its own must still resolve, by name alone.
        save_config({
            'CFTSCAL_DEVICE_NAME': 'RME Babyface',
            'CFTSCAL_DEVICE_HOSTAPI': '',
        })
        settings = self._make_settings(tmp_path, monkeypatch)
        # Resolves by name to the first match and fills in its host API.
        assert settings.selected_device_name == 'RME Babyface'
        assert settings.selected_device is settings.available_devices[1]
        assert settings.selected_device_hostapi == 'MME'


class TestInputRecordingGeneratorNotPersisted:
    '''
    The input-recording generator is free text that only ends up in the
    recording's metadata, and is too lab-specific to remember between
    sessions -- it must never be saved, and an old config that still
    carries one must not restore it.
    '''

    def _make_settings(self):
        return InputRecordingSettings({'Ch 0': 'ai0', 'Ch 1': 'ai1'})

    def test_generator_not_in_saved_config(self):
        settings = self._make_settings()
        settings.generator.name = 'Bench speaker #3 (Lab B)'
        assert 'generator' not in settings.get_config()

    def test_legacy_generator_config_is_ignored(self):
        settings = self._make_settings()
        settings.set_config({
            'generator': {'name': 'test', 'available_generators': ['test']},
        })
        assert settings.generator.name == ''

    def test_any_string_makes_it_ready(self):
        settings = self._make_settings()
        settings.available_inputs[0].sensor.switch_type('Unity')
        assert not settings.ready_to_record()
        settings.generator.name = 'anything at all, 123!'
        assert settings.ready_to_record()


class TestInputRecordingGeneratorFolder:
    '''
    The generator is free text, but with no target folder picked it also
    names the recording's folder -- so the folder name is slugified, and a
    name with nothing left after slugifying can't be recorded.
    '''

    def _make_settings(self):
        settings = InputRecordingSettings({'Ch 0': 'ai0'})
        settings.available_inputs[0].sensor.switch_type('Unity')
        return settings

    def test_punctuation_only_name_is_not_ready(self):
        settings = self._make_settings()
        settings.generator.name = '???'
        assert not settings.ready_to_record()

    def test_punctuation_only_name_refuses_to_record(self, monkeypatch):
        settings = self._make_settings()
        settings.generator.name = ' / : '
        monkeypatch.setattr(
            InputRecordingSettings, '_run_cal',
            lambda *args, **kwargs: pytest.fail('should not launch'),
        )
        with pytest.raises(ValueError, match='letter or digit'):
            settings.run_input_recording()

    def test_target_folder_ignores_generator(self, monkeypatch):
        # With a target folder picked, the generator isn't part of the
        # path at all (see CalibrationSettings._make_path).
        settings = self._make_settings()
        settings.group_path = 'Lab1/Rig'
        settings.generator.name = 'C:/weird name?'
        captured = {}
        monkeypatch.setattr(
            InputRecordingSettings, '_run_cal',
            lambda self, pathname, *args, **kwargs:
                captured.setdefault('pathname', pathname),
        )
        settings.run_input_recording()
        assert captured['pathname'] == (
            settings.data_path / 'input-recording' / 'Lab1/Rig' / '{date_time}'
        )


class TestStarshipRunPaths:
    '''
    Golay and Chirp must both auto-create the folder from the starship
    picked in the "Starship" dropdown. Chirp used to read
    ``starship.name``, which StarshipSettings doesn't have, so the
    button raised AttributeError before anything launched.
    '''

    @pytest.fixture(autouse=True)
    def _isolate_cal_root(self, tmp_path, monkeypatch):
        monkeypatch.setenv('CFTSCAL_ROOT', str(tmp_path))

    @pytest.mark.parametrize('method', ['run_cal_golay', 'run_cal_chirp'])
    def test_folder_from_selected_starship(self, method, monkeypatch):
        settings = StarshipCalibrationSettings(
            {'A': 'starship_A'}, {'Ch 0': 'ai0'},
        )
        starship = settings.selected_starship
        starship.starship = 'SS-07'
        microphone = settings.selected_input
        microphone.sensor.name = 'MMM0'
        monkeypatch.setattr(
            type(microphone), 'get_env_vars', lambda self, **kwargs: {},
        )
        captured = {}
        monkeypatch.setattr(
            StarshipCalibrationSettings, '_run_cal',
            lambda self, pathname, *args, **kwargs:
                captured.setdefault('pathname', pathname),
        )
        getattr(settings, method)(starship, microphone)
        assert captured['pathname'] == (
            settings.data_path / 'starship' / 'SS-07' / '{date_time}'
        )
