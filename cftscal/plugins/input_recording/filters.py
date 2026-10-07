'''
Filters for Input Recording's plot and Analysis table.

Every filter can be run two ways:

* **Causal** ("analog emulation"): the way an analog filter -- a sound level
  meter's A-weighting, a GRAS 12AQ's high-pass -- would act on the signal,
  phase shift and all.
* **Zero-phase**: the same magnitude response with no phase shift, applied
  in the frequency domain (see `fft_filter`). Not `scipy.signal.sosfiltfilt`:
  running a filter forwards and then backwards applies its magnitude
  response twice, so a cutoff designed to be -3 dB comes out -6 dB and the
  slope doubles. Applying ``|H(f)|`` once instead keeps the cutoff, slope
  and every RMS level identical to the causal filter; only the phase
  differs.

A-weighting additionally comes in two forms: the bilinear-transform IIR
filter (`a_weighting_sos`), which falls short of the standard curve near
Nyquist, and the exact analog curve applied in the frequency domain
(`a_weighting_response`).
'''
import numpy as np
from scipy import fft, signal


#: Pole frequencies of the A-weighting curve, in Hz (IEC 61672-1).
A_WEIGHTING_POLES_HZ = (20.598997, 107.65265, 737.86223, 12194.217)


def a_weighting_zpk():
    '''
    The analog A-weighting filter as zeros, poles and gain.

    Returns
    -------
    zeros : np.ndarray
        Four zeros at 0 rad/s.
    poles : np.ndarray
        Six poles, in rad/s.
    gain : float
        Gain normalizing the response to 0 dB (gain 1) at 1 kHz, per the
        standard.
    '''
    f1, f2, f3, f4 = A_WEIGHTING_POLES_HZ
    zeros = np.zeros(4)
    poles = -2 * np.pi * np.array([f1, f1, f4, f4, f2, f3])
    _, h = signal.freqs_zpk(zeros, poles, 1, [2 * np.pi * 1000])
    return zeros, poles, 1 / abs(h[0])


def a_weighting_sos(fs):
    '''
    Digital A-weighting filter, as second-order sections.

    The analog A-weighting curve (`a_weighting_zpk`) converted to a digital
    filter with the bilinear transform. It is exact at low frequencies but
    falls increasingly short of the standard curve towards Nyquist (a known
    property of the bilinear transform): at 48 kHz it is 1.2 dB low at
    10 kHz and 6.4 dB low at 16 kHz; at 96 kHz, 0.3 and 1.1 dB. Use
    `a_weighting_response` for the exact curve.

    Parameters
    ----------
    fs : float
        Sampling rate, in Hz.

    Returns
    -------
    sos : np.ndarray
        Second-order sections, for a single pass (`filter_once`) -- not
        `scipy.signal.sosfiltfilt`, which would apply the weighting twice.
    '''
    z, p, k = signal.bilinear_zpk(*a_weighting_zpk(), fs)
    return signal.zpk2sos(z, p, k)


def a_weighting_response(f):
    '''
    The exact (analog) A-weighting response at frequencies `f`.

    Parameters
    ----------
    f : array_like
        Frequencies, in Hz.

    Returns
    -------
    h : np.ndarray
        Complex gain at each frequency: 0 dB at 1 kHz, with the analog
        filter's phase. Take ``abs(h)`` for the magnitude alone.
    '''
    _, h = signal.freqs_zpk(*a_weighting_zpk(), 2 * np.pi * np.asarray(f))
    return h


def filter_once(sos, y):
    '''
    Filter ``y`` in one forward pass, the way an analog filter would.

    Starts from the steady state for the first sample, so a DC offset
    doesn't show up as a step at t=0.
    '''
    zi = signal.sosfilt_zi(sos) * y[0]
    return signal.sosfilt(sos, y, zi=zi)[0]


