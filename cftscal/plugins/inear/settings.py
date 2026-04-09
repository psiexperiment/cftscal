from atom.api import set_default, List, Typed

from ..settings import CalibrationSettings, InEarSettings


class InEarCalibrationSettings(CalibrationSettings):

    ears = List(Typed(InEarSettings))
    available_outputs = List(Typed(InEarSettings))
    settings_filename = set_default('inear.json')

    def __init__(self, outputs):
        settings = []
        for label, name in outputs.items():
            setting = InEarSettings(output=name)
            settings.append(setting)
        self.ears = settings

    def run_cal(self, ear):
        filename = f'{{date_time}}_{ear.ear}_{ear.name}'
        filename = ' '.join(filename.split())
        pathname = self.data_path / 'inear' / ear.ear / filename
        env = ear.get_env_vars()
        self._run_cal(pathname, 'cftscal.paradigms.iec', env)
