from atom.api import set_default, List, Typed

from psi import get_config

from ..settings import CalibrationSettings, InputSettings, InputAmplifierReference

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
                sensor=InputAmplifierReference(),
            )
            settings.append(setting)
        self.available_inputs = settings

    def run_calibration(self, ai):
        pathname = self._make_path(
            'input_amplifier', ai.group_path, ai.sensor.name, '{date_time}',
        )
        env_prefix = f'CFTS_INPUT_AMPLIFIER_{ai.input_name.upper()}'
        env = {
            **ai.get_env_vars(include_cal=False, env_prefix='CFTS_INPUT_AMPLIFIER'),
            **ai.sensor.get_env_vars(include_cal=False, env_prefix=env_prefix),
        }
        metadata = {
            'total_gain': ai.sensor.total_gain,
            'freq_lb': ai.sensor.freq_lb,
            'freq_ub': ai.sensor.freq_ub,
            'filt_60Hz': ai.sensor.filt_60Hz,
        }
        self._run_cal(pathname, 'cftscal.paradigms.input_amplifier_calibration',
                      env, metadata=metadata)
