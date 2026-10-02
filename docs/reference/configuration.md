# Settings and the handoff contract

cftscal deals with two kinds of named value, and keeping them apart is the
whole point of this page. **Settings** are configuration: durable, yours to
edit, and resolved from the psi configuration file or the environment.
**Handoff variables** are a process contract: written into the environment of
a `psi` subprocess at launch, read by the paradigm at startup, and gone when
the subprocess exits. They are never configuration and never belong in
`config.toml`.

## Settings

These resolve the same way as any psiexperiment setting — built-in default,
then `config.toml`, then the environment, last one winning. See the
[psiexperiment configuration reference][psi-config] for the resolution rules
and the file's location.

| Setting | Default | Contents |
| --- | --- | --- |
| `CFTSCAL_ROOT` | `~/Documents/cftscal` | Where calibration data is stored. |
| `CFTSCAL_IO` | `default` if this machine has its own IO manifest, else `sound-card` | The IO manifest cftscal *and* the cfts, abts and noise-exp launchers run psi with — see below. |
| `CFTSCAL_DEVICE_NAME` | `''` | Name of the selected audio device. Only used when `CFTSCAL_IO` is `sound-card`. |
| `CFTSCAL_DEVICE_HOSTAPI` | `''` | Host API the device belongs to. Together with the name this is the *durable* identity of a device — never a PortAudio index, which is meaningless across sessions. Only used when `CFTSCAL_IO` is `sound-card`. |
| `CFTSCAL_SAMPLE_RATE` | `0.0` | Sampling rate for the selected device. Only used when `CFTSCAL_IO` is `sound-card`. |

`CFTSCAL_IO` is one of:

- `sound-card` — the audio device chosen by `CFTSCAL_DEVICE_NAME`,
  `CFTSCAL_DEVICE_HOSTAPI` and `CFTSCAL_SAMPLE_RATE`.
- `default` — this machine's own manifest, `<PSI_IO_ROOT>/<hostname>.enaml`,
  the one `psi` uses when run without `--io`.
- Anything else is given to psi's `--io` as written: a file
  (`C:/io/rig.enaml`, optionally `::ClassName`) or a dotted module path
  (`cftscal.io.dummy_fireface.IOManifest`).

The launchers fill their channel choices from this manifest and run their
experiments on it, so the two can no longer disagree. `cftscal.util.resolve_io`
is the one place it is interpreted.
| `CFTSCAL_ENABLED_PLUGINS` | `[]` | Plugins to load regardless of what their hardware probes report, so a machine without the hardware can still browse existing calibrations. |
| `CFTSCAL_PLUGIN` | `{}` | Per-plugin GUI state, one `[CFTSCAL_PLUGIN.<name>]` table each. Written by the GUI; there is no reason to edit it by hand. |

Everything except `CFTSCAL_PLUGIN` is editable through **Workspace →
Settings**, which writes the configuration file when you save:

| In Workspace → Settings | Setting |
| --- | --- |
| **Data folder** | `CFTSCAL_ROOT` |
| **Hardware**: *This computer's IO manifest* | `CFTSCAL_IO` = `default` |
| **Hardware**: *Sound card*, with **Audio device** and **Sample rate (Hz)** | `CFTSCAL_IO` = `sound-card`, plus `CFTSCAL_DEVICE_NAME`, `CFTSCAL_DEVICE_HOSTAPI` and `CFTSCAL_SAMPLE_RATE` |
| **Hardware**: *Other IO manifest*, with **IO manifest file** and **Manifest class** | `CFTSCAL_IO` = the file, as `path::Class` |
| **Always load these plugins** | `CFTSCAL_ENABLED_PLUGINS` |

