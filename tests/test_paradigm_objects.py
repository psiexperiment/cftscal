'''
Tests for the objects defined in ``cftscal/paradigms/objects.enaml``.

Focus is on how each object is configured from environment variables:
what it does when everything is set, what it does when an optional
setting is missing, and -- the reason ``required_vars`` exists -- that a
missing *required* setting raises an error naming the environment
variable that was expected instead of silently carrying on with the GUI
defaults.
'''
import enaml
import pytest

from cftscal.paradigms.calibration_status import (
    CalibrationParameter, NOT_CONFIGURED, NOT_LOADED
)
from cftscal.paradigms.env_vars import MissingEnvironmentVariables

from .fakes import FakeManager, set_env

with enaml.imports():
    from cftscal.paradigms import objects


def find_context_items(manifest, item_type):
    '''
    Return every context item of `item_type` a manifest contributes.
    '''
    items = []
    def scan(node):
        for child in node.children:
            if isinstance(child, item_type):
                items.append(child)
            scan(child)
    manifest.initialize()
    scan(manifest)
    return items


def find_command_handler(manifest):
    '''
    Return the handler of the (single) Command declared by a manifest.
    '''
    handlers = []
    def scan(node):
        if hasattr(node, 'handler') and node.handler is not None:
            handlers.append(node.handler)
        for child in node.children:
            scan(child)
    scan(manifest)
    assert len(handlers) == 1
    return handlers[0]


#: Objects that load a calibration, and therefore contribute a
#: calibration context item. The input amplifier has none (it has filter
#: cutoffs dialed in on its front panel instead).
CALIBRATED = ['Input', 'Output', 'Speaker', 'Microphone', 'Starship']

#: Name of each of those objects' calibration item, with the manifest
#: built using its default id.
CALIBRATION_ITEMS = {
    'Input': 'input_calibration',
    'Output': 'output_calibration',
    'Speaker': 'system_output_calibration',
    # The microphone names its items after the input, not the manifest.
    'Microphone': 'system_microphone_input_calibration',
    'Starship': 'starship_calibration',
}


class TestRequiredVarDefaults:
    '''
    By default, every setting an object knows how to read is required.
    '''

    @pytest.mark.parametrize('name, expected', [
        ('Input', ['name', 'gain', 'calibration']),
        ('Output', ['name', 'calibration']),
        ('Speaker', ['name', 'calibration']),
        ('Microphone', ['name', 'gain', 'calibration']),
        ('Starship', ['name', 'gain', 'calibration']),
        ('InputAmplifier', ['name', 'gain', 'freq_lb', 'freq_ub']),
    ])
    def test_default_required_vars(self, name, expected):
        assert getattr(objects, name)().required_vars == expected

    @pytest.mark.parametrize('name', CALIBRATED + ['InputAmplifier'])
    def test_required_vars_passed_to_handler(self, name):
        # The command handler is wired up with functools.partial, so a
        # paradigm that overrides required_vars only has an effect if
        # the override is picked up when the handler is created.
        manifest = getattr(objects, name)(required_vars=['name'])
        assert find_command_handler(manifest).args[-1] == ['name']


class TestInitializeInput:

    def test_all_vars_set(self, event, monkeypatch):
        manager = FakeManager()
        monkeypatch.setattr(objects, 'input_manager', manager)
        set_env(CFTS_INPUT='mic_1', CFTS_INPUT_MIC_1_GAIN='40',
                CFTS_INPUT_MIC_1='some/calibration')

        objects.initialize_input('my_input', 'CFTS_INPUT',
                                 ['name', 'gain', 'calibration'], event)

        item = event.context.items['my_input']
        # Quotes around the name are important -- the value of an
        # EnumParameter is an expression, not a plain string.
        assert item.expression == '"mic_1"'
        assert item.editable is False
        assert event.context.items['my_input_gain'].value == '40'
        assert event.context.items['my_input_gain'].editable is False
        channel = event.controller.channels['hw_ai::mic_1']
        assert channel.calibration == 'calibration for some/calibration'

    def test_optional_calibration_not_set(self, event):
        set_env(CFTS_INPUT='mic_1', CFTS_INPUT_MIC_1_GAIN='40')

        objects.initialize_input('my_input', 'CFTS_INPUT',
                                 ['name', 'gain'], event)

        assert event.context.items['my_input'].expression == '"mic_1"'
        assert event.controller.channels == {}

    def test_missing_required_calibration_raises(self, event):
        set_env(CFTS_INPUT='mic_1', CFTS_INPUT_MIC_1_GAIN='40')

        with pytest.raises(MissingEnvironmentVariables) as exc:
            objects.initialize_input('my_input', 'CFTS_INPUT',
                                     ['name', 'gain', 'calibration'], event)
        assert 'CFTS_INPUT_MIC_1' in str(exc.value)

    def test_nothing_required_and_nothing_set(self, event):
        # Nothing is configured, but the experiment can still be set up
        # by hand in the GUI.
        objects.initialize_input('my_input', 'CFTS_INPUT', [], event)
        # Including the calibration item, which is left showing the
        # NOT_CONFIGURED it was declared with.
        assert event.context.items == {}

    def test_custom_env_prefix(self, event):
        set_env(CFTS_EEG='mic_1', CFTS_EEG_MIC_1_GAIN='40')

        objects.initialize_input('my_input', 'CFTS_EEG', ['name', 'gain'],
                                 event)

        assert event.context.items['my_input_gain'].value == '40'


