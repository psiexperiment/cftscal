'''
Tests for the `AllInputs` manifest in ``cftscal/paradigms/record.enaml``.

Unlike the objects in ``objects.enaml``, which configure one channel
selected by an environment variable, `AllInputs` configures every
channel named in ``CFTS_INPUT_CHANNELS``. Each of those channels is
expected to come with its own gain and calibration, so the same
``required_vars`` mechanism applies -- per channel.
'''
import enaml
import pytest

from cftscal.paradigms.calibration_status import (
    CalibrationParameter, NOT_LOADED
)
from cftscal.paradigms.env_vars import MissingEnvironmentVariables

from .fakes import FakeChannel, FakeManager, set_env
from .test_paradigm_objects import find_command_handler, find_context_items

with enaml.imports():
    from cftscal.paradigms import record


@pytest.fixture
def manager(monkeypatch):
    manager = FakeManager()
    monkeypatch.setattr(record, 'input_manager', manager)
    return manager


def set_channels(*names, **kwargs):
    '''
    Set CFTS_INPUT_CHANNELS plus, for each channel, whichever of its gain
    and calibration variables the test asks for.
    '''
    env = {'CFTS_INPUT_CHANNELS': ','.join(names)}
    for name in names:
        if 'gain' in kwargs:
            env[f'CFTS_INPUT_{name.upper()}_GAIN'] = kwargs['gain']
        if 'calibration' in kwargs:
            env[f'CFTS_INPUT_{name.upper()}'] = kwargs['calibration']
    set_env(**env)


class TestAllInputsManifest:

    def test_default_required_vars(self):
        # By default, every channel must come with a gain and a
        # calibration.
        assert record.AllInputs().required_vars == \
            ['channels', 'gain', 'calibration']

    def test_required_vars_passed_to_handler(self):
        manifest = record.AllInputs(required_vars=['channels'])
        handler = find_command_handler(manifest)
        assert handler.args[-1] == ['channels']


