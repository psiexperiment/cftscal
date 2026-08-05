# Getting Started

## Installation

cftscal is a standard Python package, installable via pip:

    python -m pip install cftscal

This registers a `cfts-cal` command in your environment. — see [Calibration Concepts](concepts.md) for why cftscal itself has no hardware I/O of its own).

## Launching cftscal

In a console:
```bash
# Show only workspaces that support the detected hardware.
cfts-cal

# Show every workspace regardless of detected hardware (useful for reviewing calibrations on another computer)
cfts-cal --load-all
```

If a workspace you expect doesn't show up, it's almost always because cftscal couldn't detect the corresponding hardware channel — see [Workspace Settings](#workspace-settings) below for how that's configured.

## Workspace Settings

Before calibrating anything, cftscal needs to know:

- **Data folder** — where calibration results get saved. Defaults to `~/Documents/cftscal`, but you can point it anywhere (e.g. a shared lab drive).
- **Hardware** — which acquisition backend to use (a dedicated sound card, an NI-DAQ system, etc.). This determines which input/output channels are available to every other plugin.
- **Audio device & sample rate** *(sound card hardware only)* — the specific device and sampling rate to record/play at. Pick a sample rate your hardware and microphones actually support; if you're not sure, the dropdown only lists rates cftscal has confirmed the selected device supports.

## The general pattern

Every calibration workspace in cftscal (microphone, speaker, starship, input recording, ...) follows the same basic layout:

- A **Settings** panel (usually top-left) — pick an input/output channel, a target folder, a sensor/device label, and any other parameters, then click a button to run the calibration or recording.
- A **plot** area showing the result of the currently selected calibration from the list below.
- A **list/tree** of everything previously recorded for this workspace, organized by device and date. **Right-click an entry** for actions like exporting or deleting it.

Once you're oriented, move on to the [Plugins](plugins/index.md):

- [Measurement Microphone Calibration](plugins/measurement-microphone.md) — usually the first thing you do in a session.
- [Input Recording](plugins/input-recording.md) — for recording and reviewing any signal from one or more channels at once, with flexible filtering and calibrated WAV export.
- [Speaker Calibration](plugins/speaker.md) and [Generic Microphone Calibration](plugins/generic-microphone.md) — calibrate a speaker or a non-precision microphone against your measurement microphone.
- [Starship Calibration](plugins/starship.md) and [Starship Check](plugins/starship-check.md) — calibrate a starship, then periodically verify it's still behaving once it's in use.
- [Input Amplifier Calibration](plugins/input-amplifier.md) — verify a standalone signal preamp's actual gain.
- [IR Sensor Calibration](plugins/ir-sensor.md) — a diagnostic recording tool for IR emitter/detector pairs.
