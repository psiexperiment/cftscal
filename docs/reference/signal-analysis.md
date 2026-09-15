# Signal Analysis

Every calibration in cftscal comes down to measuring the frequency content of a
recording. This page covers the choices involved in doing that — mainly
windowing and spectrum estimation — plus a few related topics (spectrum vs. band
level, chirps, reproducible noise) that come up when you are interpreting a
measurement that did not turn out the way you expected.

## Choosing a window

Before taking an FFT, the recording is normally multiplied by a *window* — a
smooth envelope that tapers the ends toward zero. Windowing trades two kinds of
error against each other:

- **Spectral leakage.** Energy from one frequency smears into neighboring bins.
  A window with low sidelobes keeps a loud tone from burying a quiet one nearby.
- **Amplitude accuracy.** If a tone does not land exactly on an FFT bin center,
  the measured peak reads *low*. A window with a flat top reads the correct
  amplitude regardless of where the tone falls between bins.

Different windows sit at different points on that trade-off, which leads to a
simple rule for cftscal's calibrations:

!!! tip "The rule"
    **Use a Hamming window** as the general-purpose default for measuring a
    signal whose content you do not control — a broadband recording, noise, or
    anything of unknown composition.

    **Use a flattop window** for a single-tone measurement against a
    standard — specifically, measuring a calibration microphone's sensitivity
    with a pistonphone (e.g. 114 dB SPL at 1 kHz). Here you care only about
    getting that one peak's amplitude exactly right, and a flattop window is
    designed for precisely that.

    **Use no window at all** when the record contains a whole number of cycles
    of a stimulus you generated yourself — see [the next
    section](#windowing-is-not-always-the-right-answer).

The amplitude error from reading the tallest bin is called **scalloping loss**,
and it depends entirely on where the tone sits relative to the nearest bin
center. It is zero on a bin center and worst exactly halfway between two bins:

| Window | Tone on a bin center | Tone 1/2 bin off (worst case) | Tone 1/10 bin off |
| --- | --- | --- | --- |
| Boxcar (no window) | 0.000 dB | **−3.92 dB** | −0.14 dB |
| Hamming | 0.000 dB | −1.75 dB | −0.07 dB |
| Hann | 0.000 dB | −1.42 dB | −0.06 dB |
| Blackman | 0.000 dB | −1.10 dB | −0.04 dB |
| **Flattop** | 0.000 dB | **−0.01 dB** | +0.00 dB |

Two things to take from this. First, the worst case is not a rounding error:
reading an unwindowed tone off the wrong side of a bin costs nearly **4 dB**,
and even a Hamming window costs 1.75 dB. That is why a pistonphone measurement —
where the whole result is one peak's height, and you do not control the
pistonphone's exact frequency — uses a flattop window, which holds the error to
0.01 dB no matter where the tone falls.

Second, *if* your tone lands exactly on a bin center, every window gets the
amplitude right and the choice does not matter for amplitude at all. Which
brings us to the next point.

!!! note "Where these numbers come from"
    Measured by taking the largest FFT bin magnitude of a windowed complex
    exponential at a controlled sub-bin offset, normalized by the window's sum.
    The boxcar figure is the analytic scalloping loss
    \(20 \times log_{10}(2/\pi) = -3.92\) dB, and the rest agree with the
    standard published values for these windows.

## Windowing is not always the right answer

Applying a window is not automatically a good idea. The reason a window is
needed at all is that the FFT implicitly assumes the record repeats forever; if
the signal does not contain a whole number of cycles, the wrap-around point is a
discontinuity, and that discontinuity is what produces leakage. Tapering the
ends hides the discontinuity, but it also spreads each tone over more bins,
which reduces your ability to resolve two nearby frequencies.

If you control the stimulus, there is a better option: **choose frequencies that
fit a whole number of cycles into the record**, so there is no discontinuity to
hide. For a record of duration \(T\), coerce the desired frequency \(f\) to:

```python
coerced_f = np.round(duration * f) / duration
```

**Worked example.** In a 50 ms record at 100 kHz: a 500 Hz tone gives
\(0.05 \times 500 = 25\) cycles exactly — fine as-is. A tone one-fifth of an
octave below it, \(500/1.2 = 416.67\) Hz, gives 20.83 cycles — not an integer,
so it leaks. Rounding 20.83 to 21 cycles and dividing back out by the duration
gives 420 Hz, which fits exactly. That 3.3 Hz shift is usually irrelevant
acoustically, and it removes the leakage entirely (see the first column of the
table above).

This matters most for multi-tone stimuli (for example, the two primaries of a
DPOAE measurement), where leakage from one loud primary can otherwise obscure a
much quieter distortion product nearby.

!!! info "What cftscal actually does"
    The three cases in the rule above map cleanly onto cftscal's three kinds of
    calibration:

    - **Pistonphone** ([Measurement Microphone
      Calibration](../plugins/measurement-microphone.md)) — a single tone whose
      exact frequency cftscal does not control, so the tone power is measured
      with a **flattop** window. The PSD plot additionally shows both a Hann
      and a flattop trace so you can see the trade-off directly.
    - **Chirp and Golay** ([Speaker](../plugins/speaker.md),
      [Starship](../plugins/starship.md), [Generic
      Microphone](../plugins/generic-microphone.md)) — **no analysis window**,
      just linear detrending. The analysis epoch is an exact whole number of
      repetitions of a stimulus cftscal generated itself, so there is no
      wrap-around discontinuity to taper, and skipping the window preserves
      full frequency resolution. (Golay does not take a plain FFT at all; it
      cross-correlates the response against the known complementary code pair.)
    - The **Hamming window** in those paradigms is something different — a
      smoothing kernel convolved across the *resulting sensitivity curve*, not
      an FFT window on the signal. See [Run
      parameters](../plugins/speaker.md#run-parameters).

!!! note "Further reading"
    [The Scientist and Engineer's Guide to Digital Signal
    Processing, chapter 9](https://www.dspguide.com/ch9/1.htm) has a good,
    readable treatment of windowing and the DFT's spectral properties.

## Estimating the spectrum

In practice, use `psiaudio.util.psd`, `psd_df` and `psd_freq` rather than
writing this yourself — they handle detrending, windowing, scaling and waveform
averaging consistently.

!!! warning "`psd()` returns RMS amplitude, not power — use 20·log₁₀ on it"
    Despite the name, `psiaudio.util.psd` returns `np.abs(csd)`, where `csd`
    applies a scale factor of \(\frac{2}{n\sqrt{2}}\) to the `rfft`. The result
    is the **RMS amplitude in each bin, in volts** — so a 2 V-amplitude sine on
    a bin center comes back as 1.414, its RMS.

    Convert it with `util.db()` (i.e. \(20 \times log_{10}\)), which is what
    `Calibration.get_db()` does internally. Applying \(10 \times log_{10}\) to
    it, as you would to a true power quantity, gives an answer exactly half as
    many dB as it should be.

    Because the bins hold RMS amplitude, Parseval's relation takes the form
    \(\sqrt{\sum p_k^2} = \) the waveform's RMS — which is exactly the summation
    used in [Total level is easy to get
    wrong](#total-level-is-easy-to-get-wrong) below.

Two further details are easy to get wrong.

**Normalizing the window.** Every window removes energy from the signal, and the
correction depends on what you are measuring:

- For a **tone**, divide by the window's *mean* (`w / w.mean()`) — its coherent
  gain. A Hamming window averages 0.54, so without this a tone would read
  5.35 dB low. This is what psiaudio's `csd` does.
- For **broadband** content (noise, a noise floor), the mean is the wrong
  correction; you need the window's *RMS*, \(\sqrt{\overline{w^2}}\).

Using the mean-normalized result on broadband content therefore reads **high**,
by an amount that depends only on the window:

| Window | mean | RMS | Broadband error if normalized by mean |
| --- | --- | --- | --- |
| Boxcar | 1.000 | 1.000 | 0.00 dB |
| Hamming | 0.540 | 0.630 | +1.35 dB |
| Hann | 0.500 | 0.612 | +1.77 dB |
| Blackman | 0.420 | 0.552 | +2.37 dB |
| Flattop | 0.216 | 0.419 | **+5.77 dB** |

In cftscal this is not a live problem — the one place a window is applied is the
pistonphone measurement, which is a *tone*, so mean normalization is correct
there. But it does mean that if you reach for `util.psd(s, fs, window='flattop')`
on a noise recording, the level will come back nearly 6 dB high. Measure
broadband levels unwindowed, or apply the RMS correction yourself.

**`rfft`, not `fft`.** For a real-valued recording the negative-frequency half of
the spectrum is redundant. `np.fft.rfft` and its matching `np.fft.rfftfreq`
return just the useful half.

Finally, psiaudio's `csd` **detrends linearly by default** before transforming,
which removes any DC offset or slow drift in the recording. Without that, a DC
offset lands entirely in the first bin and a drift smears energy across the
lowest bins, either of which can masquerade as low-frequency signal.

## FFT size

The classic advice is to pad the record out to a power of two before taking the
FFT. That advice is largely obsolete with modern NumPy, which handles any length
that factors into small primes just as efficiently. What still hurts is a record
length that is *prime* (or has a large prime factor), which falls back to a much
slower algorithm.

Measured on one machine with NumPy 2.4 (`np.fft.fft`, complex output):

| Length | Kind | Time per FFT |
| --- | --- | --- |
| 50,000 | small prime factors | 1.18 ms |
| 65,536 | power of two | 1.33 ms |
| 49,999 | prime | 5.59 ms |
| 50,021 | prime | 5.34 ms |
| 65,537 | prime | 6.84 ms |

So padding a 50,000-sample record up to 65,536 samples makes it *slower*, not
faster — but padding an awkward prime-length record up to any nearby
small-factored length (a power of two being the easiest one to reach for) is
roughly a 4× win. In practice, pick a record duration that yields a round number
of samples and you will never hit the slow path.

## Spectrum level and band level

A single number describing the level of a broadband signal depends on how wide a
band you are talking about, so two different quantities get used:

- **Spectrum level (SL)** — the level in a 1 Hz-wide band, i.e. the level *per
  hertz*.
- **Band level (BL)** — the total level integrated over a band of width
  \(\Delta f\).

Starting from \(BL = 10 \times log\frac{I_{tot}}{I_{ref}}\) with
\(I_{tot} = I_{SL} \times \Delta f\), and applying the multiplication rule for
logarithms:

$$ BL = 10 \times log\frac{I_{SL} \times 1\,Hz}{I_{ref}} + 10 \times log\frac{\Delta f}{1\,Hz} $$

which simplifies to:

$$ BL = SL + 10 \times log_{10}(\Delta f) $$

**Worked example.** A noise with a flat spectrum level of 56 dB spanning
4–64 kHz has a bandwidth of 60,000 Hz, so its band level is
\(56 + 10 \times log_{10}(60000) = 103.78\) dB SPL. Verified numerically: summing
the actual per-bin powers across that band and converting back gives 103.78 dB.

Note the \(10 \times log_{10}\) — this is a *power* ratio, unlike the
\(20 \times log_{10}\) used for the amplitude ratios on the
[Calibration Math](calibration-math.md) page.

## Total level is easy to get wrong

To compute the overall level of a measured spectrum, sum the *powers* of the
individual bins and convert back at the end:

```python
power = (10 ** (power_db / 20.0)) * 20e-6   # per-bin pressure, Pa
total_db = 20 * np.log10(np.sum(power ** 2) ** 0.5 / 20e-6)
```

The non-obvious consequence is that **a low noise floor spread over a wide
bandwidth can dominate the total**, because it is being summed over many
thousands of bins. Consider a 4 kHz-wide band at a 65 dB spectrum level (a band
level of 101 dB SPL), sitting on a flat noise floor that extends from DC to
50 kHz:

| Noise floor (spectrum level) | Total level |
| --- | --- |
| 20 dB | 101.02 dB SPL |
| 30 dB | 101.04 dB SPL |
| 40 dB | 101.18 dB SPL |
| 50 dB | 102.37 dB SPL |
| 60 dB | 107.68 dB SPL |

The signal band is 4,000 bins wide; the noise floor is 46,000 bins wide. That
11 dB of extra bandwidth means a noise floor only 5 dB below the signal's
spectrum level still adds 6.7 dB to the total. This is why the
[Input Recording](../plugins/input-recording.md) workspace lets you restrict the
analysis to a selected region and apply a band-pass filter before computing a
level: an unfiltered "total level" over the full bandwidth is often measuring
your noise floor, not your stimulus.

## Synthesizing a signal with a target spectrum

The reverse of estimating a spectrum is building a waveform that *has* a chosen
spectrum — useful for generating a noise stimulus shaped to a specification
(e.g. a flat band between two frequencies sitting on a defined floor). Specify
the magnitude per frequency bin, assign random phase, and inverse-transform:

```python
power_db = np.full_like(frequency, 30.0)   # spectrum level, dB SPL per bin
power_db[mask] = 65.0                      # ... raised inside the band
power = 10 ** (power_db / 20.0) * 20e-6    # per-bin pressure, Pa

n = 2 * (len(frequency) - 1)               # number of output samples
mag = power * n / np.sqrt(2)               # scale for numpy's irfft
phase = rng.uniform(0, 2 * np.pi, len(mag))
waveform = np.fft.irfft(mag * np.exp(-1j * phase), n=n)
```

The random phase is what makes it noise rather than an impulse; the magnitude
spectrum alone does not determine the waveform.

!!! warning "Get the scaling factor right, then verify it"
    The \(n/\sqrt{2}\) factor is the part that is easy to get wrong, and an
    error here is a silent, frequency-independent level offset — exactly the
    kind of mistake that produces a stimulus a fixed 6 dB away from what you
    asked for. Always check a synthesized waveform by measuring its RMS level
    back and comparing against the level implied by the spectrum you specified:

    ```python
    rms = np.mean(waveform ** 2) ** 0.5
    measured = 20 * np.log10(rms / 20e-6)
    expected = 20 * np.log10(np.sum(power ** 2) ** 0.5 / 20e-6)
    ```

    With the scaling above these agree to better than 0.01 dB (verified over
    repeated random-phase draws).

!!! note "Bins 0 and Nyquist are a special case"
    `irfft` reconstructs each bin between DC and Nyquist from a conjugate
    *pair*, which is where the factor of 2 in the scaling comes from. The DC bin
    and — for an even-length transform — the Nyquist bin have no partner, so the
    scaling above overstates them by \(\sqrt{2}\). With a spectrum spread over
    thousands of bins the effect is unmeasurable (it does not move the total by
    0.001 dB in the example above), but if you want it exact, set
    `power[0] = power[-1] = 0` before synthesizing.

One incidental note, since both forms appear in older code: `np.real(csd *
np.conj(csd))` and `np.abs(csd) ** 2` both give power from a complex spectrum.
They are algebraically identical and agree to within floating-point rounding —
`np.abs` computes the magnitude via `hypot`, so the two can differ in the last
bit or two. Use whichever is clearer.

## Chirps and frequency ramps

A chirp sweeps frequency over time, which is what lets
[Speaker](../plugins/speaker.md),
[Starship](../plugins/starship.md) and
[Generic Microphone](../plugins/generic-microphone.md) calibrations cover a
broad frequency range in a single run rather than one tone at a time.

For an **exponential** (log-spaced) sweep from \(f_0\) to \(f_1\) over duration
\(T\), the frequency at time \(t\) is \(f(t) = f_0 k^t\) where:

$$ k = e^{\frac{ln(f_1/f_0)}{T}} $$

```python
def exp_ramp(f0, f1, t):
    k = np.exp(np.log(f1 / f0) / t[-1])
    return f0 * k ** t
```

An exponential sweep spends equal time per octave, which matches how acoustic
systems are usually characterized. A **linear** sweep spends equal time per Hz
instead, and spends most of its duration at high frequencies.

To turn an instantaneous-frequency array into a waveform, integrate the
frequency to get phase. Phase in radians is \(2 \pi\) times the integral of
frequency, so that is a cumulative sum divided by the sample rate, multiplied
by \(2 \pi\):

$$ \phi(t) = 2 \pi \int_{0}^{t} f(\tau)\,d\tau $$

```python
f = np.linspace(50, 200, int(fs))               # instantaneous frequency, Hz
waveform = np.sin(2 * np.pi * f.cumsum() / fs)
```

Two mistakes are easy to make here, and both are silent — the waveform still
looks like a plausible sweep, it just is not the sweep you asked for.

!!! warning "Don't drop the \(2 \pi\), and don't skip the integral"
    **Omitting the \(2 \pi\)** — `np.sin(f.cumsum() / fs)` — treats the
    frequency array as radians per second rather than Hz, so every frequency
    comes out a factor of \(2 \pi\) too low.

    **Using `np.sin(2 * np.pi * f * t)`** with a time-varying `f` skips the
    integration. For a linear sweep \(f(t) = f_0 + kt\), the correct phase is
    \(2 \pi (f_0 t + kt^2/2)\) but this gives \(2 \pi (f_0 t + kt^2)\) — so the
    instantaneous frequency ramps at \(f_0 + 2kt\), twice the intended sweep
    rate.

    Measured on a 1-second sweep specified as 50 → 200 Hz, recovering
    instantaneous frequency from the analytic signal:

    | Form | at t=0.25 s | at t=0.50 s | at t=0.75 s |
    | --- | --- | --- | --- |
    | Intended | 87.5 Hz | 125.0 Hz | 162.5 Hz |
    | `sin(2*pi*f.cumsum()/fs)` | 87.6 Hz | 125.0 Hz | 162.6 Hz |
    | `sin(f.cumsum()/fs)` | 13.9 Hz | 19.9 Hz | 26.0 Hz |
    | `sin(2*pi*f*t)` | 125.3 Hz | 200.0 Hz | 274.5 Hz |

    Only the first tracks the intended sweep. The second is low by exactly
    \(2 \pi\); the third reaches the target end frequency at the halfway point
    and overshoots from there.

## Reproducible filtered noise

A noise stimulus generated in real time arrives in chunks, and the chunk
boundaries are set by the hardware buffer — not by anything about the stimulus.
For a calibration to be repeatable, the waveform must come out identical
regardless of how it happened to be chunked. Two things are needed.

**A seeded random number generator produces the same sequence regardless of how
you slice it.** Drawing 5,000 samples twice gives the same values as drawing
3,330 + 3,330 + 3,340, so the unfiltered noise is already chunk-independent:

```python
rs = np.random.RandomState(seed=1)
a1 = rs.uniform(-1, 1, 5000)
a2 = rs.uniform(-1, 1, 5000)

rs = np.random.RandomState(seed=1)          # same seed
b1 = rs.uniform(-1, 1, 3330)
b2 = rs.uniform(-1, 1, 3330)
b3 = rs.uniform(-1, 1, 3340)

np.equal(np.concatenate((a1, a2)),
         np.concatenate((b1, b2, b3))).all()   # True
```

**Filter state must be carried across chunk boundaries.** An IIR filter's output
depends on its internal state, so filtering each chunk independently restarts
the filter every time and produces transients at every boundary. Initialize the
state with `lfilter_zi` and thread the returned state into the next call:

```python
zi = signal.lfilter_zi(b, a)
chunk1, zf = signal.lfilter(b, a, chunk1_in, zi=zi)
chunk2, zf = signal.lfilter(b, a, chunk2_in, zi=zf)   # carry state forward
```

With the state carried forward, chunked filtering is bit-for-bit identical to
filtering the whole waveform at once. Without it, it is not — verified both
ways.

!!! tip "Use second-order sections for steep filters"
    For narrow or high-order filters, design with `output='sos'` and filter with
    `sosfilt`/`sosfiltfilt` rather than the `b, a` polynomial form. The
    polynomial form becomes numerically unstable at higher orders and narrower
    relative bandwidths. cftscal's own 1/3-octave analysis filter in
    [Input Recording](../plugins/input-recording.md#choosing-a-filter) is built
    this way for exactly this reason.

## Equalizing a signal

A calibration tells you the system's frequency response, so in principle you can
pre-filter a stimulus by the inverse of that response and get a flat output.

!!! danger "Do not invert an impulse response directly"
    It is tempting to take the system's impulse response `ir` and filter by its
    reciprocal. Two forms of this are wrong, and both appear in old exploratory
    code:

    - `signal.lfilter(ir ** -1, 1, x)` takes the reciprocal of each *sample* of
      the impulse response. That is not the inverse of anything — inverting a
      filter means inverting its transfer function \(1/H(z)\), not its
      samples. Since an impulse response decays toward zero, `ir ** -1` also
      explodes to enormous values.
    - `signal.lfilter([1], ir, x)` *is* the algebraically correct inverse for an
      FIR `ir`, but it is an IIR filter that is unstable whenever `ir` has any
      zero outside the unit circle — which a real measured response generally
      does.

    Inversion is fragile for a deeper reason too: wherever the measured response
    is near zero — a notch, or anything outside the usable band — its inverse
    blows up, so the "correction" amplifies noise instead of fixing anything.

The robust approach, and the one psiaudio actually uses, is to design an FIR
filter in the *frequency* domain from the calibration, with the correction
explicitly bounded. That is
`InterpCalibration.make_eq_filter()` (`psiaudio/calibration.py`):

1. Take the per-frequency scale factors needed to hit a target level,
   `get_sf(freq, target_level)`, on a 1 Hz grid across the calibrated range.
2. Clip them with `apply_max_correction(sf, max_correction)` — default 30 dB,
   which limits the correction to within ±30 dB of its own mean, so no single
   frequency can be boosted arbitrarily.
3. Force the gain to **zero** at DC, below the lower edge, above the upper edge,
   and at Nyquist. This is the part that keeps the filter from trying to
   equalize frequencies the calibration says nothing about.
4. Build the filter with `signal.firwin2(ntaps, freq, gain, window='hann')` —
   1001 taps by default — and return it alongside a `lfilter_zi` initial state,
   so a stimulus generated in chunks stays continuous across buffer boundaries
   (the same concern as [Reproducible filtered
   noise](#reproducible-filtered-noise) above).

An FIR designed this way is unconditionally stable, and steps 2 and 3 are what
make it usable on a real measured response rather than a textbook one. This is
also why the **Max. Freq.** column in the calibration lists matters:
equalization is only meaningful over the range the calibration actually covers,
and outside it the filter is deliberately silent.
