# Starship Calibration

A *starship* is CFTS's probe assembly: an integrated probe-tube microphone plus two speaker drivers (primary and secondary), used to present sound very close to the eardrum and record what's happening there. This calibrates a starship against a physical coupler, using a calibrated measurement microphone as the reference.

## What you'll need

- A calibrated measurement microphone (see [Measurement Microphone Calibration](measurement-microphone.md)) and its preamp.
- The starship you're calibrating.
- A calibration coupler.
- An analog to digital converter and a digital to analog converter.

## Opening the workspace

Launch CFTSCal and select the Starship Calibration workspace.

## Settings

| Field | What it means |
| --- | --- |
| **Cal. Mic. → Input** | Which physical input the reference measurement microphone is wired to. |
| **Cal. Mic. → Sensor** | Which calibrated measurement microphone to use as the reference, and the preamp gain (dB) currently applied to that channel. |
| **Coupler** | Which physical coupler you're calibrating into. Recorded in the calibration's metadata; cftscal doesn't otherwise act on it. A free-form, user-managed list — starts empty, so click + to add your coupler labels (e.g. `tube-2mm`, `tube-0mm`, `3D-basic`) before first use. |
| **Starship → Connection** | Which physical starship connection you're calibrating into, if your system has more than one (e.g. Connection A/B). |
| **Starship → Starship** | Which starship is plugged into the selected connection. Click + to add a new one to the drop-down list. |
| **dB gain** | The preamp gain, in dB, currently applied to the starship's own microphone. |
| **Target folder** | Organizes calibrations into folders. To create a new target folder, use the right-click context menu under the *Calibrations* dock item. |

!!! note "Entries suffixed \"(EPL)\""
    Some starship names in the drop-down end in `(EPL)` — these are calibrations imported from the legacy EPL CFTS program. They're read-only reference entries; you can't run a new calibration into one directly.

## Running the calibration

To run the calibration, click **Golay** or **Chirp** next to the starship you want to calibrate. Both buttons stay disabled until a reference microphone and a starship have both been selected.

- **Golay** plays a pair of complementary Golay-code sequences, several times each, and cross-correlates the recorded response against them. More robust to background noise, at the cost of taking longer.
- **Chirp** plays a single frequency sweep. Much faster, but somewhat more sensitive to noise.

## Reviewing the results

*Starship Sensitivity* plots the frequency response (in dB re 1 V<sub>rms</sub>) of every calibration currently selected in the list below.

**Starship Calibrations** (the list) shows every calibration ever run for this workspace, with the following columns:

| Column | Meaning |
| --- | --- |
| Name | Which starship was calibrated (organizes the list; see Device below if you've filed calibrations into folders that don't match the device). |
| Device | The starship label recorded at calibration time, independent of which folder the calibration is filed under. Usually matches Name — compare the two if you've reorganized calibrations into folders. |
| Microphone | Which reference measurement microphone was used. |
| Mic. Channel | Which input channel the reference microphone was wired to. |
| Starship Channel | Which physical connection the starship was plugged into (e.g. Connection A/B). |
| Gain | The preamp gain, in dB, applied to the starship's own microphone. |
| Mic. Gain | The preamp gain, in dB, applied to the reference microphone's channel. |
| Coupler | Which coupler was selected at the time. |
| Stimulus | Whether Golay or Chirp was used. |

## Sanity-checking a calibration

- **Does the response look like previous calibrations of the same starship?** A sudden change usually means the probe tube shifted, got clogged with debris, or the coupler seal broke.
- **Is the curve reasonably smooth, without unexpected notches?** That usually points to a leak or obstruction rather than a real change in the starship.
- **Was the correct coupler selected?** Calibrating with the wrong coupler produces a response that won't match how the starship is actually used.

## Troubleshooting

!!! tip "Common pitfalls"
    - **Probe tube not fully seated in the coupler**, or partially blocked by debris, is the most common cause of a bad calibration.
    - **Gain mismatch** between the Settings panel and the physical starship preamp shifts the whole curve by a fixed, predictable amount.
    - **Wrong reference microphone selected**, or that microphone's own calibration is stale, propagates straight into the starship's measured response.
