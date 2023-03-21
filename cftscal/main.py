import enaml
from enaml.workbench.ui.api import UIWorkbench


def main():
    import enamlx
    enamlx.install()
    with enaml.imports():
        from .calibration_plugin import CalibrationManifest
        from .microphone.plugin import MicrophoneManifest
    workbench = UIWorkbench()
    workbench.register(CalibrationManifest())
    workbench.register(MicrophoneManifest())
    workbench.run()


if __name__ == '__main__':
    main()