class TestInitializeAllInputs:

    def test_all_vars_set(self, event, manager):
        set_channels('mic_1', 'mic_2', gain='40', calibration='some/cal')

        record.initialize_all_inputs('all_inputs', 'CFTS_INPUT',
                                     ['channels', 'gain', 'calibration'],
                                     event)

        for name in ('mic_1', 'mic_2'):
            channel = event.controller.channels[f'hw_ai::{name}']
            # The gain is a string in the environment, but the channel
            # expects a number.
            assert channel.gain == 40.0
            assert channel.calibration == 'calibration for some/cal'

    def test_items_use_channel_label(self, event, manager):
        # Labeled as the IO manifest labels the hardware ("Input 1"), not
        # with the channel's name ("input_1").
        event.controller.channels['hw_ai::input_1'] = FakeChannel('Input 1')
        event.controller.channels['hw_ai::input_2'] = FakeChannel('Mic B')
        set_channels('input_1', 'input_2', gain='40', calibration='some/cal')

        record.initialize_all_inputs('all_inputs', 'CFTS_INPUT',
                                     ['channels', 'gain', 'calibration'],
                                     event)

        items = event.context.items
        assert items['input_1_calibration'].label == 'Input 1 calibration'
        assert items['input_2_calibration'].label == 'Mic B calibration'

    def test_channel_with_missing_settings_is_labeled(self, event):
        # Still labeled when its settings are missing: its item stays on
        # screen reporting NOT LOADED, and should say which input it is.
        event.controller.channels['hw_ai::input_1'] = FakeChannel('Input 1')
        set_channels('input_1')

        with pytest.raises(MissingEnvironmentVariables):
            record.initialize_all_inputs('all_inputs', 'CFTS_INPUT',
                                         ['channels', 'gain', 'calibration'],
                                         event)

        item = event.context.items['input_1_calibration']
        assert item.label == 'Input 1 calibration'

    def test_unity_calibration(self, event):
        # Goes through the real input manager (no `manager` fixture) with
        # the string cftscal passes when an input is set to "Unity" --
        # which used to fail the experiment while reporting the
        # calibration in use.
        from cftscal.objects import UnityInputCalibration
        set_channels('mic_1', gain='40',
                     calibration=UnityInputCalibration().to_string())

        record.initialize_all_inputs('all_inputs', 'CFTS_INPUT',
                                     ['channels', 'gain', 'calibration'],
                                     event)

        channel = event.controller.channels['hw_ai::mic_1']
        assert channel.calibration.get_sens(1000) == 0
        assert event.context.items['mic_1_calibration'].value == 'unity'

    def test_per_channel_variables(self, event, manager):
        set_env(CFTS_INPUT_CHANNELS='mic_1,mic_2',
                CFTS_INPUT_MIC_1_GAIN='40', CFTS_INPUT_MIC_1='cal/one',
                CFTS_INPUT_MIC_2_GAIN='20', CFTS_INPUT_MIC_2='cal/two')

        record.initialize_all_inputs('all_inputs', 'CFTS_INPUT',
                                     ['channels', 'gain', 'calibration'],
                                     event)

        assert event.controller.channels['hw_ai::mic_1'].gain == 40.0
        assert event.controller.channels['hw_ai::mic_2'].gain == 20.0
        # Each channel loads its own calibration (the fake manager only
        # remembers the last one it was asked for).
        assert manager.loaded == 'cal/two'

    def test_missing_gain_raises(self, event, manager):
        set_channels('mic_1', 'mic_2', calibration='some/cal')
        set_env(CFTS_INPUT_MIC_1_GAIN='40')

        with pytest.raises(MissingEnvironmentVariables) as exc:
            record.initialize_all_inputs('all_inputs', 'CFTS_INPUT',
                                         ['channels', 'gain', 'calibration'],
                                         event)
        assert exc.value.missing == [('CFTS_INPUT_MIC_2_GAIN', 'gain')]

    def test_missing_calibration_raises(self, event):
        set_channels('mic_1', gain='40')

        with pytest.raises(MissingEnvironmentVariables) as exc:
            record.initialize_all_inputs('all_inputs', 'CFTS_INPUT',
                                         ['channels', 'gain', 'calibration'],
                                         event)
        assert 'CFTS_INPUT_MIC_1' in str(exc.value)

    def test_every_missing_variable_reported_at_once(self, event):
        # Fixing these one experiment launch at a time would be tedious
        # with several channels active.
        set_channels('mic_1', 'mic_2')

        with pytest.raises(MissingEnvironmentVariables) as exc:
            record.initialize_all_inputs('all_inputs', 'CFTS_INPUT',
                                         ['channels', 'gain', 'calibration'],
                                         event)
        assert exc.value.missing == [
            ('CFTS_INPUT_MIC_1_GAIN', 'gain'),
            ('CFTS_INPUT_MIC_1', 'calibration'),
            ('CFTS_INPUT_MIC_2_GAIN', 'gain'),
            ('CFTS_INPUT_MIC_2', 'calibration'),
        ]

    def test_missing_channels_raises(self, event):
        with pytest.raises(MissingEnvironmentVariables) as exc:
            record.initialize_all_inputs('all_inputs', 'CFTS_INPUT',
                                         ['channels', 'gain', 'calibration'],
                                         event)
        assert exc.value.missing == [('CFTS_INPUT_CHANNELS', 'channels')]

    def test_empty_channels_raises(self, event):
        set_env(CFTS_INPUT_CHANNELS='')

        with pytest.raises(MissingEnvironmentVariables) as exc:
            record.initialize_all_inputs('all_inputs', 'CFTS_INPUT',
                                         ['channels', 'gain', 'calibration'],
                                         event)
        assert 'CFTS_INPUT_CHANNELS' in str(exc.value)

    def test_nothing_required_and_nothing_set(self, event):
        record.initialize_all_inputs('all_inputs', 'CFTS_INPUT', [], event)
        assert event.controller.channels == {}

    def test_optional_calibration_still_applied(self, event, manager):
        # Not requiring a setting does not stop it from being used.
        set_channels('mic_1', gain='40', calibration='some/cal')

        record.initialize_all_inputs('all_inputs', 'CFTS_INPUT',
                                     ['channels'], event)

        channel = event.controller.channels['hw_ai::mic_1']
        assert channel.gain == 40.0
        assert channel.calibration == 'calibration for some/cal'

    def test_optional_calibration_missing(self, event):
        set_channels('mic_1', gain='40')

        record.initialize_all_inputs('all_inputs', 'CFTS_INPUT',
                                     ['channels', 'gain'], event)

        channel = event.controller.channels['hw_ai::mic_1']
        assert channel.gain == 40.0
        assert channel.calibration is None

    def test_custom_env_prefix(self, event):
        set_env(CFTS_EEG_CHANNELS='amp_1', CFTS_EEG_AMP_1_GAIN='40')

        record.initialize_all_inputs('all_inputs', 'CFTS_EEG',
                                     ['channels', 'gain'], event)

        assert event.controller.channels['hw_ai::amp_1'].gain == 40.0

    def test_unknown_required_var_raises(self, event):
        set_channels('mic_1', gain='40', calibration='some/cal')

        with pytest.raises(ValueError) as exc:
            record.initialize_all_inputs('all_inputs', 'CFTS_INPUT',
                                         ['chanels', 'gain'], event)
        assert 'chanels' in str(exc.value)
        assert 'channels, gain, calibration' in str(exc.value)