class TestInitializeOutput:

    def test_all_vars_set(self, event, monkeypatch):
        manager = FakeManager()
        monkeypatch.setattr(objects, 'output_manager', manager)
        set_env(CFTS_SPEAKER='speaker_1', CFTS_SPEAKER_SPEAKER_1='some/cal')

        objects.initialize_output('my_output', 'CFTS_SPEAKER',
                                  ['name', 'calibration'], event)

        assert event.context.items['my_output'].expression == '"speaker_1"'
        channel = event.controller.channels['hw_ao::speaker_1']
        assert channel.calibration == 'calibration for some/cal'

    def test_missing_required_calibration_raises(self, event):
        set_env(CFTS_SPEAKER='speaker_1')

        with pytest.raises(MissingEnvironmentVariables) as exc:
            objects.initialize_output('my_output', 'CFTS_SPEAKER',
                                      ['name', 'calibration'], event)
        assert 'CFTS_SPEAKER_SPEAKER_1' in str(exc.value)

    def test_calibration_not_required(self, event):
        set_env(CFTS_SPEAKER='speaker_1')

        objects.initialize_output('my_output', 'CFTS_SPEAKER', ['name'], event)

        assert event.context.items['my_output'].expression == '"speaker_1"'
        assert event.controller.channels == {}


class TestInitializeMicrophone:

    def test_all_vars_set(self, event, monkeypatch):
        manager = FakeManager()
        monkeypatch.setitem(objects.MICROPHONE_MANAGERS,
                            'measurement_microphone', manager)
        set_env(CFTS_MICROPHONE='mic_1', CFTS_MICROPHONE_MIC_1_GAIN='40',
                CFTS_MICROPHONE_MIC_1='some/cal')

        objects.initialize_microphone('my_mic', 'measurement_microphone',
                                      'CFTS_MICROPHONE',
                                      ['name', 'gain', 'calibration'], event)

        assert event.context.items['my_mic_input'].expression == '"mic_1"'
        assert event.context.items['my_mic_input_gain'].value == '40'
        channel = event.controller.channels['hw_ai::mic_1']
        assert channel.calibration == 'calibration for some/cal'

    def test_calibration_loaded_by_microphone_type(self, event, monkeypatch):
        manager = FakeManager()
        monkeypatch.setitem(objects.MICROPHONE_MANAGERS,
                            'generic_microphone', manager)
        set_env(CFTS_GENERIC_MICROPHONE='mic_1',
                CFTS_GENERIC_MICROPHONE_MIC_1_GAIN='40',
                CFTS_GENERIC_MICROPHONE_MIC_1='some/cal')

        objects.initialize_microphone('my_mic', 'generic_microphone',
                                      'CFTS_GENERIC_MICROPHONE',
                                      ['name', 'gain', 'calibration'], event)

        assert manager.loaded == 'some/cal'

    def test_missing_required_gain_raises(self, event):
        set_env(CFTS_MICROPHONE='mic_1')

        with pytest.raises(MissingEnvironmentVariables) as exc:
            objects.initialize_microphone('my_mic', 'measurement_microphone',
                                          'CFTS_MICROPHONE',
                                          ['name', 'gain'], event)
        assert 'CFTS_MICROPHONE_MIC_1_GAIN' in str(exc.value)

    def test_unsupported_microphone_type_raises(self, event):
        set_env(CFTS_MICROPHONE='mic_1')

        with pytest.raises(ValueError) as exc:
            objects.initialize_microphone('my_mic', 'lapel_microphone',
                                          'CFTS_MICROPHONE', ['name'], event)
        assert 'lapel_microphone' in str(exc.value)
        assert 'measurement_microphone' in str(exc.value)


