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
| **Cal. Mic.** (first drop-down) | Which sound-card input the reference measurement microphone is plugged into. |
| **Cal. Mic.** (second drop-down) | Which calibration of the measurement microphone to use as the reference (made in [Measurement Microphone Calibration](measurement-microphone.md)). |
| **Cal. Mic.** → **dB gain** | The gain, in dB, set on the measurement microphone's amplifier. |
| **Coupler** | Which physical coupler you're calibrating into. Recorded in the calibration's metadata; cftscal doesn't otherwise act on it. A free-form, user-managed list — starts empty, so click **+** to add your coupler labels (e.g. `tube-2mm`, `tube-0mm`, `3D-basic`) before first use. **−** removes the selected label from the list. |
| **Starship** (first drop-down) | Which starship connection you're calibrating, if your system has more than one (e.g. Connection A/B). |
| **Starship** (second drop-down) | Which starship is plugged into that connection. Click **+** to add a new one to the drop-down list, or **−** to remove the selected name from the list (no calibrations are deleted). |
| **Starship** → **dB gain** | The gain, in dB, set on the amplifier for the starship's own microphone (20 or 40). |
| **Target folder** | Which folder the new calibration is saved in. Leave it on **(auto create from starship)** to have a folder named after the selected starship — Golay and Chirp both name it this way. To create a new folder, right-click in the *Calibrations* list. |

!!! note "Entries suffixed \"(EPL)\""
    Some starship names in the drop-down end in `(EPL)` — these are calibrations imported from the legacy EPL CFTS program. They're read-only reference entries; you can't run a new calibration into one directly. With one selected, Golay and Chirp stay disabled.

## Running the calibration

To run the calibration, click **Golay** or **Chirp** below the starship you want to calibrate. Both buttons stay disabled until a reference microphone calibration and a starship have both been selected.

- **Golay** plays a pair of complementary Golay-code sequences, several times each, and cross-correlates the recorded response against them. More robust to background noise, at the cost of taking longer.
- **Chirp** plays a single frequency sweep. Much faster, but somewhat more sensitive to noise.

Both runs expose a **Smoothing window** parameter (default 10) — the width, in frequency bins, of a Hamming-weighted moving average applied to the computed sensitivity *curve*. Set it to `0` to see the raw, unsmoothed measurement, which is worth doing before you conclude that a notch in the curve is or isn't real. See [Speaker Calibration](speaker.md#run-parameters) for the other run parameters, which are the same.

## How the calibration is computed

Two things are being established at once: the sensitivity of the starship's own probe-tube microphone (against the reference microphone), and the transfer function of its speaker drivers (measured with that probe-tube microphone).

Given a probe-tube microphone of known sensitivity \(S_{PT}(f)\) — a function of frequency \(f\) in Hz, meaning it takes a different value at each frequency — the sound pressure in the coupler is \(O(f) = V_{PT}(f) / S_{PT}(f)\), and the speaker transfer function follows:

$$ S_{s}(f) = \frac{V_{DAC}(f) \times S_{PT}(f)}{V_{PT}(f)} $$

[Calibration Math](../reference/calibration-math.md#step-4-in-ear-speaker-calibration) works through this in both linear and dB form.

!!! warning "A coupler calibration is not an in-ear calibration"
    This workspace calibrates the starship against a coupler on the bench. Inserting the probe into an ear *changes the acoustics of the system*: the ear canal presents a different acoustic load (largely a compliance, set by the enclosed volume), which shifts the system's resonances. So this calibration does not describe what the starship is doing once it's in an ear. An in-ear calibration has to be redone every time the probe is repositioned while it's in the ear; [Starship Check](starship-check.md) is the workspace for verifying the starship in the ear it's actually sitting in.

## Reviewing the results

*Starship Sensitivity* plots the frequency response (in dB re 1 V<sub>rms</sub>) of every calibration currently selected in the list below. As with the speaker workspace, the plotted value is the dB SPL produced at a 1 V<sub>rms</sub> drive, so you can read the voltage needed for a target level straight off the curve — see [Reading cftscal's reported numbers](../reference/calibration-math.md#reading-cftscals-reported-numbers).

**Calibrations** (the list) shows every calibration ever run for this workspace, with the following columns:

| Column | Meaning |
| --- | --- |
| Name | Which folder the calibration is filed under — by default, one folder per starship (see Device below if you've filed calibrations into folders that don't match the device). |
| Device | The starship label recorded at calibration time, independent of which folder the calibration is filed under. Usually matches Name — compare the two if you've reorganized calibrations into folders. |
| Microphone | Which reference measurement microphone was used. |
| Mic. Channel | Which input channel the reference microphone was wired to. |
| Starship Channel | Which physical connection the starship was plugged into (e.g. Connection A/B). |
| Gain | The preamp gain, in dB, applied to the starship's own microphone. |
| Mic. Gain | The preamp gain, in dB, applied to the reference microphone's channel. |
| Coupler | Which coupler was selected at the time. |
| Stimulus | Whether Golay or Chirp was used. |

### Working with the list

- **Tick** a calibration to plot it; tick a starship to plot all of its calibrations.
- **Right-click** a calibration for more:
    - **Edit note…** attaches a free-text note (e.g. "probe tube replaced"). A calibration with a note shows a sticky-note icon after its name; hover over the row to read the note. Clear the text to remove it.
    - **Set as current** chooses which of the starship's calibrations is used from now on, marked ★; without one, the most recent is used. **Clear current** goes back to the most recent.
    - **Export as WAV…** and **Delete**.
- **Double-click** a calibration to rename it, and **drag** it onto a folder to move it. Right-click a folder (or an empty part of the list) to create, rename or delete folders.
- A calibration whose files can't be read is shown in red with a warning icon after its name. Hover over it, or right-click → **Show problem…**, to see what is wrong.

## Sanity-checking a calibration

- **Does the response look like previous calibrations of the same starship?** A sudden change usually means the probe tube shifted, got clogged with debris, or the coupler seal broke.
- **Is the curve reasonably smooth, without unexpected notches?** That usually points to a leak or obstruction rather than a real change in the starship. Bear in mind that a probe tube has genuine acoustic resonances inside the measurement range — a 20 mm tube resonates at roughly 4 kHz with further modes above that (see [Acoustic tube resonance](../reference/hardware-design.md#acoustic-tube-resonance)) — so some structure is expected. What matters is whether it looks like *last time's* structure. A calibration measures and compensates for those resonances correctly, but only as long as the geometry doesn't change afterwards.
- **Was the correct coupler selected?** Calibrating with the wrong coupler produces a response that won't match how the starship is actually used.

## Troubleshooting

!!! tip "Common pitfalls"
    - **Probe tube not fully seated in the coupler**, or partially blocked by debris, is the most common cause of a bad calibration.
    - **Gain mismatch** between the Settings panel and the physical starship preamp shifts the whole curve by a fixed, predictable amount.
    - **Wrong reference microphone selected**, or that microphone's own calibration is stale, propagates straight into the starship's measured response.
