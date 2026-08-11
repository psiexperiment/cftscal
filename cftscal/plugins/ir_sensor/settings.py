from atom.api import set_default, List, Typed

from ..settings import CalibrationSettings, InputSettings, OutputSettings


class IRSensorSettings(CalibrationSettings):

    available_inputs = List(Typed(InputSettings, ())) \
        .tag(persist=True, selected='selected_input')
    available_outputs = List(Typed(OutputSettings, ())) \
        .tag(persist=True, selected='selected_output')
    selected_input = Typed(InputSettings, ())
    selected_output = Typed(OutputSettings, ())
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

    def run_recording(self, ai, ao):
        # Target = the input channel receiving the IR sensor signal.
        pathname = self._make_path(
            'ir-sensor', ai.group_path, ai.input_name, '{date_time}',
        )
        env = {
            **ai.get_env_vars(include_cal=False),
            **ao.get_env_vars(include_cal=False),
        }
        metadata = {
            'input_name': ai.input_name,
            'output_name': ao.output_name,
        }
        self._run_cal(pathname, 'cftscal.paradigms.ir_sensor',
                      env, metadata=metadata)
