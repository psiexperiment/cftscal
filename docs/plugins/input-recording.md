# Input Recording

Input Recording isn't tied to a specific calibration procedure. It's a general-purpose tool for capturing and reviewing whatever's coming into one or more input channels simultaneously.

## Recording

Run CFTSCal and select the **Input Recording** workspace.

![The Input Recording workspace: the Settings panel at top left, the list of recordings and the Analysis table below it, and the waveform and spectrum plots on the right.](../images/input-recording/workspace.png)

*Two recordings plotted, one from each ear's microphone. The shaded band on the waveform is the selected region; the Analysis table and the spectrum below it are computed from that part of each recording only (see [Selecting a region](#selecting-a-region)).*

| Field | What it means |
| --- | --- |
| **Number of inputs** | How many channels to record at once, from 1 up to the total number your hardware exposes. One row appears below for each. |
| **Input** *(first dropdown on each row)* | Which physical input this row records. The dropdown doubles as the row's label, so there's no separate "Input 0"/"Input 1" text. Pick any channel here; the same physical channel can't be assigned to two rows at once. |
| **Sensor type and calibration** *(next one or two dropdowns)* | What kind of sensor is attached (see [Sensor types](#sensor-types) below), plus — for most types — a second dropdown picking which specific calibration to use. |
| **dB gain** *(last dropdown on each row)* | The preamp gain, in dB, currently applied to that row's channel. It must match the amplifier's actual setting. |
| **Target folder** | Which folder the recording is saved in. Shared across all rows, since they're saved together as a single recording. Leave it at *(auto create from generator)* to have a folder made for you, named after the **Generator** text (lowercased, with spaces and punctuation turned into hyphens). |
| **Generator** | Free text describing what produced the sound — e.g. *pistonphone*, *speaker 3*. It's saved with the recording exactly as you type it, but isn't remembered between sessions. |

### Sensor types

| Type | What it means |
| --- | --- |
| **Meas. Mic.**, **Generic Mic.**, **Input Amp.**, **Starship** | Loads a real, on-file calibration — pick the specific one from the second dropdown. This calibration converts the recorded voltage to Pascals. |
| **Unity** | A pass-through: records the raw voltage without converting it to Pascals. Since there's nothing to pick, the second dropdown is hidden. |
| **Nominal** | For a device with no measured calibration on file — e.g. going off a spec sheet value. Replaces the second dropdown with an **mV/Pa** field where you type the sensitivity directly; the recording is calibrated to Pascals using that value. Note the direction of the ratio: millivolts *generated per Pascal*, the convention used on most datasheets. If your datasheet gives Pa/V instead, take the reciprocal — see [Which way round is "sensitivity"?](../concepts.md#which-way-round-is-sensitivity) |

## Running the recording

To run the recording, click the *Record* button — this captures every active channel simultaneously, saved together as one recording. The button stays disabled until:

- every row has a sensor selected,
- no two rows point at the same physical input, and
- the **Generator** contains at least one letter or digit.

If that state is somehow reached anyway, clicking *Record* shows a warning explaining why rather than failing silently.

## Reviewing the results

Select one or more recordings in the *Recordings* list to plot them. The *Input Recording* plot shows the calibrated time-domain waveform; the region you select drives both the PSD plot and the *Analysis* table below.

**Recordings** (the list) shows every recording ever made for this workspace, with the following columns:

| Column | Meaning |
| --- | --- |
| Name | Which folder the recording is filed under (with *auto create*, named after the generator). |
| Date | When the recording was made. |
| Generator | Which stimulus/generator label was used. |
| Channel | Which input channel(s) were recorded — comma-separated if more than one. |
| Sensor | Which sensor was attached to each channel — comma-separated in the same order as Channel. |
| Gain | The preamp gain, in dB, that was in effect for each channel — comma-separated in the same order as Channel. |

A warning icon after a recording's name means it couldn't be read properly (hover for why); a sticky-note icon means it has a note. To add or change a note, right-click the recording and choose *Edit note…* — the note is saved inside the recording's folder, and hovering over the row shows it.

Each recording gets its own color, matching its highlight in the *Recordings* list. If a recording has more than one channel, all of its channels share that color but are distinguished from each other by line style (solid, dash, dot). The *Analysis* table groups its rows by recording for the same reason — each recording's channels appear as consecutive rows sharing one color swatch, with a *Channel* column distinguishing the rows within a group — alongside *Duration*, peak-equivalent SPL, and RMS dB SPL for whatever's inside the currently selected region.

### Selecting a region

- *Ctrl+drag* anywhere on the time plot to draw a new region from scratch — including inside the current region, so you can select a smaller part of it.
- *Drag an edge* of the existing region to resize it.
- *Drag the middle* of the region to move it without resizing.
- A plain drag (no Ctrl) pans the plot as usual.

Only the samples inside the selected region are used for the Analysis table and PSD.

### Choosing a filter

The *Filter* dropdown controls the filtering that gets applied to the signal before it's plotted and the level is computed. It only changes what's shown and measured; the saved recording is never altered.

| Mode | What it does |
| --- | --- | 
| **High-pass** *(default)* | Removes everything below a *Cutoff* frequency (20 Hz unless you change it). With the default *order* of 3 it matches the HP filter on a GRAS 12AQ power module: a 3-pole Butterworth, 3 dB down at the cutoff and falling 18 dB per octave below it. Use it to keep building rumble and handling noise out of the level. A higher order cuts off more steeply. Like the 12AQ's own filter, it shifts the phase of low frequencies slightly. |
| **Unfiltered** | No filtering at all — deliberately not labeled "dBZ", since that would imply a standardized flat response over a defined range, and this is simply whatever bandwidth the raw recording happens to have. |
| **dBA** | Standard A-weighting (IEC 61672-1) |
| **1/3 Octave** | A steep band-pass filter centered on a frequency you choose (*Center freq.*), with an adjustable *order* (higher orders roll off more sharply outside the band). | 

## Interpreting the levels

A single number describing a broadband signal's level always depends on how wide a band you're talking about, so it's worth knowing which quantity you're looking at:

- **Spectrum level** is the level in a 1 Hz-wide band — i.e. the level *per hertz*. This is what the PSD plot shows, at each frequency.
- **Band level** is the total level integrated over a band of width \(\Delta f\). This is what the Analysis table's RMS dB SPL reports, over whatever bandwidth the filter leaves in place.

They're related by:

$$ BL = SL + 10 \times log_{10}(\Delta f) $$

**Worked example.** A flat noise with a spectrum level of 56 dB spanning 4–64 kHz has a band level of \(56 + 10 \times log_{10}(60000) = 103.8\) dB SPL. Note the \(10 \times log_{10}\) — this is a power ratio, unlike the \(20 \times log_{10}\) used for amplitude ratios elsewhere.

!!! warning "An unfiltered level often measures your noise floor"
    Because band level grows with bandwidth, a *low* noise floor spread across a *wide* bandwidth can dominate the reported total. For a 4 kHz-wide signal band at a 65 dB spectrum level (a 101 dB SPL band level) sitting on a flat noise floor that extends out to 50 kHz:

    | Noise floor (spectrum level) | Reported total |
    | --- | --- |
    | 30 dB | 101.0 dB SPL |
    | 40 dB | 101.2 dB SPL |
    | 50 dB | 102.4 dB SPL |
    | 60 dB | 107.7 dB SPL |

    A noise floor 5 dB *below* the signal's spectrum level still adds 6.7 dB to the total, purely because it's 11 dB wider in bandwidth. This is why the region selection and the filter matter: restricting the analysis to the region and band you actually care about is what makes the reported level a measurement of your stimulus rather than of your noise floor. [Total level is easy to get wrong](../reference/signal-analysis.md#total-level-is-easy-to-get-wrong) has the full worked numbers.

## Exporting a calibrated WAV

Right-click any recording (in Input Recording, or any other workspace's list) and choose *Export as WAV…* to save it as a standard WAV file, calibrated so that *a sample value of `1.0` represents exactly `1.0` Pascal* of sound pressure (with the exception of recordings generated by unity, in which case the output is `1.0` represents exactly `1.0` Volts). If the recording has multiple channels, they're exported as a single interleaved multi-channel WAV file, all channels sharing the same sample rate. The file also carries the recording's metadata (per-channel sensitivity, sensor ID, calibration date, etc.) embedded directly in it, in a way that doesn't interfere with normal playback.
