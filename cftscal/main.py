from psi.application import configure_logging
#configure_logging('DEBUG')

import importlib

# OpenGL rendering makes cftscal's result plots noticeably smoother, but it
# crashes some plots in psiexperiment during live acquisition -- so this is
# only enabled here, in cftscal's own process, never in the `psi` subprocess
# that runs calibrations (a separate process with its own pyqtgraph state,
# unaffected by this).
import pyqtgraph as pg
pg.setConfigOptions(useOpenGL=True)

import enaml
from enaml.application import deferred_call
from enaml.workbench.ui.api import UIWorkbench

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
    args = parser.parse_args()

    with enaml.imports():
        from .plugins.manifest import CalibrationManifest, TO_REGISTER
    workbench = CalibrationWorkbench()
    workbench.register(CalibrationManifest())

    with enaml.imports():
        for rank, (module_name, class_name) in enumerate(TO_REGISTER):
            try:
                module = importlib.import_module(module_name)
                instance = getattr(module, class_name)(rank=rank)
                if instance.available:
                    workbench.register(getattr(module, class_name)(rank=rank))
                else:
                    print(f'{module_name} is not available')
            except ModuleNotFoundError as e:
                print(f'Could not load {module_name}.{class_name} plugin')

    workbench.run(args.obj)
