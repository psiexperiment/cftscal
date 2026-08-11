from pathlib import Path

from atom.api import set_default, List, Typed

from psi import get_config

from ..settings import (
    CalibrationSettings,
    InputSettings,
    MeasurementMicrophoneReference,
    OutputSettings,
    SpeakerSettings,
)


class SpeakerCalibrationSettings(CalibrationSettings):

    available_outputs = List(Typed(OutputSettings, ())) \
        .tag(persist=True, selected='selected_output')
    selected_output = Typed(OutputSettings, ())
    available_inputs = List(Typed(InputSettings, ())) \
        .tag(persist=True, selected='selected_input')
    selected_input = Typed(InputSettings, ())
    settings_filename = set_default('speaker.json')

    def __init__(self, outputs, inputs):
        settings = []
        for label, name in outputs.items():
            setting = OutputSettings(
                output_label=label,
                output_name=name,
                generator=SpeakerSettings(),
            )
            settings.append(setting)
        self.available_outputs = settings
        self.selected_output = self.available_outputs[0]

        settings = []
        for label, name in inputs.items():
            setting = InputSettings(
                input_label=label,
                input_name=name,
                sensor=MeasurementMicrophoneReference(),
            )
            settings.append(setting)
        self.available_inputs = settings
        self.selected_input = self.available_inputs[0]

    def run_cal(self, ao, ai, which):
        # Target = the speaker output being calibrated.
        pathname = self._make_path(
            'speaker', ao.group_path, ao.generator.name, '{date_time}',
        )
        env = ai.get_env_vars(env_prefix='CFTS_MICROPHONE')
        env.update(ao.get_env_vars(include_cal=False, env_prefix='CFTS_SPEAKER'))
        metadata = {
            'microphone': ai.sensor.name,
            'microphone_channel': ai.input_label,
            'output_channel': ao.output_label,
            'gain': ai.sensor.gain,
            'method': which,
        }
        self._run_cal(pathname, f'cftscal.paradigms.speaker_calibration_{which}',
                      env, metadata=metadata)
