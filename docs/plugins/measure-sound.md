# Comparing results with Measure Sound

This page is for anyone who has measured sound levels with the lab's MATLAB program, **Measure Sound** (`measure_sound_v2022.m`), and wants to compare those results with [Input Recording](input-recording.md). The two programs measure the same things, but they don't always calculate them the same way, so some numbers come out differently. This page explains each difference and how to allow for it.

The short version:

- **dB SPL**, **peSPL** and **Max/Min** agree once you allow for Measure Sound's channel correction factors (see [Calibration](#calibration)), set the *Filter* to **Unfiltered** and select the same stretch of the recording.
- **dBA** is calculated differently, and the two programs' values can't be converted into each other for a general sound. See [dBA](#dba).
- **The band-pass filter** has the same band edges in both programs but a different shape, so band-passed levels differ. See [Band-pass filter](#band-pass-filter).

## Where things are

| In Measure Sound | In Input Recording |
| --- | --- |
| Load a B&K PULSE `.mat` file or a WAV file | Copy the `.mat` file into Input Recording's folder and tick it in the *Recordings* list (see [Reviewing PULSE `.mat` files](input-recording.md#reviewing-pulse-mat-files)). WAV files can't be opened. |
| Choose one channel to analyze | Every channel of a recording is plotted at once, with a column each in the *Analysis* table. |
| The analysis window is what's on screen: *Select*, *Advance*, *Rewind*, *Zoom in*, *Zoom out* | Zooming and panning the plot doesn't change what's measured. The measurement comes from the **selected region**, the shaded band you draw with *Ctrl+drag* (see [Selecting a region](input-recording.md#selecting-a-region)). As in Measure Sound, the plot opens on the first 90 seconds, but no region is selected until you draw one. |
| RMS (dB SPL) | **dB SPL** row. |
| dBA | **dBA** row (see [dBA](#dba)). |
| Max Pa, Min Pa | **Max (Pa)** and **Min (Pa)** rows. |
| Equivalent RMS (Pa and dB) | **peSPL** row (see [Peak levels](#peak-levels)). |
| *Peak-trough*: click a peak and a trough | There's no click-to-pick. Select a region that contains just the peak and trough you want; **peSPL** then uses the largest peak and deepest trough in that region. |
| "Filter waveform before analysis" | *Filter* set to **Band-pass** (see [Band-pass filter](#band-pass-filter)). |
| *FFT* button (spectrum plots in a new window) | The spectrum plot is always shown, below the waveform, for the selected region, in dB SPL. Measure Sound's spectrum plot is labeled "Power (dB)" and isn't scaled to dB SPL. |
| *Listen* | **Play region**. Measure Sound sends the pressure values to the sound card as they are, and the sound card plays values between −1 and +1, so anything beyond ±1 Pa (a tone of about 91 dB SPL) plays clipped. Play region uses a fixed scale with 20 Pa at full volume. |
| *Save* (a `.mat` file of the window) | **Export region…** (a calibrated WAV file in which 1.0 means 1 Pa). Like Measure Sound's *Save*, it saves the region after the filter. |

## Calibration

When Measure Sound opens a B&K PULSE `.mat` file, it takes the numbers in the file as pascals and multiplies channel 1 by 1.165 and channel 2 by 1.187: correction factors for the setup it was written for (+1.33 dB and +1.49 dB). WAV files are used as they are.

Input Recording takes the numbers in a PULSE file as pascals exactly as stored, without any correction factor. So for the same file, Measure Sound's levels are **1.33 dB higher on channel 1 and 1.49 dB higher on channel 2**, and its pressures (Max, Min, equivalent RMS in Pa) are 1.165 and 1.187 times larger.

Recordings made with Input Recording itself are converted to pascals using the calibration of the sensor chosen when recording (see [Sensor types](input-recording.md#sensor-types)).

## Filtering

By default Measure Sound doesn't filter, while Input Recording's default *Filter* is a 20 Hz **High-pass**, which keeps building rumble out of the level (see [Choosing a filter](input-recording.md#choosing-a-filter)). To compare with Measure Sound's default, set the *Filter* to **Unfiltered**. This can make a big difference: see the [worked example](#a-worked-example), where the high-pass changes dB SPL by 5 dB.

### Band-pass filter

Measure Sound's filter (on when "Filter waveform before analysis" is ticked) is a band-pass filter. With its default settings, a center frequency of 1000 Hz and a width of 4 octaves, it keeps 250 Hz to 4 kHz. Input Recording's **Band-pass** works out its band edges the same way, so 1000 Hz and 4 octaves gives the same 250 Hz to 4 kHz. The *shape* of the filter is different:

- Measure Sound uses a first-order Butterworth band-pass filter and applies it with MATLAB's `filtfilt`, which runs the filter forwards and then backwards. This keeps the waveform's timing, and applies the filter's attenuation twice, so the band edges are 6 dB down.
- Input Recording applies its filter's attenuation once, so the band edges are 3 dB down, and its default *order* is 4, which cuts off more steeply outside the band.

Because of this, no setting in Input Recording gives Measure Sound's filter exactly. Ticking **Zero-phase** doesn't change that: it changes the timing of the filtered waveform, not how much of each frequency gets through (see [Choosing a filter](input-recording.md#choosing-a-filter)). Here is how the filters compare for 1000 Hz and 4 octaves at a 48 kHz sampling rate:

| Frequency | 31.5 Hz | 125 Hz | 250 Hz | 500 Hz | 1 kHz | 2 kHz | 4 kHz | 8 kHz | 16 kHz |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Measure Sound's filter | −37.2 dB | −14.6 dB | −6.0 dB | −1.3 dB | 0 dB | −1.2 dB | −6.0 dB | −15.7 dB | −33.7 dB |
| Input Recording, order 1 (with or without *Zero-phase*) | −18.6 dB | −7.3 dB | −3.0 dB | −0.7 dB | 0 dB | −0.6 dB | −3.0 dB | −7.9 dB | −16.8 dB |
| Input Recording, order 4 (with or without *Zero-phase*) | −74.1 dB | −25.8 dB | −3.0 dB | 0 dB | 0 dB | 0 dB | −3.0 dB | −28.4 dB | −67.0 dB |

In practice:

- A sound well inside the band, such as a 1 kHz tone, reads the same in both.
- Broadband sound (noise) can read higher or lower. With order 1, Input Recording lets through more of every frequency, so it reads higher. With order 4, it lets through more near the band edges but much less outside the band, so the result depends on how much of the sound lies outside the band.

### Filtering more than once

In Measure Sound, with the filter ticked, the *Advance*, *Rewind*, *Zoom in* and *Zoom out* buttons each filter the waveform currently held in memory, which has already been filtered, and keep the result. Each press therefore adds one more pass of the filter: at the band edges of the default filter, 6 dB after opening the file, 12 dB after one press, 18 dB after two, and so on. *Select* and *Refresh* continue from the waveform as it is, and unticking the filter keeps it as it is; reopening the file starts again from the recording.

So a band-passed level from Measure Sound depends on how many of those buttons were pressed since the file was opened. Input Recording always filters the original recording, so its result doesn't depend on how you zoomed or moved around. To compare band-passed results, measure in Measure Sound straight after opening the file, using *Select* only.

### dBA

Both programs A-weight the sound, but in different ways.

**Input Recording** uses the A-weighting curve of the sound level meter standard, IEC 61672-1: for example −30.3 dB at 50 Hz, 0 dB at 1 kHz and +1.0 dB at 4 kHz. Its dBA is what a standard sound level meter would read.

**Measure Sound** calculates dBA from the recording's spectrum, in three steps (`estimateLevel` and `filterA` in `measure_sound_v2022.m`):

1. Its A-weighting function, `filterA`, returns the A-weighting curve as a *power* ratio.
2. It multiplies the recording's *amplitude* spectrum by that ratio, then squares the result to get power. The weighting is therefore applied in dB twice over: −60.5 dB at 50 Hz, 0 dB at 1 kHz, +1.9 dB at 4 kHz.
3. It adds a constant, `C = 42.8051`, chosen so that a 1 kHz tone reads the same in dB SPL and dBA. The constant needed for that depends on the sampling rate, and 42.8051 is the value for 131,072 Hz. At other rates, Measure Sound's dBA is offset by 10·log₁₀(sampling rate ÷ 131,072): −3.0 dB at 65,536 Hz (the rate of the lab's PULSE recordings), −4.4 dB at 48 kHz, −1.3 dB at 96 kHz and +1.7 dB at 192 kHz.

At 1 kHz, the weighting is 0 dB in both programs, so a 1 kHz tone gives the same dBA in both, apart from the sampling-rate offset. At other frequencies they differ. For pure tones at 94 dB SPL:

| Tone | Input Recording dBA | Measure Sound dBA at 65,536 Hz | Measure Sound dBA at 48 kHz |
| --- | --- | --- | --- |
| 50 Hz | 63.7 | 30.5 | 29.1 |
| 125 Hz | 77.8 | 58.6 | 57.3 |
| 1 kHz | 94.0 | 91.0 | 89.6 |
| 4 kHz | 95.0 | 92.9 | 91.6 |
| 16 kHz | 87.3 | 77.6 | 76.2 |

The gap grows the further the sound's energy is from 1 kHz, so for a sound with energy at many frequencies there's no single number that converts one program's dBA into the other's. Compare dBA values only within one program. If you need Input Recording's dBA for a sound that was measured with Measure Sound, open the recording in Input Recording.

Two more differences:

- **Which A-weighting setting is closer to Measure Sound's method?** Measure Sound weights the spectrum, which is what Input Recording does when **Exact A-weighting** is ticked; unticked, Input Recording uses a digital filter that matches the standard curve closely below about 8 kHz. Either way, Input Recording applies the standard curve once.
- **Filtered recordings.** When Measure Sound's filter is ticked, its dBA is measured from the band-passed waveform. Input Recording's **dBA** row always starts from the unfiltered recording, whatever the *Filter* is set to.

## Peak levels

Measure Sound's "equivalent RMS" is the average size of the largest positive and largest negative pressure in the window, divided by √2. That's the level of a sine wave that swings as far as the recording does, which Input Recording calls **peSPL**. The two match whenever the region contains both a positive and a negative pressure, which is almost always.

In the rare case where the whole window is positive (or the whole window negative), Measure Sound counts the minimum (or maximum) as 0 Pa, while Input Recording uses the region's actual values.

Input Recording also reports **Peak SPL**, half the full swing without dividing by √2. It's 3 dB above peSPL.

## Getting numbers you can compare

To compare a measurement with one made in Measure Sound:

1. Set the *Filter* to **Unfiltered**, or, if you used Measure Sound's filter, **Band-pass** with the same center frequency and width, keeping the differences above in mind.
2. Draw the region over the same stretch of sound that Measure Sound's window covered.
3. Compare **dB SPL** with Measure Sound's RMS, and **peSPL** with its equivalent RMS. For a PULSE `.mat` file, take off Measure Sound's correction factor first: 1.33 dB for channel 1, 1.49 dB for channel 2.
4. Compare **dBA** only within one program (see [dBA](#dba)).

## A worked example

Here is one real recording, `iPad3 60 dB Calibrated PART 1kHz-1.mat` (a B&K PULSE file recorded at 65,536 Hz on 15 March 2011), measured in both programs. The numbers are for the left channel (*LeftEar*, channel 1) over the whole 11.8-second recording, with Input Recording's *Filter* set to **Unfiltered**.

| Measurement | Measure Sound | Input Recording | Difference |
| --- | --- | --- | --- |
| RMS level / **dB SPL** | 61.7285 dB SPL | 60.4019 dB SPL | 1.3266 dB: the channel 1 correction factor |
| Max-min equivalent RMS / **peSPL** | 73.0518 dB SPL | 71.7252 dB SPL | 1.3266 dB: the correction factor |
| Equivalent RMS level | 0.089871 Pa | 0.077142 Pa | ×1.165 |
| Max level / **Max (Pa)** | 0.12492 Pa | 0.10722 Pa | ×1.165 |
| Min level / **Min (Pa)** | −0.12928 Pa | −0.11097 Pa | ×1.165 |
| **dBA** | 34.4108 dBA | 41.03 dBA | 6.6 dB, see below |

Everything except dBA differs only by the correction factor. The dBA difference is the sum of the differences described in [dBA](#dba):

- the correction factor: Measure Sound 1.33 dB higher;
- the sampling-rate offset at 65,536 Hz: Measure Sound 3.01 dB lower;
- the weighting applied twice over, for this recording's spectrum: Measure Sound 4.97 dB lower.

Allowing for all three gives 41.06 dBA, within 0.03 dB of Input Recording.

This recording also shows why the *Filter* setting matters. Despite its name, almost all of its sound is below 20 Hz (it peaks at about 11 Hz), with very little at 1 kHz. With Input Recording's default 20 Hz **High-pass** filter, dB SPL is 55.2 rather than 60.4, because the high-pass removes that low-frequency sound. Measure Sound doesn't filter by default, so set the *Filter* to **Unfiltered** to compare.