class TestCalibrationItems:
    '''
    One calibration item per active channel, rather than the single item
    the objects in objects.enaml contribute: this manifest configures
    every channel named in CFTS_INPUT_CHANNELS.
    '''

    def test_one_item_per_channel(self, event):
        set_env(CFTS_INPUT_CHANNELS='mic_1,mic_2')
        items = find_context_items(record.AllInputs(), CalibrationParameter)
        assert [i.name for i in items] == \
            ['mic_1_calibration', 'mic_2_calibration']
        assert [i.label for i in items] == \
            ['mic_1 calibration', 'mic_2 calibration']

    def test_reports_every_channel(self, event, manager):
        set_env(CFTS_INPUT_CHANNELS='mic_1,mic_2',
                CFTS_INPUT_MIC_1_GAIN='40', CFTS_INPUT_MIC_1='cal_a',
                CFTS_INPUT_MIC_2_GAIN='20', CFTS_INPUT_MIC_2='cal_b')

        record.initialize_all_inputs('all_inputs', 'CFTS_INPUT',
                                     ['channels', 'gain', 'calibration'],
                                     event)

        assert event.context.items['mic_1_calibration'].value == \
            'cal_a (2025-06-12)'
        assert event.context.items['mic_2_calibration'].value == \
            'cal_b (2025-06-12)'

    def test_one_uncalibrated_channel_is_reported(self, event, manager):
        # That channel is recording against unity while the others are
        # calibrated, which is exactly the case worth catching.
        set_env(CFTS_INPUT_CHANNELS='mic_1,mic_2',
                CFTS_INPUT_MIC_1_GAIN='40', CFTS_INPUT_MIC_1='cal_a',
                CFTS_INPUT_MIC_2_GAIN='20')

        record.initialize_all_inputs('all_inputs', 'CFTS_INPUT',
                                     ['channels', 'gain'], event)

        assert event.context.items['mic_1_calibration'].value == \
            'cal_a (2025-06-12)'
        assert event.context.items['mic_2_calibration'].value == NOT_LOADED

    def test_channel_with_missing_variables_is_reported(self, event):
        # The run is going to fail anyway, but the item should not be
        # left looking like the channel was simply never configured.
        set_env(CFTS_INPUT_CHANNELS='mic_1')

        with pytest.raises(MissingEnvironmentVariables):
            record.initialize_all_inputs('all_inputs', 'CFTS_INPUT',
                                         ['channels', 'gain', 'calibration'],
                                         event)

        assert event.context.items['mic_1_calibration'].value == NOT_LOADED
