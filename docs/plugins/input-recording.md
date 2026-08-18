# Input Recording

Input Recording isn't tied to a specific calibration procedure. It's a general-purpose tool for capturing and reviewing whatever's coming into one or more input channels simultaneously.

## Recording

Run CFTSCal and select the **Input Recording** workspace.

| Field | What it means |
| --- | --- |
| **Number of inputs** | How many channels to record at once, from 1 up to the total number your hardware exposes. |
| **Input** *(one row per active channel)* | A dropdown listing every available physical input — this doubles as the row's label, so there's no separate "Input 0"/"Input 1" text. Pick any channel here; the same physical channel can't be assigned to two active rows at once. |
| **Sensor** *(per row)* | A dropdown picking what kind of sensor is attached, plus (for most types) a second dropdown picking which specific one. |
| **Gain** *(per row)* | The preamp gain, in dB, currently applied to that row's channel. |
| **Target folder** | Organizes recordings into folders, same as every other workspace. Shared across all active channels, since they're saved together as a single recording. |
| **Generator** | A free-form label that can be used to record the details of the test stimulus. Click *+* to add a new one. |

### Sensor types

| Type | What it means |
| --- | --- |
| **Meas. Mic.**, **Generic Mic.**, **Input Amp.**, **Starship** | Loads a real, on-file calibration — pick the specific one from the second dropdown. This calibration converts the recorded voltage to Pascals. |
| **Unity** | A pass-through: records the raw voltage without converting it to Pascals. Since there's nothing to pick, the second dropdown is hidden. |
| **Nominal** | For a device with no measured calibration on file — e.g. going off a spec sheet value. Replaces the second dropdown with an **mV/Pa** field where you type the sensitivity directly; the recording is calibrated to Pascals using that value. |

## Running the recording

To run the recording, click the *Record* button — this captures every active channel simultaneously, saved together as one recording. The button stays disabled until every active channel has a sensor selected and no two channels point at the same physical input; if that state is somehow reached anyway, clicking *Record* shows a warning explaining why rather than failing silently.

## Reviewing the results

Select one or more recordings in the *Recordings* list to plot them. The *Input Recording* plot shows the calibrated time-domain waveform; the region you select drives both the PSD plot and the *Analysis* table below.

**Recordings** (the list) shows every recording ever made for this workspace, with the following columns:

| Column | Meaning |
| --- | --- |
| Name | Which folder the recording is filed under (usually the generator label). |
| Date | When the recording was made. |
| Generator | Which stimulus/generator label was used. |
| Channel | Which input channel(s) were recorded — comma-separated if more than one. |
| Sensor | Which sensor was attached to each channel — comma-separated in the same order as Channel. |
| Gain | The preamp gain, in dB, that was in effect for each channel — comma-separated in the same order as Channel. |

Each recording gets its own color, matching its highlight in the *Recordings* list. If a recording has more than one channel, all of its channels share that color but are distinguished from each other by line style (solid, dash, dot). The *Analysis* table groups its rows by recording for the same reason — each recording's channels appear as consecutive rows sharing one color swatch, with a *Channel* column distinguishing the rows within a group — alongside *Duration*, peak-equivalent SPL, and RMS dB SPL for whatever's inside the currently selected region.

### Selecting a region

- *Ctrl+drag* anywhere on the time plot to draw a new region from scratch.
- *Drag an edge* of the existing region to resize it.
- *Drag the middle* of the region to move it without resizing.
- A plain drag (no Ctrl) pans the plot as usual.

Only the samples inside the selected region are used for the Analysis table and PSD.

### Choosing a filter

The *Filter* dropdown controls the filtering that gets applied to the signal before it's plotted and the level is computed.

| Mode | What it does |
| --- | --- | 
| **Unfiltered** | No filtering — deliberately not labeled "dBZ", since that would imply a standardized flat response over a defined range, and this is simply whatever bandwidth the raw recording happens to have. |
| **dBA** | Standard A-weighting (IEC 61672-1) |
| **1/3 Octave** | A steep band-pass filter centered on a frequency you choose (*Center freq.*), with an adjustable *order* (higher orders roll off more sharply outside the band). | 

## Exporting a calibrated WAV

Right-click any recording (in Input Recording, or any other workspace's list) and choose *Export as WAV…* to save it as a standard WAV file, calibrated so that *a sample value of `1.0` represents exactly `1.0` Pascal* of sound pressure (with the exception of recordings generated by unity, in which case the output is `1.0` represents exactly `1.0` Volts). If the recording has multiple channels, they're exported as a single interleaved multi-channel WAV file, all channels sharing the same sample rate. The file also carries the recording's metadata (per-channel sensitivity, sensor ID, calibration date, etc.) embedded directly in it, in a way that doesn't interfere with normal playback.
