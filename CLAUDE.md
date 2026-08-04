# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**cftscal** is a plugin-based GUI application for calibrating acoustic equipment such as that used in the Cochlear Function Test Suite (CFTS) and Auditory Behavior Test Suite (ABTS). It calibrates measurement microphones, speakers, starships (probe-tube mics), amplifiers, and related hardware. The UI framework is **Enaml** (declarative Qt) with **Atom** for the object model.

## Commands

```bash
# Install in development mode (from repo root)
pip install -e .

# Launch the app (shows all available calibration workspaces based on detected hardware)
cfts-cal

# Launch targeting a specific workspace tab directly
cfts-cal microphone
cfts-cal speaker
cfts-cal starship

# Load all plugins regardless of hardware availability (useful for development)
cfts-cal --load-all

# Run the test suite (tests/test_objects.py, test_settings.py, test_migrate_metadata.py)
python -m pytest
```

## Sibling Repos & Dev Environment

cftscal has no hardware I/O layer of its own — it launches calibrations by
shelling out to the `psi` CLI from the sibling repo **psiexperiment**
(`../psiexperiment` relative to this repo, git remote
`psiexperiment/psiexperiment`). `cftscal/util.py`'s `io_manifest()` and
`CalibrationSettings._run_cal()`'s `--io` argument reference dotted paths
into psiexperiment's IO manifest/engine classes (e.g.
`psi.controller.engines.soundcard.standard_io.AutoSoundCardManifest`).
When debugging a calibration-launch issue (device selection, channel
matching, sample rate, workbench registration errors, hangs), check
**both** repos — cftscal only sets env vars and a `--io` class path; the
actual engine/channel logic lives entirely in psiexperiment. Fixes
frequently require commits in both repos since they're independent git
repos with no shared branch.

There's also a third sibling repo, **psiaudio** (`../psiaudio`), a
lower-level DSP/calibration library both cftscal and psiexperiment depend
on (`from psiaudio import util`, `from psiaudio.calibration import ...`).

Both cftscal and psiexperiment are editable-installed (`pip install -e .`)
into the same conda env in this dev setup; run `python -m pytest` from
each repo's root using that env's interpreter.

## Architecture

### Plugin System (Enaml Workbench)

`main.py` bootstraps an `UIWorkbench`, registers the core manifest, then dynamically imports and registers one manifest per calibration type. A plugin is only registered if `instance.available` is true (hardware detected) or `--load-all` is passed.

Each plugin lives under `cftscal/plugins/<name>/` and contains:
- `manifest.enaml` — declares the workspace tab via `CalibrationPluginManifest` template, wiring together a view and settings class
- `settings.py` — an `Atom`-based settings class that extends `CalibrationSettings`; members tagged `.tag(persist=True)` are auto-saved/loaded as JSON to `~/.config/cfts/calibration/<name>.json`
- `view.enaml` — the Enaml UI for that calibration type

### Calibration Object Hierarchy (`cftscal/objects.py`)

The file defines the full device/calibration model:

- **`Calibration`** — abstract base; subclasses represent a single calibration file on disk. Key method: `load()` returns a psiaudio calibration object.
- **`CalibratedObject`** — represents a physical device (microphone, speaker, etc.); holds a list of loaders and exposes `list_calibrations()` / `get_current_calibration()` (returns the latest by datetime).
- **`CalibrationLoader`** — scans a filesystem path and yields `CalibratedObject` instances. `CFTSBaseLoader` is the standard file-system implementation.
- **`CalibrationManager`** — global registry of loaders and objects; exposes `list_objects()`, `list_names()`, `get_object(name)`.

Global manager singletons (`measurement_microphone_manager`, `speaker_manager`, `starship_manager`, etc.) are instantiated at the bottom of `objects.py` and imported throughout the codebase.

### Settings Persistence (`cftscal/plugins/settings.py`)

- **`CalibrationSettings`** — base class for all plugin settings. `save_config()` / `load_config()` serialize `persist`-tagged Atom members to JSON. `_run_cal(filename, experiment, env)` launches a calibration run via `subprocess` calling `psi <experiment> <filename>`.
- **`PersistentSettings`** — mixin for nested settings objects that participate in `get_persistence()` / `set_persistence()` serialization.

