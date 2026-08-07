import logging
log = logging.getLogger(__name__)

import json
from pathlib import Path

from atom.api import Atom, Dict, Enum, Float, List, Property, Str, Typed, Value

from psi import get_config_folder

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

    # Optional callback fired after save_config() writes the JSON file.
    # Set by the caller (e.g. show_workspace_settings) to trigger plugin reload.
    _on_save = Value()
    selected_device = Str()
    selected_device_info = Str()
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
        # Ensure sample rates are populated even if no observer fired (e.g.,
        # first run where selected_device comes from the default, not setattr).
        self._update_sample_rates()

    def _default_data_path(self):
        from cftscal import CAL_ROOT
        return CAL_ROOT

    def _default_available_devices(self):
        return [dict(d) for d in sd.query_devices()]

    def _default_selected_device(self):
        devices = self.available_devices
        if not devices:
            return ''
        try:
            default_idx = sd.default.device[0]
            if 0 <= default_idx < len(devices):
                return devices[default_idx]['name']
        except Exception:
            pass
        return devices[0]['name']

    def _observe_selected_device(self, event):
        self._update_sample_rates()

    def _device_index(self):
        """Return the sounddevice index for the currently selected device."""
        for i, d in enumerate(self.available_devices):
            if d['name'] == self.selected_device:
                return i
        return None

    def _update_sample_rates(self):
        if not self.selected_device:
            self.sample_rate = 0.0
            self.available_sample_rates = []
            self.selected_device_info = ''
            return
        idx = self._device_index()
        if idx is None:
            self.sample_rate = 0.0
            self.available_sample_rates = []
            self.selected_device_info = ''
            return
        d = self.available_devices[idx]
        n_in = d['max_input_channels']
        n_out = d['max_output_channels']
        self.selected_device_info = f'{n_in} input, {n_out} output'
        rates = get_supported_samplerates(idx)
        # Update sample_rate BEFORE available_sample_rates so the two-way
        # ObjectCombo binding never sees a selected value absent from the items.
        new_rate = self.sample_rate if self.sample_rate in rates else (rates[0] if rates else 0.0)
        self.sample_rate = new_rate
        self.available_sample_rates = rates

    def save_config(self):
        file = get_config_folder() / 'cfts' / 'workspace.json'
        file.parent.mkdir(exist_ok=True, parents=True)
        config = {
            'data_path': str(self.data_path),
            'hw_mode': self.hw_mode,
            'custom_io_path': self.custom_io_path,
            'custom_io_class': self.custom_io_class,
            'selected_device': self.selected_device,
            'sample_rate': self.sample_rate,
            'enabled_plugins': list(self.enabled_plugins),
        }
        file.write_text(json.dumps(config, indent=2))
        if self._on_save is not None:
            self._on_save()

    def load_config(self):
        file = get_config_folder() / 'cfts' / 'workspace.json'
        if not file.exists():
            return
        config = json.loads(file.read_text())
        try:
            for k, v in config.items():
                if k == 'data_path':
                    v = Path(v)
                if k == 'hw_configuration':
                    # Back-compat: configs saved before hw_mode/
                    # custom_io_path/custom_io_class replaced the single
                    # free-form hw_configuration string (picked from a
                    # flat list of every discovered IO file/module path).
                    self._load_legacy_hw_configuration(v)
                    continue
                setattr(self, k, v)
        except Exception as e:
            log.warning(f'Error loading workspace config: {e}')

    def _load_legacy_hw_configuration(self, value):
        if value == 'Sound Card':
            self.hw_mode = 'Sound Card'
            return
        self.hw_mode = 'Custom (Enaml IO manifest)'
        path, sep, klass = value.partition('::')
        self.custom_io_path = path
        self.custom_io_class = klass if sep else 'IOManifest'


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
