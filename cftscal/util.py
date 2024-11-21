from psi.application import get_default_io, load_io_manifest
from psi.controller.api import HardwareAIChannel


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


NO_SPEAKER_ERROR = '''
No speaker could be found in the IO manifest. To use this plugin, you must
have an analog output channel named speaker_ID. ID is the name of the speaker
that will appear in any drop-down selectors where you can select which speaker
to use (assuming your system is configured for more than one speaker).
'''


def list_speaker_connections():
    '''
    List all speakers found in the IO Manifest
    '''
    choices = {}
    manifest = load_io_manifest()()
    for channel in manifest.find_all('^speaker_', regex=True):
        choices[channel.label] = channel.name.split('_', 1)[1]

    if len(choices) == 0:
        raise ValueError(NO_SPEAKER_ERROR)

    return choices


NO_MICROPHONE_ERROR = '''
No microphone could be found in the IO manifest. To use this plugin, you must
have an analog input channel named microphone_ID. ID is the name of the
microphone that will appear in any drop-down selectors where you can select
which microphone to use (assuming your system is configured for more than one
microphone).
'''


def list_microphone_connections():
    '''
    List all microphones found in the IO Manifest
    '''
    choices = {}
    manifest = load_io_manifest()()
    for channel in manifest.find_all('^microphone_', regex=True):
        # Strip quotation marks off
        choices[channel.label] = channel.name.split('_', 1)[1]

    if len(choices) == 0:
        raise ValueError(NO_MICROPHONE_ERROR)

    return choices


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
    try:
        print(list_starship_connections())
    except ValueError:
        pass
    try:
        print(list_speaker_connections())
    except ValueError:
        pass
    try:
        print(list_microphone_connections())
    except ValueError:
        pass
    try:
        print(list_input_amplifier_connections())
    except ValueError:
        pass


if __name__ == '__main__':
    show_connections()
