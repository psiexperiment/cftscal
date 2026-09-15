# Speaker Calibration

This calculates the frequency response of a speaker, using a calibrated measurement microphone as the reference.

## What you'll need

- A calibrated measurement microphone (see [Measurement Microphone Calibration](measurement-microphone.md)) and its preamp.
- The speaker you're calibrating, positioned the same way it'll be used in an actual experiment.
- An analog to digital converter and a digital to analog converter (such as those on a soundcard or NI multifunction DAQ).

## Opening the workspace

Launch CFTSCal and select the Speaker Calibration workspace.

## Settings

| Field | What it means |
| --- | --- |
| **Microphone → Input** | Which physical input the reference measurement microphone is wired to. |
| **Microphone → Mic.** | Which calibrated measurement microphone to use as the reference (drawn from [Measurement Microphone Calibration](measurement-microphone.md)). |
| **Microphone → Gain** | The preamp gain, in dB, currently applied to that channel. |
| **Speaker → Output Channel** | Which physical output you're calibrating, if your system has more than one. |
| **Speaker → Speaker** | A free-form label for identifying the speaker connected to the selected output channel (e.g., product ID, serial number, asset tag, etc.). Click + to add a new one to the drop-down list. |
| **Target folder** | Organizes calibrations into folders (e.g. by lab, by study). To create a new target folder, use the right-click context menu under the *Calibrations* dock item. |

!!! warning "The microphone gain field doesn't control your hardware!"
    You are responsible for verifying that this value matches what is set on the preamp, since cftscal has no way of setting or reading it. If it's wrong, the calibration will be wrong.

## Running the calibration

To run the calibration, click **Golay** or **Chirp**. Both buttons stay disabled until a reference microphone and a speaker have both been selected for the currently-chosen output channel.

- **Golay** plays a pair of complementary Golay-code sequences, several times each, and cross-correlates the recorded response against them. This averages out uncorrelated noise, so it's the more robust choice in a noisy environment — at the cost of taking longer.
- **Chirp** plays a single frequency sweep. It's much faster than Golay, but slightly more sensitive to background noise.

Either one measures the speaker's frequency response across a broad range in a single run, unlike the pistonphone tone used for measurement microphones.

### Run parameters

The window that opens when you click Golay or Chirp exposes a few parameters. As with every calibration paradigm, use its *Configuration → Preferences → Set Default* menu to make a change stick.

| Parameter | What it does |
| --- | --- |
| **Smoothing window** (Golay; default 10) | Width, in frequency bins, of a Hamming-weighted moving average applied to the computed sensitivity *curve*. It trades fine frequency detail for a less noisy curve. Set it to `0` to disable smoothing and see the raw measurement. The chirp analysis also shows this field, but currently ignores it — a chirp result is always unsmoothed. |
| **Averages** (chirp; default 32) | How many sweeps to average. More averaging buys signal-to-noise ratio at the cost of time. |
| **FFT averages** / **Waveform averages** / **Discard** (Golay; defaults 4 / 2 / 2) | How many responses are averaged, and how many initial repetitions are thrown away so the measurement isn't contaminated by the system's startup transient. |
| **Number of bits for Golay** (Golay; default 14) | Length of the Golay code, as a power of two. Longer codes cover lower frequencies and average more noise away, but take longer. |
| **Output gain** (Golay; default −20) | Level, in dB relative to full scale, at which the stimulus is played. Lower it if the speaker distorts; raise it if the measurement is buried in noise. |

!!! tip "Smoothing is cosmetic; averaging is not"
    The smoothing window only post-processes the final curve — it can hide a real notch as easily as it hides noise. If a measurement looks noisy, increase the averaging (or the output gain) rather than the smoothing, and compare against a run with smoothing set to `0` before concluding anything about a feature in the curve.

## How the calibration is computed

The reference microphone's known sensitivity converts its recorded voltage into the sound pressure the speaker actually produced:

$$ O(f) = \frac{V_{cal}(f)}{S_{cal}} $$

Writing a quantity as a function of \(f\) just means it takes a different value at each frequency, with \(f\) in Hz.

Since the drive voltage was known, that gives the speaker's transfer function directly. [Calibration Math](../reference/calibration-math.md#step-2-speaker-output) works through the derivation and the dB forms.

## Reviewing the results

*Speaker Sensitivity* plots the frequency response (in dB re 1 V<sub>rms</sub>) of every calibration currently selected in the list below.

Concretely, the plotted value at each frequency is **the dB SPL the speaker produces when driven at 1 V<sub>rms</sub>** — so a higher curve means a more efficient speaker. That also makes it easy to read off the drive voltage for a target level:

$$ V_{DAC}(f) = 10^{\frac{O_{dBSPL} - O_{dBSPL\ at\ 1V}(f)}{20}} $$

**Worked example.** If the curve reads 100 dB SPL at some frequency and you want 80 dB SPL there, you need \(10^{(80-100)/20} = 0.1\) V<sub>rms</sub>. This is exactly the calculation psiexperiment performs when you request a level in an experiment. See [Generating a tone at a specific level](../reference/calibration-math.md#generating-a-tone-at-a-specific-level) for the general form and for how this relates to sensitivity expressed in V/Pa.

**Speaker Calibrations** (the list) shows every calibration ever run for this workspace, with the following columns:

| Column | Meaning |
| --- | --- |
| Name | Which physical speaker was calibrated (organizes the list; see Device below if you've filed calibrations into folders that don't match the device). |
| Date | When the calibration was run. |
| Device | The speaker label recorded at calibration time, independent of which folder the calibration is filed under. Usually matches Name — compare the two if you've reorganized calibrations into folders. |
| Output | Which output channel was calibrated. |
| Microphone | Which reference measurement microphone was used. |
| Mic. Channel | Which input channel the reference microphone was wired to. |
| Gain | The reference microphone's preamp gain, in dB, that was in effect. |
| Method | Whether Golay or Chirp was used. |
| Max. Freq. | The highest frequency the calibration covers. |

## Sanity-checking a calibration

- **Does the response look like previous calibrations of the same speaker?** A sudden change usually means something changed physically (the speaker shifted position, a coupler seal broke, or the speaker itself is damaged).
- **Is the curve reasonably smooth?** Sharp notches or dropouts that don't match the speaker's datasheet usually point to a setup problem rather than a real property of the speaker.
- **Is Max. Freq. as high as you need for your experiments?** It's limited by both the speaker and the reference microphone's usable bandwidth.
- **Does the speaker reach the levels your experiment needs?** Read the curve at your frequencies of interest and work out the drive voltage required, then check it against the speaker's safe voltage limit — see [Maximum safe drive voltage](../reference/hardware-design.md#maximum-safe-drive-voltage). If the arithmetic says you'd have to exceed the speaker's rating, no amount of recalibration will help.

## Troubleshooting

!!! tip "Common pitfalls"
    - **Wrong reference microphone selected**, or that microphone's own calibration is stale, propagates straight into the speaker's measured response.
    - **Gain mismatch** between the Settings panel and the physical preamp shifts the whole curve up or down by a fixed, predictable amount.
    - **Speaker not properly coupled or seated** (e.g. a loose coupler, or the speaker moved between calibration and use) is the most common cause of an odd-looking response.
    - **Driving the speaker past its rated voltage** makes it distort rather than get louder, and the calibration will faithfully record the distorted response as though it were real. [Hardware Design](../reference/hardware-design.md) covers how to work out the safe limit, what maximum SPL to expect from a datasheet figure, and how to size a voltage divider if your DAC's full-scale output is higher than the speaker can take.
