'''
Tests for :mod:`cftscal.migrate_metadata` — parsers that recover metadata
from legacy calibration directory names.  These are one-shot recovery
code, so tests exist mainly to prevent someone touching the module from
silently breaking migration of already-acquired data.
'''
import datetime as dt
from pathlib import Path

import pytest

from cftscal import migrate_metadata as mm


def _folder(name):
    '''Parsers only touch ``folder.name``, so a Path stub is enough.'''
    return Path(name)


class TestParseDatetime:

    def test_valid_prefix(self):
        assert mm._parse_datetime('20260701-123456_anything') == (
            dt.datetime(2026, 7, 1, 12, 34, 56).isoformat()
        )

    def test_missing_prefix_raises(self):
        with pytest.raises(ValueError):
            mm._parse_datetime('no-timestamp-here')


class TestMicrophoneMeasurement:

    def test_extracts_pistonphone(self):
        result = mm._parse_microphone_measurement(
            _folder('20260701-123456_MMM0_PP1')
        )
        assert result == {
            'datetime': dt.datetime(2026, 7, 1, 12, 34, 56).isoformat(),
            'pistonphone': 'PP1',
        }


class TestMicrophoneGeneric:

    def test_extracts_measurement_mic_and_stimulus(self):
        result = mm._parse_microphone_generic(
            _folder('20260701-123456_generic_MMM0_golay')
        )
        assert result['measurement_microphone'] == 'MMM0'
        assert result['stimulus'] == 'golay'


class TestSpeaker:

    def test_extracts_microphone_and_method(self):
        result = mm._parse_speaker(
            _folder('20260701-123456_SPK1_MMM0_tone')
        )
        assert result['microphone'] == 'MMM0'
        assert result['method'] == 'tone'


class TestStarship:

    def test_extracts_microphone_coupler_stimulus(self):
        result = mm._parse_starship(
            _folder('20260701-123456_SS1_MMM0_coupler-A_golay')
        )
        assert result['microphone'] == 'MMM0'
        assert result['coupler'] == 'coupler-A'
        assert result['stimulus'] == 'golay'


class TestInputAmplifier:

    def test_only_datetime(self):
        result = mm._parse_input_amplifier(
            _folder('20260701-123456_AMP1_1000x_10-10000Hz-filt-60Hz-input')
        )
        assert result == {
            'datetime': dt.datetime(2026, 7, 1, 12, 34, 56).isoformat(),
        }


class TestInputRecording:

    def test_extracts_generator_and_sensor(self):
        result = mm._parse_input_recording(
            _folder('20260701-123456_chirp_MMM0')
        )
        assert result['generator'] == 'chirp'
        assert result['sensor'] == 'MMM0'


class TestInear:

    def test_extracts_ear_and_starship(self):
        result = mm._parse_inear(
            _folder('20260701-123456_left_SS1')
        )
        assert result['ear'] == 'left'
        assert result['starship'] == 'SS1'


class TestIrSensor:

    def test_extracts_input_name(self):
        result = mm._parse_ir_sensor(
            _folder('20260701-123456_ai0')
        )
        assert result['input_name'] == 'ai0'
