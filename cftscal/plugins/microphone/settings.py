from atom.api import List, Typed

from psi import get_config

from ..settings import CalibrationSettings, MicrophoneSettings, PistonphoneSettings

from cftscal import CAL_ROOT


class MicrophoneCalibrationSettings(CalibrationSettings):

    microphones = List(Typed(MicrophoneSettings, ()))
    pistonphone = Typed(PistonphoneSettings, ())

    def __init__(self, inputs):
        self.microphones = [MicrophoneSettings(input_label=k, input_name=v) \
                            for k, v in inputs.items()]
        self.pistonphone = PistonphoneSettings()

    def save_config(self):
        for m in self.microphones:
            m.save_config()
        self.pistonphone.save_config()

    def run_mic_cal(self, microphone):
        filename = f'{{date_time}}_{microphone.connected_device}_{self.pistonphone.name}'
        filename = ' '.join(filename.split())
        pathname = CAL_ROOT / 'microphone' / microphone.connected_device / filename
        env = {
            **microphone.get_env_vars(include_cal=False),
            **self.pistonphone.get_env_vars(),
        }
        self._run_cal(pathname, 'cftscal.paradigms::pistonphone_calibration', env)
