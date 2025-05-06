import json

from atom.api import List, Str, Typed

from psi import get_config, get_config_folder

from ..settings import CalibrationSettings, MicrophoneSettings, StarshipSettings

from cftscal import CAL_ROOT


class StarshipCalibrationSettings(CalibrationSettings):

    starships = List(Typed(StarshipSettings))
    microphones = List(Typed(MicrophoneSettings))
    selected_microphone = Typed(MicrophoneSettings)
    calibration_coupler = Str()

    def __init__(self, outputs, inputs):
        self.starships = [StarshipSettings(output=o) for o in outputs]
        self.microphones = [MicrophoneSettings(input_name=n, input_label=l) for l, n in inputs.items()]
        self.selected_microphone = self.microphones[0]
        self.load_config()

    def save_config(self):
        for m in self.microphones:
            m.save_config()
        for s in self.starships:
            s.save_config()
        file = get_config_folder() / 'cfts' / 'calibration' / \
            'starship_calibration.json'
        config = {'calibration_coupler': self.calibration_coupler}
        file.write_text(json.dumps(config, indent=2))

    def load_config(self):
        file = get_config_folder() / 'cfts' / 'calibration' / \
            'starship_calibration.json'
        if not file.exists():
            return
        config = json.loads(file.read_text())
        for k, v in config.items():
            try:
                setattr(self, k, v)
            except Exception as e:
                pass

    def run_cal_golay(self, starship, microphone):
        filename = f'{{date_time}}_{starship.name}_{microphone.name}_{self.calibration_coupler}_golay'
        filename = ' '.join(filename.split())
        pathname = CAL_ROOT / 'starship' / starship.name / filename
        env = {
            **microphone.get_env_vars(),
            **starship.get_env_vars(include_cal=False),
        }
        self._run_cal(pathname, 'cftscal.paradigms.pt_calibration_golay', env)

    def run_cal_chirp(self, starship, microphone):
        filename = f'{{date_time}}_{starship.name}_{microphone.name}_{self.calibration_coupler}_chirp'
        filename = ' '.join(filename.split())
        pathname = CAL_ROOT / 'starship' / starship.name / filename
        env = microphone.get_env_vars()
        env.update(starship.get_env_vars(include_cal=False))
        self._run_cal(pathname, 'cftscal.paradigms.pt_calibration_chirp', env)
