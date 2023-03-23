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

    def get_env_vars(self):
        return {
            **self.speaker.get_env_vars(),
            **self.microphone.get_env_vars(),
        }

    def save_config(self):
        self.microphone.save_config()
        for s in self.speakers:
            s.save_config()

    def run_cal_golay(self, mic_settings):
        filename = f'{{date_time}} {self.speaker} {mic_settings.microphone} speaker_calibration_golay'
        filename = ' '.join(filename.split())
        pathname = CAL_ROOT / 'speaker' / self.speaker / filename
        env = mic_settings.get_env_vars()
        self._run_cal(pathname, 'speaker_calibration_golay', env)

    def run_cal_chirp(self):
        filename = f'{{date_time}} {self.speaker} {mic_settings.microphone} speaker_calibration_chirp'
        filename = ' '.join(filename.split())
        pathname = CAL_ROOT / 'speaker' / self.speaker / filename
        env = mic_settings.get_env_vars()
        self._run_cal(pathname, 'speaker_calibration_chirp', env)
