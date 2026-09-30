'''
Tests for the dummy Fireface IO manifest (`cftscal.io.dummy_fireface`).

The manifest exists so that cftscal, cfts, abts and noise-exp can all be run
on one sound card. These tests pin the channels each of them looks for, so
that renaming one breaks here rather than in whichever program stops finding
its hardware. Declaring the manifest does not touch the sound card; only the
last test does, and it is skipped when no Fireface is attached.
'''
import time

import pytest

from psi.application import initialize_io_manifest
from psi.controller.api import Channel

from cftscal import util


MANIFEST = 'cftscal.io.dummy_fireface.IOManifest'


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
    assert util.list_starship_connections() == {'A': 'starship_A', 'B': 'starship_B'}
    assert set(util.list_speaker_connections().values()) == {'speaker_1', 'speaker_2'}
    assert list(util.list_measurement_microphone_connections().values()) == ['cal_microphone']
    assert list(util.list_connections('hw_ai', 'generic_microphone').values()) == ['microphone_1']
    assert list(util.list_input_amplifier_connections().values()) == ['eeg']


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
    # cfts: output monitor and temperature plugins.
    ('hw_ai', 'output_monitor'),
    ('hw_ai', 'temperature'),
])
def test_channels_looked_up_by_name(manifest, type_code, name):
    assert name in channels(manifest, type_code)


def test_names_and_channel_numbers_are_unique(manifest):
    everything = [o for o in manifest.traverse() if isinstance(o, Channel)]
    names = [c.name for c in everything]
    assert len(names) == len(set(names))
    for type_code in ('hw_ai', 'hw_ao'):
        numbers = [c.channel for c in channels(manifest, type_code).values()]
        assert len(numbers) == len(set(numbers)), type_code


def test_every_output_has_a_matching_input_number(manifest):
    # So output N can be patched to input N for a loopback check.
    ai = {c.channel for c in channels(manifest, 'hw_ai').values()}
    ao = {c.channel for c in channels(manifest, 'hw_ao').values()}
    assert ao <= ai


def test_digital_outputs_are_logged(manifest):
    engine = next(iter(channels(manifest).values())).parent
    engine.set_sw_do('cue_light', True)
    assert engine.sw_do_state['cue_light'] is True
    engine.fire_sw_do('pellet_1', duration=0.01)
    assert engine.sw_do_state['pellet_1'] == 1
    deadline = time.time() + 2
    while engine.sw_do_state['pellet_1'] != 0:
        assert time.time() < deadline, 'pellet_1 was never turned off'
        time.sleep(0.01)


def _fireface_present():
    try:
        import sounddevice as sd
        sd.query_devices('ASIO Fireface USB')
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _fireface_present(), reason='No ASIO Fireface USB attached')
def test_streams_on_fireface(manifest):
    '''
    Opens every channel on the real device. Nothing is attached to the
    outputs, so they play silence.
    '''
    engine = next(iter(channels(manifest).values())).parent
    engine.configure(active=False)
    received = []
    engine.register_ai_callback(lambda data: received.append(data.shape))
    engine.start()
    try:
        time.sleep(1)
    finally:
        engine.stop()
    assert received
    assert received[0][0] == len(channels(manifest, 'hw_ai'))
