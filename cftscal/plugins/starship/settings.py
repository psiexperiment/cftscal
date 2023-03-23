from atom.api import List, Typed

from psi import get_config

from ..settings import CalibrationSettings, MicrophoneSettings, StarshipSettings

CAL_ROOT = get_config('CAL_ROOT')


class StarshipCalibrationSettings(CalibrationSettings):

    starships = List(Typed(StarshipSettings))
    microphone = Typed(MicrophoneSettings)

    def __init__(self, outputs):
        self.starships = [StarshipSettings(output=o) for o in outputs]
        self.microphone = MicrophoneSettings()

    def save_config(self):
        self.microphone.save_config()
        for s in self.speakers:
            s.save_config()

    def run_cal_golay(self, starship, microphone):
        filename = f'{{date_time}} {starship.name} {microphone.name} pt_calibration_golay'
        filename = ' '.join(filename.split())
        pathname = CAL_ROOT / 'starship' / starship.name / filename
        env = microphone.get_env_vars()
        env.update(starship.get_env_vars())
        self._run_cal(pathname, 'pt_calibration_golay', env)

    def run_cal_chirp(self, starship, microphone):
        filename = f'{{date_time}} {starship.name} {microphone.name} pt_calibration_chirp'
        filename = ' '.join(filename.split())
        pathname = CAL_ROOT / 'starship' / starship.name / filename
        env = microphone.get_env_vars()
        env.update(starship.get_env_vars())
        self._run_cal(pathname, 'pt_calibration_chirp', env)