class TestInitializeStarship:

    def test_all_vars_set(self, event, monkeypatch):
        manager = FakeManager()
        monkeypatch.setattr(objects, 'starship_manager', manager)
        set_env(CFTS_TEST_STARSHIP='ss_1', CFTS_STARSHIP_SS_1_GAIN='40',
                CFTS_STARSHIP_SS_1='some/cal')

        objects.initialize_starship('my_starship', 'test',
                                    ['name', 'gain', 'calibration'], event)

        assert event.context.items['my_starship'].value == 'ss_1'
        assert event.context.items['my_starship_input_gain'].value == '40'
        channel = event.controller.channels['hw_ai::ss_1_microphone']
        assert channel.calibration == 'calibration for some/cal'

    def test_side_selects_environment_variable(self, event):
        set_env(CFTS_NONTEST_STARSHIP='ss_2', CFTS_STARSHIP_SS_2_GAIN='40')

        objects.initialize_starship('my_starship', 'nontest',
                                    ['name', 'gain'], event)

        assert event.context.items['my_starship'].value == 'ss_2'

    def test_missing_required_starship_raises(self, event):
        with pytest.raises(MissingEnvironmentVariables) as exc:
            objects.initialize_starship('my_starship', 'test',
                                        ['name', 'gain'], event)
        assert 'CFTS_TEST_STARSHIP' in str(exc.value)

    def test_calibration_not_required(self, event):
        # The probe-tube calibration paradigms create the calibration,
        # so there is none to load yet.
        set_env(CFTS_TEST_STARSHIP='ss_1', CFTS_STARSHIP_SS_1_GAIN='40')

        objects.initialize_starship('my_starship', 'test',
                                    ['name', 'gain'], event)

        assert event.controller.channels == {}


class TestInitializeInputAmplifier:

    def test_all_vars_set(self, event):
        set_env(CFTS_INPUT_AMPLIFIER='amp_1',
                CFTS_INPUT_AMPLIFIER_AMP_1_GAIN='50000',
                CFTS_INPUT_AMPLIFIER_AMP_1_FREQ_LB='10',
                CFTS_INPUT_AMPLIFIER_AMP_1_FREQ_UB='10000')

        objects.initialize_input_amplifier(
            'eeg', 'CFTS_INPUT_AMPLIFIER',
            ['name', 'gain', 'freq_lb', 'freq_ub'], event)

        items = event.context.items
        assert items['eeg'].expression == '"amp_1"'
        assert items['eeg_gain'].value == '50000'
        assert items['eeg_highpass'].value == '10'
        assert items['eeg_lowpass'].value == '10000'
        assert all(not i.editable for i in items.values())

    def test_missing_required_filter_cutoff_raises(self, event):
        set_env(CFTS_INPUT_AMPLIFIER='amp_1',
                CFTS_INPUT_AMPLIFIER_AMP_1_GAIN='50000',
                CFTS_INPUT_AMPLIFIER_AMP_1_FREQ_LB='10')

        with pytest.raises(MissingEnvironmentVariables) as exc:
            objects.initialize_input_amplifier(
                'eeg', 'CFTS_INPUT_AMPLIFIER',
                ['name', 'gain', 'freq_lb', 'freq_ub'], event)
        assert 'CFTS_INPUT_AMPLIFIER_AMP_1_FREQ_UB' in str(exc.value)

    def test_missing_amplifier_not_required(self, event):
        # User configures the amplifier by hand in the GUI.
        objects.initialize_input_amplifier('eeg', 'CFTS_INPUT_AMPLIFIER', [],
                                           event)
        assert event.context.items == {}


