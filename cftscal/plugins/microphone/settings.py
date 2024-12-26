import json

from atom.api import List, Typed

from psi import get_config, get_config_folder

from ..settings import CalibrationSettings, MicrophoneSettings, PistonphoneSettings

from cftscal import CAL_ROOT


class MicrophoneCalibrationSettings(CalibrationSettings):

    selected_input = Typed(MicrophoneSettings, ())
    microphones = List(Typed(MicrophoneSettings, ()))
    pistonphone = Typed(PistonphoneSettings, ())

    def __init__(self, inputs):
        self.microphones = [MicrophoneSettings(input_label=k, input_name=v) \
                            for k, v in inputs.items()]
        self.pistonphone = PistonphoneSettings()
        self.selected_input = self.microphones[0]
        self.load_config()

    def save_config(self):
        for m in self.microphones:
            m.save_config()
        self.pistonphone.save_config()
        file = get_config_folder() / 'cfts' / 'calibration' / \
            'microphone_calibration.json'
        config = {'selected_input': self.selected_input.input_name}
        file.write_text(json.dumps(config, indent=2))

    def load_config(self):
        file = get_config_folder() / 'cfts' / 'calibration' / \
            'microphone_calibration.json'
        if not file.exists():
            return
        config = json.loads(file.read_text())
        selected_input = config.pop('selected_input')
        for microphone in self.microphones:
            if microphone.input_name == selected_input:
                self.selected_input = microphone
                break

    def run_mic_cal(self, microphone):
        filename = f'{{date_time}}_{microphone.connected_device}_{self.pistonphone.name}'
        filename = ' '.join(filename.split())
        pathname = CAL_ROOT / 'microphone' / microphone.connected_device / filename
        env = {
            **microphone.get_env_vars(include_cal=False),
            **self.pistonphone.get_env_vars(),
        }
        self._run_cal(pathname, 'cftscal.paradigms::pistonphone_calibration', env)
