from functools import partial

from psi.application import get_default_io, load_io_manifest
from psi.controller.api import Channel


NO_INPUT_ERROR = '''
No input channels could be found in the IO manifest. To use this plugin, you must
have at least one analog input channel.
'''


def list_inputs():
    inputs = {}
    manifest = load_io_manifest()()
    for obj in manifest.traverse():
        if isinstance(obj, HardwareAIChannel):
            inputs[obj.label] = obj.name

    if len(inputs) == 0:
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

def list_starship_connections():
    '''
    List all starships found in the IO Manifest
    '''
    starships = {}
    manifest = load_io_manifest()()
    for channel in manifest.find_all('^starship_', regex=True):
        # Strip quotation marks off
        _, starship_id, starship_output = channel.name.split('_')
        starships.setdefault(starship_id, []).append(starship_output)

    choices = {}
    for name, channels in starships.items():
        for c in ('microphone', 'primary', 'secondary'):
            if c not in channels:
                raise ValueError(f'Must define starship_{name}_{c} channel')
        choices[name] = f'starship_{name}'

    if len(choices) == 0:
        raise ValueError(NO_STARSHIP_ERROR)

    return choices




NO_DEVICE_ERROR = '''
No channel supporting {} could be found in the IO manifest. To use this plugin,
you must add {} as a supported device to at least one analog channel via the
supported_devices list attribute on that channel.
'''


def list_connections(channel_type_code, device_type, label_fmt=None,
                     as_expression=False):
    if label_fmt is None:
        label_fmt = lambda x: x
    choices = {}
    manifest = load_io_manifest()()
    for obj in manifest.traverse():
        if isinstance(obj, Channel):
            if channel_type_code == obj.type_code:
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
    if len(choices) == 0:
        raise ValueError(NO_DEVICE_ERROR.format(device_type, device_type))
    return choices


list_speaker_connections = partial(list_connections, 'hw_ao', 'speaker')
list_microphone_connections = partial(list_connections, 'hw_ai', 'measurement_microphone')


NO_INPUT_AMPLIFIER_ERROR = '''
No input amplifier could be found in the IO manifest. To use this plugin, you
must have an analog input channel named amplifier_ID. ID is the name of the
amplifier that will appear in any drop-down selectors where you can select
which amplifier to use (assuming your system is configured for more than one
amplifier).
'''


def list_input_amplifier_connections():
    '''
    List all input amplifiers found in the IO Manifest
    '''
    choices = {}
    manifest = load_io_manifest()()
    for channel in manifest.find_all('^amplifier_', regex=True):
        choices[channel.label] = channel.name.split('_', 1)[1]

    if len(choices) == 0:
        raise ValueError(NO_INPUT_AMPLIFIER_ERROR)

    return choices


def show_connections():
    print(f'Looking for connections in {get_default_io()}')
    #try:
    #    print(list_starship_connections())
    #except ValueError:
    #    pass
    try:
        print(list_speaker_connections())
    except ValueError:
        pass
    try:
        print(list_microphone_connections())
    except ValueError:
        pass
    #try:
    #    print(list_input_amplifier_connections())
    #except ValueError:
    #    pass


if __name__ == '__main__':
    show_connections()
