import json
import os
import subprocess

from atom.api import set_default, Atom, Enum, Float, List, Property, Str, Typed

from psi import get_config_folder
from psi.util import get_tagged_members, get_tagged_values


from cftscal.objects import (
    generic_microphone_manager, input_amplifier_manager, input_manager,
    inear_manager, measurement_microphone_manager, output_manager,
    speaker_manager, starship_manager, CalibrationManager,
)


class PersistentSettings(Atom):

    def get_persistence(self):
        config = get_tagged_values(self, 'persist')
        for k, v in config.items():
            if isinstance(v, PersistentSettings):
                config[k] = v.get_persistence()
            if v and isinstance(v, (list, tuple)) and isinstance(v[0], PersistentSettings):
                config[k] = [i.get_persistence() for i in v]
        return config

    def set_persistence(self, config):
        for name in get_tagged_members(self, 'persist'):
            if name in config:
                obj = getattr(self, name)
                if hasattr(obj, 'set_persistence'):
                    obj.set_persistence(config[name])
                else:
                    setattr(self, name, config[name])


class CalibrationSettings(Atom):

    settings_filename = Str()

    def save_config(self):
        file = get_config_folder() / 'cfts' / 'calibration' / self.settings_filename
        file = file.with_suffix('.json')
        file.parent.mkdir(exist_ok=True, parents=True)
        config = self.get_config()
        file.write_text(json.dumps(config, indent=2))

    def load_config(self):
        file = get_config_folder() / 'cfts' / 'calibration' / self.settings_filename
        file = file.with_suffix('.json')
        if not file.exists():
            return
        config = json.loads(file.read_text())
        self.set_config(config)

    def _run_cal(self, filename, experiment, env=None):
        if env is None:
            env = {}
        print(json.dumps(env, indent=2))
        env = {**os.environ, **env}
        args = ['psi', experiment, str(filename)]
        print(' '.join(args))
        subprocess.check_output(args, env=env)


class GeneratorSettings(PersistentSettings):

    #: Name of generator.
    name = Str().tag(persist=True)

    #: List of available generators.
    available_generators = List().tag(persist=True)

    def _default_name(self):
        try:
            return self.available_generators[0]
        except IndexError:
            return ''


class PistonphoneSettings(GeneratorSettings):

    frequency = Float(1e3).tag(persist=True)
    level = Float(114).tag(persist=True)

    def get_env_vars(self):
        return {
            'CFTS_PISTONPHONE_LEVEL': str(self.level),
            'CFTS_PISTONPHONE_FREQUENCY': str(self.frequency),
        }


class SpeakerSettings(GeneratorSettings):

    #: Name of the actual speaker. This is not necessarily the same as the
    #: channel in the IO manifest. For example, one can connect a different
    #: speaker to the same channel, so the name may indicate which of
    #: several speakers available in the lab that is currently connected.
    name = Str().tag(persist=True)

    def _default_name(self):
        try:
            return self.available_speakers[0]
        except IndexError:
            return ''

    @property
    def available_speakers(self):
        return sorted(speaker_manager.list_names())


class SensorSettings(PersistentSettings):

    #: Name of the connected sensor. This is not necessarily the same as the
    #: channel in the IO manifest. For example, one can connect a different
    #: sensor to the same channel, so the name may indicate which of several
    #: sensors available in the lab is currently connected.
    name = Str().tag(persist=True)

    #: Gain of the device. Some preamps/power supplies have a hardware switch
    #: to configure the gain. This value must match the gain set on the preamp.
    gain = Float(0).tag(persist=True)

    def _sensor_name(self):
        try:
            return self.available_sensors[0]
        except IndexError:
            return ''

    @property
    def available_sensors(self):
        return sorted(input_manager.list_names())


class MeasurementMicrophoneSettings(SensorSettings):

    @property
    def available_sensors(self):
        return sorted(measurement_microphone_manager.list_names())


class GenericMicrophoneSettings(SensorSettings):

    @property
    def available_sensors(self):
        return sorted(generic_microphone_manager.list_names())


class InputSettings(PersistentSettings):

    #: Name of input channel as defined in IO manifest. This is not supposed to
    #: be settable.
    input_name = Str().tag(persist=True)

    #: Label of input channel as defined in IO manifest
    input_label = Str()

    sensor = Typed(SensorSettings, ()).tag(persist=True)
    generator = Typed(GeneratorSettings, ()).tag(persist=True)

    #: Prefix to add to environment variable names for passing to psi.
    env_prefix = Str('CFTS_INPUT')

    def _get_available_sensors(self):
        return [
            *sorted(input_manager.list_names()),
        ]

    def _get_available_generators(self):
        return []

    def get_env_vars(self, include_cal=True):
        env = {
            self.env_prefix: self.input_name,
            f'{self.env_prefix}_{self.input_name.upper()}_GAIN': str(self.sensor.gain),
        }
        if include_cal:
            obj = input_manager.get_object(self.sensor.name)
            cal = obj.get_current_calibration()
            env[f'{self.env_prefix}_{self.input_name.upper()}'] = cal.to_string()
        return env


class OutputSettings(PersistentSettings):

    #: Name of output as defined in IO manifest
    output_name = Str()

    #: Label of output as defined in IO manifest
    output_label = Str()

    #: Generator attached to output
    generator = Typed(GeneratorSettings, ()).tag(persist=True)

    #: Prefix to add to environment variable names for passing to psi.
    env_prefix = Str('CFTS_OUTPUT')

    def get_env_vars(self, include_cal=True):
        env = {
            self.env_prefix: self.output_name,
        }
        if include_cal:
            generator = output_manager.get_object(self.generator.name)
            cal = generator.get_current_calibration()
            env[f'{self.env_prefix}_{self.output_name.upper()}'] = cal.to_string()
        return env


class StarshipSettings(PersistentSettings):

    output = Str()
    name = Str().tag(persist=True)
    gain = Float(40).tag(persist=True)

    @property
    def available_starships(self):
        return sorted(starship_manager.list_names())

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

    @property
    def available_starships(self):
        choices = set(starship_manager.list_names() + inear_manager.list_names())
        return sorted(choices)

    @property
    def available_ears(self):
        return sorted(inear_manager.get_property('ear'))


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

    def _get_total_gain(self):
        return self.gain * self.gain_mult

    def _get_available_input_amplifiers(self):
        return sorted(input_amplifier_manager.list_names())

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
