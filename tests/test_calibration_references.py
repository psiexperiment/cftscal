'''
Tests for the calibration pickers launchers use for their speakers and
microphones (`SpeakerCalibrationReference`, `MicrophoneCalibrationReference`),
including the 'Nominal' and 'Unity' types that let an experiment run before
anything has been calibrated.
'''
import pytest

from cftscal.objects import (
    output_manager, NominalInputCalibration, NominalSpeakerCalibration,
    UnityInputCalibration,
)
from cftscal.plugins.settings import (
    CalibrationReference, InputSettings, MicrophoneCalibrationReference,
    OutputCalibrationReference, OutputSettings, SensorDevice, SensorSettings,
    SpeakerCalibrationReference, SpeakerSettings,
)


def test_nominal_speaker_calibration_levels():
    calibration = NominalSpeakerCalibration(110).load()
    # 110 dB SPL is 1 Vrms, and 90 dB SPL a tenth of that, at any frequency.
    for frequency in (100, 1000, 8000, 40000):
        assert calibration.get_sf(frequency, 110) == pytest.approx(1)
        assert calibration.get_sf(frequency, 90) == pytest.approx(0.1)


def test_nominal_speaker_calibration_round_trips():
    calibration = NominalSpeakerCalibration(120)
    assert calibration.name == 'Nominal (120 dB SPL at 1 Vrms)'
    # As the paradigm loads it (see `initialize_output` in
    # cftscal/paradigms/objects.enaml).
    restored = output_manager.from_string(calibration.to_string())
    assert isinstance(restored, NominalSpeakerCalibration)
    assert restored.spl == 120


def test_speaker_types():
    speaker = SpeakerCalibrationReference()
    assert speaker.DEVICE_TYPES == ['Speaker', 'Nominal']
    # Calibrated speakers by default, as before there was a choice.
    assert speaker.device_type == 'Speaker'
    assert speaker.SENSITIVITY_UNIT == 'dB SPL at 1 Vrms'


def test_nominal_speaker_env_vars():
    speaker = SpeakerCalibrationReference()
    speaker.switch_type('Nominal')
    speaker.sensitivity = 105
    assert speaker.is_configured()
    assert speaker.display_name() == 'Nominal (105 dB SPL at 1 Vrms)'
    output = OutputSettings(output_name='speaker_1', generator=speaker)
    env = output.get_env_vars(env_prefix='CFTSCAL_SPEAKER_1')
    assert env['CFTSCAL_SPEAKER_1'] == 'speaker_1'
    calibration = output_manager.from_string(env['CFTSCAL_SPEAKER_1_SPEAKER_1'])
    assert calibration.load().get_sf(1000, 105) == pytest.approx(1)


def test_uncalibrated_speaker_raises():
    output = OutputSettings(output_name='speaker_1',
                            generator=SpeakerCalibrationReference())
    output.generator.name = 'no-such-speaker'
    with pytest.raises(LookupError, match='no-such-speaker'):
        output.get_env_vars(env_prefix='CFTSCAL_SPEAKER_1')
    # Same for the speaker workspace's own settings.
    output = OutputSettings(output_name='speaker_1',
                            generator=SpeakerSettings(name='no-such-speaker'))
    with pytest.raises(LookupError, match='no-such-speaker'):
        output.get_env_vars(env_prefix='CFTSCAL_SPEAKER_1')


def test_microphone_types():
    mic = MicrophoneCalibrationReference()
    assert mic.DEVICE_TYPES == ['Generic Mic.', 'Meas. Mic.', 'Unity',
                                'Nominal']
    assert mic.device_type == 'Generic Mic.'
    assert mic.SENSITIVITY_UNIT == 'mV/Pa'


@pytest.mark.parametrize('device_type, expected', [
    ('Unity', UnityInputCalibration),
    ('Nominal', NominalInputCalibration),
])
def test_uncalibrated_microphone_env_vars(device_type, expected):
    mic = MicrophoneCalibrationReference()
    mic.switch_type(device_type)
    assert mic.is_configured()
    settings = InputSettings(input_name='microphone_1', sensor=mic)
    env = settings.get_env_vars(env_prefix='CFTSCAL_MICROPHONE_1')
    calibration = output_manager.from_string(
        env['CFTSCAL_MICROPHONE_1_MICROPHONE_1'])
    assert isinstance(calibration, expected)


def test_selection_survives_save_and_load():
    speaker = SpeakerCalibrationReference()
    speaker.switch_type('Nominal')
    speaker.sensitivity = 100
    restored = SpeakerCalibrationReference()
    restored.set_persistence(speaker.get_persistence())
    assert restored.device_type == 'Nominal'
    assert restored.sensitivity == 100


@pytest.mark.parametrize('reference', [
    SpeakerCalibrationReference, OutputCalibrationReference,
])
def test_output_references_are_not_sensors(reference):
    # Outputs pick a calibration like a sensor does, but have no gain.
    ref = reference()
    assert isinstance(ref, CalibrationReference)
    assert not isinstance(ref, SensorSettings)
    assert not hasattr(ref, 'gain')
    assert 'gain' not in ref.get_persistence()


def test_microphone_reference_is_a_sensor():
    mic = MicrophoneCalibrationReference()
    assert isinstance(mic, CalibrationReference)
    assert isinstance(mic, SensorSettings)
    assert 'gain' in mic.get_persistence()


def test_output_settings_needs_a_calibration_source():
    # A device being calibrated has no calibration to play with.
    with pytest.raises(TypeError):
        OutputSettings(output_name='speaker_1', generator=SensorDevice())


def test_speaker_settings_saved_with_gain_still_load():
    # Speaker references used to inherit an (unused) gain, which settings
    # saved before the change still carry.
    restored = SpeakerCalibrationReference()
    restored.set_persistence({'name': '', 'gain': 0.0,
                              'device_type': 'Nominal', 'sensitivity': 104})
    assert restored.device_type == 'Nominal'
    assert restored.sensitivity == 104
