from atom.api import set_default, List, Typed

from ..settings import (
    CalibrationSettings,
    InputSettings,
    MeasurementMicrophoneSettings,
    PistonphoneSettings
)


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
                sensor=MeasurementMicrophoneSettings(),
            )
            settings.append(setting)
        self.available_inputs = settings
        self.load_config()

    def get_config(self):
        config = super().get_config()
        config['pistonphone'] = self.pistonphone.get_persistence()
        return config

    def set_config(self, config):
        super().set_config(config)
        self.pistonphone.set_persistence(config.get('pistonphone', {}))

    def run_calibration(self, ai):
        filename = f'{{date_time}}_{ai.sensor.name}_{self.pistonphone.name}'
        filename = ' '.join(filename.split())
        pathname = self.data_path / 'microphone' / ai.sensor.name / filename
        env = {
            **ai.get_env_vars(include_cal=False, env_prefix='CFTS_MICROPHONE'),
            **self.pistonphone.get_env_vars(),
        }
        self._run_cal(pathname, 'cftscal.paradigms.pistonphone_calibration', env)
