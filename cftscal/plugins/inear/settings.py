from atom.api import List, Typed

from psi import get_config

from ..settings import CalibrationSettings, InEarSettings

CAL_ROOT = get_config('CAL_ROOT')


class InEarCalibrationSettings(CalibrationSettings):

    ears = List(Typed(InEarSettings))

    def __init__(self, outputs):
        self.ears = [InEarSettings(output=o) for o in outputs]

    def save_config(self):
        for e in self.ears:
            e.save_config()

    def run_cal(self, ear):
        filename = f'{{date_time}}_{ear.ear}_{ear.name}_inear_speaker_calibration_chirp'
        filename = ' '.join(filename.split())
        pathname = CAL_ROOT / 'inear' / ear.ear / filename
        env = ear.get_env_vars()
        self._run_cal(pathname, 'inear', env)
