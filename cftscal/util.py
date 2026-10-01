import logging
log = logging.getLogger(__name__)

import os
from functools import partial

from psi import get_config
from psi.application import get_default_io, initialize_io_manifest
from psi.controller.api import Channel, HardwareAIChannel, HardwareAOChannel


#: CFTSCAL_IO value meaning the audio device chosen by CFTSCAL_DEVICE_NAME,
#: CFTSCAL_DEVICE_HOSTAPI and CFTSCAL_SAMPLE_RATE.
IO_SOUND_CARD = 'sound-card'

#: CFTSCAL_IO value meaning this machine's own IO manifest,
#: <PSI_IO_ROOT>/<hostname>.enaml.
IO_DEFAULT = 'default'

#: The manifest psi builds for a single sound card from the
#: PSI_SOUND_DEVICE_* environment variables.
SOUND_CARD_MANIFEST = \
    'psi.controller.engines.soundcard.standard_io.AutoSoundCardManifest'


def device_query(name, hostapi):
    '''
    The "<name>, <host API>" string identifying an audio device.

    sounddevice matches this exactly against its own "<name>, <host API>"
    for each device, so it resolves to the one intended device even when
    the bare name substring-matches several (the same device exposed
    through several drivers). Never an index, which shifts whenever the
    set of devices changes. Falls back to the bare name if the host API is
    unknown.
    '''
    return f'{name}, {hostapi}' if hostapi else name


def resolve_io():
    '''
    The IO manifest to run psi with, and the environment it needs.

    This is the one place CFTSCAL_IO is interpreted. cftscal's own
    calibrations and every launcher built on it (cfts, abts, noise-exp)
    pass the result to psi as ``--io``, and `io_manifest`, which fills the
    launchers' channel choices, loads the same thing -- so the channels a
    user picks from are the channels the experiment then runs on.

    Returns
    -------
    manifest : str
        The value for psi's ``--io``.
    env : dict
        Environment variables the manifest reads. Empty except for the
        sound card, whose manifest is configured entirely from them.

    Raises
    ------
    ValueError
        If no manifest is configured, or CFTSCAL_IO is 'default' and this
        machine has no IO manifest of its own.
    '''
    io = get_config('CFTSCAL_IO').strip()
    if io == IO_SOUND_CARD:
        rate = get_config('CFTSCAL_SAMPLE_RATE')
        env = {
            'PSI_SOUND_DEVICE_NAME': device_query(
                get_config('CFTSCAL_DEVICE_NAME'),
                get_config('CFTSCAL_DEVICE_HOSTAPI')),
            'PSI_SOUND_DEVICE_FS': str(int(rate)),
        }
        return SOUND_CARD_MANIFEST, env
    if io == IO_DEFAULT:
        return str(get_default_io()), {}
    if not io:
        raise ValueError(
            'No IO manifest is selected. Choose the hardware in cftscal\'s '
            'workspace settings, or set CFTSCAL_IO.')
    return io, {}


NO_OUTPUT_ERROR = '''
No output channels could be found in the IO manifest. To use this plugin, you
must have at least one analog output channel.
'''

# Cache IO manifest on load because this can sometimes be slow on some systems
# (e.g., TDT).
IO_MANIFEST = None


def reset_io_manifest():
    """Clear the cached IO manifest so the next call reloads from current settings."""
    global IO_MANIFEST
    IO_MANIFEST = None


def io_manifest():
    '''
    The IO manifest `resolve_io` selects, loaded into this process.
    '''
    global IO_MANIFEST
    if IO_MANIFEST is None:
        manifest, env = resolve_io()
        # The sound card manifest reads its device from the environment
        # when it is instantiated, here as much as in a psi subprocess.
        os.environ.update(env)
        # initialize_io_manifest rather than load_io_manifest(...)(): the
        # manifest is Enaml, so the hardware is not touched until it is
        # instantiated. Doing the instantiation ourselves put the interesting
        # failure outside psi's error handling, and a missing sound card
        # surfaced as a bare ValueError from sounddevice that named neither
        # the manifest nor the setting that chose the device.
        IO_MANIFEST = initialize_io_manifest(manifest)
    return IO_MANIFEST


def list_outputs(raise_error=True):
    outputs = {}
    try:
        manifest = io_manifest()
    except ValueError as e:
        if raise_error:
            raise
        else:
            return outputs

    for obj in manifest.traverse():
        if isinstance(obj, HardwareAOChannel):
            outputs[obj.label] = obj.name

    if len(outputs) == 0 and raise_error:
        raise ValueError(NO_OUTPUT_ERROR)

    return outputs


