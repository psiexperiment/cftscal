from pathlib import Path

from atom.api import set_default, List, Typed

from psi import get_config

from ..settings import (
    CalibrationSettings,
    InputSettings,
    MeasurementMicrophoneSettings,
    OutputSettings,
    SpeakerSettings,
)

from cftscal import CAL_ROOT


class SpeakerCalibrationSettings(CalibrationSettings):

    available_outputs = List(Typed(OutputSettings, ()))
    available_inputs = List(Typed(InputSettings, ()))
    selected_input = Typed(InputSettings, ())
    settings_filename = set_default('speaker.json')

    def __init__(self, outputs, inputs):
        settings = []
        for label, name in outputs.items():
            setting = OutputSettings(
                output_label=label,
                output_name=name,
                generator=SpeakerSettings(),
                env_prefix='CFTS_SPEAKER',
            )
            settings.append(setting)
        self.available_outputs = settings

        settings = []
        for label, name in inputs.items():
            setting = InputSettings(
                input_label=label,
                input_name=name,
                sensor=MeasurementMicrophoneSettings(),
                env_prefix='CFTS_MICROPHONE',
            )
            settings.append(setting)
        self.available_inputs = settings
        self.selected_input = self.available_inputs[0]

    def save_config(self):
        for m in self.microphones:
            m.save_config()
        for s in self.speakers:
            s.save_config()

    def run_cal(self, ao, ai, which):
        filename = f'{{date_time}}_{ao.generator.name}_{ai.sensor.name}_{which}'
        pathname = CAL_ROOT / 'speaker' / ao.generator.name / filename
        env = ai.get_env_vars()
        env.update(ao.get_env_vars(include_cal=False))
        self._run_cal(pathname, f'cftscal.paradigms.speaker_calibration_{which}', env)
