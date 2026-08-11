from atom.api import set_default, List, Typed

from ..settings import (
    CalibrationSettings,
    InputSettings,
    MeasurementMicrophoneReference,
    OutputSettings,
    SensorDevice,
    SpeakerSettings,
)


class MicrophoneComparisonSettings(CalibrationSettings):

    generic_inputs = List(InputSettings) \
        .tag(persist=True, selected='generic_input')
    generic_input = Typed(InputSettings)
    measurement_inputs = List(InputSettings) \
        .tag(persist=True, selected='measurement_input')
    measurement_input = Typed(InputSettings)
    speaker_outputs = List(OutputSettings) \
        .tag(persist=True, selected='speaker_output')
    speaker_output = Typed(OutputSettings)
    settings_filename = set_default('microphone-generic.json')

    def __init__(self, measurement_inputs, generic_inputs, speaker_outputs):
        settings = []
        for label, name in measurement_inputs.items():
            # Reference — the measurement mic supplies the ground-truth
            # calibration used to calibrate the generic mic.
            setting = InputSettings(
                input_name=name,
                input_label=label,
                sensor=MeasurementMicrophoneReference(),
            )
            settings.append(setting)
        self.measurement_inputs = settings
        self.measurement_input = self.measurement_inputs[0]

        settings = []
        for label, name in generic_inputs.items():
            # Device — the generic mic is the thing being calibrated.
            # Its ``sensor.name`` is a free-form device identifier that
            # ends up in the calibration's metadata.
            setting = InputSettings(
                input_name=name,
                input_label=label,
                sensor=SensorDevice(),
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

    def run_calibration(self, which):
        # Target = the generic input (that's the thing being calibrated).
        pathname = self._make_path(
            'microphone_generic',
            self.generic_input.group_path,
            self.generic_input.sensor.name,
            '{date_time}',
        )
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
        metadata = {
            'input_channel': self.generic_input.input_label,
            'gain': self.generic_input.sensor.gain,
            'microphone': self.measurement_input.sensor.name,
            'microphone_channel': self.measurement_input.input_label,
            'speaker': self.speaker_output.generator.name,
            'speaker_channel': self.speaker_output.output_label,
            'stimulus': which,
        }
        self._run_cal(pathname, f'cftscal.paradigms.mic_calibration_{which}',
                      env, metadata=metadata)
