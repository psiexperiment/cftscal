from atom.api import set_default, List, Typed

from ..settings import CalibrationSettings, GeneratorSettings, InputSettings


class InputRecordingSettings(CalibrationSettings):

    available_inputs = List(Typed(InputSettings, ()))
    selected_input = Typed(InputSettings, ())
    settings_filename = set_default('input-recording.json')
    generator = Typed(GeneratorSettings, ())

    def __init__(self, inputs):
        settings = []
        for label, name in inputs.items():
            setting = InputSettings(
                input_label=label,
                input_name=name,
            )
            settings.append(setting)
        self.available_inputs = settings
        self.selected_input = settings[0]
        self.generator = GeneratorSettings()
        self.load_config()

    def get_config(self):
        config = super().get_config()
        config['generator'] = self.generator.get_persistence()
        return config

    def set_config(self, config):
        super().set_config(config)
        self.generator.set_persistence(config.get('generator', {}))

    def run_input_recording(self, ai):
        filename = f'{{date_time}}_{self.generator.name}_{ai.sensor.name}'
        filename = ' '.join(filename.split())
        pathname = self.data_path / 'input-recording' / self.generator.name / filename
        env = {
            **ai.get_env_vars(),
        }
        self._run_cal(pathname, 'cftscal.paradigms.input_recording', env)
