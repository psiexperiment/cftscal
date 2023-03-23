import json
import os
import subprocess

from atom.api import Atom, Float, List, Property, Str

from psi import get_config_folder
from psi.util import get_tagged_values


from cftscal.objects import microphone_manager, speaker_manager


class PersistentSettings(Atom):

    filename = Property()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_config()

    def save_config(self):
        file = get_config_folder() / 'cfts' / 'calibration' / self.filename
        file.parent.mkdir(exist_ok=True, parents=True)
        config = {m: getattr(self, m) for m in self.members()}
        file.write_text(json.dumps(config, indent=2))

    def load_config(self):
        file = get_config_folder() / 'cfts' / 'calibration' / self.filename
        if not file.exists():
            return
        config = json.loads(file.read_text())
        for k, v in config.items():
            try:
                setattr(self, k, v)
            except Exception as e:
                pass


class CalibrationSettings(Atom):

    def _run_cal(self, filename, experiment, env=None):
        if env is None:
            env = {}
        env = {**os.environ, **env, **self.get_env_vars()}
        args = ['psi', experiment, str(filename)]
        print(' '.join(args))
        subprocess.check_output(args, env=env)


class MicrophoneSettings(PersistentSettings):

    name = Str()
    gain = Float(20)
    available_microphones = Property()

    def _get_available_microphones(self):
        return sorted(microphone_manager.list_names('CFTS'))

    def get_env_vars(self):
        mic = microphone_manager.get_object(self.name)
        env = {
            'CFTS_CAL_MIC_GAIN': str(self.gain),
        }
        try:
            env['CFTS_CAL_MIC'] = mic.get_current_calibration().to_string()
        except IndexError:
            pass
        return env

    def _get_filename(self):
        return 'microphone.json'

    def _default_name(self):
        try:
            return self.available_microphones[0]
        except IndexError:
            return ''


class PistonphoneSettings(PersistentSettings):

    name = Str()
    frequency = Float(1e3)
    level = Float(114)

    def _get_filename(self):
        return 'pistonphone.json'

    def get_env_vars(self):
        return {
            'CFTS_PISTONPHONE_LEVEL': str(self.level),
            'CFTS_PISTONPHONE_FREQUENCY': str(self.frequency),
        }


class SpeakerSettings(PersistentSettings):

    output = Str()
    name = Str()
    available_speakers = Property()

    def _get_available_speakers(self):
        return sorted(speaker_manager.list_names('CFTS'))

    def _get_filename(self):
        return f'speaker_{self.output}.json'

    def _default_name(self):
        try:
            return self.available_speakers[0]
        except IndexError:
            return ''

    def get_env_vars(self):
        speaker = speaker_manager.get_object(self.speaker)
        cal = speaker.get_current_calibration()
        return {
            'CFTS_TEST_SPEAKER': self.output,
            f'CFTS_SPEAKER_{self.output}': cal.to_string()
        }


class StarshipSettings(PersistentSettings):

    output = Str()
    name = Str()
    available_starships = Property()

    def _get_available_speakers(self):
        return sorted(speaker_manager.list_names('CFTS'))

    def _get_filename(self):
        return f'speaker_{self.output}.json'

    def _default_name(self):
        try:
            return self.available_speakers[0]
        except IndexError:
            return ''

    def get_env_vars(self):
        speaker = speaker_manager.get_object(self.speaker)
        cal = speaker.get_current_calibration()
        return {
            'CFTS_TEST_SPEAKER': self.output,
            f'CFTS_SPEAKER_{self.output}': cal.to_string()
        }
