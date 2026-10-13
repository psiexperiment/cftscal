'''
Input Recording's "Emulate Measure Sound" mode: the calculations of the lab's
MATLAB program, Measure Sound (``measure_sound_v2022.m``), reproduced so that
results can be compared with measurements made in it.

This is for comparing with old results only. Input Recording's own filters and
A-weighting (`cftscal.plugins.input_recording.filters`) follow IEC 61672-1;
the calculations here follow Measure Sound instead:

* `correction_factor`: Measure Sound multiplies the first channel of a
  recording by 1.165 and the second by 1.187.
* `band_pass`: Measure Sound's band-pass filter (``butter_band``): a
  first-order Butterworth band-pass run forwards and backwards with
  ``filtfilt``, which applies its attenuation twice (band edges 6 dB down).
* `dba`: Measure Sound's dBA (``estimateLevel`` with ``filterA``), calculated
  from the spectrum with its constant ``C = 42.8051``.
* `levels`: the Analysis table's measurements, calculated the way Measure
  Sound calculates its own.

Measure Sound re-filters its already-filtered waveform each time *Advance*,
*Rewind*, *Zoom in* or *Zoom out* is pressed with the filter on. That isn't
reproduced: these functions match Measure Sound measured straight after a
file is opened.
'''
import numpy as np
from scipy import signal

from psiaudio import util


#: Measure Sound's correction factors for the first and second channel of a
#: recording (``handles.correction_factor`` in ``pb_open_Callback``). Other
#: channels get none.
CORRECTION_FACTORS = (1.165, 1.187)

#: Measure Sound's dBA calibration constant (``C`` in ``goMeasure``).
DBA_CONSTANT = 42.8051


def correction_factor(channel_index):
    '''
    Measure Sound's correction factor for a channel.

    Parameters
    ----------
    channel_index : int
        Position of the channel in its recording: 0 for the first.

    Returns
    -------
    factor : float
        1.165 for the first channel, 1.187 for the second, else 1.
    '''
    if 0 <= channel_index < len(CORRECTION_FACTORS):
        return CORRECTION_FACTORS[channel_index]
    return 1.0


def band_pass(y, fs, fc, bw):
    '''
    Measure Sound's band-pass filter (``butter_band`` with order 1).

    Parameters
    ----------
    y : np.ndarray
        Signal.
    fs : float
        Sampling rate, in Hz.
    fc : float
        Center frequency, in Hz.
    bw : float
        Width, in octaves: the band runs from ``fc * 2**(-bw/2)`` to
        ``fc * 2**(bw/2)``.

    Returns
    -------
    y_filtered : np.ndarray
        ``y`` filtered forwards and then backwards, as MATLAB's ``filtfilt``
        does, including its padding at the ends (``3 * (n - 1)`` samples
        for a filter of length ``n``; SciPy's default is slightly longer).
    '''
    lo, hi = fc * 2 ** (-0.5 * bw), fc * 2 ** (0.5 * bw)
    b, a = signal.butter(1, [lo / (fs / 2), hi / (fs / 2)], 'bandpass')
    padlen = 3 * (max(len(a), len(b)) - 1)
    if len(y) <= padlen:
        # MATLAB's filtfilt needs more samples than its padding.
        return np.full(len(y), np.nan)
    return signal.filtfilt(b, a, y, padtype='odd', padlen=padlen)


def a_weighting_power(f):
    '''
    Measure Sound's ``filterA``: the A-weighting curve as a power ratio.

    Parameters
    ----------
    f : np.ndarray
        Frequencies, in Hz.

    Returns
    -------
    a : np.ndarray
        ``10 ** (A(f) / 10)``, where A(f) is the IEC 61672-1 A-weighting
        in dB.
    '''
    c1 = 3.5041384e16
    c2 = 20.598997 ** 2
    c3 = 107.65265 ** 2
    c4 = 737.86223 ** 2
    c5 = 12194.217 ** 2
    f = np.where(np.asarray(f, dtype=float) == 0, 1e-17, f) ** 2
    num = c1 * f ** 4
    den = (c2 + f) ** 2 * (c3 + f) * (c4 + f) * (c5 + f) ** 2
    return num / den


def dba(y, fs, constant=DBA_CONSTANT):
    '''
    Measure Sound's dBA (``estimateLevel``).

    The magnitude of the FFT below Nyquist is multiplied by
    `a_weighting_power`, and the energy of the result is turned into a level
    with ``constant`` added. This weights each frequency's power by the
    square of the A-weighting power ratio (twice the A-weighting in dB), and
    ``constant`` is the value that makes a 1 kHz tone read the same in dB SPL
    and dBA at a sampling rate of 131,072 Hz.

    Parameters
    ----------
    y : np.ndarray
        Signal, in pascals.
    fs : float
        Sampling rate, in Hz.
    constant : float
        Measure Sound's calibration constant, ``C``.

    Returns
    -------
    level : float
        Measure Sound's dBA.
    '''
    x = np.abs(np.fft.fft(y))
    x[x == 0] = 1e-17
    f = fs / len(x) * np.arange(len(x))
    keep = f < fs / 2
    xa = a_weighting_power(f[keep]) * x[keep]
    total_energy = np.sum(xa ** 2) / len(xa)
    mean_energy = total_energy / ((1 / fs) * len(y))
    return 10 * np.log10(mean_energy) + constant


def levels(y, fs):
    '''
    The Analysis table's measurements, calculated as Measure Sound does.

    The same as `region_levels` in Input Recording's view, except that

    * Max (Pa) and Min (Pa) can't be below or above 0 Pa respectively:
      Measure Sound looks for them in the whole recording with everything
      outside the window set to 0;
    * peSPL (Measure Sound's equivalent RMS) and Peak SPL come from that
      Max and Min;
    * dBA is `dba`, from the same (filtered) signal.

    Parameters
    ----------
    y : np.ndarray
        The region, in pascals, after the Filter and correction factor.
    fs : float
        Sampling rate, in Hz.

    Returns
    -------
    levels : dict
        Keys as `region_levels`: ``peak``, ``pe``, ``rms``, ``dba``,
        ``max_pa``, ``min_pa``.
    '''
    max_pa = max(np.max(y), 0)
    min_pa = min(np.min(y), 0)
    half_ptp = (max_pa - min_pa) / 2
    return {
        'peak': util.patodb(half_ptp),
        'pe': util.patodb(half_ptp / np.sqrt(2)),
        'rms': util.patodb(util.rms(y)),
        'dba': dba(y, fs),
        'max_pa': max_pa,
        'min_pa': min_pa,
    }
