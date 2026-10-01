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

from psi import Setting


def _default_io():
    # A machine that already has its own IO manifest (the hostname one psi
    # falls back to) keeps using it: before CFTSCAL_IO existed, that was
    # what the experiment launchers ran on. Only a machine without one
    # starts on the sound card.
    from psi.application import get_default_io
    try:
        get_default_io()
        return 'default'
    except ValueError:
        return 'sound-card'


DEFAULTS = {
    #: Where calibration files are stored. Named CFTSCAL_ROOT rather than
    #: CAL_ROOT because cftscal owns this: psiexperiment used to emit a
    #: CAL_ROOT key into its config file that nothing ever read, while
    #: cftscal read CFTSCAL_ROOT from the environment.
    'CFTSCAL_ROOT': Setting(
        Path, lambda: Path('~/Documents/cftscal').expanduser(),
        doc='Where calibration data is stored.'),

    #: The IO manifest that cftscal, and every launcher built on it (cfts,
    #: abts, noise-exp), runs psi with. One of:
    #:
    #: - 'sound-card': the audio device chosen by CFTSCAL_DEVICE_NAME,
    #:   CFTSCAL_DEVICE_HOSTAPI and CFTSCAL_SAMPLE_RATE;
    #: - 'default': this machine's own manifest,
    #:   <PSI_IO_ROOT>/<hostname>.enaml;
    #: - anything else is passed to psi's --io as written: a file
    #:   (C:/io/rig.enaml, optionally ::ClassName) or a dotted module path
    #:   (cftscal.io.dummy_fireface.IOManifest).
    #:
    #: See cftscal.util.resolve_io, the one place this is interpreted.
    'CFTSCAL_IO': Setting(
        str, _default_io,
        doc='IO manifest to run psi with: sound-card, default, or an '
            '--io reference.'),

    #: Durable identity of the selected audio device: its name plus the
    #: host API it belongs to. Never a PortAudio index, which is
    #: meaningless across sessions. Only used when CFTSCAL_IO is
    #: 'sound-card'.
    'CFTSCAL_DEVICE_NAME': Setting(
        str, '', doc='Audio device name, for CFTSCAL_IO = sound-card.'),
    'CFTSCAL_DEVICE_HOSTAPI': Setting(
        str, '', doc='Host API of the audio device.'),

    #: Sampling rate for the selected device. Only used when CFTSCAL_IO is
    #: 'sound-card'.
    'CFTSCAL_SAMPLE_RATE': Setting(
        float, 0.0, doc='Sampling rate of the audio device.'),

    #: Plugins to force-load regardless of what their hardware probes
    #: report, so that (for example) a review-only machine with no sound
    #: card can still browse existing calibrations.
    'CFTSCAL_ENABLED_PLUGINS': Setting(
        list, [], doc='Plugins to load even without matching hardware.'),

    #: Per-plugin GUI state, as a table of tables keyed by the plugin's
    #: settings filename. Replaces the individual JSON files that used to
    #: live under the psi config folder.
    'CFTSCAL_PLUGIN': Setting(
        dict, {}, doc='Per-plugin GUI state, written by cftscal.'),
}
