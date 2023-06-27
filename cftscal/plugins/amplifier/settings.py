from atom.api import List, Typed

from psi import get_config

from ..settings import CalibrationSettings, AmplifierSettings

CAL_ROOT = get_config('CAL_ROOT')


class AmplifierCalibrationSettings(CalibrationSettings):

    amplifiers = List(Typed(AmplifierSettings, ()))

    def __init__(self, inputs):
        self.amplifiers = [AmplifierSettings(input_name=i) for i in inputs]

    def save_config(self):
        for a in self.amplifiers:
            a.save_config()

    def run_amp_cal(self, amplifier):
        filename = f'{{date_time}}_{amplifier.name}' \
            f'_{int(amplifier.cal_amplitude*1e6)}uV_{int(amplifier.gain)}x' \
            f'_{int(amplifier.freq_lb)}-{amplifier.freq_ub}Hz' \
            f'_filt-60Hz-{amplifier.filt_60Hz}'
        filename = ' '.join(filename.split())
        print(filename)
        return
        pathname = CAL_ROOT / 'amplifier' / amplifier.name / filename
        env = {
            **amplifier.get_env_vars(include_cal=False),
        }
        self._run_cal(pathname, 'amplifier_calibration', env)