class TestCalibrationItem:
    '''
    Which calibration was loaded is not visible anywhere else: the
    channel it is loaded onto has no widget, and a channel that never got
    one silently falls back to unity. Each handler therefore records what
    it did in a read-only context item shown beside the object's other
    hardware settings (and saved with the data).
    '''

    @pytest.mark.parametrize('name', CALIBRATED)
    def test_item_contributed(self, name):
        manifest = getattr(objects, name)()
        items = [i.name for i in find_context_items(manifest, CalibrationParameter)]
        assert items == [CALIBRATION_ITEMS[name]]

    @pytest.mark.parametrize('name', ['InputAmplifier'])
    def test_no_item_without_a_calibration(self, name):
        manifest = getattr(objects, name)()
        assert find_context_items(manifest, CalibrationParameter) == []

    def test_input_reports_loaded_calibration(self, event, monkeypatch):
        monkeypatch.setattr(objects, 'input_manager', FakeManager())
        set_env(CFTS_INPUT='mic_1', CFTS_INPUT_MIC_1_GAIN='40',
                CFTS_INPUT_MIC_1='cal_a')

        objects.initialize_input('my_input', 'CFTS_INPUT',
                                 ['name', 'gain', 'calibration'], event)

        assert event.context.items['my_input_calibration'].value == \
            'cal_a (2025-06-12)'

    def test_input_reports_missing_calibration(self, event):
        # The experiment still runs -- against unity -- so this is the
        # only sign anything is wrong.
        set_env(CFTS_INPUT='mic_1', CFTS_INPUT_MIC_1_GAIN='40')

        objects.initialize_input('my_input', 'CFTS_INPUT', ['name', 'gain'],
                                 event)

        assert event.context.items['my_input_calibration'].value == NOT_LOADED

    def test_output_reports_loaded_calibration(self, event, monkeypatch):
        monkeypatch.setattr(objects, 'output_manager', FakeManager())
        set_env(CFTS_SPEAKER='speaker_1', CFTS_SPEAKER_SPEAKER_1='cal_a')

        objects.initialize_output('my_output', 'CFTS_SPEAKER',
                                  ['name', 'calibration'], event)

        assert event.context.items['my_output_calibration'].value == \
            'cal_a (2025-06-12)'

    def test_microphone_reports_loaded_calibration(self, event, monkeypatch):
        monkeypatch.setitem(objects.MICROPHONE_MANAGERS,
                            'measurement_microphone', FakeManager())
        set_env(CFTS_MICROPHONE='mic_1', CFTS_MICROPHONE_MIC_1_GAIN='40',
                CFTS_MICROPHONE_MIC_1='cal_a')

        objects.initialize_microphone('my_mic', 'measurement_microphone',
                                      'CFTS_MICROPHONE',
                                      ['name', 'gain', 'calibration'], event)

        assert event.context.items['my_mic_input_calibration'].value == \
            'cal_a (2025-06-12)'

    def test_starship_reports_loaded_calibration(self, event, monkeypatch):
        monkeypatch.setattr(objects, 'starship_manager', FakeManager())
        set_env(CFTS_TEST_STARSHIP='ss_1', CFTS_STARSHIP_SS_1_GAIN='40',
                CFTS_STARSHIP_SS_1='cal_a')

        objects.initialize_starship('my_starship', 'test',
                                    ['name', 'gain', 'calibration'], event)

        assert event.context.items['my_starship_calibration'].value == \
            'cal_a (2025-06-12)'

    def test_starship_reports_missing_calibration(self, event):
        set_env(CFTS_TEST_STARSHIP='ss_1', CFTS_STARSHIP_SS_1_GAIN='40')

        objects.initialize_starship('my_starship', 'test', ['name', 'gain'],
                                    event)

        assert event.context.items['my_starship_calibration'].value == \
            NOT_LOADED


#: What each of cftscal's own calibration paradigms requires from the
#: environment, keyed by paradigm name and then by manifest id. These
#: must match what the corresponding plugin actually puts in the
#: environment (see the `include_cal` arguments to `get_env_vars` in
#: `cftscal/plugins/*/settings.py`). A paradigm that *creates* a
#: calibration has none to load, so it must not require one.
EXPECTED_REQUIRED_VARS = {
    'pt_calibration_chirp': {
        'system': ['name', 'gain'],
        'cal_microphone': ['name', 'gain', 'calibration'],
    },
    'pt_calibration_golay': {
        'system': ['name', 'gain'],
        'cal_microphone': ['name', 'gain', 'calibration'],
    },
    'mic_calibration_chirp': {
        'system': ['name'],
        'measurement_microphone': ['name', 'gain', 'calibration'],
        'generic_microphone': ['name', 'gain'],
    },
    'mic_calibration_golay': {
        'system': ['name'],
        'measurement_microphone': ['name', 'gain', 'calibration'],
        'generic_microphone': ['name', 'gain'],
    },
    'speaker_calibration_chirp': {
        'system': ['name'],
        'cal_microphone': ['name', 'gain', 'calibration'],
    },
    'speaker_calibration_golay': {
        'system': ['name'],
        'cal_microphone': ['name', 'gain', 'calibration'],
    },
    'pistonphone_calibration': {
        'cal_microphone': ['name', 'gain'],
    },
    'iec': {
        'system': ['name', 'gain', 'calibration'],
    },
    'input_amplifier_calibration': {
        'input_amplifier': ['name', 'gain', 'freq_lb', 'freq_ub'],
    },
    'ir_sensor': {
        'selected_input': ['name', 'gain'],
        'selected_output': ['name'],
    },
}


@pytest.mark.parametrize('paradigm_name', sorted(EXPECTED_REQUIRED_VARS))
def test_paradigm_required_vars(paradigm_name):
    # Importing cftscal.paradigms registers every cftscal paradigm with
    # psiexperiment's global paradigm manager.
    import cftscal.paradigms  # noqa: F401
    from psi.experiment.api import paradigm_manager

    paradigm = paradigm_manager.paradigms[paradigm_name]
    required_vars = {}
    for plugin in paradigm.plugins:
        # Only the manifests defined in objects.enaml read their
        # configuration from environment variables. `_manifest` is the
        # dotted path to the manifest, checked here so we do not have to
        # instantiate every other plugin of every paradigm.
        if not plugin._manifest.startswith('cftscal.paradigms.objects.'):
            continue
        required_vars[plugin.manifest.id] = plugin.manifest.required_vars
    assert required_vars == EXPECTED_REQUIRED_VARS[paradigm_name]
