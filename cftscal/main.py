from psi.application import configure_logging
#configure_logging('DEBUG')

import importlib

import enaml
from enaml.application import deferred_call
from enaml.workbench.ui.api import UIWorkbench
import enamlx
enamlx.install()

UI_PLUGIN = 'enaml.workbench.ui'
CORE_PLUGIN = 'enaml.workbench.core'


class CalibrationWorkbench(UIWorkbench):

    def run(self, obj=None):
        """
        Run the calibration workbench application.  This method will load the
        core and ui plugins and start the main application event loop. This is
        a blocking call which will return when the application event loop
        exits.
        """
        with enaml.imports():
            from enaml.workbench.core.core_manifest import CoreManifest
            from enaml.workbench.ui.ui_manifest import UIManifest

        self.register(CoreManifest())
        self.register(UIManifest())
        ui = self.get_plugin(UI_PLUGIN)
        core = self.get_plugin(CORE_PLUGIN)

        ui.show_window()
        if obj is not None:
            deferred_call(core.invoke_command,
                        'enaml.workbench.ui.select_workspace',
                        {'workspace': f'{obj}.workspace'}
                        )

        ui.start_application()
        self.unregister(UI_PLUGIN)
        self.unregister(CORE_PLUGIN)


def main():
    import argparse
    parser = argparse.ArgumentParser('cfts-cal')
    parser.add_argument('obj', nargs='?')
    parser.add_argument('--load-all', action='store_true')
    args = parser.parse_args()

    with enaml.imports():
        from .plugins.manifest import CalibrationManifest
    workbench = CalibrationWorkbench()
    workbench.register(CalibrationManifest())

    to_register = [
        #('cftscal.plugins.input_amplifier.manifest', 'InputAmplifierManifest'),
        ('cftscal.plugins.microphone.manifest', 'MeasurementMicrophoneManifest'),
        #('cftscal.plugins.input_recording.manifest', 'InputRecordingManifest'),
        ('cftscal.plugins.ir_sensor.manifest', 'IRSensorManifest'),
        #('cftscal.plugins.starship.manifest', 'StarshipManifest'),
        ('cftscal.plugins.speaker.manifest', 'SpeakerManifest'),
        #('cftscal.plugins.inear.manifest', 'InEarManifest'),
        #('cftscal.plugins.microphone_generic.manifest', 'GenericMicrophoneManifest'),
    ]

    with enaml.imports():
        for module_name, class_name in to_register:
            try:
                module = importlib.import_module(module_name)
                instance = getattr(module, class_name)()
                if instance.available:
                    workbench.register(getattr(module, class_name)())
                else:
                    print(f'{module_name} is not available')
            except ModuleNotFoundError as e:
                print(f'Could not load {module_name}.{class_name} plugin')

    workbench.run(args.obj)
