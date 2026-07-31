from atom.api import set_default, List, Typed

from ..settings import (
    CalibrationSettings,
    InputSettings,
    PistonphoneSettings,
    SensorDevice,
)


class MicrophoneCalibrationSettings(CalibrationSettings):

    available_inputs = List(Typed(InputSettings, ())) \
        .tag(persist=True, selected='selected_input')
    selected_input = Typed(InputSettings, ())
    pistonphone = Typed(PistonphoneSettings, ()).tag(persist=True)
    settings_filename = set_default('microphone-measurement.json')

    def __init__(self, inputs):
        settings = []
        for label, name in inputs.items():
            setting = InputSettings(
                input_name=name,
                input_label=label,
                sensor=SensorDevice(),
            )
            settings.append(setting)
        self.available_inputs = settings
        self.selected_input = self.available_inputs[0]

    def run_calibration(self, ai):
        pathname = self._make_path(
            'microphone', ai.group_path, ai.sensor.name, '{date_time}',
        )
        env = {
            **ai.get_env_vars(include_cal=False, env_prefix='CFTS_MICROPHONE'),
            **self.pistonphone.get_env_vars(),
        }
        metadata = {
            'pistonphone': self.pistonphone.name,
            'sensor_id': ai.sensor.name,
            'gain': ai.sensor.gain,
            'input_channel': ai.input_label,
        }
        self._run_cal(pathname, 'cftscal.paradigms.pistonphone_calibration',
                      env, metadata=metadata)
