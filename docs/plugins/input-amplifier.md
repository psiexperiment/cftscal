# Input Amplifier Calibration

This measures the actual gain of an input amplifier (a standalone signal preamp — e.g. for EEG/ABR electrodes — as distinct from a microphone preamp) against a known calibrator signal, and records its configured frequency-response and 60 Hz notch-filter settings alongside the measurement for reference.

## What you'll need

- A calibrator that outputs a precisely-known, small-amplitude signal (you'll tell cftscal what that amplitude is before running the calibration).
- The input amplifier you're calibrating, wired to a hardware input channel.
- An analog to digital converter.

## Opening the workspace

Launch CFTSCal and select the Input Amplifier Calibration workspace.

## Settings

| Field | What it means |
| --- | --- |
| **Sensor** | A label identifying the physical amplifier being calibrated, picked from previously-used amplifiers or added via +. |
| **Gain** and **×10 / ×1000** | The amplifier's two gain stages, as currently set on the physical hardware (e.g. a coarse ×10/×1000 switch and a finer gain dial). These describe your hardware's current settings — cftscal doesn't set them, only records them. |
| **Hz to … kHz** | The amplifier's configured high-pass and low-pass corner frequencies. |
| **60 Hz** | Whether the amplifier's 60 Hz notch filter (if it has one) is applied on its input or output stage. |
| **Target folder** | Organizes calibrations into folders. To create a new target folder, use the right-click context menu under the *Calibrations* dock item. |

!!! warning "These fields don't control your hardware!"
    Gain, corner frequencies, and the 60 Hz filter setting are all read from what you enter here, not from the amplifier itself. Make sure they match the physical switches/dials on the amplifier — the frequency and filter settings aren't verified by the calibration, only recorded alongside it.

## Running the calibration

Click **Calibrate**. Before it launches, you'll be asked for the calibrator's amplitude (e.g. `100 µV`) — this must match your calibrator's actual rated output. The run feeds that known signal through the amplifier and measures its output amplitude to compute the amplifier's actual gain.

## Reviewing the results

The plot shows the measured calibration signal waveform.

**Calibrations** (the list) shows every calibration ever run for this workspace, with the following columns:

| Column | Meaning |
| --- | --- |
| Name | Which physical amplifier was calibrated. |
| Date | When the calibration was run. |
| Meas. Gain | The measured gain, as a multiplication factor (e.g. `200.15 x`). |

## Sanity-checking a calibration

- **Is the measured gain close to the nominal gain** (Gain × ×10/×1000)? A large discrepancy usually means the Gain/×10/×1000 dropdowns don't actually match the amplifier's physical switches, or the calibrator amplitude entered doesn't match the calibrator's real output.
- **Does it look like previous calibrations of the same amplifier?** A sudden jump suggests a bad connection or a hardware fault.

## Troubleshooting

!!! tip "Common pitfalls"
    - **Wrong calibrator amplitude entered** produces a measured gain that's off by a fixed, predictable factor — double-check it against the calibrator's actual spec before every run.
    - **Gain/×10/×1000 dropdowns not matching the amplifier's physical switches** won't make the calibration itself wrong (the measured gain is computed straight from the signal), but it will make the recorded nominal gain misleading when you compare it later.
