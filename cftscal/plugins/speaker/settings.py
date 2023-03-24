from atom.api import List, Typed

from psi import get_config

from ..settings import CalibrationSettings, MicrophoneSettings, SpeakerSettings

CAL_ROOT = get_config('CAL_ROOT')


class SpeakerCalibrationSettings(CalibrationSettings):

    speakers = List(Typed(SpeakerSettings))
    microphone = Typed(MicrophoneSettings)

    def __init__(self, outputs):
        self.speakers = [SpeakerSettings(output=o) for o in outputs]
        self.microphone = MicrophoneSettings()

    def save_config(self):
        self.microphone.save_config()
        for s in self.speakers:
            s.save_config()

    def run_cal_golay(self, speaker, microphone):
        filename = f'{{date_time}} {speaker.name} {microphone.name} speaker_calibration_golay'
        filename = ' '.join(filename.split())
        pathname = CAL_ROOT / 'speaker' / speaker.name / filename

        env = microphone.get_env_vars()
        env.update(speaker.get_env_vars(include_cal=False))
        self._run_cal(pathname, 'speaker_calibration_golay', env)

    def run_cal_chirp(self, speaker, microphone):
        filename = f'{{date_time}} {speaker.name} {microphone.name} speaker_calibration_chirp'
        filename = ' '.join(filename.split())
        pathname = CAL_ROOT / 'speaker' / speaker.name / filename

        env = microphone.get_env_vars()
        env.update(speaker.get_env_vars(include_cal=False))
        self._run_cal(pathname, 'speaker_calibration_chirp', env)
