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
| **Input** | Two dropdowns on one row. The first picks which physical input the amplifier's output is wired to. The second names the physical amplifier being calibrated — pick a previously-used one, or click **+** to add a new name (**-** removes the selected name from the list; no calibrations are deleted). |
| **Gain** | The amplifier's total gain, as currently set on the physical hardware — a single combined value (the gain dial times the x10/x1000 multiplier switch, if your amplifier has both). This describes your hardware's current setting — cftscal doesn't set it, only records it. |
| **Filter** … **Hz to** … **kHz** | The amplifier's configured high-pass (low cutoff, in Hz) and low-pass (high cutoff, in kHz) corner frequencies. |
| **60 Hz notch** | Whether the amplifier's 60 Hz notch filter (if it has one) is on or off. |
| **Target folder** | The folder the new calibration is saved in. Pick an existing folder, or leave it at *(auto create from amplifier)* to have a folder made for you, named after the amplifier picked in the **Input** row. To create, rename or delete folders, right-click in the *Calibrations* list. |

!!! warning "These fields don't control your hardware!"
    Gain, corner frequencies, and the 60 Hz filter setting are all read from what you enter here, not from the amplifier itself. Make sure they match the physical switches/dials on the amplifier — the frequency and filter settings aren't verified by the calibration, only recorded alongside it.

## Running the calibration

Click **Calibrate**. It stays greyed out until an amplifier is picked in the **Input** row. A new window opens — set **Calibrator amplitude** there (e.g. `100 µV`) to match your calibrator's actual rated output, then click **Start**. The run feeds that known signal through the amplifier and measures its output amplitude to compute the amplifier's actual gain.

## Reviewing the results

The plot shows the measured calibration signal waveform.

**Calibrations** (the list) shows every calibration ever run for this workspace. Tick a calibration to plot it. Right-click it to add a note, export it, or delete it; double-click to rename it, or drag it onto a folder to move it. A sticky-note icon after a name means the calibration has a note — hover over the row to read it. A warning icon after a name means it couldn't be read properly; hover for why. The columns are:

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
    - **Excess noise on the measurement is a grounding or shielding problem, not a cable-length one.** Signal cables resonate when their physical length reaches a quarter wavelength, but for anything in the audio range that length is hundreds of meters to hundreds of kilometers — a 3 m cable resonates at about 25 MHz. Cable resonance can therefore be ruled out entirely; look at grounding, shielding, and ground loops instead. See [Cable resonance and grounding](../reference/hardware-design.md#cable-resonance-and-grounding) for the numbers.
