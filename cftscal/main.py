from psi.application import configure_logging
#configure_logging('DEBUG')

# psi.core.app_id rather than psi.launcher.api: the latter pulls in .enaml
# modules and so needs the enaml import hook active, which this needs no part
# of.
from psi.core.app_id import set_app_id

import importlib
import logging

# NOTE: do NOT set pg.setConfigOptions(useOpenGL=True) here. It was
# previously enabled to make cftscal's result plots smoother, on the
# assumption that it stayed isolated to cftscal's own process and never
# reached psiexperiment's plotting code (which crashes with it on some
# systems) since `psi` always runs as a separate subprocess. That
# assumption is wrong for PGCanvas specifically (psi/data/plots_manifest.py
# in psiexperiment): every cftscal plugin view imports and instantiates it
# directly, in-process, to render its result plot -- so useOpenGL=True here
# reaches it too. On at least one real system this reproducibly segfaults
# (Windows access violation in pg.GraphicsView.useOpenGL) the moment any
# plugin workspace is selected, killing cftscal with no error message. See
# the reload_plugins()/workspace_factory() call path in
# cftscal/plugins/manifest.enaml for where PGCanvas actually gets realized.

import enaml
from enaml.application import deferred_call
from enaml.workbench.ui.api import UIWorkbench

from .paradigms.default_state import seed_all_default_state

UI_PLUGIN = 'enaml.workbench.ui'
CORE_PLUGIN = 'enaml.workbench.core'

log = logging.getLogger(__name__)


def set_application_icon():
    '''
    Give the whole application the cftscal icon, before any window shows.

    The main window's own icon (Branding in plugins/manifest.enaml) wasn't
    enough on its own: Windows drew the taskbar button before that icon
    reached it, and only picked it up when a workspace was loaded. The
    application icon is what Qt uses from the start, and for any window
    that doesn't set its own.
    '''
    from qtpy.QtWidgets import QApplication
    from .plugins.branding import load_app_qicon
    QApplication.instance().setWindowIcon(load_app_qicon())


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
            from .plugins.manifest import HOME_WORKSPACE, check_legacy_settings

        self.register(CoreManifest())
        self.register(UIManifest())
        ui = self.get_plugin(UI_PLUGIN)
        core = self.get_plugin(CORE_PLUGIN)

        set_application_icon()
        ui.show_window()
        # Once the event loop is running, since it may ask the user
        # something, and before the workspace below is selected, so that
        # workspace starts from the imported settings if there are any.
        deferred_call(check_legacy_settings, self)
        # The workspace named on the command line, or Home.
        workspace = f'{obj}.workspace' if obj is not None else HOME_WORKSPACE
        deferred_call(core.invoke_command,
                      'enaml.workbench.ui.select_workspace',
                      {'workspace': workspace})

        ui.start_application()
        self.unregister(UI_PLUGIN)
        self.unregister(CORE_PLUGIN)


def main():
    import argparse
    parser = argparse.ArgumentParser('cfts-cal')
    parser.add_argument('obj', nargs='?')
    args = parser.parse_args()

    # Before the Qt application is created in `workbench.run`, and distinct
    # from the `psi.psi` that the calibration subprocesses claim, so cftscal
    # and the experiments it launches get their own taskbar buttons.
    set_app_id('psi.cftscal')

    seed_all_default_state()

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
                    # A plugin whose hardware is not attached is simply not
                    # shown. This is the normal case on most machines, so it
                    # is logged rather than printed -- printing it to the
                    # console made it look like an error had occurred.
                    log.debug('%s is not available', module_name)
            except ModuleNotFoundError:
                log.debug('Could not load %s.%s plugin', module_name,
                          class_name)

    workbench.run(args.obj)
