'''
Tests for :func:`cftscal.util.slugify`.
'''
import pytest

from cftscal.util import natural_sort_key, slugify


@pytest.mark.parametrize('text, expected', [
    ('MMM0', 'mmm0'),
    ('Bench speaker #3 (Lab B)', 'bench-speaker-3-lab-b'),
    # Characters Windows forbids in folder names, and '/', which would
    # otherwise create extra subfolders.
    (r'C:/a<b>c|d?e*f"g\h', 'c-a-b-c-d-e-f-g-h'),
    ('Café', 'cafe'),
    ('  --leading and trailing--  ', 'leading-and-trailing'),
    ('a   b', 'a-b'),
    ('???', ''),
    ('', ''),
])
def test_slugify(text, expected):
    assert slugify(text) == expected


@pytest.mark.parametrize('labels, expected', [
    # The order sound cards number their channels in, not "1, 10, 11, 2".
    (['Output 10', 'Output 2', 'Output 1', 'Output 19', 'Output 0'],
     ['Output 0', 'Output 1', 'Output 2', 'Output 10', 'Output 19']),
    (['Speaker 2 (right)', 'Speaker 1 (left)'],
     ['Speaker 1 (left)', 'Speaker 2 (right)']),
    # Text before the number sorts first, ignoring case.
    (['input 2', 'Input 1', 'Analog 10', 'analog 9'],
     ['analog 9', 'Analog 10', 'Input 1', 'input 2']),
    # Labels without numbers, or starting with one, still sort.
    (['b', '10 a', 'a', '9 a'], ['9 a', '10 a', 'a', 'b']),
])
def test_natural_sort_key(labels, expected):
    assert sorted(labels, key=natural_sort_key) == expected


class FakeSounddevice:
    '''
    The parts of sounddevice that `default_output_device` reads.
    '''

    class PortAudioError(Exception):
        pass

    def __init__(self, hostapis, devices, default_output):
        self.hostapis = hostapis
        self.devices = devices
        self.default_output = default_output

    def query_hostapis(self):
        return self.hostapis

    def query_devices(self, index=None, kind=None):
        if kind == 'output':
            index = self.default_output
        if index is None or index < 0:
            raise self.PortAudioError('no device')
        return self.devices[index]


def fake_sounddevice(monkeypatch, with_wasapi=True, default_output=0):
    hostapis = [{'name': 'MME', 'default_output_device': 0}]
    devices = [{'name': 'Headphones (MME)', 'hostapi': 0,
                'default_samplerate': 44100.0}]
    if with_wasapi:
        hostapis.append({'name': 'Windows WASAPI', 'default_output_device': 1})
        devices.append({'name': 'Headphones', 'hostapi': 1,
                        'default_samplerate': 96000.0})
    fake = FakeSounddevice(hostapis, devices, default_output)
    monkeypatch.setitem(__import__('sys').modules, 'sounddevice', fake)
    return fake


def test_default_output_prefers_wasapi(monkeypatch):
    from cftscal.util import default_output_device
    fake_sounddevice(monkeypatch)
    assert default_output_device() == ('Headphones, Windows WASAPI', 96000)


def test_default_output_falls_back_to_portaudio_default(monkeypatch):
    from cftscal.util import default_output_device
    fake_sounddevice(monkeypatch, with_wasapi=False)
    assert default_output_device() == ('Headphones (MME), MME', 44100)


def test_no_default_output(monkeypatch):
    from cftscal.util import default_output_device
    fake_sounddevice(monkeypatch, with_wasapi=False, default_output=-1)
    with pytest.raises(ValueError, match='no sound output'):
        default_output_device()
