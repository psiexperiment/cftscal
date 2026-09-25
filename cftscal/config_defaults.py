'''
Default values for every cftscal setting.

Registered with :func:`psi.config.register_defaults` when ``cftscal`` is
imported, so ``get_config('CFTSCAL_ROOT')`` resolves the same way as any
psi setting: default, then ``config.toml``, then the environment.

cftscal is end-user installable, and the point of putting defaults here
rather than in a shipped configuration file is that an install which
configures nothing still runs. The GUI writes what the user picks into
``config.toml``; nothing has to exist beforehand.
'''
from pathlib import Path


DEFAULTS = {
    #: Where calibration files are stored. Named CFTSCAL_ROOT rather than
    #: CAL_ROOT because cftscal owns this: psiexperiment used to emit a
    #: CAL_ROOT key into its config file that nothing ever read, while
    #: cftscal read CFTSCAL_ROOT from the environment.
    'CFTSCAL_ROOT': lambda: Path('~/Documents/cftscal').expanduser(),

    #: Either the system's audio interface ("Sound Card") or a custom
    #: psiexperiment IO manifest (NI-DAQ, TDT, and anything else with its
    #: own manifest).
    'CFTSCAL_HW_MODE': lambda: 'Sound Card',

    #: Path to the .enaml file holding a custom IO manifest, and the name
    #: of the enamldef within it. Only meaningful when CFTSCAL_HW_MODE is
    #: not 'Sound Card'.
    'CFTSCAL_CUSTOM_IO_PATH': lambda: '',
    'CFTSCAL_CUSTOM_IO_CLASS': lambda: 'IOManifest',

    #: Durable identity of the selected audio device: its name plus the
    #: host API it belongs to. Never a PortAudio index, which is
    #: meaningless across sessions.
    'CFTSCAL_DEVICE_NAME': lambda: '',
    'CFTSCAL_DEVICE_HOSTAPI': lambda: '',

    #: Sampling rate for the selected device.
    'CFTSCAL_SAMPLE_RATE': lambda: 0.0,

    #: Plugins to force-load regardless of what their hardware probes
    #: report, so that (for example) a review-only machine with no sound
    #: card can still browse existing calibrations.
    'CFTSCAL_ENABLED_PLUGINS': lambda: [],

    #: Per-plugin GUI state, as a table of tables keyed by the plugin's
    #: settings filename. Replaces the individual JSON files that used to
    #: live under the psi config folder.
    'CFTSCAL_PLUGIN': lambda: {},
}
