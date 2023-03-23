from atom.api import Typed

from psi import get_config

from ..settings import CalibrationSettings, MicrophoneSettings, PistonphoneSettings

CAL_ROOT = get_config('CAL_ROOT')


class MicrophoneCalibrationSettings(CalibrationSettings):

    microphone = Typed(MicrophoneSettings, ())
    pistonphone = Typed(PistonphoneSettings, ())

    def get_env_vars(self):
        return {
            **self.microphone.get_env_vars(),
            **self.pistonphone.get_env_vars(),
        }

    def save_config(self):
        self.microphone.save_config()
        self.pistonphone.save_config()

    def run_mic_cal(self):
        filename = f'{{date_time}}_{self.microphone.name}_{self.pistonphone.name}'
        filename = ' '.join(filename.split())
        pathname = CAL_ROOT / 'microphone' / self.microphone.name / filename
        self._run_cal(pathname, 'pistonphone_calibration')
