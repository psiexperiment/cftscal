from atom.api import set_default, List, Typed

from ..settings import CalibrationSettings, InEarSettings


class InEarCalibrationSettings(CalibrationSettings):

    ears = List(Typed(InEarSettings)).tag(persist=True)
    settings_filename = set_default('inear.json')

    def __init__(self, outputs):
        settings = []
        for label, name in outputs.items():
            setting = InEarSettings(
                connection_name=name,
                connection_label=label
            )
            settings.append(setting)
        self.ears = settings

    def run_cal(self, ear):
        filename = f'{{date_time}}_{ear.ear}_{ear.starship}'
        filename = ' '.join(filename.split())
        pathname = self.data_path / 'inear' / ear.ear / filename
        env = ear.get_env_vars()
        self._run_cal(pathname, 'cftscal.paradigms.iec', env)
