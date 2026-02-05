from atom.api import set_default, List, Typed

from ..settings import CalibrationSettings, InputSettings, OutputSettings


class IRSensorSettings(CalibrationSettings):

    available_inputs = List(Typed(InputSettings, ()))
    available_outputs = List(Typed(OutputSettings, ()))
    selected_input = Typed(InputSettings)
    selected_output = Typed(OutputSettings)
    settings_filename = set_default('ir-sensor.json')

    def __init__(self, inputs, outputs):
        settings = []
        for label, name in inputs.items():
            setting = InputSettings(
                input_label=label,
                input_name=name,
            )
            settings.append(setting)
        self.available_inputs = settings
        self.selected_input = settings[0]

        settings = []
        for label, name in outputs.items():
            setting = OutputSettings(
                output_label=label,
                output_name=name,
            )
            settings.append(setting)
        self.available_outputs = settings
        self.selected_output = settings[0]
        self.load_config()

    def run_recording(self, ai, ao):
        filename = f'{{date_time}}_{ao.generator.name}_{ai.sensor.name}'
        filename = ' '.join(filename.split())
        pathname = self.data_path / 'ir-sensor' / ai.sensor.name / filename
        env = {
            **ai.get_env_vars(include_cal=False),
            **ao.get_env_vars(include_cal=False),
        }
        self._run_cal(pathname, 'cftscal.paradigms.ir_sensor', env)
