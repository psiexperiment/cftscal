# Calibration Math

This page collects every equation behind the calibrations cftscal runs. You
don't need it to run a calibration, but it's the place to look when you want to
check cftscal's numbers against your own, or work out why a measured value came
out where it did.

## Conventions

Two conventions matter before any of the equations make sense, because getting
either one backwards flips a sign or inverts a ratio.

### Sensitivity is expressed in V/Pa

Throughout these pages, sensitivity is expressed in \(\frac{V}{Pa}\) — volts per
Pascal — which is the convention used throughout the technical literature and on
most manufacturer datasheets.

!!! warning "This is the inverse of the EPL CFTS convention"
    The legacy EPL cochlear function test suite expresses sensitivity as
    \(\frac{Pa}{V}\). If you are comparing cftscal's numbers against EPL's, or
    reading older lab notes, one of the two is the reciprocal of the other (or,
    in dB, the negative). See [Reading cftscal's reported
    numbers](#reading-cftscals-reported-numbers) below for what each field in
    the GUI actually holds.

The word "sensitivity" also means two different physical things depending on
which end of the chain you are at:

| Device | Sensitivity means | Units |
| --- | --- | --- |
| **Microphone** | The voltage the microphone generates in response to a given sound pressure. | \(\frac{V}{Pa}\) |
| **Speaker** | The sound pressure produced for a given drive voltage — or, equivalently, the drive voltage needed per Pascal of output. | \(\frac{Pa}{V}\) or \(\frac{V}{Pa}\) |

### Do the arithmetic in dB

Calibration measurements can involve very small numbers. A 20 µPa reference
pressure, a microphone output of a few hundred microvolts, and a power spectral
density value are all small enough that chaining several multiplications and
divisions together in linear units can run into the limits of floating-point
arithmetic.

!!! note "What the floating-point problem actually is"
    A computer stores a number as a fixed number of significant digits plus an
    exponent — roughly 16 significant decimal digits for the double-precision
    floats NumPy uses by default. The exponent handles the *scale* fine, so a
    value like \(20 \times 10^{-6}\) is not itself a problem. What degrades is
    everything beyond those 16 digits, in three ways that calibration
    arithmetic runs into:

    - **Rounding error compounds.** Each multiplication or division rounds its
      result to the nearest representable value. Chain enough of them together
      — microphone voltage, divided by sensitivity, squared into a power,
      divided by a reference — and those tiny individual errors accumulate.
    - **Subtracting two nearly-equal numbers destroys precision.** If two
      quantities agree in their first 14 digits, their difference retains only
      the 2 digits where they differed, and the rest is noise. This is called
      catastrophic cancellation, and it is the most damaging of the three.
    - **Summing values of wildly different magnitudes loses the small ones.**
      Adding a very small number to a very large one can change nothing at all,
      because the result rounds straight back to the large value. Summing power
      across thousands of spectral bins is exactly this pattern.

    Working in dB helps because it keeps every quantity in a narrow, well-
    conditioned range (tens to low hundreds) and replaces the long chains of
    multiplication and division with addition and subtraction, so there is far
    less opportunity for error to compound in the first place. It is a
    substantial improvement rather than a guarantee — dB arithmetic is still
    floating-point arithmetic, and a subtraction of two nearly-equal dB values
    can still cancel.

**This is why almost every equation below is given in both a linear and a dB
form, and why cftscal and psiaudio store sensitivity internally in dB.** Prefer
the dB form when you implement anything yourself.

### The flat-response assumption

A *measurement* microphone is assumed to have the same sensitivity at every
frequency, so a single number describes it. That assumption holds well for a
precision microphone — if you spend enough money on the microphone, it is
genuinely flat across its rated range.

It does **not** hold for a cheap microphone. Sometimes you only need to record
audio during an experiment and a precision microphone is overkill; an
inexpensive microphone's sensitivity will vary substantially as a function of
frequency, so it has to be described by a curve rather than a single number.
That is exactly the difference between the two microphone workspaces in cftscal:

- [Measurement Microphone Calibration](../plugins/measurement-microphone.md)
  produces a single flat sensitivity value (psiaudio's `FlatCalibration`).
- [Generic Microphone Calibration](../plugins/generic-microphone.md) produces
  sensitivity as a function of frequency (psiaudio's `InterpCalibration`).

## Symbols

| Symbol | Meaning | Units |
| --- | --- | --- |
| \(f\) | Frequency | Hz |
| \(O(f)\) | Acoustic output (sound pressure) | Pa |
| \(O_{dBSPL}\) | The same output, in dB SPL | dB re 20 µPa |
| \(S_{cal}\) | Sensitivity of the calibration (measurement) microphone | \(\frac{V}{Pa}\) |
| \(V_{cal}(f)\) | Voltage measured at the calibration microphone | \(V_{rms}\) |
| \(S_{exp}(f)\) | Sensitivity of the experiment microphone being calibrated | \(\frac{V}{Pa}\) |
| \(V_{exp}(f)\) | Voltage measured at the experiment microphone | \(V_{rms}\) |
| \(S_{PT}(f)\) | Sensitivity of a probe-tube (starship) microphone | \(\frac{V}{Pa}\) |
| \(V_{PT}(f)\) | Voltage measured at the probe-tube microphone | \(V_{rms}\) |
| \(S_{s}(f)\) | Speaker sensitivity, as drive voltage required per Pascal | \(\frac{V}{Pa}\) |
| \(V_{DAC}(f)\) | Voltage generated by the digital-to-analog converter | \(V_{rms}\) |

A subscript \(dB\) on any sensitivity (e.g. \(S_{PT_{dB}}\)) means
\(20 \times log_{10}\) of that value.

!!! note "Reading \(f\)"
    A quantity written as a function of frequency — \(S_{s}(f)\),
    \(V_{cal}(f)\) — is one that takes a different value at every frequency, as
    opposed to a single number like \(S_{cal}\). So read \(S_{s}(f)\) as simply
    "the speaker's sensitivity at this frequency".

    \(f\) is **ordinary frequency, in hertz**, which is what you handle
    everywhere in practice: cftscal's plot axes, the `frequency` column of a
    saved `chirp_sens.csv` or `golay_sens.csv`, and psiaudio's `frequency`
    arguments are all in Hz.

    Much of the acoustics literature states these same relationships in terms
    of **angular frequency** \(\omega\), in radians per second, where
    \(\omega = 2 \pi f\). The two notations describe identical quantities; only
    the label on the axis differs. Nothing on this page needs the \(2 \pi\),
    because frequency appears here purely as the argument identifying *which*
    frequency a quantity is evaluated at. The factor does matter once you
    compute a phase from a frequency — see [Chirps and frequency
    ramps](signal-analysis.md#chirps-and-frequency-ramps).

## Step 1: Measurement microphone sensitivity

The chain starts with a physical standard: a pistonphone, which generates a
precise, stable sound pressure at a known frequency and level (e.g. 114 dB SPL
at 1 kHz). Record the microphone's voltage while the pistonphone is running, and
its sensitivity follows directly from the known pressure:

$$ S_{cal} = \frac{V_{cal}}{O_{pistonphone}} $$

where the pistonphone's rated level in dB SPL is converted to Pascals using
[the dB SPL conversions](#db-spl-and-pascals) below. This is what
[Measurement Microphone Calibration](../plugins/measurement-microphone.md)
computes.

!!! tip "Use a flattop window for this one measurement"
    Because the pistonphone is a *single tone*, this is the one calibration in
    cftscal where a flattop window is the right choice rather than a Hamming
    window. See [Choosing a window](signal-analysis.md#choosing-a-window).

## Step 2: Speaker output

Once you have a microphone with a known sensitivity, you can measure what a
speaker actually produces. Play a signal with a known RMS voltage,
\(V_{DAC}(f)\), and measure the voltage at the calibration microphone,
\(V_{cal}(f)\). The speaker's output in Pascals is:

$$ O(f) = \frac{V_{cal}(f)}{S_{cal}} $$

Or in dB:

$$ O_{dB}(f) = 20 \times log_{10}\left(\frac{V_{cal}(f)}{S_{cal}}\right) $$

$$ O_{dB}(f) = 20 \times log_{10}(V_{cal}(f)) - 20 \times log_{10}(S_{cal}) $$

Note how the division became a subtraction — that is the reason for working in
dB.

## Step 3: Experiment microphone sensitivity

To calibrate an *experiment* microphone (one that is not a precision measurement
microphone), record its voltage \(V_{exp}(f)\) **at the same time** as you
measure the speaker's output in step 2. Two microphones, co-located, recording
the same stimulus. Since you know what the speaker actually produced, the
experiment microphone's sensitivity follows:

$$ S_{exp}(f) = \frac{V_{exp}(f)}{O(f)} $$

Substituting \(O(f)\) from step 2:

$$ S_{exp}(f) = \frac{V_{exp}(f)}{\frac{V_{cal}(f)}{S_{cal}}} = \frac{V_{exp}(f) \times S_{cal}}{V_{cal}(f)} $$

The result is in \(\frac{V}{Pa}\). In dB, that is sensitivity as dB re 1 V/Pa:

$$ S_{exp_{dB}}(f) = 20 \times log_{10}(V_{exp}(f)) + 20 \times log_{10}(S_{cal}) - 20 \times log_{10}(V_{cal}(f)) $$

This is what
[Generic Microphone Calibration](../plugins/generic-microphone.md) computes, and
it is why that workspace requires the two microphones to be genuinely
co-located — any difference in distance or angle from the speaker shows up in
\(S_{exp}\) as if it were a property of the microphone.

## Step 4: In-ear speaker calibration

The acoustics of the system change as soon as the experiment microphone is
inserted into an ear: the ear canal presents a different acoustic load from a
coupler — largely a compliance, set by the enclosed volume — which shifts the
resonances of the system. **This means the calibration has to be redone every
time you reposition the experiment microphone while it is in an animal's ear.**
It is not a one-time measurement.

The quantity you need is the speaker transfer function \(S_{s}(f)\), in
\(\frac{V_{rms}}{Pa}\), which tells you the voltage required to drive the
speaker to a given level. Generate a stimulus through the DAC with known
frequency content \(V_{DAC}(f)\), and measure the result with the probe-tube
microphone whose sensitivity \(S_{PT}(f)\) you already know:

$$ O(f) = \frac{V_{PT}(f)}{S_{PT}(f)} $$

$$ S_{s}(f) = \frac{V_{DAC}(f)}{O(f)} = \frac{V_{DAC}(f) \times S_{PT}(f)}{V_{PT}(f)} $$

In dB:

$$ S_{s_{dB}}(f) = 20 \times log_{10}(V_{DAC}(f)) + 20 \times log_{10}(S_{PT}(f)) - 20 \times log_{10}(V_{PT}(f)) $$

$$ S_{s_{dB}}(f) = 20 \times log_{10}(V_{DAC}(f)) + S_{PT_{dB}}(f) - 20 \times log_{10}(V_{PT}(f)) $$

This is the calibration that [Starship Calibration](../plugins/starship.md)
establishes against a coupler, and that
[Starship Check](../plugins/starship-check.md) re-verifies in the ear.

## dB SPL and Pascals

dB SPL is referenced to 20 µPa, the nominal threshold of human hearing:

$$ O_{dBSPL} = 20 \times log_{10}\left(\frac{O}{20 \times 10^{-6}}\right) $$

Solving for pressure in Pascals:

$$ O = 10^{\frac{O_{dBSPL}}{20}} \times 20 \times 10^{-6} $$

The constant \(20 \times log_{10}(20 \times 10^{-6}) \approx -93.98\) dB appears
throughout the equations below; it is just this reference pressure expressed in
dB.

## Generating a tone at a specific level

Given the speaker sensitivity \(S_{s}(f)\), the voltage needed at the DAC to
produce an output of \(O\) Pascals is simply:

$$ V_{DAC}(f) = S_{s}(f) \times O $$

In practice you want to specify the level in dB SPL rather than Pascals.
Substituting the pressure conversion from above:

$$ V_{DAC}(f) = S_{s}(f) \times 10^{\frac{O_{dBSPL}}{20}} \times 20 \times 10^{-6} $$

Expressed in dB, the multiplications collapse into additions:

$$ V_{DAC_{dB}}(f) = 20 \times log_{10}(S_{s}(f)) + 20 \times log_{10}\left(10^{\frac{O_{dBSPL}}{20}}\right) + 20 \times log_{10}(20 \times 10^{-6}) $$

$$ V_{DAC_{dB}}(f) = S_{s_{dB}}(f) + O_{dBSPL} + 20 \times log_{10}(20 \times 10^{-6}) $$

That last form is the useful one, because it is written entirely in terms of
quantities the calibration already produced. To actually drive the DAC, convert
back to a linear voltage:

$$ V_{DAC}(f) = 10^{\frac{S_{s_{dB}}(f) + O_{dBSPL} + 20 \times log_{10}(20 \times 10^{-6})}{20}} $$

## Estimating the output at a given voltage

Solving the same relationship for level instead of voltage answers the reverse
question — "what will I get out if I drive the speaker at this voltage?":

$$ O_{dBSPL}(f) = 20 \times log_{10}(V_{DAC}) - S_{s_{dB}}(f) - 20 \times log_{10}(20 \times 10^{-6}) $$

Or, if you want the answer in Pascals:

$$ O(f) = \frac{V_{DAC}}{S_{s}(f)} $$

## Quick reference

These are the two calculations you will use most often, both written in terms of
the dB-domain sensitivities that cftscal stores.

**Voltage required at the DAC for a given dB SPL:**

$$ V_{DAC}(f) = 10^{\frac{S_{s_{dB}}(f) + O_{dBSPL} + 20 \times log_{10}(20 \times 10^{-6})}{20}} $$

**Microphone voltage converted to dB SPL:**

$$ O_{dBSPL} = 20 \times log_{10}(V_{PT}(f)) - S_{PT_{dB}}(f) - 20 \times log_{10}(20 \times 10^{-6}) $$

**Sensitivity from a level measured at 1 V<sub>rms</sub>.** If you know the
speaker produces \(O_{dBSPL}(f)\) when driven at 1 V<sub>rms</sub>:

$$ S(f) = \left(10^{\frac{O_{dBSPL}(f)}{20}} \times 20 \times 10^{-6}\right)^{-1} $$

$$ S_{dB}(f) = -\left[O_{dBSPL}(f) + 20 \times log_{10}(20 \times 10^{-6})\right] $$

**Referring a level measured at some other voltage back to 1 V<sub>rms</sub>.**
If you measured the speaker's output as \(O_{dBSPL,x}(f)\) while driving it at
\(x\) V<sub>rms</sub> (say 10 V<sub>rms</sub>) rather than 1 V<sub>rms</sub>,
the level referred to a 1 V<sub>rms</sub> drive is:

$$ O_{dBSPL,1V}(f) = O_{dBSPL,x}(f) - 20 \times log_{10}(x) $$

So a measurement of 120 dB SPL at 10 V<sub>rms</sub> corresponds to 100 dB SPL
at 1 V<sub>rms</sub>. This is exactly the correction psiaudio's calibration
constructors apply through their `vrms=` argument (`sensitivity = level -
db(vrms)`), and the same one used by the attenuation calculation in the legacy
`neurogen` package.

!!! warning "This rescaling applies to the *level*, not to a V/Pa sensitivity"
    It is easy to state this as "converting a sensitivity measured at \(x\)
    V<sub>rms</sub> to one at 1 V<sub>rms</sub>", but that phrasing is wrong for
    the \(\frac{V}{Pa}\) sensitivity used elsewhere on this page. For a linear
    system, \(S_{s} = x / O\) comes out the *same* no matter what \(x\) you
    drove at — doubling the drive doubles the output, so the ratio is
    unchanged, and subtracting \(20 \times log_{10}(x)\) from it would be an
    error.

    The quantity that genuinely needs the correction is the one psiaudio
    stores: **dB SPL produced at 1 V<sub>rms</sub>**, which is defined relative
    to a specific drive voltage and so has to be referred back to 1 V if you
    measured at anything else.

## Reading cftscal's reported numbers

The equations above use the \(\frac{V}{Pa}\) convention. cftscal and psiaudio
report things in the units that are most convenient per device type, so here is
the mapping.

| Where | What is actually stored/shown | Convention |
| --- | --- | --- |
| Measurement microphone list, **Sens** column | `mV/Pa` | \(\frac{V}{Pa}\), scaled to mV |
| Measurement microphone list, **Sens (dB)** column | `dB(mV/Pa)` | \(20 \times log_{10}\) of the mV/Pa value |
| Input Recording, **Nominal** sensor's mV/Pa field | `mV/Pa` | same as above; typed in by hand from a datasheet |
| Speaker / Starship / Generic Mic. sensitivity plots | The dB SPL produced at a 1 V<sub>rms</sub> drive, per frequency | dB SPL per V<sub>rms</sub> |
| psiaudio `FlatCalibration` / `InterpCalibration` internals | dB SPL at 1 V<sub>rms</sub> | dB SPL per V<sub>rms</sub> |

The plotted curves and psiaudio's internal `sensitivity` are therefore in the
\(\frac{Pa}{V}\) sense (how much output you get per volt), not the
\(\frac{V}{Pa}\) sense used in the equations above. The two are related by the
sensitivity-at-1-V<sub>rms</sub> equation in the previous section:

$$ O_{dBSPL}(f) = -S_{dB}(f) - 20 \times log_{10}(20 \times 10^{-6}) $$

**Worked example.** A speaker plot reads 100 dB SPL at 1 V<sub>rms</sub> for
some frequency. In Pascals that is
\(10^{100/20} \times 20 \times 10^{-6} = 2\) Pa, so
\(S_{s} = 1\,V / 2\,Pa = 0.5\ \frac{V}{Pa}\), i.e.
\(S_{s_{dB}} = -6.02\) dB re 1 V/Pa. Checking against the formula:
\(-[100 + (-93.98)] = -6.02\). To then generate 80 dB SPL at that frequency,
\(V_{DAC} = 0.5 \times 10^{80/20} \times 20 \times 10^{-6} = 0.1\) V<sub>rms</sub>.

!!! note "Gain is removed before any of this arithmetic runs"
    None of the equations above include preamp gain, because it has already been
    divided out by the time the analysis sees the recording. The **Gain** you
    enter in a Settings panel is passed through to the acquisition engine as the
    input channel's `gain` (in dB), and the engine scales the incoming samples
    down by it — in the sound-card engine, literally `data / dbi(total_gain)`.
    Every voltage in the equations above is therefore referred to the
    *microphone's own output*, before the preamp.

    That is why a gain value which does not match the physical hardware shifts a
    whole curve by exactly that many dB: the samples get divided by the wrong
    constant, and a constant scale error in volts is a constant offset in dB. A
    mismatch of 20 dB moves the reported sensitivity by 20 dB, no more and no
    less, at every frequency equally.
