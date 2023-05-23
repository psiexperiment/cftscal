import enaml
from enaml.application import Application, deferred_call
from enaml.workbench.ui.api import UIWorkbench
import enamlx
enamlx.install()

UI_PLUGIN = 'enaml.workbench.ui'
CORE_PLUGIN = 'enaml.workbench.core'


class CalibrationWorkbench(UIWorkbench):

    def run(self, obj):
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
    parser.add_argument('obj', nargs='?', default='starship')
    args = parser.parse_args()

    with enaml.imports():
        from .plugins.manifest import CalibrationManifest
        from .plugins.microphone.manifest import MicrophoneManifest
        from .plugins.starship.manifest import StarshipManifest
        from .plugins.speaker.manifest import SpeakerManifest
        from .plugins.inear.manifest import InEarManifest

    workbench = CalibrationWorkbench()
    workbench.register(CalibrationManifest())
    workbench.register(MicrophoneManifest())
    workbench.register(StarshipManifest())
    workbench.register(SpeakerManifest())
    workbench.register(InEarManifest())
    workbench.run(args.obj)
