from pathlib import Path
from atom.api import set_default, List, Typed

from psi import get_config

from ..settings import (
    CalibrationSettings,
    InputSettings,
    MeasurementMicrophoneSettings,
    PistonphoneSettings
)

from cftscal import CAL_ROOT


class MicrophoneCalibrationSettings(CalibrationSettings):

    available_inputs = List(Typed(InputSettings, ()))
    pistonphone = Typed(PistonphoneSettings, ())
    settings_filename = set_default('microphone-measurement.json')

    def __init__(self, inputs):
        settings = []
        for label, name in inputs.items():
            setting = InputSettings(
                input_name=name,
                input_label=label,
                generator=self.pistonphone,
                sensor=MeasurementMicrophoneSettings(),
                env_prefix='CFTS_MICROPHONE',
            )
            settings.append(setting)
        self.available_inputs = settings
        self.load_config()

    def get_config(self):
        return {
            'available_inputs': {i.input_name: i.get_persistence() for i in self.available_inputs},
            'pistonphone': self.pistonphone.get_persistence(),
        }

    def set_config(self, config):
        for name, settings in config.get('available_inputs', {}).items():
            for i in self.available_inputs:
                if i.input_name == name:
                    i.set_persistence(settings)
                    break
        self.pistonphone.set_persistence(config.get('pistonphone', {}))

    def run_mic_cal(self, channel):
        filename = f'{{date_time}}_{channel.sensor.name}_{channel.generator.name}'
        filename = ' '.join(filename.split())
        pathname = CAL_ROOT / 'microphone' / channel.sensor.name / filename
        env = {
            **channel.get_env_vars(include_cal=False),
            **self.pistonphone.get_env_vars(),
        }
        self._run_cal(pathname, 'cftscal.paradigms.pistonphone_calibration', env)
