import json

from atom.api import List, Str, Typed

from psi import get_config, get_config_folder

from ..settings import (
    CalibrationSettings,
    GenericMicrophoneSettings,
    MeasurementMicrophoneSettings,
    SpeakerSettings,
)

from cftscal import CAL_ROOT


class MicrophoneComparisonSettings(CalibrationSettings):

    generic_inputs = List(GenericMicrophoneSettings)
    measurement_inputs = List(MeasurementMicrophoneSettings)

    generic_input = Typed(GenericMicrophoneSettings)
    measurement_input = Typed(MeasurementMicrophoneSettings)

    speaker_outputs = List(SpeakerSettings)
    speaker_output = Typed(SpeakerSettings)

    def __init__(self, measurement_inputs, generic_inputs, speaker_outputs):
        self.measurement_inputs = [MeasurementMicrophoneSettings(input_name=n, input_label=l) for l, n in measurement_inputs.items()]
        self.generic_inputs = [GenericMicrophoneSettings(input_name=n, input_label=l) for l, n in generic_inputs.items()]
        self.speaker_outputs = [SpeakerSettings(output_name=n, output_label=l) for l, n in speaker_outputs.items()]
        self.generic_input = self.generic_inputs[0]
        self.measurement_input = self.measurement_inputs[0]
        self.speaker_output = self.speaker_outputs[0]

    def save_config(self):
        self.generic_input.save_config()
        self.measurement_input.save_config()
        self.speaker_output.save_config()

    def run_cal_golay(self):
        filename = f'{{date_time}}_{self.generic_input.name}_{self.generic_input.name}_golay'
        filename = ' '.join(filename.split())
        pathname = CAL_ROOT / 'microphone_comparison' / self.generic_input.name / filename
        env = {
            **self.measurement_input.get_env_vars(),
            # Since we are calibrating the test microphone, we do not load the
            # calibration for the microphone.
            **self.generic_input.get_env_vars(include_cal=False),
            # It's not necessary to load the calibration for the speaker since
            # we just need a sound source that both mics can record.
            **self.speaker_output.get_env_vars(include_cal=False),
        }
        self._run_cal(pathname, 'cftscal.paradigms.mic_calibration_golay', env)

    def run_cal_chirp(self):
        filename = f'{{date_time}}_{self.generic_input.name}_{self.generic_input.name}_chirp'
        filename = ' '.join(filename.split())
        pathname = CAL_ROOT / 'microphone_comparison' / self.generic_input.name / filename
        env = {
            **self.measurement_input.get_env_vars(),
            # Since we are calibrating the test microphone, we do not load the
            # calibration for the microphone.
            **self.generic_input.get_env_vars(include_cal=False),
            # It's not necessary to load the calibration for the speaker since
            # we just need a sound source that both mics can record.
            **self.speaker_output.get_env_vars(include_cal=False),
        }
        self._run_cal(pathname, 'cftscal.paradigms.mic_calibration_chirp', env)
