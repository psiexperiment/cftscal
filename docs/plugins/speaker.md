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
| **Speaker** | A free-form label for identifying the speaker you calibrated (e.g., product ID, serial number, asset tag, etc.). Click + to add a new one to the drop-down list. |
| **Target folder** | Organizes calibrations into folders (e.g. by lab, by study). To create a new target folder, use the right-click context menu under the *Calibrations* dock item. |

!!! warning "The microphone gain field doesn't control your hardware!"
    You are responsible for verifying that this value matches what is set on the preamp, since cftscal has no way of setting or reading it. If it's wrong, the calibration will be wrong.

## Running the calibration

To run the calibration, click **Golay** or **Chirp** next to the speaker you want to calibrate. Both buttons stay disabled until a reference microphone and a speaker have both been selected.

- **Golay** plays a pair of complementary Golay-code sequences, several times each, and cross-correlates the recorded response against them. This averages out uncorrelated noise, so it's the more robust choice in a noisy environment — at the cost of taking longer.
- **Chirp** plays a single frequency sweep. It's much faster than Golay, but slightly more sensitive to background noise.

Either one measures the speaker's frequency response across a broad range in a single run, unlike the pistonphone tone used for measurement microphones.

## Reviewing the results

*Speaker Sensitivity* plots the frequency response (in dB re 1 V<sub>rms</sub>) of every calibration currently selected in the list below.

**Speaker Calibrations** (the list) shows every calibration ever run for this workspace, with the following columns:

| Column | Meaning |
| --- | --- |
| Name | Which physical speaker was calibrated. |
| Date | When the calibration was run. |
| Microphone | Which reference measurement microphone was used. |
| Method | Whether Golay or Chirp was used. |
| Max. Freq. | The highest frequency the calibration covers. |

## Sanity-checking a calibration

- **Does the response look like previous calibrations of the same speaker?** A sudden change usually means something changed physically (the speaker shifted position, a coupler seal broke, or the speaker itself is damaged).
- **Is the curve reasonably smooth?** Sharp notches or dropouts that don't match the speaker's datasheet usually point to a setup problem rather than a real property of the speaker.
- **Is Max. Freq. as high as you need for your experiments?** It's limited by both the speaker and the reference microphone's usable bandwidth.

## Troubleshooting

!!! tip "Common pitfalls"
    - **Wrong reference microphone selected**, or that microphone's own calibration is stale, propagates straight into the speaker's measured response.
    - **Gain mismatch** between the Settings panel and the physical preamp shifts the whole curve up or down by a fixed, predictable amount.
    - **Speaker not properly coupled or seated** (e.g. a loose coupler, or the speaker moved between calibration and use) is the most common cause of an odd-looking response.
