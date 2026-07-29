import logging
log = logging.getLogger(__name__)

import json
from pathlib import Path

from atom.api import Atom, Dict, Float, List, Str, Typed, Value

from psi import get_config_folder
from psi.application import list_io

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
    hw_configuration = Str()

    # Optional callback fired after save_config() writes the JSON file.
    # Set by the caller (e.g. show_workspace_settings) to trigger plugin reload.
    _on_save = Value()
    selected_device = Str()
    selected_device_info = Str()
    sample_rate = Float()

    available_hw_configurations = List(Str())
    available_devices = List(Dict())
    available_sample_rates = List(Float())

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.load_config()
        # Ensure sample rates are populated even if no observer fired (e.g.,
        # first run where selected_device comes from the default, not setattr).
        self._update_sample_rates()

    def _default_data_path(self):
        from cftscal import CAL_ROOT
        return CAL_ROOT

    def _default_hw_configuration(self):
        configs = self.available_hw_configurations
        return configs[0] if configs else ''

    def _default_available_hw_configurations(self):
        configs = [str(i) for i in list_io()]
        configs.append('Sound Card')
        return sorted(configs)

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
            'hw_configuration': self.hw_configuration,
            'selected_device': self.selected_device,
            'sample_rate': self.sample_rate,
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
                setattr(self, k, v)
        except Exception as e:
            log.warning(f'Error loading workspace config: {e}')


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
