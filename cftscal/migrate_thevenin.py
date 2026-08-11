'''
One-off cleanup script, specific to labs that run Thevenin-equivalent
calibrations for their starships.

A Thevenin-equivalent calibration uses a special-case coupler (named with a
``TH-`` prefix, e.g. ``TH-32``) that isn't a normal in-ear coupler -- it's
only used to compute the starship's Thevenin equivalent circuit, not to
calibrate an actual test coupler. Historically these were recorded straight
into the regular ``inear/<starship>/`` tree alongside real coupler
calibrations, making it hard to tell them apart at a glance.

This script finds every inear calibration whose ``coupler`` metadata starts
with ``TH-`` and moves it to ``inear/Thevenin/<starship>/<timestamp>/``,
mirroring the layout used everywhere else in the calibration tree (device ID
as the master folder). It is separate from :mod:`cftscal.migrate_metadata`
-- that script's per-run enrichment applies uniformly across every lab;
this one is a lab-specific, one-time reorganization that shouldn't run as
part of routine migration.

Only ``metadata.json``-having calibration folders are considered (i.e. ones
:mod:`cftscal.migrate_metadata` has already migrated to the cftscal sidecar
format) -- run that script first if the tree still has legacy-named folders.

Idempotent: calibrations already under ``inear/Thevenin/`` are left alone,
so re-running after a partial manual reorganization is safe.

Run with::

    python -m cftscal.migrate_thevenin
    python -m cftscal.migrate_thevenin --dry-run
    python -m cftscal.migrate_thevenin --root /path/to/cftscal
'''
import argparse
import json
from pathlib import Path


THEVENIN_COUPLER_PREFIX = 'TH-'


def move_thevenin_calibrations(root, dry_run=False):
    '''
    Move every inear calibration whose coupler starts with ``TH-`` under
    ``<root>/inear/`` into ``<root>/inear/Thevenin/<starship>/<timestamp>/``.

    Parameters
    ----------
    root : Path
        Root of the calibration tree (typically ``CAL_ROOT``).
    dry_run : bool
        If True, log what would be moved without touching the filesystem.

    Returns
    -------
    dict
        Counters: ``moved``, ``already_organized``, ``move_conflicts``,
        ``skipped_error``.
    '''
    counts = {
        'moved': 0, 'already_organized': 0, 'move_conflicts': 0,
        'skipped_error': 0,
    }
    inear_root = Path(root) / 'inear'
    if not inear_root.exists():
        return counts
    thevenin_root = inear_root / 'Thevenin'

    # Materialize the full list before moving anything -- mutating the
    # directory tree while rglob is still lazily walking it is unsafe
    # (same concern as migrate_metadata._iter_calibration_folders).
    meta_files = sorted(inear_root.rglob('metadata.json'))

    for meta_file in meta_files:
        cal_dir = meta_file.parent
        if cal_dir.is_relative_to(thevenin_root):
            counts['already_organized'] += 1
            continue

        try:
            metadata = json.loads(meta_file.read_text())
        except (OSError, json.JSONDecodeError) as e:
            print(f'SKIP  {cal_dir}: could not read metadata.json ({e})')
            counts['skipped_error'] += 1
            continue

        coupler = metadata.get('coupler', '')
        if not coupler.startswith(THEVENIN_COUPLER_PREFIX):
            continue

        starship = metadata.get('starship')
        if not starship:
            print(f'SKIP  {cal_dir}: coupler {coupler!r} looks like a '
                  f'Thevenin coupler but metadata has no starship')
            counts['skipped_error'] += 1
            continue

        new_path = thevenin_root / str(starship) / cal_dir.name
        if new_path.exists():
            print(f'SKIP  move {cal_dir} -> {new_path}: target already exists')
            counts['move_conflicts'] += 1
            continue

        old_parent = cal_dir.parent
        if dry_run:
            print(f'WOULD MOVE {cal_dir} -> {new_path}')
        else:
            new_path.parent.mkdir(parents=True, exist_ok=True)
            cal_dir.rename(new_path)
            print(f'MOVED {cal_dir} -> {new_path}')
            # Clean up the now-vestigial old starship folder once its
            # last Thevenin calibration has moved out of it.
            if old_parent.exists() and not any(old_parent.iterdir()):
                old_parent.rmdir()
        counts['moved'] += 1

    return counts


def main():
    from cftscal import CAL_ROOT

    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument(
        '--root', type=Path, default=CAL_ROOT,
        help=f'Calibration root directory (default: {CAL_ROOT}).'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Print what would be moved without touching the filesystem.'
    )
    args = parser.parse_args()

    print(f'Reorganizing Thevenin-equivalent inear calibrations under {args.root}')
    counts = move_thevenin_calibrations(args.root, dry_run=args.dry_run)
    verb = 'Would move' if args.dry_run else 'Moved'
    print(
        f'\nDone. {verb} {counts["moved"]} calibration(s); '
        f'{counts["already_organized"]} already organized; '
        f'{counts["move_conflicts"]} move conflict(s) left untouched; '
        f'{counts["skipped_error"]} unrecoverable.'
    )


if __name__ == '__main__':
    main()
