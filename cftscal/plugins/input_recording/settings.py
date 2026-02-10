from atom.api import set_default, List, Typed

from ..settings import CalibrationSettings, GeneratorSettings, InputSettings


class InputRecordingSettings(CalibrationSettings):

    available_inputs = List(Typed(InputSettings, ())).tag(persist=True)
    selected_input = Typed(InputSettings, ()).tag(persist=True)
    generator = Typed(GeneratorSettings, ()).tag(persist=True)
    settings_filename = set_default('input-recording.json')

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

    def run_input_recording(self, ai):
        filename = f'{{date_time}}_{self.generator.name}_{ai.sensor.name}'
        filename = ' '.join(filename.split())
        pathname = self.data_path / 'input-recording' / self.generator.name / filename
        env = {
            **ai.get_env_vars(),
        }
        self._run_cal(pathname, 'cftscal.paradigms.input_recording', env)
