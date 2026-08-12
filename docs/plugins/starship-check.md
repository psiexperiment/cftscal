# Starship Check

Unlike Starship Calibration, this isn't computing a fresh calibration — it's a quick verification that an *already-calibrated* starship still behaves as expected once it's actually inserted into an ear (or an ear-simulating coupler). It plays a chirp through the starship and records the response with the starship's own probe-tube microphone, letting you catch drift or a bad seal before you trust the data from a session.

## What you'll need

- A previously calibrated starship (see [Starship Calibration](starship.md)).
- The ear (or coupler) you want to check the starship in.
- An analog to digital converter and a digital to analog converter.

## Opening the workspace

Launch CFTSCal and select the Starship Check workspace.

## Settings

Each row corresponds to one physical starship connection on your system.

| Field | What it means |
| --- | --- |
| **Starship** | Which calibrated starship is plugged into this connection. Click + to add a new one to the drop-down list. |
| **dB gain** | The preamp gain, in dB, currently applied to the starship's microphone. |
| **Coupler** | A free-form label identifying the coupler or test fixture the starship is checked in (e.g. `C1`) — some labs instead use this to track a subject/ear per session (e.g. subject ID plus left/right). Click + to add a new one. |
| **Output** | Whether this check is of the coupler's primary or secondary output. |
| **Target folder** | Organizes checks into folders, same as every other workspace. |

## Running a check

Click **Calibrate** next to a connection once both a Starship and a Coupler have been selected.

## Reviewing the results

*In-Ear Sensitivity* plots the frequency response (in dB) for every check currently selected in the list below. Use **Selected frequency (Hz)** (or drag the horizontal line on the plot) to pick a frequency of interest.

*Δ In-Ear Sensitivity* tracks the sensitivity at that one selected frequency across every past check for the same starship, in date order — this is the fastest way to spot slow drift across sessions rather than comparing curves by eye.

Check **Show noise floor?** to overlay a dashed noise-floor trace on the sensitivity plot.

**In-Ear Calibrations** (the list) groups checks by folder, same as every other workspace — by default that's one folder per starship, but a lab can reorganize checks into different folders (e.g. by study) via the right-click context menu, independent of which starship was actually checked. Columns:

| Column | Meaning |
| --- | --- |
| Starship | Which folder this check is filed under (organizes the list; see Device below if you've filed checks into folders that don't match the starship). |
| Device | The starship label recorded at check time, independent of which folder the check is filed under. Usually matches Starship — compare the two if you've reorganized checks into folders. |
| Coupler | Which coupler/fixture (or ear/subject label) was used. |
| Starship Channel | Which physical connection the starship was plugged into (e.g. Connection A/B). |
| Output | Whether the coupler's primary or secondary output was checked. |
| Gain | The preamp gain, in dB, applied to the starship's microphone. |

## Sanity-checking a check

- **Does the response look like previous checks of the same starship?** A sudden drop or shift usually means the probe moved, got blocked (e.g. by earwax), or the seal in the ear/coupler is leaking.
- **Is the Δ plot flat over time?** A slow, steady drift across many sessions is exactly what this workspace is meant to catch — it may be time to recalibrate the starship.

## Troubleshooting

!!! tip "Common pitfalls"
    - **Probe not fully inserted, or blocked by debris/earwax**, is the most common cause of an unexpected reading.
    - **Gain mismatch** between the Settings panel and the starship's actual preamp setting shifts the whole curve by a fixed, predictable amount.
    - **Testing against the wrong Starship entry** (e.g. after swapping probes) will look like a big, confusing jump in the Δ plot — double-check the selection before assuming the hardware drifted.