### Hardware Detection (`cftscal/util.py`)

Functions like `list_outputs()`, `list_inputs()`, `list_starship_connections()` scan the psiexperiment IO manifest to enumerate available hardware channels. Plugin `available` properties call these functions to determine if the plugin should be shown.

### Workspace Settings (`cftscal/plugins/workspace.py`)

Manages global settings (data path, hardware configuration, audio device, sample rate) stored in `~/.config/cfts/workspace.json`. The `WorkspaceSettings` Atom class is shared across all plugins.

### Data Storage

Calibration root defaults to `~/Documents/cftscal` (overridable via `$CFTSCAL_ROOT` env var or PSI config). Each calibration run creates a timestamped directory `YYYYMMDD-HHMMSS_<metadata>/` containing CSV data and JSON metadata. Subdirectories per type: `microphone/`, `speaker/`, `starship/`, `input_amplifier/`, etc.

### Experiment Paradigms (`cftscal/paradigms/`)

Enaml-based experiment definitions consumed by `psi` (the psiexperiment runner). A calibration settings class calls `_run_cal(output_dir, 'cftscal.<paradigm_name>', env_vars)` to launch the experiment. Environment variables (e.g. `CFTS_PISTONPHONE_LEVEL`, `CFTS_TEST_STARSHIP`) pass hardware configuration to the paradigm.

## Adding a New Plugin

1. Create `cftscal/plugins/<name>/` with `__init__.py`, `manifest.enaml`, `settings.py`, `view.enaml`.
2. In `settings.py`, subclass `CalibrationSettings`; tag persisted members with `.tag(persist=True)` and set `settings_filename`.
3. In `manifest.enaml`, use `CalibrationPluginManifest` template, providing `title`, `workspace_id`, `view_class`, `settings_class`, and an `available` computed property that checks hardware via `util.py` functions.
4. Register the new manifest in `main.py`'s `to_register` list.

## Key Conventions

- **Enaml files (`.enaml`)**: use `enaml.imports()` context manager before importing. Enaml syntax looks like Python but is declarative; `enamldef` defines UI components.
- **Atom members**: use `Typed`, `Str`, `Float`, `Enum`, `List` from `atom.api`. Tag with `.tag(persist=True)` for JSON persistence, `.tag(config=True)` for config-system integration.
- **`get_tagged_members` / `get_tagged_values`** (from `psi.util`): introspect Atom members by tag — used throughout settings serialization.

## Gotchas & Established Patterns

These are lessons from real bugs/design discussions, not just architecture description — read before touching the related code.

