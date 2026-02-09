from atom.api import set_default, List, Typed

from ..settings import (
    CalibrationSettings,
    GenericMicrophoneSettings,
    InputSettings,
    MeasurementMicrophoneSettings,
    OutputSettings,
    SpeakerSettings,
)


class MicrophoneComparisonSettings(CalibrationSettings):

    generic_inputs = List(InputSettings).tag(persist=True)
    generic_input = Typed(InputSettings).tag(persist=True)
    measurement_inputs = List(InputSettings).tag(persist=True)
    measurement_input = Typed(InputSettings).tag(persist=True)
    speaker_outputs = List(OutputSettings).tag(persist=True)
    speaker_output = Typed(OutputSettings).tag(persist=True)
    settings_filename = set_default('microphone-generic.json')

    def __init__(self, measurement_inputs, generic_inputs, speaker_outputs):
        settings = []
        for label, name in measurement_inputs.items():
            setting = InputSettings(
                input_name=name,
                input_label=label,
                sensor=MeasurementMicrophoneSettings(),
            )
            settings.append(setting)
        self.measurement_inputs = settings
        self.measurement_input = self.measurement_inputs[0]

        settings = []
        for label, name in generic_inputs.items():
            setting = InputSettings(
                input_name=name,
                input_label=label,
                sensor=MeasurementMicrophoneSettings(),
            )
            settings.append(setting)
        self.generic_inputs = settings
        self.generic_input = self.generic_inputs[0]

        settings = []
        for label, name in speaker_outputs.items():
            setting = OutputSettings(
                output_label=label,
                output_name=name,
                generator=SpeakerSettings(),
            )
            settings.append(setting)
        self.speaker_outputs = settings
        self.speaker_output = self.speaker_outputs[0]
        self.load_config()

    def run_calibration(self, which):
        filename = f'{{date_time}}_{self.generic_input.sensor.name}_{self.measurement_input.sensor.name}_{which}'
        filename = ' '.join(filename.split())
        pathname = self.data_path / 'microphone_generic' / self.generic_input.sensor.name / filename
        env = {
            **self.measurement_input.get_env_vars(
                env_prefix='CFTS_MICROPHONE',
            ),
            # Since we are calibrating the test microphone, we do not load the
            # calibration for the microphone.
            **self.generic_input.get_env_vars(
                env_prefix='CFTS_GENERIC_MICROPHONE',
                include_cal=False,
            ),
            # It's not necessary to load the calibration for the speaker since
            # we just need a sound source that both mics can record.
            **self.speaker_output.get_env_vars(
                env_prefix='CFTS_SPEAKER',
                include_cal=False,
            ),
        }
        self._run_cal(pathname, f'cftscal.paradigms.mic_calibration_{which}', env)