def settling_samples(sos, tolerance=1e-6):
    '''
    How many samples the filter's impulse response takes to die away.

    Used as the padding for `fft_filter`, so the circular wrap-around of
    the FFT has died away before it reaches the signal.

    Parameters
    ----------
    sos : np.ndarray
        Second-order sections of a stable filter.
    tolerance : float
        Decay, relative to the start, counted as died away.

    Returns
    -------
    n : int
        Number of samples. Doubled from the decay of the slowest pole, as a
        margin for repeated poles (whose response decays more slowly than a
        single pole's).
    '''
    _, poles, _ = signal.sos2zpk(sos)
    radius = np.abs(poles).max() if len(poles) else 0
    if radius == 0:
        return 0
    return int(np.ceil(2 * np.log(tolerance) / np.log(radius)))


def fft_filter(y, fs, response, pad):
    '''
    Filter ``y`` by multiplying its spectrum by ``response(f)``.

    Multiplying spectra is circular convolution: whatever the filter does at
    the end of the signal wraps round into its start. ``y`` is therefore
    padded at both ends with its first and last values -- the same
    assumption `filter_once` makes, that the signal was steady before it
    started, so a DC offset doesn't become a step -- and the padding is
    trimmed off again afterwards.

    A complex ``response`` that isn't real at Nyquist (such as the analog
    A-weighting curve) gives a filter that is not strictly causal: a
    discrete-time filter can't both match an analog curve all the way to
    Nyquist and be causal. A small, slowly decaying response appears
    before an abrupt onset (for A-weighting, about 2% of the signal a
    sample before it, 0.3% 10 ms before).

    Parameters
    ----------
    y : np.ndarray
        Signal.
    fs : float
        Sampling rate, in Hz.
    response : callable
        Takes an array of frequencies in Hz and returns the gain at each:
        complex to apply phase as well as magnitude, real and non-negative
        for zero phase.
    pad : int
        Samples of padding at each end: at least as long as the filter's
        impulse response takes to die away (see `settling_samples`).

    Returns
    -------
    y_filtered : np.ndarray
        Same length as ``y``.
    '''
    n = len(y)
    if n == 0:
        return np.array(y, dtype=float)
    nfft = fft.next_fast_len(n + 2 * pad, real=True)
    # Any extra length the FFT needs goes on the end, as more padding --
    # rfft's zeros would put a step there.
    padded = np.pad(y, (pad, nfft - n - pad), mode='edge')
    spectrum = fft.rfft(padded)
    spectrum *= response(fft.rfftfreq(nfft, 1 / fs))
    return fft.irfft(spectrum, nfft)[pad:pad + n]


def sos_filter(sos, y, fs, zero_phase=False):
    '''
    Apply a digital filter, causally or with zero phase.

    Parameters
    ----------
    sos : np.ndarray
        Second-order sections.
    y : np.ndarray
        Signal.
    fs : float
        Sampling rate, in Hz.
    zero_phase : bool
        If False, filter causally (`filter_once`). If True, apply the
        filter's magnitude response, ``|H(f)|``, with no phase shift (see
        the module docstring for why not ``sosfiltfilt``).

    Returns
    -------
    y_filtered : np.ndarray
    '''
    if not zero_phase:
        return filter_once(sos, y)

    def response(f):
        return np.abs(signal.sosfreqz(sos, worN=f, fs=fs)[1])

    return fft_filter(y, fs, response, settling_samples(sos))


def a_weight(y, fs, zero_phase=False, exact=False):
    '''
    A-weight a signal.

    Parameters
    ----------
    y : np.ndarray
        Signal.
    fs : float
        Sampling rate, in Hz.
    zero_phase : bool
        If True, apply the magnitude of the weighting only; if False, its
        phase too, as a sound level meter would.
    exact : bool
        If True, apply the exact analog curve in the frequency domain
        (`a_weighting_response`). If False, use the bilinear-transform IIR
        filter (`a_weighting_sos`), which is cheaper but falls short of the
        curve near Nyquist.

    Returns
    -------
    y_weighted : np.ndarray
    '''
    sos = a_weighting_sos(fs)
    if not exact:
        return sos_filter(sos, y, fs, zero_phase)
    if zero_phase:
        response = lambda f: np.abs(a_weighting_response(f))
    else:
        response = a_weighting_response
    # The bilinear filter's low-frequency poles, which set how long the
    # response takes to die away, are the analog filter's.
    return fft_filter(y, fs, response, settling_samples(sos))
