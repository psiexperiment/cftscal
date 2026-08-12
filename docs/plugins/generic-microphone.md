# Generic Microphone Calibration

This calibrates a "generic" microphone — one that doesn't need to be a precision measurement mic (e.g., an inexpensive electret used just to record verification tones in a booth) — by playing a broadband stimulus through a speaker and comparing what it records against a co-located, already-calibrated measurement microphone.

## What you'll need

- A calibrated measurement microphone (see [Measurement Microphone Calibration](measurement-microphone.md)) and its preamp, positioned alongside the generic microphone.
- The generic microphone being calibrated.
- A speaker to play the stimulus.
- An analog to digital converter and a digital to analog converter.

## Opening the workspace

Launch CFTSCal and select the Generic Microphone Calibration workspace.

## Settings

| Field | What it means |
| --- | --- |
| **Test → Input** | Which input channel the generic microphone under test is wired to. |
| **Test → Device / Ref.** | A free-form label for identifying the generic microphone you're calibrating (e.g., product ID, serial number, asset tag, etc.). Click + to add a new one to the drop-down list. |
| **Test → Target folder** | Organizes calibrations into folders. |
| **Ref. → Input** | Which input channel the reference measurement microphone is wired to. |
| **Ref. → Device / Ref.** | Which calibrated measurement microphone to use as the reference, and its gain. To add a new reference microphone, use [Measurement Microphone Calibration](measurement-microphone.md) — it can't be added from here. |
| **Speaker** | Which output the speaker playing the stimulus is wired to. |

## Running the calibration

Click **Golay** or **Chirp** — both are always available once a generic microphone, a reference microphone, and a speaker output are selected.

- **Golay** plays a pair of complementary Golay-code sequences, several times each, and cross-correlates the recorded response against them. More robust to background noise, at the cost of taking longer.
- **Chirp** plays a single frequency sweep. Much faster, but somewhat more sensitive to noise.

## Reviewing the results

*Generic Microphone Sensitivity* plots the frequency response (in dB re 1 V<sub>rms</sub>) of every calibration currently selected in the list below.

**Generic Microphone Calibrations** (the list) shows every calibration ever run for this workspace, with the following columns:

| Column | Meaning |
| --- | --- |
| Name | Which generic microphone was calibrated (organizes the list; see Device below if you've filed calibrations into folders that don't match the device). |
| Date | When the calibration was run. |
| Device | The device label recorded at calibration time, independent of which folder the calibration is filed under. Usually matches Name — compare the two if you've reorganized calibrations into folders. |
| Input | Which input channel the generic microphone was wired to. |
| Gain | The generic microphone's preamp gain, in dB, that was in effect. |
| Microphone | Which reference measurement microphone was used. |
| Mic. Channel | Which input channel the reference microphone was wired to. |
| Speaker | Which speaker played the stimulus. |
| Speaker Channel | Which output channel the speaker was wired to. |
| Max. Freq. | The highest frequency the calibration covers. |

## Sanity-checking a calibration

- **Does the response look like previous calibrations of the same device?** A sudden change usually means the microphone moved relative to the speaker, or is damaged.
- **Are the two microphones actually co-located?** If the generic and reference mics are at noticeably different distances or angles from the speaker, the computed sensitivity will reflect that mismatch, not the generic mic's real response.
- **Is Max. Freq. as high as you need?** It's limited by both the speaker and the reference microphone's usable bandwidth.

## Troubleshooting

!!! tip "Common pitfalls"
    - **Reusing a device label for a different physical microphone** breaks your ability to track a specific unit over time — give each physical mic its own label.
    - **Wrong reference microphone selected**, or that microphone's own calibration is stale, propagates straight into the generic mic's measured response.
    - **Microphones not close together** is a common, easy-to-miss source of a distorted-looking response.
