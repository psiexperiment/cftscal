'''
Tests for the keyboard IO manifest (`cftscal.io.keyboard`).

The manifest lets abts's behavior paradigms run on any computer, with keys
standing in for the IR sensors. These tests pin the channels the paradigms
look for and the keys. Declaring the manifest does not open the sound card.
'''
import time

import pytest

from psi.application import initialize_io_manifest
from psi.controller.api import Channel
from psi.controller.engines.keyboard import KeyboardAIChannel

from cftscal import util


MANIFEST = 'cftscal.io.keyboard.IOManifest'


@pytest.fixture
def manifest(monkeypatch):
    manifest = initialize_io_manifest(MANIFEST)
    monkeypatch.setattr(util, 'IO_MANIFEST', manifest)
    return manifest


def channels(manifest, type_code=None):
    result = [o for o in manifest.traverse() if isinstance(o, Channel)]
    if type_code is not None:
        result = [c for c in result if c.type_code == type_code]
    return {c.name: c for c in result}


def test_launcher_lookups(manifest):
    assert set(util.list_speaker_connections().values()) == \
        {'speaker_1', 'speaker_2'}
    # Every abts paradigm records a microphone.
    assert list(util.list_connections('hw_ai', 'generic_microphone').values()) \
        == ['microphone_1']


@pytest.mark.parametrize('type_code, name', [
    # abts: behavior_nafc and the go/nogo IR sensor.
    ('hw_ao', 'speaker_1'),
    ('hw_ai', 'loopback_1'),
    ('hw_ao', 'ir_emitter'),
    ('hw_ai', 'np_contact'),
    ('hw_ai', 'resp_contact_1'),
    ('hw_ai', 'resp_contact_2'),
    # abts: psibehavior's reward, cue and timeout plugins.
    ('sw_do', 'pellet_1'),
    ('sw_do', 'pellet_2'),
    ('sw_do', 'cue_light'),
    ('sw_do', 'room_light'),
])
def test_channels_looked_up_by_name(manifest, type_code, name):
    assert name in channels(manifest, type_code)


def test_keys(manifest):
    keys = {c.name: c.key for c in channels(manifest).values()
            if isinstance(c, KeyboardAIChannel)}
    assert keys == {
        'np_contact': 'Space',
        'resp_contact_1': 'Left',
        'resp_contact_2': 'Right',
    }


def test_keyboard_keeps_sound_card_time(manifest):
    loopback = channels(manifest)['loopback_1']
    sound = channels(manifest)['speaker_1'].engine
    assert loopback.engine.clock is sound
    assert sound.master_clock
    assert loopback.source is channels(manifest)['speaker_1']
    assert loopback.fs == sound.fs


def test_plays_on_default_output(monkeypatch):
    import cftscal.io.keyboard as keyboard
    monkeypatch.setattr(keyboard, 'default_output_device',
                        lambda: ('Headphones, Windows WASAPI', 96000))
    manifest = initialize_io_manifest(MANIFEST)
    sound = channels(manifest)['speaker_1'].engine
    assert sound.device_name == 'Headphones, Windows WASAPI'
    assert sound.fs == 96000


def test_loads_without_sound_output(monkeypatch):
    # E.g., to list its channels on a computer without one.
    import cftscal.io.keyboard as keyboard

    def no_output():
        raise ValueError('This computer has no sound output.')

    monkeypatch.setattr(keyboard, 'default_output_device', no_output)
    manifest = initialize_io_manifest(MANIFEST)
    assert 'speaker_1' in channels(manifest)


def test_uncalibrated_speakers_play_quietly(manifest):
    # 60 dB SPL on the fallback calibration is 1 mVrms.
    speaker = channels(manifest)['speaker_1']
    assert speaker.calibration.get_sf(1000, 60) == pytest.approx(1e-3)


def test_digital_outputs_are_logged(manifest):
    engine = channels(manifest)['pellet_1'].engine
    engine.set_sw_do('cue_light', True)
    assert engine.sw_do_state['cue_light'] is True
    engine.fire_sw_do('pellet_1', duration=0.01)
    assert engine.sw_do_state['pellet_1'] == 1
    deadline = time.time() + 2
    while engine.sw_do_state['pellet_1'] != 0:
        assert time.time() < deadline, 'pellet_1 was never turned off'
        time.sleep(0.01)
