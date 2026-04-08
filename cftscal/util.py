import logging
log = logging.getLogger(__name__)

from functools import partial

from psi.application import get_default_io, load_io_manifest
from psi.controller.api import Channel, HardwareAIChannel, HardwareAOChannel


NO_OUTPUT_ERROR = '''
No output channels could be found in the IO manifest. To use this plugin, you
must have at least one analog output channel.
'''

# Cache IO manifest on load because this can sometimes be slow on some systems
# (e.g., TDT).
IO_MANIFEST = load_io_manifest()()


def list_outputs():
    outputs = {}
    manifest = IO_MANIFEST
    for obj in manifest.traverse():
        if isinstance(obj, HardwareAOChannel):
            outputs[obj.label] = obj.name

    if len(outputs) == 0:
        raise ValueError(NO_OUTPUT_ERROR)

    return outputs


NO_INPUT_ERROR = '''
No input channels could be found in the IO manifest. To use this plugin, you must
have at least one analog input channel.
'''


def list_inputs():
    inputs = {}
    manifest = IO_MANIFEST
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
    manifest = IO_MANIFEST
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
                     as_expression=False):
    if channel_type_code not in valid_type_codes:
        raise ValueError(f'Invalid channel type code: {channel_type_code}')
    if isinstance(device_types, str):
        device_types = [device_types]
    if label_fmt is None:
        label_fmt = lambda x: x
    choices = {}
    manifest = IO_MANIFEST
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

    if len(choices) == 0:
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
    print(f'Looking for connections in {get_default_io()}')
    fn_list = {
        'Starship': list_starship_connections,
        'Input Amplifier': list_input_amplifier_connections,
        'Speaker': list_speaker_connections,
        'Measurement Microphone': list_measurement_microphone_connections,
        'Generic Microphone': list_generic_microphone_connections,
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
