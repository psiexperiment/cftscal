# Default preferences

Packaged default preference sets, one per paradigm:

```
<paradigm_name>/default.preferences
```

`<paradigm_name>` is the string passed as the first argument to that
paradigm's `ParadigmDescription(...)` call in `cftscal/paradigms/__init__.py`
(e.g. `pistonphone_calibration`, `input_recording`) — the same name psi
itself uses as the directory key under `PREFERENCES_ROOT`.

These are seeded into psiexperiment's `PREFERENCES_ROOT`
(`~/Documents/psi/preferences` by default) the first time `cfts-cal`
starts, via `cftscal.paradigms.default_state.seed_all_default_state()` —
but only if the user doesn't already have a `default.preferences` for
that paradigm. A user's own saved preferences (via psi's *Configuration
> Preferences > Set default*) always take precedence and are never
overwritten.

To capture preferences to add here: configure a running paradigm the way
you want, use *Configuration > Preferences > Set default*, then copy the
resulting file from `<PREFERENCES_ROOT>/<paradigm_name>/default.preferences`
into this directory.

Preferences files are YAML (see `psi/experiment/experiment_commands.py`),
so unlike layout files these are human-readable and diffable in git.
