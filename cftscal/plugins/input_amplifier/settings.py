from atom.api import List, Typed

from psi import get_config

from ..settings import CalibrationSettings, InputAmplifierSettings

CAL_ROOT = get_config('CAL_ROOT')


class InputAmplifierCalibrationSettings(CalibrationSettings):

    input_amplifiers = List(Typed(InputAmplifierSettings, ()))

    def __init__(self, inputs):
        self.input_amplifiers = [InputAmplifierSettings(name=k, input_name=v) \
                                 for k, v in inputs.items()]

    def save_config(self):
        for a in self.input_amplifiers:
            a.save_config()

    def run_amp_cal(self, input_amplifier):
        filename = input_amplifier._get_filename()
        pathname = CAL_ROOT / 'input_amplifier' / input_amplifier.name / filename
        env = {
            **input_amplifier.get_env_vars(include_cal=False),
        }
        self._run_cal(pathname, 'input_amplifier_calibration', env)
