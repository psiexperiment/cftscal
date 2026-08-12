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
| **Input** | Which physical input the amplifier's output is wired to. |
| **Sensor** | A label identifying the physical amplifier being calibrated, picked from previously-used amplifiers or added via +. |
| **Gain** | The amplifier's total gain, as currently set on the physical hardware — a single combined value (e.g. accounting for both a coarse multiplier switch and a finer gain dial, if your amplifier has both). This describes your hardware's current setting — cftscal doesn't set it, only records it. |
| **Filter → Hz to … kHz** | The amplifier's configured high-pass and low-pass corner frequencies. |
| **Filter → 60 Hz notch** | Whether the amplifier's 60 Hz notch filter (if it has one) is on or off. |
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
| Name | Which physical amplifier was calibrated (organizes the list; see Device below if you've filed calibrations into folders that don't match the amplifier). |
| Date | When the calibration was run. |
| Device | The amplifier label recorded at calibration time, independent of which folder the calibration is filed under. Usually matches Name — compare the two if you've reorganized calibrations into folders. |
| Input | Which input channel was used. |
| Gain | The amplifier's configured gain, as a multiplication factor (e.g. `50000 x`) — what you entered in Settings, not measured. |
| Meas. Gain | The measured gain, as a multiplication factor (e.g. `200.15 x`). |

## Sanity-checking a calibration

- **Is the measured gain (Meas. Gain) close to the configured gain (Gain)?** A large discrepancy usually means the Gain dropdown doesn't actually match the amplifier's physical switches/dial, or the calibrator amplitude entered doesn't match the calibrator's real output.
- **Does it look like previous calibrations of the same amplifier?** A sudden jump suggests a bad connection or a hardware fault.

## Troubleshooting

!!! tip "Common pitfalls"
    - **Wrong calibrator amplitude entered** produces a measured gain that's off by a fixed, predictable factor — double-check it against the calibrator's actual spec before every run.
    - **Gain dropdown not matching the amplifier's physical switches** won't make the calibration itself wrong (the measured gain is computed straight from the signal), but it will make the recorded configured gain misleading when you compare it later.
