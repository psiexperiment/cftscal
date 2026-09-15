# Hardware Design

cftscal measures whatever hardware you point it at, but a calibration can only
be as good as the signal chain underneath it. This page covers the electrical
and acoustic limits worth working out *before* you calibrate — how hard you can
safely drive a speaker, how much output to expect from it, how to bring a DAC's
voltage down to a level the speaker can take, and the resonances that can put a
peak or notch in a measured response that has nothing to do with the device you
think you are measuring.

None of this is something cftscal computes for you. It is the arithmetic you do
once, on paper, when you build or modify a rig.

## Power, voltage, and current

Speaker sensitivity is typically reported on a datasheet in \(\frac{dB}{W}\) at a
distance of 1 meter — so many dB SPL for one watt of input. To use that number
you need to convert between watts and volts, which requires the speaker's
impedance.

Starting from \(P = I^2 \times R\) and \(V = I \times R\), and solving for
\(I\):

$$ I = \sqrt{\frac{P}{R}} \qquad \text{and} \qquad I = \frac{V}{R} $$

$$ \sqrt{\frac{P}{R}} = \frac{V}{R} $$

which gives the two forms you actually use:

$$ P = \frac{V^2}{R} \qquad \qquad V = R \times \sqrt{\frac{P}{R}} = \sqrt{PR} $$

(\(R\sqrt{P/R}\) and \(\sqrt{PR}\) are the same thing; the second is easier to
evaluate in your head.)

**Worked example.** For an 8 Ω speaker,
\(8 \times \sqrt{1/8} = 2.83\) V produces exactly 1 W — which is why datasheet
figures for 8 Ω drivers are often quoted at 2.83 V. Checking the other
direction: \(2.83^2 / 8 = 1.00\) W.

## Maximum safe drive voltage

Work backwards from the speaker's power rating to the voltage you must not
exceed.

**Worked example.** An 8 Ω speaker with a 0.5 W handling capacity:

$$ V = R \times \sqrt{\frac{P}{R}} = 8\,\Omega \times \sqrt{\frac{0.5\,W}{8\,\Omega}} = 2\,V $$

!!! warning "There is no point in exceeding this voltage"
    Even if your system can generate a larger value, driving the speaker above
    its rated voltage does not buy you more usable output — it will simply
    distort, or damage the driver. The calibration will happily record the
    distorted response as though it were real.

Your system also has to *supply the current* that voltage implies:

$$ I = \sqrt{\frac{P}{R}} = \sqrt{\frac{0.5\,W}{8\,\Omega}} = 0.25\,A $$

A DAC output or op-amp that cannot source 0.25 A into 8 Ω will clip on current
even though its voltage looks fine, which shows up in a calibration as
compression at high levels.

!!! warning "These are RMS values; datasheets often quote peaks"
    Power ratings, and therefore the 2 V and 0.25 A above, are **RMS**
    quantities. A converter's *full-scale* output, and an op-amp's output swing
    and current limit, are usually **peak** figures. For a sine wave the two
    differ by \(\sqrt{2}\):

    | | RMS | Peak (sine) |
    | --- | --- | --- |
    | Voltage | 2.00 V | 2.83 V |
    | Current | 0.25 A | 0.35 A |

    So the 2 V<sub>rms</sub> limit means the amplifier has to swing ±2.83 V
    cleanly without clipping. Compare like with like before concluding you have
    headroom — and note that a broadband stimulus such as noise or a chirp has a
    higher peak-to-RMS ratio than a sine, so it needs more headroom still for
    the same RMS level.

Many datasheets give both a long-term (continuous) and a short-term (peak)
rating. Compute the voltage limit for each, and treat the continuous figure as
your working limit:

| Rating | Power | Max. voltage into 8 Ω |
| --- | --- | --- |
| Long-term / continuous | 0.3 W | 1.55 V |
| Short-term / peak | 0.5 W | 2.00 V |

!!! note "These are *nominal* specs"
    Every number in this section comes off a datasheet, and datasheet figures
    are nominal. Treat them as a ceiling to stay well below, not a target to
    hit, and verify the actual behavior with a calibration.

## Estimating maximum output in dB SPL

Once you know the maximum power you can put into the speaker, you can convert
the datasheet's rated SPL to the SPL you will actually be able to reach. Power
ratios are \(10 \times log_{10}\):

$$ \Delta dB = 10 \times log_{10}\left(\frac{P_{new}}{P_{rated}}\right) $$

**Worked example.** A datasheet reports 92 dB at 0.3 W, and you have determined
you can safely drive 0.5 W:

$$ 10 \times log_{10}\left(\frac{0.5\,W}{0.3\,W}\right) = 2.2\ dB $$

So you gain only 2.2 dB, for a maximum of **94.2 dB SPL** — doubling the power
buys 3 dB, and this is not even a doubling. If instead you can only manage
0.1 W, \(10 \times log_{10}(0.1/0.3) = -4.8\) dB, i.e. 87.2 dB SPL.

Note that this scales the datasheet's SPL figure, which is quoted at **1 metre
on axis**. If your speaker sits a few centimetres from the ear, or is coupled
into a tube, the absolute level will be nothing like the datasheet number — but
the \(10 \times log_{10}\) power scaling still tells you how much *more* you can
get out of it than at the rated power.

This calculation is the fastest way to find out early that a speaker cannot
physically reach the levels your experiment requires — long before you have
wired up a rig and discovered it during calibration.

## Sizing a voltage divider

If your DAC's full-scale output exceeds the speaker's safe voltage, you need to
bring it down. A series resistor forms a voltage divider with the speaker's own
impedance:

$$ V_{speaker} = V_{out} \times \frac{R_{speaker}}{R + R_{speaker}} $$

Solving for the series resistor:

$$ R = \frac{R_{speaker} \times (V_{out} - V_{speaker})}{V_{speaker}} $$

**Worked example.** An 8 Ω speaker that must not see more than 2 V<sub>rms</sub>,
driven from a source that delivers 10 V<sub>rms</sub> at full scale:

$$ R = \frac{8\,\Omega \times (10\,V - 2\,V)}{2\,V} = 32\,\Omega $$

Both voltages must be expressed the same way — both RMS, or both peak. Mixing a
peak full-scale figure with an RMS limit gives a divider that is wrong by
\(\sqrt{2}\), i.e. 3 dB.

Using a divider rather than just turning the software level down is worth it
when you want to use the *full range of your DAC*: attenuating in software
throws away bits of resolution and leaves you closer to the converter's own
noise floor, whereas attenuating in hardware lets the DAC run near full scale
where its signal-to-noise ratio is best.

!!! warning "Size the resistor for power, not just resistance"
    Most of the power now lands in the resistor, not the speaker. In the example
    above the current is \(10\,V / 40\,\Omega = 0.25\) A, so the series resistor
    dissipates \(0.25^2 \times 32 = 2\) W while the speaker gets 0.5 W. A
    common 1/4 W resistor would cook. Pick one rated well above the dissipation
    you calculate, and remember the source has to supply the full 2.5 W.

!!! note "A series resistor also changes the speaker's damping"
    Adding resistance in series raises the source impedance the driver sees,
    which reduces its electrical damping and alters the response around its
    resonance. This is not a reason to avoid the divider — you calibrate the
    system as built, and the calibration captures whatever the response turns
    out to be — but it does mean the divider is part of the system, so changing
    or removing it invalidates the calibration.

!!! warning "Account for gain elsewhere in the chain"
    \(V_{out}\) is the voltage that actually arrives at the divider, which is
    not necessarily the DAC's output. Do not forget to compensate for any gain
    built into an op-amp or buffer circuit between the DAC and the speaker.

## Cable resonance and grounding

Signal cables resonate when their physical length is a quarter wavelength of the
signal they carry. The wavelength of an *electrical* signal is set by the speed
of light:

$$ \lambda/4 = \frac{c}{4f} \qquad \text{or} \qquad f_{resonant} = \frac{c}{4l} $$

Running the numbers for the audio range makes the conclusion obvious:

| Frequency | Quarter wavelength |
| --- | --- |
| 100 Hz | 749,481 m (749 km) |
| 1 kHz | 74,948 m |
| 100 kHz | 749 m |

A 3 m cable resonates at about 25 MHz — three orders of magnitude above anything
in an acoustic measurement.

!!! success "Cable resonance is a non-issue for acoustic work"
    Since nobody is running 750 meters of cable inside a sound booth, cable
    resonance can be ruled out as a source of artifacts across the entire
    100 Hz – 100 kHz range. If you are chasing noise or an odd response, look
    at grounding, shielding, and ground loops instead — not cable length.

    (Strictly, a signal travels through real cable at a *velocity factor* of
    roughly 0.6–0.85 of \(c\), depending on the dielectric, so the lengths above
    are overestimates by that factor — 100 kHz needs more like 450–640 m rather
    than 749 m. That does not change the conclusion in the slightest.)

## Acoustic tube resonance

Acoustic resonance is a completely different story, because sound travels at
roughly 340 m/s instead of \(3 \times 10^{8}\) m/s. The relevant lengths
therefore come out in *millimeters*, which is exactly the scale of a probe tube,
a coupler, or an ear canal.

The wavelength of a 14 kHz tone in air is only
\(340 / 14000 = 24.3\) mm; its quarter wavelength is 6.1 mm.

For a tube of length \(L\), the resonances depend on its boundary conditions —
and so does the *pattern* of higher modes, which is easy to get wrong:

| Tube | Lowest resonance | Higher modes | 20 mm tube |
| --- | --- | --- | --- |
| Closed at one end (quarter-wave) | \(f_1 = \frac{c}{4L}\) | **odd** multiples: \(3f_1, 5f_1, \ldots\) | 4.25, 12.75, 21.25 kHz |
| Open at both ends, or closed at both (half-wave) | \(f_1 = \frac{c}{2L}\) | **all** integer multiples: \(2f_1, 3f_1, \ldots\) | 8.5, 17.0, 25.5 kHz |

A quarter-wave tube (one open end, one closed — the closest simple model for a
probe tube sealed against an eardrum) skips the even multiples entirely: its
modes are at \(c/4L\), \(3c/4L\), \(5c/4L\). Only the half-wave case has modes
at every integer multiple. Either way, a single tube puts a whole series of
peaks and notches into the response, not just one.

!!! note "These are idealizations"
    Real probe tubes are neither ideally open nor ideally closed at their ends,
    have finite wall losses, and couple into a cavity rather than free space, so
    measured resonances land near these frequencies rather than exactly on them,
    with finite Q. Use the formulas to know roughly *where* to expect structure,
    not to predict a measured curve. The speed of sound itself is also only
    roughly 340 m/s — it rises about 0.6 m/s per °C — so across a realistic
    range of room temperatures every frequency in the table moves by a percent
    or two.

!!! tip "This is what most odd-looking notches actually are"
    A 20 mm probe tube has resonances squarely inside the frequency range of a
    typical CFTS measurement. This is why the
    [Starship](../plugins/starship.md) and
    [Starship Check](../plugins/starship-check.md) workspaces care so much about
    the probe tube being fully seated and unobstructed, and why the coupler used
    for a calibration has to match how the starship is actually used: change the
    length of the acoustic cavity and you move every one of these resonances.

    A calibration correctly *measures* these resonances and compensates for
    them, so they are not inherently a problem — but they only stay compensated
    if the geometry does not change between calibration and use.