[Workspace Settings](../getting-started.md#workspace-settings) describes
each of these in more detail.

### When the environment wins

Because the environment outranks the configuration file, a `CFTSCAL_*`
variable set in your environment cannot be changed from the GUI: the save
would succeed and change nothing the application then reads. Rather than
accept a write that does nothing, the settings view disables the affected
control, and hovering over it names the variable responsible. Clear the
variable to edit the setting normally.

To see which layer supplied a value:

```bash
psi-config show
```

### Upgrading from the old settings files

Older versions of cftscal kept these settings in their own JSON files in
the psi configuration folder (`~/psi`, or the folder named by the
`PSI_CONFIG` environment variable): `cfts/workspace.json` and one
`cfts/calibration/<plugin>.json` per plugin.

When cftscal starts and finds these files, it shows what they contain and
asks whether to import them into `config.toml`:

- **Import** fills in the settings `config.toml` does not have yet. Nothing
  already there is overwritten.
- **Not now** imports nothing and asks again at the next start.
- **Don't ask again** imports nothing and stops asking.

If `config.toml` already has everything the files contain, cftscal does not
ask. Either way, once the files have been imported or declined, a note,
`cfts/MIGRATED.txt`, is written beside them saying what happened, and that
note is what stops cftscal from asking again. The old files are left
untouched.

To import them later, or again, use **Import old settings...** in
**Workspace → Settings** (shown only when the old files exist). It imports
even if they were imported or declined before, and can replace the
settings already in `config.toml` with the old values.

`psi-config migrate` converts the same files, with or without a
`config.py` beside them (on a machine that has one, it converts both at
once). Unlike cftscal, it does not ask: it writes everything it finds,
replacing what `config.toml` already has, and does not write
`MIGRATED.txt`.

To preview the import without changing anything:

```bash
python -m cftscal.migrate_settings
```

`--apply` writes it, `--force` ignores `MIGRATED.txt` and `--replace`
replaces settings already in `config.toml`.

## The handoff contract

cftscal has no hardware I/O layer of its own. It runs a calibration by
shelling out to the `psi` command and passing the hardware configuration —
which device, which channel, which calibration to load — through environment
variables set on that subprocess. The paradigm manifests in
`cftscal/paradigms/` read them at startup.

These variables are ephemeral. They exist for the lifetime of one subprocess,
they are written afresh on every run, and putting one in `config.toml` has no
effect at all.

### Naming

Every handoff variable carries the `CFTSCAL_` prefix, because cftscal owns
the format and exports the manifests that read it. The single exception is
`CFTSCAL_ROOT`, which is a genuine setting and is listed above.

Two related prefixes are easy to confuse:

- `CFTS_ROOT` belongs to the **cfts** package, and is where the cfts launcher
  keeps saved experiment and hardware presets. It is unrelated to calibration
  storage.
- `PSI_SOUND_DEVICE_NAME` and `PSI_SOUND_DEVICE_FS` are also handoff
  variables, but they are psiexperiment's: cftscal writes them from the
  device it has selected, and `AutoSoundCardEngine` reads them *instead of*
  anything in the IO manifest. When they are set, they — not the manifest —
  decide which device is opened.

### Shape

Most objects follow one pattern. A variable names the piece of hardware, and
its value is then substituted into the names of that object's own variables:

```
CFTSCAL_MICROPHONE                  = mic_a
CFTSCAL_MICROPHONE_MIC_A            = <calibration string>
CFTSCAL_MICROPHONE_MIC_A_GAIN       = 20
```

So the reader resolves `CFTSCAL_MICROPHONE` first, upper-cases the value, and
builds the remaining names from it. `cftscal/paradigms/env_vars.py` implements
this: `read_env_vars` where a variable names the hardware,
`read_named_vars` + `check_required_vars` where the caller already knows the
name.

The manifest attribute `env_prefix` is what sets the leading portion —
`CFTSCAL_INPUT`, `CFTSCAL_OUTPUT`, `CFTSCAL_SPEAKER`, `CFTSCAL_MICROPHONE`,
`CFTSCAL_INPUT_AMPLIFIER` and so on — so the naming lives in one place per
object rather than being spelled out at each read.

Multi-channel recording works the same way per channel, with
`CFTSCAL_INPUT_CHANNELS` naming the channels and each channel contributing
its own gain and calibration variables.

### Missing variables are an error, not a default

Each manifest declares a `required_vars` list naming the settings the
experiment cannot run without, and it defaults to *every* setting that
manifest knows how to read. A missing or misspelled variable therefore fails
loudly at startup — `MissingEnvironmentVariables`, naming the exact variables
expected — instead of silently running with whatever default the GUI happened
to show. That silent fallback was the original behaviour and it produced bad
data.

A paradigm whose *purpose* is to create one of those calibrations has none to
load, so it overrides `required_vars` to drop that setting. Those overrides
must agree with the `include_cal` arguments the corresponding plugin passes to
`get_env_vars`; `tests/test_paradigm_objects.py` pins the expected
`required_vars` for every cftscal paradigm.

[psi-config]: https://psiexperiment.readthedocs.io/en/latest/configuration.html
