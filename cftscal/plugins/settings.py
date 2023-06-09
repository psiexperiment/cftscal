import json
import os
import subprocess

from atom.api import Atom, Enum, Float, List, Property, Str

from psi import get_config_folder
from psi.util import get_tagged_values


from cftscal.objects import (
    amplifier_manager, inear_manager, microphone_manager, speaker_manager,
    starship_manager
)


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
        print(json.dumps(env, indent=2))
        env = {**os.environ, **env}
        args = ['psi', experiment, str(filename)]
        print(' '.join(args))
        subprocess.check_output(args, env=env)


class MicrophoneSettings(PersistentSettings):

    input_name = Str()
    name = Str()
    gain = Float(20)
    available_microphones = Property()

    def _get_available_microphones(self):
        return sorted(microphone_manager.list_names('CFTS'))

    def get_env_vars(self, include_cal=True):
        env = {
            'CFTS_MICROPHONE': self.input_name,
            f'CFTS_MICROPHONE_{self.input_name.upper()}_GAIN': str(self.gain),
        }
        if include_cal:
            mic = microphone_manager.get_object(self.name)
            cal = mic.get_current_calibration()
            env[f'CFTS_MICROPHONE_{self.input_name.upper()}'] = cal.to_string()
        return env

    def _get_filename(self):
        return f'microphone_{self.input_name}.json'

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

    def get_env_vars(self, include_cal=True):
        env = {
            'CFTS_TEST_SPEAKER': self.output,
        }
        if include_cal:
            speaker = speaker_manager.get_object(self.name)
            cal = speaker.get_current_calibration()
            env[f'CFTS_SPEAKER_{self.output}'] = cal.to_string()
        return env


class StarshipSettings(PersistentSettings):

    output = Str()
    name = Str()
    gain = Float(40)
    available_starships = Property()

    def _get_available_starships(self):
        return sorted(starship_manager.list_names('CFTS'))

    def _get_filename(self):
        return f'starship_{self.output}.json'

    def _default_name(self):
        try:
            return self.available_starships[0]
        except IndexError:
            return ''

    def get_env_vars(self, include_cal=True):
        env = {
            'CFTS_TEST_STARSHIP': self.output,
            f'CFTS_STARSHIP_{self.output}_GAIN': str(self.gain),
        }
        if include_cal:
            starship = starship_manager.get_object(self.name)
            cal = starship.get_current_calibration()
            env[f'CFTS_STARSHIP_{self.output}'] = cal.to_string()
        return env


class InEarSettings(StarshipSettings):

    ear = Str()
    available_ears = Property()

    def _get_available_starships(self):
        return sorted(starship_manager.list_names())

    def _get_available_ears(self):
        return sorted(inear_manager.list_names('CFTS'))

    def _get_filename(self):
        return f'inear_{self.output}.json'


class InputAmplifierSettings(PersistentSettings):

    input_name = Str()
    name = Str()
    gain = Float(50)
    gain_mult = Enum(10, 1000)
    freq_lb = Float(10)
    freq_ub = Float(10000)
    filt_60Hz = Enum('input', 'output')
    # Choices are 10 20 50 100 200 500 uV or 1 2 5 10 20 50 mV
    cal_amplitude = Float(100e-6)
    total_gain = Property()

    available_amplifiers = Property()

    def _get_total_gain(self):
        return self.gain * self.gain_mult

    def _get_available_amplifiers(self):
        return sorted(amplifier_manager.list_names('CFTS'))

    def get_env_vars(self, include_cal=True):
        return {
            'CFTS_INPUT_AMPLIFIER': self.input_name,
            f'CFTS_INPUT_AMPLIFIER_{self.input_name.upper()}_GAIN': str(self.total_gain),
            f'CFTS_INPUT_AMPLIFIER_{self.input_name.upper()}_CAL_AMPLITUDE': str(self.cal_amplitude),
            f'CFTS_INPUT_AMPLIFIER_{self.input_name.upper()}_FREQ_LB': str(self.freq_lb),
            f'CFTS_INPUT_AMPLIFIER_{self.input_name.upper()}_FREQ_UB': str(self.freq_ub),
            f'CFTS_INPUT_AMPLIFIER_{self.input_name.upper()}_FILT_60Hz': self.filt_60Hz,
        }

    def _get_filename(self):
        return f'{{date_time}}_{self.name}_{self.cal_amplitude*1e6}uV' \
            f'_{self.total_gain}x_{self.freq_lb}-{self.freq_ub}Hz' \
            f'-filt-60Hz-{self.filt_60Hz}'

    def _default_name(self):
        try:
            return self.available_amplifiers[0]
        except IndexError:
            return ''
