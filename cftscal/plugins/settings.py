import json
import os
import subprocess

from atom.api import Atom, Enum, Float, List, Property, Str

from psi import get_config_folder
from psi.util import get_tagged_members, get_tagged_values


from cftscal.objects import (
    input_amplifier_manager, inear_manager, microphone_manager, speaker_manager,
    starship_manager
)


class PersistentSettings(Atom):

    settings_filename = Property()
    calibration_filename = Property()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_config()

    def save_config(self):
        file = get_config_folder() / 'cfts' / 'calibration' / self.settings_filename
        file.parent.mkdir(exist_ok=True, parents=True)
        config = get_tagged_values(self, 'persist')
        file.write_text(json.dumps(config, indent=2))

    def load_config(self):
        file = get_config_folder() / 'cfts' / 'calibration' / self.settings_filename
        if not file.exists():
            return
        config = json.loads(file.read_text())
        for name in get_tagged_members(self, 'persist'):
            if name in config:
                setattr(self, name, config[name])


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

    #: Name of input as defined in IO manifest
    input_name = Str()

    #: Label of input as defined in IO manifest
    input_label = Str()

    #: Name of the actual microphone. This is not necessarily the same as the
    #: channel in the IO manifest. For example, one can connect a different
    #: microphone to the same channel, so the name may indicate which of
    #: several microphones available in the lab is currently connected.
    name = Str().tag(persist=True)

    gain = Float(20).tag(persist=True)

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

    def _get_settings_filename(self):
        return f'microphone_{self.input_name}.json'

    def _default_name(self):
        try:
            return self.available_microphones[0]
        except IndexError:
            return ''


class PistonphoneSettings(PersistentSettings):

    name = Str().tag(persist=True)
    frequency = Float(1e3).tag(persist=True)
    level = Float(114).tag(persist=True)

    def _get_settings_filename(self):
        return 'pistonphone.json'

    def get_env_vars(self):
        return {
            'CFTS_PISTONPHONE_LEVEL': str(self.level),
            'CFTS_PISTONPHONE_FREQUENCY': str(self.frequency),
        }


class SpeakerSettings(PersistentSettings):

    #: Name of output as defined in IO manifest
    output_name = Str()

    #: Label of output as defined in IO manifest
    output_label = Str()

    #: Name of the actual speaker. This is not necessarily the same as the
    #: channel in the IO manifest. For example, one can connect a different
    #: speaker to the same channel, so the name may indicate which of
    #: several speakers available in the lab that is currently connected.
    name = Str().tag(persist=True)
    available_speakers = Property()

    def _get_available_speakers(self):
        return sorted(speaker_manager.list_names('CFTS'))

    def _get_settings_filename(self):
        return f'speaker_{self.output_name}.json'

    def _default_name(self):
        try:
            return self.available_speakers[0]
        except IndexError:
            return ''

    def get_env_vars(self, include_cal=True):
        env = {
            f'CFTS_SPEAKER': self.output_name,
        }
        if include_cal:
            speaker = speaker_manager.get_object(self.name)
            cal = speaker.get_current_calibration()
            env[f'CFTS_SPEAKER_{self.output_name.upper()}'] = cal.to_string()
        return env


class StarshipSettings(PersistentSettings):

    output = Str()
    name = Str().tag(persist=True)
    gain = Float(40).tag(persist=True)
    available_starships = Property()

    def _get_available_starships(self):
        return sorted(starship_manager.list_names('CFTS'))

    def _get_settings_filename(self):
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

    ear = Str().tag(persist=True)
    available_ears = Property()

    def _get_available_starships(self):
        choices = set(starship_manager.list_names() + inear_manager.list_names())
        return sorted(choices)

    def _get_available_ears(self):
        return sorted(inear_manager.get_property('ear'))

    def _get_settings_filename(self):
        return f'inear_{self.output}.json'


class InputAmplifierSettings(PersistentSettings):

    input_name = Str()
    name = Str().tag(persist=True)
    gain = Float(50).tag(persist=True)
    gain_mult = Enum(10, 1000).tag(persist=True)
    freq_lb = Float(10).tag(persist=True)
    freq_ub = Float(10000).tag(persist=True)
    filt_60Hz = Enum('input', 'output').tag(persist=True)
    total_gain = Property()

    available_input_amplifiers = Property()

    def _get_settings_filename(self):
        return f'input_amplifier_{self.input_name}.json'

    def _get_total_gain(self):
        return self.gain * self.gain_mult

    def _get_available_input_amplifiers(self):
        return sorted(input_amplifier_manager.list_names('CFTS'))

    def get_env_vars(self, include_cal=True):
        return {
            'CFTS_INPUT_AMPLIFIER': self.input_name,
            f'CFTS_INPUT_AMPLIFIER_{self.input_name.upper()}_GAIN': str(self.total_gain),
            f'CFTS_INPUT_AMPLIFIER_{self.input_name.upper()}_FREQ_LB': str(self.freq_lb),
            f'CFTS_INPUT_AMPLIFIER_{self.input_name.upper()}_FREQ_UB': str(self.freq_ub),
            f'CFTS_INPUT_AMPLIFIER_{self.input_name.upper()}_FILT_60Hz': self.filt_60Hz,
        }

    def _get_calibration_filename(self):
        return f'{{date_time}}_{self.name}' \
            f'_{self.total_gain}x_{self.freq_lb}-{self.freq_ub}Hz' \
            f'-filt-60Hz-{self.filt_60Hz}'

    def _default_name(self):
        try:
            return self.available_input_amplifiers[0]
        except IndexError:
            return ''
