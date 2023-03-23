from atom.api import Float, List, Str

from psi import get_config
from cftscal.objects import starship_manager, CFTSStarshipLoader

from ..settings import PersistentSettings

CAL_ROOT = get_config('CAL_ROOT')
cfts_starship_loader = CFTSStarshipLoader()


class StarshipSettings(PersistentSettings):

    output = Str()
    starship = Str()
    starship_gain = Float(40)
    ear = Str()
    available_starships = List().tag(transient=True)
    available_ears = List().tag(transient=True)

    def _default_available_starships(self):
        return sorted(cfts_starship_loader.list_names())

    def _default_available_ears(self):
        return sorted(cfts_inear_loader.list_names())

    def _get_filename(self):
        return f'output_{self.output}.json'

    def _default_starship(self):
        try:
            return next(cfts_starship_loader.list_names())
        except StopIteration:
            return ''

    def _default_ear(self):
        try:
            return next(cfts_inear_loader.list_names())
        except StopIteration:
            return ''

    def get_env_vars(self):
        starship = starship_manager.get_object(self.starship)
        cal = starship.get_current_calibration()
        return {
            'CFTS_TEST_STARSHIP': self.output,
            f'CFTS_STARSHIP_{self.output}_GAIN': str(self.starship_gain),
            f'CFTS_STARSHIP_{self.output}': cal.to_string()
        }

    def run_pt_cal_golay(self, mic_settings):
        filename = f'{{date_time}} {self.starship} {mic_settings.microphone} pt_calibration_golay'
        filename = ' '.join(filename.split())
        pathname = CAL_ROOT / 'starship' / self.starship / filename
        env = mic_settings.get_env_vars()
        self._run_cal(pathname, 'pt_calibration_golay', env)

    def run_pt_cal_chirp(self):
        filename = f'{{date_time}} {self.starship} {mic_settings.microphone} pt_calibration_chirp'
        filename = ' '.join(filename.split())
        pathname = CAL_ROOT / 'starship' / self.starship / filename
        env = mic_settings.get_env_vars()
        self._run_cal(pathname, 'pt_calibration_chirp', env)

    def run_inear_cal_chirp(self, save=True):
        filename = f'{{date_time}} {self.ear} {self.starship}'
        filename = ' '.join(filename.split())
        pathname = CAL_ROOT / 'inear' / self.ear / filename
        self._run_cal(pathname, 'inear_speaker_calibration_chirp')
