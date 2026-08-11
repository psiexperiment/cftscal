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
        # Target = the starship (device ID) being checked -- the master
        # folder for inear calibrations, not the coupler.  InEarSettings
        # inherits group_path from StarshipSettings.
        pathname = self._make_path(
            'inear', ear.group_path, ear.starship, '{date_time}',
        )
        env = ear.get_env_vars()
        metadata = {
            'coupler': ear.coupler,
            'starship': ear.starship,
            'gain': ear.gain,
            'output': ear.output,
        }
        self._run_cal(pathname, 'cftscal.paradigms.iec', env, metadata=metadata)
