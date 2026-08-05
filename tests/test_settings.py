'''
Tests for plugin settings classes in :mod:`cftscal.plugins.settings` and
per-plugin ``settings.py`` modules.

Focus on construction-time defaults — the kind of bug that hides behind
a stale local config file (``load_config()`` overwrites the bad default
before anyone notices) and only surfaces on a fresh install.
'''
import pytest

from cftscal.plugins.microphone.settings import MicrophoneCalibrationSettings
from cftscal.plugins.input_recording.settings import InputRecordingSettings
from cftscal.plugins.settings import SensorDevice


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
        monkeypatch.setattr(
            'cftscal.plugins.settings.input_manager.get_object',
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


class _StubCalibration:
    def to_string(self):
        return 'stub-cal-string'


class _StubCalObject:
    def get_current_calibration(self):
        return _StubCalibration()
