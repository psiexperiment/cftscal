from pathlib import Path
from atom.api import List, Typed

from psi import get_config

from ..settings import (
    CalibrationSettings,
    InputSettings,
    MeasurementMicrophoneSettings,
    PistonphoneSettings
)

from cftscal import CAL_ROOT


class MicrophoneCalibrationSettings(CalibrationSettings):

    measurement_inputs = List(Typed(InputSettings, ()))
    pistonphone = Typed(PistonphoneSettings, ())

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
        self.measurement_inputs = settings

    def save_config(self):
        for m in self.measurement_inputs:
            m.save_config()
        self.pistonphone.save_config()

    def run_mic_cal(self, channel):
        filename = f'{{date_time}}_{channel.sensor.name}_{channel.generator.name}'
        filename = ' '.join(filename.split())
        pathname = CAL_ROOT / 'microphone' / channel.sensor.name / filename
        env = {
            **channel.get_env_vars(include_cal=False),
            **self.pistonphone.get_env_vars(),
        }
        self._run_cal(pathname, 'cftscal.paradigms.pistonphone_calibration', env)
