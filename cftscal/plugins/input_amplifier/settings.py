from atom.api import set_default, List, Typed

from psi import get_config

from ..settings import CalibrationSettings, InputSettings, InputAmplifierSettings

from cftscal import CAL_ROOT


class InputAmplifierCalibrationSettings(CalibrationSettings):

    available_inputs = List(Typed(InputSettings, ())).tag(persist=True)
    settings_filename = set_default('input-amplifier.json')

    def __init__(self, inputs):
        settings = []
        for label, name in inputs.items():
            setting = InputSettings(
                input_name=name,
                input_label=label,
                sensor=InputAmplifierSettings(),
            )
            settings.append(setting)
        self.available_inputs = settings

    def run_calibration(self, ai):
        filename = f'{{date_time}}_{ai.sensor.name}' \
            f'_{ai.sensor.total_gain}x_{ai.sensor.freq_lb}-{ai.sensor.freq_ub}Hz' \
            f'-filt-60Hz-{ai.sensor.filt_60Hz}'
        filename = ' '.join(filename.split())
        pathname = self.data_path / 'input_amplifier' / ai.sensor.name / filename
        env_prefix = f'CFTS_INPUT_AMPLIFIER_{ai.input_name.upper()}'
        env = {
            **ai.get_env_vars(include_cal=False, env_prefix='CFTS_INPUT_AMPLIFIER'),
            **ai.sensor.get_env_vars(include_cal=False, env_prefix=env_prefix),
        }
        self._run_cal(pathname, 'cftscal.paradigms.input_amplifier_calibration', env)
