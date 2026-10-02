# Starship Check

Unlike Starship Calibration, this isn't computing a fresh calibration — it's a quick verification that an *already-calibrated* starship still behaves as expected once it's actually inserted into an ear (or an ear-simulating coupler). It plays a chirp through the starship and records the response with the starship's own probe-tube microphone, letting you catch drift or a bad seal before you trust the data from a session.

## Why a bench calibration isn't enough

Inserting the probe into an ear changes the acoustics of the system. The ear canal presents a different acoustic load — largely a compliance, set by the enclosed volume — which shifts the resonances of the system, so the transfer function measured in a coupler on the bench is not the transfer function you have in the ear. The probe tube's own resonances move too, since they depend on the length of the acoustic cavity (see [Acoustic tube resonance](../reference/hardware-design.md#acoustic-tube-resonance)).

The practical rule is that **an in-ear measurement has to be repeated every time the probe is repositioned while it's in the ear** — it isn't a one-time measurement you can carry across a session. Running a check after each repositioning is what makes that rule cheap to follow. [Calibration Math](../reference/calibration-math.md#step-4-in-ear-speaker-calibration) has the equations.

## What you'll need

- A previously calibrated starship (see [Starship Calibration](starship.md)).
- The ear (or coupler) you want to check the starship in.
- An analog to digital converter and a digital to analog converter.

## Opening the workspace

Launch CFTSCal and select the Starship Check workspace.

## Settings

Each block of controls corresponds to one physical starship connection on your system, labeled with the connection's name (e.g. *Starship A*).

| Field | What it means |
| --- | --- |
| **Starship** (the drop-down beside the connection's name) | Which calibrated starship is plugged into this connection. Its current calibration from [Starship Calibration](starship.md) is used for the check, so the starship must have one. Starships are added in Starship Calibration, not here. |
| **dB gain** | The gain, in dB, set on the amplifier for the starship's microphone (20 or 40). |
| **Coupler** (second row) | A free-form label identifying the coupler or test fixture the starship is checked in (e.g. `C1`) — some labs instead use this to track a subject/ear per session (e.g. subject ID plus left/right). Click **+** to add a new one, or **−** to remove the selected label from the list. |
| **primary / secondary** (end of the second row) | Which output of the coupler this check is for. It's saved with the check as a label only; it doesn't change what is played. |
| **Target folder** (third row) | Which folder the check is saved in. Leave it on **(auto create from starship)** to have a folder named after the starship. To create a new folder, right-click in the *Calibrations* list. |

## Running a check

Click **Calibrate** under a connection once both a Starship and a Coupler have been selected.

## Reviewing the results

*In-Ear Sensitivity* plots the frequency response (in dB) for every check currently selected in the list below. Use **Selected frequency (Hz)** (or drag the horizontal line on the plot) to pick a frequency of interest.

*Δ In-Ear Sensitivity* tracks the sensitivity at that one selected frequency across every past check for the same starship, in date order — this is the fastest way to spot slow drift across sessions rather than comparing curves by eye.

Check **Show noise floor?** to overlay a dashed noise-floor trace on the sensitivity plot.

**Calibrations** (the list) groups checks by folder, same as every other workspace — by default that's one folder per starship, but a lab can reorganize checks into different folders (e.g. by study) via the right-click context menu, independent of which starship was actually checked. Columns:

| Column | Meaning |
| --- | --- |
| Starship | Which folder this check is filed under (organizes the list; see Device below if you've filed checks into folders that don't match the starship). |
| Device | The starship label recorded at check time, independent of which folder the check is filed under. Usually matches Starship — compare the two if you've reorganized checks into folders. |
| Coupler | Which coupler/fixture (or ear/subject label) was used. |
| Starship Channel | Which physical connection the starship was plugged into (e.g. Connection A/B). |
| Output | Whether the coupler's primary or secondary output was checked. |
| Gain | The preamp gain, in dB, applied to the starship's microphone. |

### Working with the list

- **Tick** a check to plot it; tick a starship to plot all of its checks.
- **Right-click** a check for more:
    - **Edit note…** attaches a free-text note (e.g. "left ear, re-inserted twice"). A check with a note shows a sticky-note icon after its name; hover over the row to read the note. Clear the text to remove it.
    - **Export as WAV…** and **Delete**.
- **Double-click** a check to rename it, and **drag** it onto a folder to move it. Right-click a folder (or an empty part of the list) to create, rename or delete folders.
- A check whose files can't be read is shown in red with a warning icon after its name. Hover over it, or right-click → **Show problem…**, to see what is wrong.

## Sanity-checking a check

- **Does the response look like previous checks of the same starship?** A sudden drop or shift usually means the probe moved, got blocked (e.g. by earwax), or the seal in the ear/coupler is leaking.
- **Is the Δ plot flat over time?** A slow, steady drift across many sessions is exactly what this workspace is meant to catch — it may be time to recalibrate the starship.

## Troubleshooting

!!! tip "Common pitfalls"
    - **Probe not fully inserted, or blocked by debris/earwax**, is the most common cause of an unexpected reading.
    - **Gain mismatch** between the Settings panel and the starship's actual preamp setting shifts the whole curve by a fixed, predictable amount.
    - **Testing against the wrong Starship entry** (e.g. after swapping probes) will look like a big, confusing jump in the Δ plot — double-check the selection before assuming the hardware drifted.