- **Every plugin's `__init__` must explicitly set `self.selected_<target> = self.available_<targets>[0]`** right after building the `available_*` list (see `starship/settings.py`, `speaker/settings.py`, `ir_sensor/settings.py`, `input_recording/settings.py`, `microphone_generic/settings.py` for the pattern). If you skip it, `selected_input`/`selected_output`/etc. falls back to the bare Atom default (`Typed(InputSettings, ())`), whose `.sensor` defaults to `SensorReference` instead of whatever role the plugin actually needs. This bug hides on any machine with a saved config JSON (`load_config()`/`set_config()` overwrites the bad default with the persisted selection) and only surfaces as an `AttributeError` on a fresh install with no config file yet — see the `MicrophoneCalibrationSettings` bug fixed in commit `fce5953`.
- **`SensorReference` vs `SensorDevice`** (`cftscal/plugins/settings.py`): both subclass abstract `SensorSettings`. `SensorReference` (and subclasses `MeasurementMicrophoneReference`, `GenericMicrophoneReference`, `InputAmplifierReference`) picks an *existing calibration* by path — `name` is a calibration path, exposes `available_references`. `SensorDevice` labels a *physical device being calibrated* — `name` is a free-form serial/asset-tag identifier, exposes `available_devices`. Don't mix them up: a plugin calibrating a new device (microphone, generic mic) uses `SensorDevice`; a plugin that needs to *load* an existing calibration as a reference (speaker's mic, starship's mic, input amplifier) uses the appropriate `SensorReference` subclass. The `AddItem` popup's "+" button and `SensorView` widget both assume whichever role's `available_*`/`name` fields exist on the `sensor` passed in.
- **`AddItem` popup** (`cftscal/plugins/widgets.enaml`): uses a `RegexField` (client-side validated — invalid keystrokes never reach `field.text`) with `submit_triggers = ['return_pressed']` (deliberately excludes `lost_focus`, so clicking Cancel doesn't add the typed text) wired to a shared `_add_item()` func, also called by the OK button (`enabled << bool(field.text)`). Enter therefore "just works" as soon as the field validates, with no extra enabling logic needed — the validator already gates it. Per-caller custom regexes are passed via `AddItem(..., regex=r'...')` (default `^[\w\d-]+$`; widened to `^[\w\d/_\- ]+$` wherever the value is a calibration path that can contain `/`).
- **`TimePSDPlotManager` region-select** (`cftscal/plugins/widgets.enaml`): uses a native `pg.LinearRegionItem(movable=True)`, not a hand-rolled click state machine — grab an edge to resize, the middle to move. Analysis recompute is wired to `sigRegionChangeFinished` (fires once, on release), **not** `sigRegionChanged` (fires continuously during drag) — an expensive recompute on every mouse-move is a real perf problem on slow machines. `region.setRegion(...)` unconditionally fires `sigRegionChangeFinished` on every call (see `LinearRegionItem.setRegion`/`lineMoveFinished` in pyqtgraph source), so don't use it for smooth intermediate updates during a custom drag — set `region.lines[0]`/`region.lines[1]` directly instead (see `RegionSelectViewBox.mouseDragEvent`, which implements Ctrl+drag-to-draw-a-new-region this way; a plain drag still pans via `super().mouseDragEvent()`).
- **`cftscal/plugins/export.py`**: WAV export where `1.0` in the file = `1.0` Pa (float32, no int16 scaling). Arbitrary JSON metadata is embedded in a custom `CFTS`-tagged RIFF chunk appended after `data` — any reader that doesn't know the tag (audio players, MATLAB's `audioread`) skips it via its declared byte length and reads the audio normally; nothing needs the chunk to work.
- **pyqtgraph OpenGL** (`cftscal/main.py`): `pg.setConfigOptions(useOpenGL=True)` is set only here, at cftscal's own entry point — never in psiexperiment, where it crashes some live-acquisition plots. Safe because `psi` always runs as a separate subprocess (its own interpreter, its own pyqtgraph state) when cftscal launches a calibration, so this setting never reaches it.
- **Filter design for level/PSD analysis** (`InputRecordingPlotManager._y_transform` in `cftscal/plugins/input_recording/view.enaml`): `filter_mode` is `'dBZ'` (true bypass, the default), `'dBA'` (standard IEC 61672-1 A-weighting, built from the analog pole/zero definition + bilinear transform — see `a_weighting_sos()`), or `'1/3 Octave'` (steep bandpass around `filter_fc`, built from `psiaudio.util.octave_band_freqs(fc, 1/3)`). Narrow/steep IIR filters should use `output='sos'` + `sosfiltfilt` rather than `'ba'` form + `filtfilt` — the polynomial ('ba') form gets numerically unstable at higher orders/narrower relative bandwidths.
- **ASIO/soundcard engine bugs are almost always in psiexperiment, not cftscal** — see `psiexperiment`'s own `CLAUDE.md` for the ASIO+WASAPI+dispatcher-threading gotchas (a real, hard-won multi-session debugging story). If a calibration hangs specifically on "hit Start" with an ASIO device, read that first before re-deriving it.

## Project conventions

As code is added or modified, unit-tests should be created or modified accordingly as unit-tests are critical for detecting regressions. Maximize reuse where possible. It is preferred to update classes and functions to make more generic rather than writing one-off functions for each use-case.

Use Numpy-style docstrings. When writing documentation, assume that the user is a novice Python programmer.
