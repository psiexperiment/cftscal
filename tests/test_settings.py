'''
Tests for plugin settings classes in :mod:`cftscal.plugins.settings` and
per-plugin ``settings.py`` modules.

Focus on construction-time defaults — the kind of bug that hides behind
a stale local config file (``load_config()`` overwrites the bad default
before anyone notices) and only surfaces on a fresh install.
'''
from cftscal.plugins.microphone.settings import MicrophoneCalibrationSettings
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
