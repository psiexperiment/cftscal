import logging
log = logging.getLogger(__name__)

from pathlib import Path

from atom.api import (
    Atom, Dict, Enum, Float, List, Property, Str, Typed, Value
)

from psi import (
    config_source, get_config as get_setting, get_config_file,
    save_config as save_settings
)

# Belt-and-suspenders: cftscal/__init__.py already sets this before any
# cftscal.* module (including this one) can be imported, but set it again
# right at the sounddevice import site so this module stays correct even if
# imported through some path that bypasses the package __init__. Mirrors the
# per-module pattern in psi.controller.engines.soundcard. Idempotent.
import os
os.environ['SD_ENABLE_ASIO'] = '1'

import sounddevice as sd


def get_supported_samplerates(device=None):
    standard_rates = [44100, 48000, 88200, 96000, 192000]
    supported_rates = []
    for rate in standard_rates:
        try:
            sd.check_input_settings(device=device, samplerate=rate)
            supported_rates.append(rate)
        except Exception:
            pass
    return supported_rates


class WorkspaceSettings(Atom):

    data_path = Typed(Path)

    #: Either the system's audio interface ("Sound Card", configured via
    #: selected_device/sample_rate below) or a custom psiexperiment IO
    #: manifest .enaml file (custom_io_path/custom_io_class below) -- e.g.
    #: for NI-DAQ, TDT, or other hardware with its own IO manifest.
    hw_mode = Enum('Sound Card', 'Custom (Enaml IO manifest)')

    #: Path to the .enaml file containing the custom IO manifest, and the
    #: name of the enamldef class within it to load. Only meaningful when
    #: hw_mode == 'Custom (Enaml IO manifest)'.
    custom_io_path = Str()
    custom_io_class = Str('IOManifest')

    #: The actual string passed to psi's ``--io`` argument / cftscal's
    #: ``load_io_manifest()`` -- derived from hw_mode and (when custom)
    #: custom_io_path/custom_io_class rather than stored directly, so
    #: there's a single place composing it. See _run_cal in
    #: cftscal/plugins/settings.py and io_manifest() in cftscal/util.py,
    #: the only two readers.
    hw_configuration = Property()

    def _get_hw_configuration(self):
        if self.hw_mode == 'Sound Card':
            return 'Sound Card'
        if not self.custom_io_path:
            return ''
        klass = self.custom_io_class.strip() or 'IOManifest'
        return f'{self.custom_io_path}::{klass}'

    # Optional callback fired after save_config() writes the settings.
    # Set by the caller (e.g. show_workspace_settings) to trigger plugin reload.
    _on_save = Value()

    #: Durable identity of the selected audio device: its name plus the host
    #: API it belongs to. This -- NOT the PortAudio index -- is what we persist
    #: and (combined into selected_device_query) hand off to the psi
    #: subprocess. The index is unstable: it shifts whenever the set of
    #: devices/drivers changes, which can happen between sessions, or even
    #: between launching cftscal and starting a calibration. name + host API is
    #: stable across those reshuffles and is unambiguous where a bare name is
    #: not (the same device exposed through several drivers reports colliding
    #: names; the host API distinguishes them, and an exact "<name>, <host
    #: API>" match sidesteps sounddevice's substring matcher, which otherwise
    #: raises "Multiple devices found" when a truncated name -- e.g. MME's
    #: 31-char limit -- is a substring of another driver's fuller name).
    selected_device_name = Str()
    selected_device_hostapi = Str()
    selected_device_info = Str()

    #: Fully-qualified "<name>, <host API>" query string handed to the psi
    #: subprocess (as PSI_SOUND_DEVICE_NAME). sounddevice matches this exactly
    #: against its own "<name>, <host API>" per device, so it resolves to the
    #: one intended device even when the bare name substring-matches several
    #: (see _get_device_id in sounddevice: an exact full-string match wins
    #: over ambiguous substring matches). The ", " separator must match
    #: sounddevice's exactly. Falls back to the bare name if the host API is
    #: unknown.
    selected_device_query = Property()

    def _get_selected_device_query(self):
        if self.selected_device_hostapi:
            return f'{self.selected_device_name}, {self.selected_device_hostapi}'
        return self.selected_device_name

    #: Transient, in-memory only: the ``available_devices`` entry (a device
    #: dict) currently highlighted in the picker, or None when the saved
    #: device isn't present right now. This only drives the combo selection,
    #: the sample-rate lookup, and the channel-count label -- it is never
    #: persisted or handed off. The durable identity (selected_device_name +
    #: selected_device_hostapi, above) is the source of truth; this is just
    #: whichever live device dict currently matches it.
    selected_device = Value()

    sample_rate = Float()

    available_devices = List(Dict())
    available_sample_rates = List(Float())

    #: ids of plugins to force-load regardless of what their
    #: settings_config hardware probes report -- e.g. so a review-only
    #: machine without a sound card can still show (in view-only mode)
    #: the plugins it needs to browse existing calibrations. Empty by
    #: default: same behavior as today, hardware-detection only. See
    #: _CalibrationPluginManifest._get_available in
    #: cftscal/plugins/manifest.enaml, the only place this is read.
    enabled_plugins = List(Str())

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.load_config()
        # On a fresh install (no saved config) there is no durable identity
        # yet -- seed it from the default device so save_config persists a
        # real device, not an empty string. Observers don't fire for Atom
        # defaults, so this can't be left to _observe_selected_device.
        if not self.selected_device_name:
            self._sync_identity_from_selection()
        # Ensure sample rates are populated even if no observer fired (e.g.,
        # first run where selected_device comes from the default, not a
        # setattr in load_config).
        self._update_sample_rates()

    def _default_data_path(self):
        # Resolved on demand rather than read from a module-level constant
        # captured at import: the old constant never changed after startup,
        # so picking a new folder in the GUI left every later reader on the
        # previous path until the process was restarted.
        return Path(get_setting('CFTSCAL_ROOT'))

    def _default_available_devices(self):
        return [dict(d) for d in sd.query_devices()]

    def _default_selected_device(self):
        devices = self.available_devices
        if not devices:
            return None
        try:
            default_idx = sd.default.device[0]
            if 0 <= default_idx < len(devices):
                return devices[default_idx]
        except Exception:
            pass
        return devices[0]

    def _hostapi_name(self, device):
        """Host API name for a sounddevice device dict ('' if unknown)."""
        try:
            return sd.query_hostapis(device['hostapi'])['name']
        except Exception:
            return ''

    def device_label(self, device):
        """Human-readable label for a device dict ('' for None).

        Includes the host API name so that the same physical device exposed
        through multiple drivers can be told apart in the picker.
        """
        if not device:
            return ''
        hostapi = self._hostapi_name(device)
        return f"{device['name']} ({hostapi})" if hostapi else device['name']

    def _sync_identity_from_selection(self):
        """Capture the selected device's durable identity (name + host API).

        Called whenever the picker selection changes so that name/host API --
        which are what we persist and hand off -- always reflect the user's
        current choice. Only updates on a real selection: a transient None
        (e.g. the saved device isn't present) must not wipe out the identity.
        """
        d = self.selected_device
        if d:
            self.selected_device_name = d['name']
            self.selected_device_hostapi = self._hostapi_name(d)

    def _observe_selected_device(self, event):
        self._sync_identity_from_selection()
        self._update_sample_rates()

    def _update_sample_rates(self):
        d = self.selected_device
        if not d:
            self.sample_rate = 0.0
            self.available_sample_rates = []
            self.selected_device_info = ''
            return
        n_in = d['max_input_channels']
        n_out = d['max_output_channels']
        self.selected_device_info = f'{n_in} input, {n_out} output'
        rates = get_supported_samplerates(self.selected_device_query)
        # Update sample_rate BEFORE available_sample_rates so the two-way
        # ObjectCombo binding never sees a selected value absent from the items.
        new_rate = self.sample_rate if self.sample_rate in rates else (rates[0] if rates else 0.0)
        self.sample_rate = new_rate
        self.available_sample_rates = rates

    #: Setting name for each persisted member. These used to live in the
    #: workspace's own workspace.json, which gave the calibration folder
    #: two homes: the JSON quietly outranked the CFTSCAL_ROOT environment
    #: variable, so setting the variable on a configured rig did nothing.
    #: They are ordinary settings now, resolved like any other.
    SETTINGS = {
        'data_path': 'CFTSCAL_ROOT',
        'hw_mode': 'CFTSCAL_HW_MODE',
        'custom_io_path': 'CFTSCAL_CUSTOM_IO_PATH',
        'custom_io_class': 'CFTSCAL_CUSTOM_IO_CLASS',
        # The durable device identity (name + host API), never an index --
        # an index is meaningless across sessions. See load_config, which
        # re-finds the live device from these on startup.
        'selected_device_name': 'CFTSCAL_DEVICE_NAME',
        'selected_device_hostapi': 'CFTSCAL_DEVICE_HOSTAPI',
        'sample_rate': 'CFTSCAL_SAMPLE_RATE',
        'enabled_plugins': 'CFTSCAL_ENABLED_PLUGINS',
    }

    def save_config(self):
        updates = {}
        for member, setting in self.SETTINGS.items():
            value = getattr(self, member)
            if isinstance(value, Path):
                value = str(value)
            elif isinstance(value, list):
                value = list(value)
            updates[setting] = value
        save_settings(updates)
        if self._on_save is not None:
            self._on_save()

    def overridden_settings(self):
        '''
        Members whose value is being forced by the environment.

        Saving one of these succeeds but changes nothing the application
        then reads, so the view disables the control and names the
        variable responsible rather than letting the user write into a
        void and wonder why nothing happened.
        '''
        return {member: setting for member, setting in self.SETTINGS.items()
                if config_source(setting) == 'environment'}

    def load_config(self):
        # Each setting is applied on its own. Reading them in one try block
        # meant that a single failure -- an unparseable configuration file,
        # say -- silently abandoned every setting after it and left the
        # workspace on its built-in defaults, which looks exactly like a
        # machine that was never configured.
        for member, setting in self.SETTINGS.items():
            try:
                setattr(self, member, get_setting(setting))
            except Exception as e:
                log.exception('Could not apply %s from %s: %s',
                              setting, get_config_file(), e)

        # Resolve the live device from the durable identity, which is set
        # first so that it survives a device being absent right now; the
        # device dict only drives the picker and the sample rate list.
        if self.selected_device_name:
            try:
                self.selected_device = self._resolve_device(
                    self.selected_device_name, self.selected_device_hostapi)
            except Exception as e:
                log.exception('Could not resolve the saved audio device: %s', e)

    def _resolve_device(self, name, hostapi):
        """Return the current device dict matching a saved identity, or None.

        Matches ``name`` and ``hostapi`` exactly against the current device
        list. Exact matching -- rather than sounddevice's substring matcher --
        is what makes this unambiguous: it distinguishes a truncated MME name
        from the fuller name of the same device under another driver.

        When ``hostapi`` is set (the normal case) it must match: we will NOT
        fall back to a same-named device on a *different* host API, since that
        would silently switch the user's selection to a different driver. A
        blank ``hostapi`` only happens for legacy name-only configs, where a
        best-effort match by name is all we can do.

        Returns None if the device can't be found (e.g. it was unplugged),
        leaving the durable identity intact for when it reappears.
        """
        for d in self.available_devices:
            if d['name'] == name and (not hostapi
                                      or self._hostapi_name(d) == hostapi):
                return d
        log.warning('Saved audio device %r (host API %r) not found',
                    name, hostapi)
        return None


if __name__ == '__main__':
    #print(get_supported_samplerates(7))
    settings = WorkspaceSettings()
    import enaml
    from enaml.qt.qt_application import QtApplication
    app = QtApplication()

    with enaml.imports():
        from .workspace_view import WorkspaceSettingsView
        view = WorkspaceSettingsView(settings=settings)
        view.show()

    app.start()
