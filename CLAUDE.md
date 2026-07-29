# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**cftscal** is a plugin-based GUI application for managing acoustic equipment calibrations at CFTS (Center for Translational Sound and Sensor Technology at OHSU). It calibrates measurement microphones, speakers, starships (probe-tube mics), amplifiers, and related hardware. The UI framework is **Enaml** (declarative Qt) with **Atom** for the object model.

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
```

There is no test suite in this repository.

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

## Project conventions

As code is added or modified, unit-tests should be created or modified accordingly as unit-tests are critical for detecting regressions. Maximize reuse where possible. It is preferred to update classes and functions to make more generic rather than writing one-off functions for each use-case.

Use Numpy-style docstrings. When writing documentation, assume that the user is a novice Python programmer.
