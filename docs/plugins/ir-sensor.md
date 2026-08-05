# IR Sensor Calibration

Unlike the other workspaces, this isn't computing a sensitivity value — it's a diagnostic recording tool for checking that an infrared (IR) emitter/detector pair (used elsewhere in CFTS/ABTS to track things like an animal's position or nose-pokes) is producing a healthy analog signal.

## Opening the workspace

Launch CFTSCal and select the IR Sensor Calibration workspace.

## Recording

| Field | What it means |
| --- | --- |
| **Output Channel** | Which physical output drives the IR emitter. |
| **Generator** | A free-form label for the physical IR emitter connected to this output. Click + to add a new one. |
| **Input Channel** | Which physical input the IR detector is wired to. |
| **Sensor** | A free-form label for the physical IR detector connected to this input. Click + to add a new one. |
| **Target folder** | Organizes recordings into folders, same as every other workspace. |

## Running the recording

Click **Record**. A new window will open; once ready to acquire, click **Start**.

## Reviewing the results

*Input Recording* shows the detector's raw signal over time.

**Recordings** (the list) shows every recording ever made for this workspace, with the following columns:

| Column | Meaning |
| --- | --- |
| Input | Which input channel was recorded. |
| Date | When the recording was made. |
| Range | The signal's 5th-to-95th-percentile range (e.g. `-0.021 to 4.982`), in volts. Using a percentile range rather than the raw min/max keeps a single stray spike from making a healthy signal look wider than it really is. |

## Sanity-checking a recording

- **Is the Range a healthy swing?** It should track the detector's expected working range for your setup, not sit pinned near 0 (no signal) or the supply rails (saturated).
- **Does it look like previous recordings of the same input?** A shrinking range over time can mean dust or misalignment is gradually blocking the beam.

## Troubleshooting

!!! tip "Common pitfalls"
    - **Emitter and detector misaligned, or the beam path obstructed** produces a narrow or flat Range.
    - **Detector saturated** (Range pinned at one extreme) usually means the emitter is too bright or too close for this detector.
