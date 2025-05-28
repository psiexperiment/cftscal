import json

from atom.api import List, Str, Typed

from psi import get_config, get_config_folder

from ..settings import (
    CalibrationSettings,
    GenericMicrophoneSettings,
    MeasurementMicrophoneSettings,
)

from cftscal import CAL_ROOT


class MicrophoneComparisonSettings(CalibrationSettings):

    generic_inputs = List(GenericMicrophoneSettings)
    measurement_inputs = List(MeasurementMicrophoneSettings)

    generic_input = Typed(GenericMicrophoneSettings)
    measurement_input = Typed(MeasurementMicrophoneSettings)

    def __init__(self, inputs):
        self.measurement_inputs = [MeasurementMicrophoneSettings(input_name=n, input_label=l) for l, n in inputs.items()]
        self.generic_inputs = [GenericMicrophoneSettings(input_name=n, input_label=l) for l, n in inputs.items()]
        self.generic_input = self.generic_inputs[0]
        self.measurement_input = self.measurement_inputs[-1]

    def save_config(self):
        self.generic_input.save_config()
        self.measurement_input.save_config()

    def run_cal_golay(self):
        filename = f'{{date_time}}_{self.generic_input.name}_{self.generic_input.name}_golay'
        filename = ' '.join(filename.split())
        pathname = CAL_ROOT / 'microphone_comparison' / self.generic_input.name / filename
        env = {
            **self.measurement_input.get_env_vars(),
            # Since we are calibrating the test microphone, we do not load the
            # calibration for the microphone.
            **self.generic_input.get_env_vars(include_cal=False),
        }
        self._run_cal(pathname, 'cftscal.paradigms.pt_calibration_golay', env)

    def run_cal_chirp(self):
        filename = f'{{date_time}}_{self.generic_input.name}_{self.generic_input.name}_chirp'
        filename = ' '.join(filename.split())
        pathname = CAL_ROOT / 'microphone_comparison' / self.generic_input.name / filename
        env = {
            **self.measurement_input.get_env_vars(),
            # Since we are calibrating the test microphone, we do not load the
            # calibration for the microphone.
            **self.generic_input.get_env_vars(include_cal=False),
        }
        self._run_cal(pathname, 'cftscal.paradigms.pt_calibration_chirp', env)
