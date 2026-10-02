'''
Exporting and playing the region selected on Input Recording's time plot.

Both use the region exactly as plotted and measured -- after the Filter --
so what you hear and export is what the Analysis table describes. The GUI
side (buttons, dialogs) is in view.enaml.
'''
from fractions import Fraction
from pathlib import Path

import numpy as np
from atom.api import Atom, Bool, Int
from scipy import signal

from psiaudio import util

from cftscal.plugins.export import export_calibration_wav


#: Pressure played at full volume (a sample value of 1.0): 20 Pa, a peak
#: of 120 dB SPL. A fixed scale, so recordings can be compared by ear -- a
#: 94 dB SPL calibrator tone plays at about -23 dB re full scale -- at the
#: cost of quiet recordings sounding faint. Anything louder than this
#: clips, which play_region warns about first.
PLAYBACK_FULL_SCALE_PA = 20.0


def region_filename(name, start, end):
    '''
    File name for a recording's exported region, e.g.
    ``20260616-101544_18.000-22.000s.wav``.

    Parameters
    ----------
    name : str
        The recording's folder name.
    start, end : float
        The region, in seconds from the start of the recording.
    '''
    return f'{name}_{start:.3f}-{end:.3f}s.wav'


def _unused(path):
    '''``path``, or ``path`` with _2, _3, ... added if it already exists.'''
    candidate, n = path, 2
    while candidate.exists():
        candidate = path.with_name(f'{path.stem}_{n}{path.suffix}')
        n += 1
    return candidate


def export_region(folder, name, channels, fs, metadata):
    '''
    Write one recording's region to a calibrated WAV file in ``folder``.

    Parameters
    ----------
    folder : str or Path
        Folder to write to.
    name : str
        The recording's folder name (the file is named after it and the
        region; see region_filename).
    channels : list of np.ndarray
        Each channel's region, in pascals, after the Filter. Written as one
        interleaved file in this order (1.0 in the file = 1 Pa).
    fs : float
        Sampling rate, in Hz.
    metadata : dict
        Embedded in the file. Must include 'region' as (start, end).

    Returns
    -------
    path : Path
        The file written. Never overwrites: an existing file of the same
        name gets _2, _3, ... added instead.
    '''
    n = min(len(c) for c in channels)
    samples = np.stack([c[:n] for c in channels], axis=-1)
    start, end = metadata['region']
    path = _unused(Path(folder) / region_filename(name, start, end))
    return export_calibration_wav(path, samples, fs, metadata)


def clipping_peak(y, full_scale=PLAYBACK_FULL_SCALE_PA):
    '''
    The region's peak in pascals if playing it would clip, else None.
    '''
    peak = float(np.max(np.abs(y))) if len(y) else 0.0
    return peak if peak > full_scale else None


def playback_samples(y, fs, device_fs=None, full_scale=PLAYBACK_FULL_SCALE_PA):
    '''
    Scale a region for playback and, if needed, resample it.

    Parameters
    ----------
    y : np.ndarray
        The region, in pascals.
    fs : float
        Its sampling rate, in Hz.
    device_fs : float or None
        Rate to play at, if the output device can't play ``fs``.
    full_scale : float
        Pressure that plays at full volume (see PLAYBACK_FULL_SCALE_PA).

    Returns
    -------
    samples : np.ndarray (float32)
        ``y / full_scale``, clipped to +/-1.
    fs : float
        The rate ``samples`` is at.
    '''
    out = np.asarray(y, dtype=float) / full_scale
    if device_fs and device_fs != fs:
        ratio = Fraction(int(device_fs), int(fs)).limit_denominator(1000)
        out = signal.resample_poly(out, ratio.numerator, ratio.denominator)
        fs = device_fs
    return np.clip(out, -1, 1).astype(np.float32), fs


class Player(Atom):
    '''
    Plays one region at a time through the default output device.

    ``playing`` is True from play() until the sound ends or stop() is
    called, so a button can show Play or Stop.
    '''

    playing = Bool(False)

    #: Incremented on every play(), so the timer for an earlier sound
    #: doesn't mark a later one as finished.
    _token = Int(0)

    def play(self, y, fs):
        '''
        Start playing ``y`` (pascals, sampled at ``fs``), stopping anything
        already playing. Raises ImportError without sounddevice, and the
        device's error if it can't play.
        '''
        import sounddevice as sd
        from enaml.application import timed_call

        self.stop()
        try:
            sd.check_output_settings(samplerate=fs)
            device_fs = None
        except Exception:
            device_fs = sd.query_devices(kind='output')['default_samplerate']
        samples, play_fs = playback_samples(y, fs, device_fs)
        sd.play(samples, play_fs)
        self._token += 1
        self.playing = True
        token = self._token
        duration_ms = int(1000 * len(samples) / play_fs) + 200
        timed_call(duration_ms, self._finished, token)

    def stop(self):
        if self.playing:
            import sounddevice as sd
            sd.stop()
        self.playing = False

    def _finished(self, token):
        if token == self._token:
            self.playing = False


def peak_db(pa):
    '''A peak pressure in Pa as dB SPL, for messages.'''
    return util.patodb(pa)