NO_INPUT_ERROR = '''
No input channels could be found in the IO manifest. To use this plugin, you must
have at least one analog input channel.
'''


def list_inputs(raise_error=True):
    inputs = {}
    try:
        manifest = io_manifest()
    except ValueError as e:
        if raise_error:
            raise
        else:
            return inputs

    for obj in manifest.traverse():
        if isinstance(obj, HardwareAIChannel):
            inputs[obj.label] = obj.name
    if len(inputs) == 0 and raise_error:
        raise ValueError(NO_INPUT_ERROR)
    return inputs


NO_STARSHIP_ERROR = '''
No starship could be found in the IO manifest. To use this plugin, you must
have an analog input channel named starship_ID_microphone and two analog output
channels named starship_ID_primary and starship_ID_secondary. ID is the name of
the starship that will appear in any drop-down selectors where you can select
which starship to use (assuming your system is configured for more than one
starship).
'''

def list_starship_connections(raise_error=True):
    '''
    List all starships found in the IO Manifest
    '''
    starships = {}
    for name in list_connections('hw_ai', 'starship', raise_error=raise_error).values():
        _, starship_id, starship_input = name.split('_')
        starships.setdefault(starship_id, []).append(starship_input)

    for name in list_connections('hw_ao', 'starship', raise_error=raise_error).values():
        _, starship_id, starship_output = name.split('_')
        starships.setdefault(starship_id, []).append(starship_output)

    choices = {}
    for name, channels in starships.items():
        for c in ('microphone', 'primary', 'secondary'):
            if c not in channels:
                raise ValueError(f'Must define starship_{name}_{c} channel')
        choices[name] = f'starship_{name}'

    if len(choices) == 0 and raise_error:
        raise ValueError(NO_STARSHIP_ERROR)

    return choices



NO_DEVICE_ERROR = '''
No channel supporting {} could be found in the IO manifest. To use this plugin,
you must add {} as a supported device to at least one analog channel via the
supported_devices list attribute on that channel.
'''


valid_type_codes = [
    'hw_ai',
    'hw_ao',
    'hw_di',
    'hw_do',
    'sw_ai',
    'sw_ao',
    'sw_di',
    'sw_do',
]


def list_connections(channel_type_code, device_types, label_fmt=None,
                     as_expression=False, raise_error=True):
    if channel_type_code not in valid_type_codes:
        raise ValueError(f'Invalid channel type code: {channel_type_code}')
    if isinstance(device_types, str):
        device_types = [device_types]
    if label_fmt is None:
        label_fmt = lambda x: x
    choices = {}

    try:
        manifest = io_manifest()
    except ValueError as e:
        if raise_error:
            raise
        else:
            return choices

    for obj in manifest.traverse():
        if isinstance(obj, Channel):
            if channel_type_code == obj.type_code:
                for device_type in device_types:
                    if device_type in obj.supported_devices:
                        label = label_fmt(obj.label)
                        if as_expression:
                            # Wrap name in quotation marks so that `eval` returns a
                            # string when this is passed through the context
                            # expression evaluation system.
                            name = f'"{obj.name}"'
                        else:
                            name = obj.name
                        choices[label] = name
                        break

    if len(choices) == 0 and raise_error:
        info = ', '.join(device_types)
        raise ValueError(NO_DEVICE_ERROR.format(info, info))
    return choices


list_speaker_connections = \
    partial(list_connections, 'hw_ao', 'speaker')
list_measurement_microphone_connections = \
    partial(list_connections, 'hw_ai', 'measurement_microphone')
list_generic_microphone_connections = \
    partial(list_connections, 'hw_ai', ['generic_microphone', 'measurement_microphone'])
list_input_amplifier_connections = \
    partial(list_connections, 'hw_ai', 'input_amplifier')


def show_connections():
    print(f'Looking for connections in {resolve_io()[0]}')
    fn_list = {
        'Starship': list_starship_connections,
        'Input Amplifier': list_input_amplifier_connections,
        'Speaker': list_speaker_connections,
        'Measurement Microphone': list_measurement_microphone_connections,
        'Generic Microphone': list_generic_microphone_connections,
        'Input': list_inputs,
    }

    for name, fn in fn_list.items():
        try:
            options = fn()
            print('============================================')
            print(f' {name} ')
            print('============================================')
            for k, v in options.items():
                print(f' * {k}: {v}')
        except ValueError as e:
            print(e)


if __name__ == '__main__':
    show_connections()
