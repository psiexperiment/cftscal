import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess

from atom.api import set_default, Atom, Enum, Float, List, Str, Typed

from psi import get_config_folder
from psi.util import get_tagged_members, get_tagged_values


from cftscal.objects import (
    generic_microphone_manager, input_amplifier_manager, input_manager,
    inear_manager, measurement_microphone_manager, output_manager,
    speaker_manager, starship_manager, unity_manager, CalibrationManager,
)

from cftscal.plugins.workspace import WorkspaceSettings


def _merge_picker_list(obj, list_attr, source):
    '''
    Union a discovered ``source`` iterable into ``obj.<list_attr>`` and
    re-assign, so a picker's dropdown shows both disk-discovered options
    and anything the user added via "+" in previous sessions.

    Standard shape for every reference-picker's ``__init__``:

        _merge_picker_list(self, 'available_x', self.get_available_x())

    Also called from ``refresh_available()`` methods so widget-side
    observers can re-run the merge after a new acquisition.
    '''
    persisted = set(getattr(obj, list_attr))
    discovered = set(source)
    setattr(obj, list_attr, sorted(persisted | discovered))


class PersistentSettings(Atom):

    def get_persistence(self):
        config = get_tagged_values(self, 'persist')
        for k, v in config.items():
            if isinstance(v, PersistentSettings):
                config[k] = v.get_persistence()
            if v and isinstance(v, (list, tuple)) and isinstance(v[0], PersistentSettings):
                config[k] = [i.get_persistence() for i in v]
        return config

    def set_persistence(self, config):
        for name in get_tagged_members(self, 'persist'):
            if name in config:
                obj = getattr(self, name)
                if hasattr(obj, 'set_persistence'):
                    obj.set_persistence(config[name])
                else:
                    setattr(self, name, config[name])


