'''
Seeds psiexperiment's per-paradigm default layout/preferences files from
cftscal's own packaged copies, so a fresh cftscal install starts from a
curated dock-panel arrangement instead of Enaml's unopinionated default.

psi itself already has this concept -- ``psi.get_default_layout``/
``psi.get_default_preferences`` (``psi/experiment/experiment_commands.py``
in psiexperiment) load ``<LAYOUT_ROOT>/<paradigm_name>/default.layout``/
``<PREFERENCES_ROOT>/<paradigm_name>/default.preferences`` on every
launch, silently doing nothing if the file doesn't exist yet. Today that
file only ever gets created by a user manually choosing *Configuration >
Layout > Set default* (or the preferences equivalent) inside a running
experiment. This module materializes cftscal's packaged copies (see
``cftscal/resources/layout/`` and ``cftscal/resources/preferences/``)
into those same locations, once, the first time a paradigm would need
one -- never overwriting a real default a user (or a previous seed)
already created there.
'''
import logging
log = logging.getLogger(__name__)

import shutil
from pathlib import Path

from psi import get_config


#: cftscal's own packaged copies, mirroring psiexperiment's own
#: <ROOT>/<paradigm_name>/default.<ext> layout exactly so seeding is a
#: plain "copy this relative path if the destination doesn't exist yet"
#: with no renaming/reshaping.
RESOURCE_ROOT = Path(__file__).resolve().parent.parent / 'resources'

#: which -> the psi config key naming that kind of file's root directory.
_ROOTS = {'layout': 'LAYOUT_ROOT', 'preferences': 'PREFERENCES_ROOT'}


def seed_default_state(paradigm_name):
    '''
    Copy cftscal's packaged default layout/preferences for
    ``paradigm_name`` into psiexperiment's LAYOUT_ROOT/PREFERENCES_ROOT,
    if and only if the user doesn't already have one there.

    Parameters
    ----------
    paradigm_name : str
        The name passed as the first argument to that paradigm's
        ``ParadigmDescription(...)`` call (e.g. ``'pistonphone_calibration'``)
        -- the same string psi itself uses as the directory key under
        ``LAYOUT_ROOT``/``PREFERENCES_ROOT``.
    '''
    for which, root_config in _ROOTS.items():
        src = RESOURCE_ROOT / which / paradigm_name / f'default.{which}'
        if not src.exists():
            continue
        dest = Path(get_config(root_config)) / paradigm_name / f'default.{which}'
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def seed_all_default_state():
    '''
    Seed every paradigm that has a packaged default layout and/or
    preferences file, discovered directly from ``RESOURCE_ROOT``'s own
    subdirectories.

    Meant to be called once, at application startup -- not from a
    per-run hot path -- since ``seed_default_state``'s never-overwrite
    semantics mean there's nothing left for a later call to do for a
    paradigm once it's been seeded (or once the user has saved their own
    default), so repeating the check on every calibration run would just
    be wasted filesystem I/O with no ongoing benefit.
    '''
    names = set()
    for which in _ROOTS:
        base = RESOURCE_ROOT / which
        if base.exists():
            names.update(p.name for p in base.iterdir() if p.is_dir())
    for name in sorted(names):
        try:
            seed_default_state(name)
        except OSError as e:
            # One bad/unwritable destination shouldn't block startup or
            # seeding every other paradigm.
            log.warning('Could not seed default state for %s: %s', name, e)
