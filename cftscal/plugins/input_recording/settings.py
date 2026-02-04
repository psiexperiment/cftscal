from atom.api import set_default, List, Typed

from ..settings import CalibrationSettings, InputSettings


class InputRecordingSettings(CalibrationSettings):

    available_inputs = List(Typed(InputSettings, ()))
    selected_input = Typed(InputSettings, ())
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
        self.load_config()

    def run_input_recording(self, obj):
        filename = f'{{date_time}}_{obj.generator.name}_{obj.sensor.name}'
        filename = ' '.join(filename.split())
        pathname = self.data_folder / 'input-recording' / obj.generator.name / filename
        env = {
            **obj.get_env_vars(),
        }
        self._run_cal(pathname, 'cftscal.paradigms.input_recording', env)

    def get_config(self):
        return {
            'available_inputs': {i.input_name: i.get_persistence() for i in self.available_inputs},
            'selected_input': self.selected_input.input_name,
        }

    def set_config(self, config):
        for name, settings in config.get('available_inputs', {}).items():
            for i in self.available_inputs:
                if i.input_name == name:
                    i.set_persistence(settings)
                    break
        selected_name = config['selected_input']
        for i in self.available_inputs:
            if i.input_name == selected_name:
                self.selected_input = i
