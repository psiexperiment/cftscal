# Reference

These pages are the background theory behind what cftscal does. You don't need
any of it to run a routine calibration — start with
[Calibration Concepts](../concepts.md) and the
[plugin workflow pages](../plugins/index.md) for that. Come here when you want
to know *why* a number looks the way it does, check cftscal's arithmetic against
your own, or design new hardware that cftscal will later calibrate.

<div class="grid cards" markdown>

-   :material-function-variant:{ .lg .middle } **Calibration Math**

    ---

    Every equation cftscal uses, from pistonphone to "what voltage do I send to
    the speaker for 80 dB SPL?", plus the sign and unit conventions you need to
    interpret the numbers the GUI reports.

    [:octicons-arrow-right-24: Read](calibration-math.md)

-   :material-chart-bell-curve:{ .lg .middle } **Signal Analysis**

    ---

    Windowing, power spectral density estimation, spectrum level vs. band
    level, chirps, and reproducible filtered noise. Read this if a measured
    level or spectrum isn't what you expected.

    [:octicons-arrow-right-24: Read](signal-analysis.md)

-   :material-sine-wave:{ .lg .middle } **Hardware Design**

    ---

    Choosing safe drive voltages for a speaker, estimating its maximum output,
    sizing a voltage divider, and the cable and acoustic-tube resonances worth
    (and not worth) worrying about.

    [:octicons-arrow-right-24: Read](hardware-design.md)

</div>
