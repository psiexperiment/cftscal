import logging
log = logging.getLogger(__name__)

import json
from pathlib import Path

from atom.api import Atom, Dict, Float, List, Str, Typed, set_default

from psi import get_config_folder


import sounddevice as sd


def get_supported_samplerates(device=None):
    # Common sampling rates to test
    standard_rates = [44100, 48000, 88200, 96000, 192000]
    supported_rates = []
    for rate in standard_rates:
        try:
            # Tests if the specific device and rate are compatible
            sd.check_input_settings(device=device, samplerate=rate)
            supported_rates.append(rate)
        except Exception:
            pass
    return supported_rates


class WorkspaceSettings(Atom):

    data_path = Typed(Path)
    hardware_configuration = Str()
    selected_device = Str()
    sample_rate = Float()
    available_configurations = List(Str())
    available_devices = List(Dict())
    available_sample_rates = List(Float())

    def _default_data_path(self):
        from cftscal import CAL_ROOT
        return CAL_ROOT

    def _default_hardware_configuration(self):
        return 'default'

    def _default_available_configurations(self):
        config_folder = get_config_folder() / 'io'
        if not config_folder.exists():
            return ['default']
        configs = [f.stem for f in config_folder.glob('*.enaml')]
        if 'default' not in configs:
            configs.append('default')
        return sorted(configs)

    def _default_available_devices(self):
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            return [dict(d) for d in devices]
        except ImportError:
            log.warning('sounddevice not installed. Cannot list devices.')
            return []
        except Exception as e:
            log.warning(f'Error querying devices: {e}')
            return []

    def _observe_selected_device(self, event):
        self._update_sample_rates()

    def _update_sample_rates(self):
        if not self.selected_device:
            self.available_sample_rates = []
            return
        self.available_sample_rates = get_supported_samplerates(self.selected_device)

    def save_config(self):
        file = get_config_folder() / 'cfts' / 'workspace.json'
        file.parent.mkdir(exist_ok=True, parents=True)
        config = {
            'data_path': str(self.data_path),
            'hardware_configuration': self.hardware_configuration,
            'selected_device': self.selected_device,
            'sample_rate': self.sample_rate,
        }
        file.write_text(json.dumps(config, indent=2))

    def load_config(self):
        file = get_config_folder() / 'cfts' / 'workspace.json'
        if not file.exists():
            return
        try:
            config = json.loads(file.read_text())
            self.data_path = Path(config.get('data_path', self.data_path))
            self.hardware_configuration = config.get('hardware_configuration', self.hardware_configuration)
            self.selected_device = config.get('selected_device', '')
            self.sample_rate = config.get('sample_rate', 0.0)
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
