# IR Sensor Calibration

Unlike the other workspaces, this isn't computing a sensitivity value — it's a diagnostic recording tool for checking that an infrared (IR) emitter/detector pair (used elsewhere in CFTS/ABTS to track things like an animal's position or nose-pokes) is producing a healthy analog signal.

## Opening the workspace

Launch CFTSCal and select the IR Sensor Calibration workspace.

## Recording

| Field | What it means |
| --- | --- |
| **Output Channel** | Which physical output drives the IR emitter. |
| **Generator** | A label for the physical IR emitter connected to this output. Click **+** to add a new one; **-** removes the selected one from the list. |
| **Input Channel** | Which physical input the IR detector is wired to. |
| **Target folder** | The folder the recording is saved in. Pick an existing folder, or leave it at *(auto create from input channel)* to have one made for you. Note the auto-created folder is named after the input's *hardware* name (e.g. `ai2`), not the label shown in the **Input Channel** dropdown (e.g. `Ch 2`). To create, rename or delete folders, right-click in the *Recordings* list. |
| **Sensor** | A label for the physical IR detector connected to this input. Click **+** to add a new one; **-** removes the selected one from the list. |

## Running the recording

Click **Record**. It stays greyed out until both a **Generator** and a **Sensor** are picked. A new window will open; once ready to acquire, click **Start**.

## Reviewing the results

*Input Recording* shows the detector's raw signal over time.

**Recordings** (the list) shows every recording ever made for this workspace. Tick a recording to plot it. Right-click it to export or delete it; double-click to rename it, or drag it onto a folder to move it. A warning icon after a name means it couldn't be read properly; hover for why. The columns are:

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