class CalibrationSettings(Atom):

    settings_filename = Str()
    data_path = Typed(Path)

    def _default_data_path(self):
        from cftscal import CAL_ROOT
        return CAL_ROOT

    def _make_path(self, subfolder, group_path, *parts):
        '''
        Build an on-disk output path for a new calibration.

        Parameters
        ----------
        subfolder : str
            Plugin's calibration subfolder ("microphone", "speaker", …).
        group_path : str
            Target folder for the calibration, sourced from the currently
            selected target (InputSettings, OutputSettings,
            StarshipSettings, or InEarSettings) via its ``group_path``
            attribute.  Required — callers pass e.g. ``ai.group_path``
            explicitly.
        *parts : str
            Additional path segments; conventionally ``(device_name,
            filename)`` for the legacy layout where each calibration
            lives under a device-name folder.

        Behavior depends on ``group_path``:

        - Empty ("(root)") → legacy layout:
          ``data_path / subfolder / device_name / filename``.
        - Set (e.g. ``"Lab1"`` or ``"Lab1/MMM0"``) → the selected folder
          IS the object dir; only the filename (last part) is appended:
          ``data_path / subfolder / group_path / filename``.
        '''
        path = self.data_path / subfolder
        group = (group_path or '').strip().strip('/').strip('\\')
        if group:
            path = path / group
            if parts:
                # Only the filename (last part) is appended; the
                # device-name middle segment is dropped.
                path = path / parts[-1]
        else:
            for part in parts:
                path = path / part
        return path

    def save_config(self):
        file = get_config_folder() / 'cfts' / 'calibration' / self.settings_filename
        file = file.with_suffix('.json')
        file.parent.mkdir(exist_ok=True, parents=True)
        config = self.get_config()
        file.write_text(json.dumps(config, indent=2))

    def load_config(self):
        file = get_config_folder() / 'cfts' / 'calibration' / self.settings_filename
        file = file.with_suffix('.json')
        if not file.exists():
            return
        config = json.loads(file.read_text())
        if config is not None:
            self.set_config(config)

    def get_config(self):
        config = {}
        for k, v in get_tagged_values(self, 'persist').items():
            if isinstance(v, list):
                if len(v) == 0:
                    config[k] = []
                elif isinstance(v[0], PersistentSettings):
                    config[k] = {o.id: o.get_persistence() for o in v}
                    selected_member = self.members()[k].metadata.get('selected')
                    if selected_member is not None:
                        config[selected_member] = getattr(self, selected_member).id
                else:
                    raise ValueError('Unknown type')
            elif isinstance(v, PersistentSettings):
                config[k] = v.get_persistence()
            else:
                config[k] = v
        return config

    def set_config(self, config):
        for name, value in get_tagged_values(self, 'persist').items():
            if name not in config:
                continue
            if isinstance(value, list):
                if len(value) == 0:
                    continue
                elif isinstance(value[0], PersistentSettings):
                    for obj in value:
                        if obj.id in config[name]:
                            obj.set_persistence(config[name][obj.id])
                    selected_member = self.members()[name].metadata.get('selected')
                    if selected_member in config:
                        selected_id = config[selected_member]
                        for obj in value:
                            if obj.id == selected_id:
                                setattr(self, selected_member, obj)
            elif isinstance(value, PersistentSettings):
                value.set_persistence(config[name])
            else:
                setattr(self, name, config[name])

    def _run_cal(self, filename, experiment, env=None, metadata=None):
        settings = WorkspaceSettings()
        if env is None:
            env = {}
        env = {**os.environ, **env}

        # Substitute {date_time} ourselves so the directory name is known
        # up-front.  psi refuses to launch into a non-empty directory, so we
        # DO NOT create the directory here — psi creates it itself.  After
        # psi returns we either write metadata.json into it (if any data was
        # recorded) or prune it (if the user aborted before acquisition).
        now = dt.datetime.now()
        filename = Path(str(filename).replace(
            '{date_time}', now.strftime('%Y%m%d-%H%M%S')
        ))

        args = ['psi', experiment, str(filename)]
        if settings.hw_configuration == 'Sound Card':
            env.update({
                'PSI_SOUND_DEVICE_NAME': settings.selected_device,
                'PSI_SOUND_DEVICE_FS': str(int(settings.sample_rate)),
            })
            args.extend(['--io', 'psi.controller.engines.soundcard.standard_io.AutoSoundCardManifest'])
        else:
            args.extend(['--io', settings.hw_configuration])
        print(json.dumps(env, indent=2))
        print(' '.join(args))

        try:
            subprocess.check_output(args, env=env)
        finally:
            # Runs on both clean exit and subprocess failure.  Any raised
            # CalledProcessError still propagates after this cleanup.
            if filename.exists():
                if not any(filename.iterdir()):
                    shutil.rmtree(filename, ignore_errors=True)
                elif metadata is not None:
                    # psi/psidata may have already written their own
                    # metadata.json into this folder (run provenance:
                    # hostname/timestamp/version). Merge on top of it
                    # rather than clobbering it -- our fields are what
                    # cftscal's calibration classes read, but psi's are
                    # still worth keeping around.
                    meta_file = filename / 'metadata.json'
                    existing = {}
                    if meta_file.exists():
                        try:
                            existing = json.loads(meta_file.read_text())
                        except (OSError, json.JSONDecodeError):
                            existing = {}
                    meta = {
                        **existing,
                        'datetime': now.isoformat(),
                        **metadata,
                    }
                    meta_file.write_text(
                        json.dumps(meta, indent=2, sort_keys=True)
                    )


class GeneratorSettings(PersistentSettings):

    #: Name of generator.
    name = Str().tag(persist=True)

    #: List of available generators.
    available_generators = List().tag(persist=True)

    def _default_name(self):
        try:
            return self.available_generators[0]
        except IndexError:
            return ''


class PistonphoneSettings(GeneratorSettings):

    frequency = Float(1e3).tag(persist=True)
    level = Float(114).tag(persist=True)

    def get_env_vars(self):
        return {
            'CFTS_PISTONPHONE_LEVEL': str(self.level),
            'CFTS_PISTONPHONE_FREQUENCY': str(self.frequency),
        }


