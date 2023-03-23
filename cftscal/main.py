import enaml
from enaml.workbench.ui.api import UIWorkbench


def main():
    import enamlx
    enamlx.install()
    with enaml.imports():
        from .plugins.manifest import CalibrationManifest
        from .plugins.microphone.manifest import MicrophoneManifest
        from .plugins.starship.manifest import StarshipManifest
        from .plugins.speaker.manifest import SpeakerManifest
    workbench = UIWorkbench()
    workbench.register(CalibrationManifest())
    workbench.register(MicrophoneManifest())
    workbench.register(StarshipManifest())
    workbench.register(SpeakerManifest())
    workbench.run()


if __name__ == '__main__':
    main()
