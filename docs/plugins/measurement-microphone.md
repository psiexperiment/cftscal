# Measurement Microphone Calibration

This calculates the sensitivity of the measurement microphone in units of V<sub>rms</sub>/Pa using a pistonphone.

This is the first link in the calibration chain — every other calibration in cftscal inherits its accuracy from this one (see [Calibration Concepts](../concepts.md#the-calibration-chain)). A measurement microphone is assumed to have a flat frequency response, so the result is a single number rather than a curve.

## What you'll need

- A pistonphone (with good batteries or dedicated power supply).
- The measurement microphone and its preamp.
- An analog to digital converter (such as that on a soundcard or NI multifunction DAQ).

## Opening the workspace

Launch CFTSCal and select Measurement Microphone Calibration workspace.

## Settings

| Field | What it means |
| --- | --- |
| **Pistonphone** | A free-form label for identifying the pistonphone you used (e.g., product ID, serial number, asset tag, etc.). This is useful if you have more than one so you can trace a calibration back to the specific calibrator used.
| **Pistonphone frequency / level** | Must match the pistonphone's actual rated output (e.g. `1000` Hz, `114` dB SPL). These values are used by cftscal to calculate the sensitivity of the microphone.
| **Input Channel** | Which physical input the microphone is wired to. |
| **Target folder** | Organizes calibrations into folders (e.g. by lab, by study). To create a new target folder, use the right-click context menu under the *Calibrations* dock item.
| **Sensor ID** | A free-form label for identifying the microphone you used (e.g., product ID, serial number, asset tag, etc.). This is separate from the input channel since the same channel might have different microphones connected to it over time. Click + to add a new one to the drop-down list. Whenever adding a new Sensor ID, be sure to select the *Set Defaults* option under the *Workspace* menu so that this addition to the list persists across sessions.
| **Gain** | The preamp gain, in dB, currently applied to this channel. |

!!! warning "The pistonphone frequency, pistonphone level, and gain fields don't control your hardware!"
    You are responsible for verifying that these values match what is set on the hardware since cftsfcal does not have a way of setting these values or reading them. If incorrect values are entered, the calibration will not be accurate.

## Running the calibration

To run the calibration, click the *Calibrate* button. The only setting that will be available for you to modify is the *Sample Duration* which adjusts the duration of the recording used to calculate the sensitivity of the microphone. To change the default value of this parameter, use the *Configuration -> Preferences -> Set Default* option in the menu.

Click *Start* to run the calibration.

## How the sensitivity is computed

The pistonphone produces a known sound pressure, so the microphone's sensitivity is just the measured voltage divided by that pressure:

$$ S_{cal} = \frac{V_{cal}}{O_{pistonphone}} $$

where the pistonphone's rated level in dB SPL is first converted to Pascals:

$$ O = 10^{\frac{O_{dBSPL}}{20}} \times 20 \times 10^{-6} $$

A 114 dB SPL pistonphone therefore produces \(10^{114/20} \times 20 \times 10^{-6} \approx 10\) Pa. If the microphone reads 0.1 V<sub>rms</sub> against it, its sensitivity is 0.01 V/Pa — reported as `10.00 mV/Pa`, or `20.00 dB(mV/Pa)`. See [Calibration Math](../reference/calibration-math.md#step-1-measurement-microphone-sensitivity) for the full derivation and for how this feeds every downstream calibration.

cftscal actually computes the microphone voltage three different ways, and saves all three in the calibration's `microphone_sensitivity.json`:

| Value | How the voltage is measured |
| --- | --- |
| **overall** | Broadband RMS of the whole recording (after detrending). This is the value shown in the **Sens** and **Sens (dB)** columns. |
| **nominal** | Tone power at exactly the *Pistonphone frequency* you entered. |
| **peak** | Tone power at the largest peak found within ±10% of the frequency you entered — i.e. at the pistonphone's *real* frequency rather than its rated one. |

Comparing these three is a useful diagnostic. They should agree closely. *Overall* being noticeably higher than *peak* means the recording contains energy that isn't the pistonphone tone (a noisy channel, hum, or a poorly seated pistonphone). *Nominal* differing from *peak* means the pistonphone isn't running at quite the frequency you told cftscal it was.

!!! note "This is the one calibration that uses a flattop window"
    Because the pistonphone generates a single tone, cftscal measures its tone power with a flattop window rather than the Hamming/Hann window appropriate to broadband measurements. A flattop window reads a tone's amplitude correctly even when the tone doesn't land exactly on an FFT bin center, which is exactly what matters when the whole measurement is one peak's height. See [Choosing a window](../reference/signal-analysis.md#choosing-a-window) for the trade-off involved.

## Reviewing the results

*Signal view (time)* shows the measured microphone voltage and *Signal view (PSD)* shows the measured microphone voltage in dB re 1 Vrms. With the pistonphone seated and running correctly, you should see a clean, sharp peak exactly at the pistonphone's rated frequency (e.g. 1 kHz). That peak is the tone generated by the pistonphone. Everything else is noise floor. If you don't see an obvious peak there, something's wrong (see [Troubleshooting](#troubleshooting) below).

The PSD plot draws **two traces**, labeled in its legend: one computed with a Hann window (black) and one with a flattop window (red). They're two views of the same recording, and the difference between them is the windowing trade-off in action — the flattop trace gets the peak's *height* right but spreads it over a wider span of frequencies, while the Hann trace resolves frequency more sharply but can under-read the peak's amplitude if the tone falls between FFT bins. For judging the peak's level, read the flattop trace; for judging how clean and narrow the tone is, read the Hann trace. See [Choosing a window](../reference/signal-analysis.md#choosing-a-window) for details.

**Microphone Calibrations** (the list) shows every calibration ever run for this workspace, with the following columns:

| Column | Meaning |
| --- | --- |
| Name | Which physical microphone was calibrated (same value as Sensor ID — this column groups/organizes the list). |
| Date | When the calibration was run. |
| Input | Which input channel was used. |
| Sensor ID | Which physical microphone was used. |
| Gain | The preamp gain that was in effect. |
| Sens | Computed sensitivity, in mV/Pa. |
| Sens (dB) | The same sensitivity, in dB re 1 mV/Pa. Typically more convenient for comparing units or spotting drift at a glance. |
| Pistonphone | Which pistonphone was used for this calibration. |

## Sanity-checking a calibration

A reasonable sensitivity value depends entirely on your specific microphone model (check its datasheet), but two things are always worth checking after every calibration:

- **Does the sensitivity look like previous calibrations of the same physical mic (same Sensor ID)?** A sudden large jump usually means something changed (e.g., a loose or bad connector, wrong gain setting, or a damaged microphone).
- **Is there a clean peak at the expected pistonphone frequency in the plot?** No peak, or a peak somewhere else, almost always means a setup problem (see below) rather than a real change in the microphone.
- **Is the measured sensitivity close to the nominal sensitivity?** The manufacturer will report the expected (nominal) sensitivity of the microphone. If it's very different, this suggests an issue with the calibration.

## Troubleshooting

!!! tip "Common pitfalls"
    - **Pistonphone not actually on, or not fully seated** on the microphone is the most common cause of calibration errors.
    - **Gain mismatch** between the Settings panel and the physical preamp produces a sensitivity that's off by a fixed, predictable factor (20 dB of gain mismatch, the sensitivity, in dB, will also be off by 20 dB).
    - **Wrong pistonphone frequency/level entered** resulting in the computed sensitivity being wrong even if the recording itself looks fine.
    - **Reusing a Sensor ID for a different physical microphone** breaks your ability to track a specific unit's sensitivity over time. Give each physical microphone its own ID (e.g., include both the part ID and the serial number, GRAS40 - SN 1321).
