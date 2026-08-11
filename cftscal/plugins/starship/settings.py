from atom.api import set_default, List, Str, Typed

from ..settings import (CalibrationSettings, InputSettings,
                        MeasurementMicrophoneReference,
                        StarshipSettings)

class StarshipCalibrationSettings(CalibrationSettings):

    starship_connections = List(Typed(StarshipSettings, ())) \
        .tag(persist=True, selected='selected_starship')
    selected_starship = Typed(StarshipSettings, ())
    available_inputs = List(Typed(InputSettings, ())) \
        .tag(persist=True, selected='selected_input')
    selected_input = Typed(InputSettings, ())
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
        self.selected_starship = self.starship_connections[0]

        settings = []
        for label, name in inputs.items():
            setting = InputSettings(
                input_name=name,
                input_label=label,
                sensor=MeasurementMicrophoneReference(),
            )
            settings.append(setting)
        self.available_inputs = settings
        self.selected_input = self.available_inputs[0]

    def run_cal_golay(self, starship, microphone):
        pathname = self._make_path(
            'starship', starship.group_path, starship.starship, '{date_time}',
        )
        env = {
            **microphone.get_env_vars(env_prefix='CFTS_MICROPHONE'),
            **starship.get_env_vars(include_cal=False),
        }
        metadata = {
            'microphone': microphone.sensor.name,
            'microphone_channel': microphone.input_label,
            'starship_channel': starship.connection_label,
            'coupler': self.calibration_coupler,
            'gain': starship.gain,
            'stimulus': 'golay',
        }
        self._run_cal(pathname, 'cftscal.paradigms.pt_calibration_golay',
                      env, metadata=metadata)

    def run_cal_chirp(self, starship, microphone):
        pathname = self._make_path(
            'starship', starship.group_path, starship.name, '{date_time}',
        )
        env = microphone.get_env_vars()
        env.update(starship.get_env_vars(include_cal=False))
        metadata = {
            'microphone': microphone.sensor.name,
            'microphone_channel': microphone.input_label,
            'starship_channel': starship.connection_label,
            'coupler': self.calibration_coupler,
            'gain': starship.gain,
            'stimulus': 'chirp',
        }
        self._run_cal(pathname, 'cftscal.paradigms.pt_calibration_chirp',
                      env, metadata=metadata)
