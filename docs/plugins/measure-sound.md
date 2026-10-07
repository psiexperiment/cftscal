# Coming from measure_sound

This page is for anyone who used the lab's older MATLAB program, **measure_sound** (`measure_sound_v2022.m`), to measure sound levels. [Input Recording](input-recording.md) does the same job, but it doesn't always do it the same way. Some numbers will come out differently, a few of them by a lot, and this page explains why.

The short version:

- **dB SPL** agrees, as long as you set the *Filter* to **Unfiltered** and select the same stretch of the recording.
- **dBA** does **not** agree, and it shouldn't. measure_sound's dBA has two bugs: it applies the A-weighting twice, and it is only calibrated for one sampling rate. cftscal's dBA follows the standard. See [dBA](#dba).
- **The band-pass filter** has the same band edges as measure_sound's, but a different shape, so band-passed levels differ. No cftscal setting reproduces it exactly. See [Band-pass filter](#band-pass-filter).
- **peSPL** matches measure_sound's "equivalent RMS" when the stretch you select contains both a positive and a negative peak.

## Where things moved

| In measure_sound | In Input Recording |
| --- | --- |
| Load a B&K PULSE `.mat` file or a WAV file | Copy the `.mat` file into Input Recording's folder and tick it in the *Recordings* list. See [Reviewing PULSE `.mat` files](input-recording.md#reviewing-pulse-mat-files). WAV files can't be opened. |
| Choose one channel to analyze | Every channel of a recording is plotted at once, with a column each in the *Analysis* table. |
| The analysis window is whatever is on screen: *Select*, *Advance*, *Rewind*, *Zoom in*, *Zoom out* | Zooming and panning the plot doesn't change what's measured. The measurement comes from the **selected region**, the shaded band you draw with *Ctrl+drag*. See [Selecting a region](input-recording.md#selecting-a-region). Like measure_sound, the plot opens on the first 90 seconds, but no region is selected until you draw one. |
| RMS (dB SPL) | **dB SPL** row. |
| dBA | **dBA** row, but see [dBA](#dba). |
| Max Pa, Min Pa | **Max (Pa)** and **Min (Pa)** rows. |
| Equivalent RMS (Pa and dB) | **peSPL** row. See [Peak levels](#peak-levels). |
| *Peak-trough*: click a peak and a trough | No click-to-pick. Select a region that contains just the peak and trough you want; **peSPL** then uses the largest peak and deepest trough in that region. |
| "Filter waveform before analysis" | *Filter* set to **Band-pass**. See [Band-pass filter](#band-pass-filter). |
| *FFT* button (spectrum plots in a new window) | The spectrum plot is always shown, below the waveform, for the selected region. It's calibrated in dB SPL; measure_sound's spectrum was in uncalibrated "Power (dB)". |
| *Listen* | **Play region**. measure_sound played pressure values directly, so any part of the sound beyond ±1 Pa (a tone of about 91 dB SPL) was clipped. Play region uses a fixed scale with 20 Pa at full volume. |
| *Save* (a `.mat` file of the window) | **Export region…** (a calibrated WAV file in which 1.0 means 1 Pa). Like measure_sound's *Save*, it saves the region after the filter. |

## Calibration

measure_sound took the numbers in the file as pascals, after multiplying PULSE channel 1 by 1.165 and channel 2 by 1.187 (+1.33 and +1.49 dB). Those were fixed correction factors for one particular setup, and WAV files got no correction at all.

When Input Recording opens a PULSE `.mat` file, it also takes the numbers as pascals, but it does **not** apply measure_sound's correction factors. Its levels for channel 1 therefore read 1.33 dB lower than measure_sound's, and for channel 2, 1.49 dB lower.

Input Recording instead converts each channel to pascals using the calibration of the sensor you chose when you recorded (see [Sensor types](input-recording.md#sensor-types)). If you compare a level from measure_sound with one from cftscal, remember that the two programs may not have started from the same calibration, so a difference of a dB or so can come from calibration alone.

## Filtering

By default, measure_sound doesn't filter at all, while Input Recording's default *Filter* is a 20 Hz **High-pass** that keeps building rumble out of the level (see [Choosing a filter](input-recording.md#choosing-a-filter)). To compare with measure_sound's default, set the *Filter* to **Unfiltered**.

### Band-pass filter

measure_sound's filter (on when "Filter waveform before analysis" is ticked) is a band-pass filter. With its default settings, a center frequency of 1000 Hz and a width of 4 octaves, it keeps 250 Hz to 4 kHz. Input Recording's **Band-pass** works out its band edges the same way, so 1000 Hz and 4 octaves gives the same 250 Hz to 4 kHz. The *shape* of the filter is different, though:

- measure_sound uses the gentlest possible Butterworth band-pass (order 1) and runs it forwards and then backwards (MATLAB's `filtfilt`). That applies the filter twice, so the band edges end up 6 dB down instead of the usual 3 dB.
- Input Recording applies its filter once, so the band edges are 3 dB down, and its default *order* is 4, which cuts off much more steeply outside the band.

No setting in Input Recording gives exactly measure_sound's filter. Here is how far each choice is from it, for 1000 Hz and 4 octaves at a 48 kHz sampling rate:

| Frequency | 31.5 Hz | 125 Hz | 250 Hz | 500 Hz | 1 kHz | 2 kHz | 4 kHz | 8 kHz | 16 kHz |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| measure_sound's filter | −37.2 dB | −14.7 dB | −6.0 dB | −1.3 dB | 0 dB | −1.2 dB | −6.0 dB | −15.8 dB | −33.7 dB |
| Input Recording, order 1, compared with measure_sound | +18.6 dB | +7.3 dB | +3.0 dB | +0.7 dB | 0 dB | +0.6 dB | +3.0 dB | +7.9 dB | +16.8 dB |
| Input Recording, order 4, compared with measure_sound | −36.9 dB | −11.1 dB | +3.0 dB | +1.3 dB | 0 dB | +1.2 dB | +3.0 dB | −12.7 dB | −33.3 dB |

A positive number means Input Recording lets more of that frequency through than measure_sound did. In practice:

- A sound that sits well inside the band, such as a 1 kHz tone, reads the same in both.
- Broadband sound (noise) can read higher or lower. With order 1, Input Recording keeps more of every frequency, so it reads higher. With order 4, it keeps more near the band edges but far less outside the band, so the result depends on how much of the sound lies outside the band.

Two smaller differences:

- measure_sound filtered the whole recording and then measured the window. Input Recording's *Analysis* table filters just the selected region. This only matters very close to the start and end of a short region.
- The **Zero-phase** checkbox makes no difference to dB SPL or dBA, so it can't make the two programs agree. In measure_sound, running the filter forwards and backwards removed the delay but also doubled the filter. Input Recording's Zero-phase removes the delay without doubling anything (see [Choosing a filter](input-recording.md#choosing-a-filter)).

### dBA

measure_sound worked out dBA from the recording's spectrum, which is a perfectly good method. Two mistakes in how it did it mean its dBA values are wrong, though, and cftscal deliberately doesn't copy them.

**1. The A-weighting is applied twice.** The A-weighting curve says how much to turn down each frequency: by about 30 dB at 50 Hz, for example. measure_sound's formula for the curve gives the weighting for sound *power*, but the program applied it to the *amplitude* spectrum and then squared the result. That squares the weighting too, so every frequency is turned down twice as much as the standard says: about 60 dB at 50 Hz instead of about 30 dB. At 1 kHz the weighting is 0 dB, and twice 0 dB is still 0 dB, so a 1 kHz calibration tone gives the right answer and the mistake doesn't show up in that check.

**2. The calibration constant only fits one sampling rate.** measure_sound adds a fixed constant, `C = 42.8051`, to make a 1 kHz tone read the same in dB SPL and dBA. The correct constant depends on the sampling rate (it is 93.98 − 10·log₁₀(sampling rate)). 42.8051 is correct for 131,072 Hz, the rate the B&K PULSE recordings were presumably made at. At any other rate, every dBA value is shifted by 10·log₁₀(sampling rate ÷ 131,072): 4.4 dB too low at 48 kHz, 1.3 dB too low at 96 kHz, and 1.7 dB too high at 192 kHz.

Here's what the two programs report for pure tones at 94 dB SPL:

| Tone | Standard A-weighting | Input Recording dBA | measure_sound dBA (131,072 Hz) | measure_sound dBA (48 kHz) |
| --- | --- | --- | --- | --- |
| 50 Hz | −30.3 dB | 63.7 | 33.5 | 29.1 |
| 125 Hz | −16.2 dB | 77.8 | 61.6 | 57.3 |
| 1 kHz | 0 dB | 94.0 | 94.0 | 89.6 |
| 4 kHz | +1.0 dB | 95.0 | 95.9 | 91.6 |
| 16 kHz | −6.7 dB | 87.3 | 80.6 | 76.2 |

For anything other than a 1 kHz tone recorded at 131,072 Hz, measure_sound's dBA is off. It's too low for sound that is mostly at low or high frequencies, and slightly too high for sound that is mostly between about 1 and 5 kHz, where the standard curve turns sound *up* a little. Old dBA values should be treated with care: a low-frequency noise could easily have read 10 to 30 dB too low.

!!! note "Which A-weighting setting matches measure_sound's method?"
    measure_sound applied the weighting to the spectrum, which is what Input Recording does when **Exact A-weighting** is ticked. Without it, cftscal uses a digital approximation that is very slightly low above about 8 kHz at 48 kHz sampling (see [Choosing a filter](input-recording.md#choosing-a-filter)). Either way, cftscal's dBA follows the standard curve once, so neither setting reproduces measure_sound's numbers.

Finally, when measure_sound's filter was ticked, its dBA was measured from the band-passed recording. Input Recording's **dBA** row always starts from the unfiltered recording, whatever the *Filter* is set to.

## Peak levels

measure_sound's "equivalent RMS" is the average size of the biggest positive and biggest negative pressure in the window, divided by √2. That's the level of a sine wave that swings as far as the recording does, which is what Input Recording calls **peSPL**. The two match when the region contains both a positive and a negative peak, which is almost always true.

They can differ in one unusual case. measure_sound treated everything outside the window as silence when it looked for the biggest and smallest values, so if the whole window was positive (or the whole window negative), it counted the minimum (or maximum) as 0 Pa. Input Recording uses the region's actual values.

Input Recording also reports **Peak SPL**, half the full swing without dividing by √2. It's 3 dB above peSPL, and measure_sound had no equivalent.

## Getting numbers you can compare

To compare a new measurement with one made in measure_sound:

1. Set the *Filter* to **Unfiltered** (or, if you used measure_sound's filter, **Band-pass** with the same center frequency and width, keeping the differences above in mind).
2. Draw the region over the same stretch of sound that measure_sound's window covered.
3. Compare **dB SPL** with measure_sound's RMS, and **peSPL** with its equivalent RMS.
4. Don't compare **dBA** directly. Unless the sound was a 1 kHz tone recorded at 131,072 Hz, measure_sound's dBA was wrong, and the newer value is the one to trust.
