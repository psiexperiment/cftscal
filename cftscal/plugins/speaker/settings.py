from pathlib import Path

from atom.api import List, Typed

from psi import get_config

from ..settings import CalibrationSettings, MicrophoneSettings, SpeakerSettings

from cftscal import CAL_ROOT


class SpeakerCalibrationSettings(CalibrationSettings):

    speakers = List(Typed(SpeakerSettings))
    microphones = List(Typed(MicrophoneSettings))
    selected_microphone = Typed(MicrophoneSettings)

    def __init__(self, outputs, inputs):
        self.speakers = [SpeakerSettings(output_name=n, output_label=l) for l, n in outputs.items()]
        self.microphones = [MicrophoneSettings(input_name=n, input_label=l) for l, n in inputs.items()]
        self.selected_microphone = self.microphones[0]

    def save_config(self):
        for m in self.microphones:
            m.save_config()
        for s in self.speakers:
            s.save_config()

    def run_cal_golay(self, speaker, microphone):
        filename = f'{{date_time}}_{speaker.name}_{microphone.name}_golay'
        pathname = CAL_ROOT / 'speaker' / speaker.name / filename

        env = microphone.get_env_vars()
        env.update(speaker.get_env_vars(include_cal=False))
        self._run_cal(pathname, 'cftscal.paradigms.speaker_calibration_golay', env)

    def run_cal_chirp(self, speaker, microphone):
        filename = f'{{date_time}}_{speaker.name}_{microphone.name}_chirp'
        pathname = CAL_ROOT / 'speaker' / speaker.name / filename

        env = microphone.get_env_vars()
        env.update(speaker.get_env_vars(include_cal=False))
        self._run_cal(pathname, 'cftscal.paradigms.speaker_calibration_chirp', env)
