from atom.api import set_default, List, Str, Typed

from ..settings import (CalibrationSettings, InputSettings,
                        MeasurementMicrophoneSettings,
                        StarshipSettings)

class StarshipCalibrationSettings(CalibrationSettings):

    starship_connections = List(Typed(StarshipSettings, ())).tag(persist=True)
    available_inputs = List(Typed(InputSettings, ())).tag(persist=True)
    selected_input = Typed(InputSettings, ()).tag(persist=True)
    calibration_coupler = Str().tag(persist=True)
    settings_filename = set_default('starship.json')

    def __init__(self, starship_connections, inputs):
        settings = []
        for label, name in starship_connections.items():
            setting = StarshipSettings(
                connection_name=name,
                connection_label=label
            )
            settings.append(setting)
        self.starship_connections = settings

        settings = []
        for label, name in inputs.items():
            setting = InputSettings(
                input_name=name,
                input_label=label,
                sensor=MeasurementMicrophoneSettings(),
            )
            settings.append(setting)
        self.available_inputs = settings
        self.selected_input = self.available_inputs[0]

    def run_cal_golay(self, starship, microphone):
        filename = f'{{date_time}}_{starship.starship}_{microphone.input_name}_{self.calibration_coupler}_golay'
        filename = ' '.join(filename.split())
        pathname = self.data_path / 'starship' / starship.starship / filename
        env = {
            **microphone.get_env_vars(env_prefix='CFTS_MICROPHONE'),
            **starship.get_env_vars(include_cal=False),
        }
        self._run_cal(pathname, 'cftscal.paradigms.pt_calibration_golay', env)

    def run_cal_chirp(self, starship, microphone):
        filename = f'{{date_time}}_{starship.starship}_{microphone.input_name}_{self.calibration_coupler}_chirp'
        filename = ' '.join(filename.split())
        pathname = self.data_path / 'starship' / starship.name / filename
        env = microphone.get_env_vars()
        env.update(starship.get_env_vars(include_cal=False))
        self._run_cal(pathname, 'cftscal.paradigms.pt_calibration_chirp', env)