class SpeakerSettings(GeneratorSettings):

    #: Name of the actual speaker. This is not necessarily the same as the
    #: channel in the IO manifest. For example, one can connect a different
    #: speaker to the same channel, so the name may indicate which of
    #: several speakers available in the lab that is currently connected.
    #:
    #: Uses the inherited ``available_generators`` list for its picker —
    #: consistent with PistonphoneSettings and any other GeneratorSettings
    #: subclass.  What differs is the source: SpeakerSettings' ``__init__``
    #: merges in speaker_manager.list_names() so the dropdown shows
    #: existing calibrated speakers.
    name = Str().tag(persist=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.refresh_available()

    def refresh_available(self):
        _merge_picker_list(
            self, 'available_generators', self.get_available_generators(),
        )

    def get_available_generators(self):
        return sorted(speaker_manager.list_names())


class SensorSettings(PersistentSettings):
    '''
    Abstract base for :class:`SensorReference` and :class:`SensorDevice`.

    Exposes the two fields every ``InputSettings.sensor`` caller reads:
    ``name`` (the current selection — a calibration path for references,
    a device identifier for devices) and ``gain`` (preamp / power-supply
    gain applied during the recording).  Subclasses diverge on what
    ``name`` semantically identifies and how the picker's list is
    populated; ``InputSettings.sensor`` is ``Typed(SensorSettings)`` so
    either role can be plugged in per plugin.

    Not intended for direct instantiation — the two roles are
    ``SensorReference`` (loads existing calibrations by path) and
    ``SensorDevice`` (labels a physical device being calibrated).
    '''
    #: Current selection.  Interpretation depends on the subclass —
    #: a fully-qualified calibration path for SensorReference, a
    #: free-form device identifier for SensorDevice.
    name = Str().tag(persist=True)

    #: Preamp / power-supply gain in dB during the recording.  Same
    #: field on both roles — for a reference picker it captures the
    #: gain applied at experiment time; for a device it's the gain
    #: applied at calibration time (saved to metadata.json).
    gain = Float(0).tag(persist=True)

    def __init__(self, *args, **kwargs):
        if type(self) is SensorSettings:
            raise TypeError(
                'SensorSettings is abstract — construct SensorReference '
                '(to load existing calibrations by path) or SensorDevice '
                '(to label a physical device being calibrated).'
            )
        super().__init__(*args, **kwargs)


class SensorReference(SensorSettings):
    '''
    Picks an existing calibration to load in an experiment.

    ``name`` is a fully-qualified calibration path (e.g. ``"MMM0"`` or
    ``"Bramhall/MMM"``) that ``get_manager().get_object(name)`` resolves
    to a calibrated object.  ``available_references`` is the persistent
    picker list; on init we union disk-discovered paths (via
    ``get_available_references``) with anything the user has added via
    the SensorView "+" button in prior sessions.  Pair with
    :class:`SensorDevice` — pick one based on whether the plugin is
    loading an existing calibration or labelling a new one.

    Subclasses that only ever draw from one calibration type (e.g.
    :class:`MeasurementMicrophoneReference`) override ``get_manager()``.
    :class:`MultiTypeSensorReference` (below) instead switches which
    manager ``get_manager()`` returns based on a ``sensor_type``
    selection, for plugins (input_recording) where a channel might be
    wired to any of several differently-typed calibrations.
    '''
    #: Persistent list of calibration paths shown in the dropdown.
    available_references = List().tag(persist=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.refresh_available()

    def get_manager(self):
        return input_manager

    def get_available_references(self):
        return sorted(self.get_manager().list_names())

    def resolve_object(self):
        return self.get_manager().get_object(self.name)

    def refresh_available(self):
        '''Re-union disk-discovered references into the persistent list.
        Called from ``__init__``, from ``set_persistence()`` (below), and
        from widget observers after a new calibration is recorded.'''
        _merge_picker_list(
            self, 'available_references', self.get_available_references(),
        )

    def set_persistence(self, config):
        # PersistentSettings.set_persistence() (inherited) sets
        # available_references to exactly the persisted list, discarding
        # whatever refresh_available() had just merged in during
        # __init__ -- so anything discoverable now but not yet present
        # in a config saved before it existed (e.g. a newly-added
        # calibration type) would otherwise vanish from the picker on
        # every single load, not just be missing until the next
        # calibration is recorded. Re-merge after the persisted name
        # selection is restored so newly-available options aren't lost.
        super().set_persistence(config)
        self.refresh_available()


class MeasurementMicrophoneReference(SensorReference):

    def get_manager(self):
        return measurement_microphone_manager


class GenericMicrophoneReference(SensorReference):

    def get_manager(self):
        return generic_microphone_manager


class SensorDevice(SensorSettings):
    '''
    Tracks metadata about a physical sensor being calibrated.

    ``name`` is a free-form device identifier (serial number, asset tag,
    etc.) — written into ``metadata.json`` when a calibration is
    recorded, purely for tracking which physical unit was used.
    Multiple labs can share the same physical device via its ID while
    maintaining their own separate calibrations (each identified by
    :class:`SensorReference` paths); those two concepts are
    intentionally decoupled.

    ``available_devices`` is a purely user-managed list — the "+"
    button appends; no manager auto-populates.  Device IDs have no
    relationship to on-disk calibration paths.
    '''
    #: Persistent user-managed list of device identifiers.
    available_devices = List().tag(persist=True)


class InputAmplifierReference(SensorReference):

    #: Total linear gain applied by the amplifier.  Previously modeled as
    #: two orthogonal controls (a fine ``gain`` dial and a coarse
    #: ``gain_mult`` x10/x1000 switch, multiplied together as
    #: ``total_gain``) mirroring the amp's physical knobs -- but nothing
    #: downstream ever consumed the two factors separately (get_env_vars
    #: only ever sent their product), so the split just added a second
    #: dropdown to the UI for no benefit. ``gain`` now holds the combined
    #: value directly; the picker offers every value achievable via
    #: either physical switch position (see InputAmplifierView's `gains`).
    freq_lb = Float(10).tag(persist=True)
    freq_ub = Float(10000).tag(persist=True)
    #: Whether the amplifier's 60Hz notch filter is engaged. Historically
    #: modeled as 'input'/'output' (mirroring the physical switch's "IN
    #: circuit"/"OUT of circuit" labeling); renamed to the clearer 'on'/
    #: 'off' -- see migrate_metadata.py's _parse_input_amplifier for the
    #: legacy-value translation applied to old recordings' metadata.
    filt_60Hz = Enum('on', 'off').tag(persist=True)

    def get_manager(self):
        return input_amplifier_manager

    def get_env_vars(self, env_prefix, include_cal=True):
        return {
            f'{env_prefix}_GAIN': str(self.gain),
            f'{env_prefix}_FREQ_LB': str(self.freq_lb),
            f'{env_prefix}_FREQ_UB': str(self.freq_ub),
            f'{env_prefix}_FILT_60Hz': self.filt_60Hz,
        }


class MultiTypeSensorReference(SensorReference):
    '''
    Draws from any of several differently-typed managers rather than one
    fixed manager -- used by input_recording, where a channel might be
    wired to a measurement mic, generic mic, or starship probe mic (a
    starship's probe mic is a perfectly normal frequency-dependent
    calibration too).

    Picking ``sensor_type`` narrows ``available_references``/
    ``resolve_object()`` to that type's own manager, so names/paths never
    need cross-type disambiguation the way a single flat merged list
    would -- each of measurement_microphone_manager/
    generic_microphone_manager/starship_manager/unity_manager already
    produces correct ``folder/name`` paths entirely on its own.
    '''
    TYPE_MANAGERS = {
        'Meas. Mic.': measurement_microphone_manager,
        'Generic Mic.': generic_microphone_manager,
        'Starship': starship_manager,
        'Unity': unity_manager,
    }

    sensor_type = Enum(*TYPE_MANAGERS.keys()).tag(persist=True)

    def get_manager(self):
        return self.TYPE_MANAGERS[self.sensor_type]

    def switch_type(self, new_type):
        '''Explicit, UI-triggered type change -- clears the now-invalid
        name/option list for the old type. Deliberately not wired up as
        an ``_observe_sensor_type`` handler: ``set_persistence()``
        restores ``sensor_type`` via plain ``setattr`` alongside ``name``,
        and their relative order isn't guaranteed, so an observer-based
        clear could run *after* ``name`` was already correctly restored
        and wipe it back out. Keeping the clear-on-switch behavior in an
        explicit method callers opt into (the widget, on user action)
        avoids that hazard entirely.'''
        self.sensor_type = new_type
        self.name = ''
        self.available_references = []
        self.refresh_available()


class InputSettings(PersistentSettings):

    @property
    def id(self):
        return self.input_name

    #: Name of input channel as defined in IO manifest. This is not supposed to
    #: be settable.
    input_name = Str().tag(persist=True)

    #: Label of input channel as defined in IO manifest
    input_label = Str()

    #: Sensor attached to input channel — either a SensorReference (for
    #: plugins that pick an existing calibration) or a SensorDevice (for
    #: plugins that label a physical device being calibrated).  Plugins
    #: specify the concrete type via the ``sensor=`` constructor arg.
    sensor = Typed(SensorSettings, factory=SensorReference).tag(persist=True)

    #: Per-channel target folder for new calibrations.  Different input
    #: channels can be pointed at different labs/studies, so switching
    #: channels in the plugin view swaps in that channel's saved value.
    group_path = Str().tag(persist=True)

    def get_env_vars(self, include_cal=True, env_prefix='CFTS_INPUT'):
        # NOTE: the bare `env_prefix` key below is only meaningful to the
        # old single-channel initialize_input() handler
        # (cftscal/paradigms/objects.enaml). input_recording's
        # multi-channel run_input_recording() calls this once per active
        # channel and merges the results, so that bare key ends up
        # holding whichever channel's call happened last -- harmless,
        # since the multi-channel paradigm side only reads
        # CFTS_INPUT_CHANNELS and the per-channel-namespaced keys below.
        env = {
            env_prefix: self.input_name,
            f'{env_prefix}_{self.input_name.upper()}_GAIN': str(self.sensor.gain),
        }
        if include_cal:
            # Only ever reached for a SensorReference-backed sensor --
            # every SensorDevice-based caller (e.g. microphone's
            # calibrate-a-new-device channels) already passes
            # include_cal=False, since there's no existing calibration
            # to resolve yet.
            obj = self.sensor.resolve_object()
            cal = obj.get_current_calibration()
            env[f'{env_prefix}_{self.input_name.upper()}'] = cal.to_string()
        return env


class OutputSettings(PersistentSettings):

    @property
    def id(self):
        return self.output_name

    #: Name of output as defined in IO manifest
    output_name = Str()

    #: Label of output as defined in IO manifest
    output_label = Str()

    #: Generator attached to output
    generator = Typed(GeneratorSettings, ()).tag(persist=True)

    #: Per-output target folder for new calibrations.  Same semantics as
    #: InputSettings.group_path — the plugin view's picker swaps in
    #: whichever output is currently selected.
    group_path = Str().tag(persist=True)

    def get_env_vars(self, include_cal=True, env_prefix='CFTS_OUTPUT'):
        env = {
            env_prefix: self.output_name,
        }
        if include_cal:
            generator = output_manager.get_object(self.generator.name)
            cal = generator.get_current_calibration()
            env[f'{env_prefix}_{self.output_name.upper()}'] = cal.to_string()
        return env


class StarshipSettings(PersistentSettings):

    @property
    def id(self):
        return self.connection_name

    connection_name = Str()
    connection_label = Str()

    starship = Str().tag(persist=True)
    gain = Float(40).tag(persist=True)

    #: Per-starship target folder for new calibrations.  Same semantics
    #: as InputSettings.group_path — swaps when the plugin's selected
    #: starship connection changes.
    group_path = Str().tag(persist=True)

    #: Persistent list of starship names, populated via the standard
    #: merge pattern.  Subclasses override ``get_available_starships``
    #: to change the source (e.g. InEarSettings combines two managers).
    available_starships = List().tag(persist=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.refresh_available()

    def refresh_available(self):
        _merge_picker_list(
            self, 'available_starships', self.get_available_starships(),
        )

    def get_available_starships(self):
        return sorted(starship_manager.list_names(loader_label='CFTSStarshipLoader'))

    def _default_starship(self):
        try:
            return self.available_starships[0]
        except IndexError:
            return ''

    def get_env_vars(self, include_cal=True):
        env = {
            'CFTS_TEST_STARSHIP': self.connection_name,
            f'CFTS_STARSHIP_{self.connection_name.upper()}_GAIN': str(self.gain),
        }
        if include_cal:
            starship = starship_manager.get_object(self.starship)
            cal = starship.get_current_calibration()
            env[f'CFTS_STARSHIP_{self.connection_name.upper()}'] = cal.to_string()
        return env


class InEarSettings(StarshipSettings):

    #: Coupler/ear-mold identifier (e.g. "C1") -- historically called
    #: "ear", but it's really identifying the coupler, not an anatomical
    #: ear or animal. Which output of that coupler this recording used
    #: is now the separate `output` field below, rather than encoded as
    #: a "-secondary" suffix baked into this string.
    coupler = Str().tag(persist=True)

    #: Whether this recording is of the coupler's primary or secondary
    #: output.
    output = Enum('primary', 'secondary').tag(persist=True)

    #: Persistent list of coupler identifiers, populated via the standard
    #: merge pattern.  Same merge pattern as available_starships.
    available_couplers = List().tag(persist=True)

    def refresh_available(self):
        # Chain to StarshipSettings' refresh (which will re-merge
        # available_starships via polymorphic dispatch to *our*
        # get_available_starships), then extend with the coupler list.
        # Any future work added to StarshipSettings.refresh_available is
        # picked up automatically.
        super().refresh_available()
        _merge_picker_list(
            self, 'available_couplers', self.get_available_couplers(),
        )

    def get_available_couplers(self):
        return sorted(inear_manager.get_property('coupler'))

    def get_available_starships(self):
        # Override — inear picker combines both managers' names.
        return sorted(
            starship_manager.list_names() + inear_manager.list_names()
        )
