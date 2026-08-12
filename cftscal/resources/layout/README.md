# Default layouts

Packaged default dock-area layouts, one per paradigm:

```
<paradigm_name>/default.layout
```

`<paradigm_name>` is the string passed as the first argument to that
paradigm's `ParadigmDescription(...)` call in `cftscal/paradigms/__init__.py`
(e.g. `pistonphone_calibration`, `input_recording`) — the same name psi
itself uses as the directory key under `LAYOUT_ROOT`.

These are seeded into psiexperiment's `LAYOUT_ROOT`
(`~/Documents/psi/layout` by default) the first time `cfts-cal` starts,
via `cftscal.paradigms.default_state.seed_all_default_state()` — but only
if the user doesn't already have a `default.layout` for that paradigm.
A user's own saved layout (via psi's *Configuration > Layout > Set
default*) always takes precedence and is never overwritten.

To capture a layout to add here: arrange the dock panels the way you
want inside a running paradigm, use *Configuration > Layout > Set
default*, then copy the resulting file from
`<LAYOUT_ROOT>/<paradigm_name>/default.layout` into this directory.

Layout files are pickled `enaml.layout.dock_layout.DockLayout` objects
(psi's own format, see `psi/experiment/experiment_commands.py`) — not
human-readable/diffable, and not guaranteed to load if generated with a
substantially different Enaml/psi version than what's installed when
loading it back.
