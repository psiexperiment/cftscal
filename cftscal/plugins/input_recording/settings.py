from atom.api import List, Typed

from psi import get_config

from ..settings import CalibrationSettings, InputSettings

from cftscal import CAL_ROOT


class InputRecordingSettings(CalibrationSettings):

    inputs = List(Typed(InputSettings, ()))

    def __init__(self, inputs):
        self.inputs = [InputSettings(input_label=k, input_name=v) for k, v in inputs.items()]

    def save_config(self):
        for i in self.inputs:
            i.save_config()

    def run_input_recording(self, obj):
        filename = f'{{date_time}}_{obj.generator_name}_{obj.sensor_name}'
        filename = ' '.join(filename.split())
        pathname = CAL_ROOT / 'input_recording' / obj.generator_name / filename
        env = {
            **obj.get_env_vars(),
        }
        self._run_cal(pathname, 'cftscal.paradigms.input_recording', env)
