'''
One-time migration script.

Older CFTS calibrations encoded metadata (datetime, sensor names, stimulus,
etc.) in the calibration directory name itself.  Newer calibrations store
that same information in a ``metadata.json`` sidecar file inside the
calibration directory, and the calibration classes in :mod:`cftscal.objects`
read from that file rather than parsing the directory name -- the directory
itself is just named after its timestamp (see every plugin's ``settings.py``,
which builds new calibration paths as ``.../<object>/{date_time}``).

This script walks an existing calibration tree, parses the legacy directory
names per calibration type, and writes a ``metadata.json`` file into each
calibration folder that does not already have a *cftscal-format* one.  A
folder containing some other ``metadata.json`` -- e.g. psiexperiment/psidata's
own run-provenance file (``hostname``/``timestamp``/``version``), written for
calibrations recorded before the cftscal sidecar feature existed -- is still
migrated: the folder-name-derived fields are merged into the existing file
rather than skipped, so no data (ours or the pre-existing file's) is lost.

Once a folder's metadata has been captured in its ``metadata.json``, the
folder itself is renamed to drop the now-redundant legacy suffix, leaving
just the ``YYYYMMDD-HHMMSS`` timestamp -- matching the layout new
calibrations are already recorded under.  This only happens *after* the
metadata has actually been written, since the directory name is the only
place that information exists for a not-yet-migrated calibration.

Run with::

    python -m cftscal.migrate_metadata
    python -m cftscal.migrate_metadata --dry-run
    python -m cftscal.migrate_metadata --overwrite
    python -m cftscal.migrate_metadata --root /path/to/cftscal
'''
import argparse
import datetime as dt
import json
from pathlib import Path
import re


METADATA_FILENAME = 'metadata.json'


def _parse_datetime(folder_name):
    '''
    Extract the ISO datetime from the leading ``YYYYMMDD-HHMMSS`` prefix
    of a calibration directory name.
    '''
    prefix = folder_name.split('_', 1)[0]
    return dt.datetime.strptime(prefix, '%Y%m%d-%H%M%S').isoformat()


def _parse_microphone_measurement(folder):
    # Filename: {date_time}_{sensor.name}_{pistonphone}
    rest = folder.name.split('_', 1)[1]
    sensor_id, pistonphone = rest.rsplit('_', 1)
    return {
        'datetime': _parse_datetime(folder.name),
        'sensor_id': sensor_id,
        'pistonphone': pistonphone,
    }


def _parse_microphone_generic(folder):
    # Filename: {date_time}_{generic_input.sensor.name}_{measurement_mic}_{stimulus}
    return {
        'datetime': _parse_datetime(folder.name),
        'measurement_microphone': folder.name.rsplit('_', 2)[1],
        'stimulus': folder.name.rsplit('_', 1)[1],
    }


def _parse_speaker(folder):
    # Filename: {date_time}_{speaker.name}_{mic.name}_{method}
    parts = folder.name.split('_')
    return {
        'datetime': _parse_datetime(folder.name),
        'microphone': parts[2],
        'method': parts[3],
    }


def _parse_starship(folder):
    # Filename: {date_time}_{starship.name}_{mic}_{coupler}_{stimulus}
    parts = folder.name.split('_')
    return {
        'datetime': _parse_datetime(folder.name),
        'microphone': parts[2],
        'coupler': parts[3],
        'stimulus': parts[-1],
    }


# Filename: {date_time}_{name}_{total_gain}x_{freq_lb}-{freq_ub}Hz-filt-60Hz-{filt_60Hz}
# (see InputAmplifierSettings._get_calibration_filename in the pre-sidecar
# code, build/lib/cftscal/plugins/settings.py, for the format this recovers).
_INPUT_AMPLIFIER_RE = re.compile(
    r'^\d{8}-\d{6}_.+?_(?P<total_gain>[\d.]+)x_'
    r'(?P<freq_lb>[\d.]+)-(?P<freq_ub>[\d.]+)Hz-filt-60Hz-(?P<filt_60Hz>input|output)$'
)


def _parse_input_amplifier(folder):
    m = _INPUT_AMPLIFIER_RE.match(folder.name)
    if not m:
        raise ValueError(
            f'Could not parse gain/filter fields from {folder.name!r}'
        )
    return {
        'datetime': _parse_datetime(folder.name),
        'total_gain': float(m['total_gain']),
        'freq_lb': float(m['freq_lb']),
        'freq_ub': float(m['freq_ub']),
        'filt_60Hz': m['filt_60Hz'],
    }


def _parse_input_recording(folder):
    # Filename: {date_time}_{generator}_{sensor}
    parts = folder.name.split('_')
    return {
        'datetime': _parse_datetime(folder.name),
        'generator': parts[1],
        'sensor': parts[2],
    }


def _parse_inear(folder):
    # Filename: {date_time}_{ear}_{starship}
    return {
        'datetime': _parse_datetime(folder.name),
        'ear': folder.name.split('_', 2)[1],
        'starship': folder.name.rsplit('_', 1)[1],
    }


def _parse_ir_sensor(folder):
    # Filename: {date_time}_{input_name}
    return {
        'datetime': _parse_datetime(folder.name),
        'input_name': folder.name.split('_', 1)[1],
    }


# Each entry maps a subfolder name under CAL_ROOT to the parser that
# extracts the metadata dict from a leaf calibration directory in that tree.
PARSERS = {
    'microphone': _parse_microphone_measurement,
    'microphone_generic': _parse_microphone_generic,
    'speaker': _parse_speaker,
    'starship': _parse_starship,
    'input_amplifier': _parse_input_amplifier,
    'input-recording': _parse_input_recording,
    'inear': _parse_inear,
    'ir-sensor': _parse_ir_sensor,
}


# Each entry maps a subfolder name to the metadata key (beyond ``datetime``,
# which every parser always supplies) that only appears once that folder's
# calibrations have actually been migrated to the cftscal sidecar format.
# Used to tell a genuinely-migrated metadata.json apart from a *foreign* one
# -- e.g. psiexperiment/psidata itself writes its own ``metadata.json`` with
# run provenance (``hostname``, ``timestamp``, ``version``) into the same
# calibration directory for runs that predate the cftscal sidecar feature.
# Such a file exists on disk (so a plain existence check would skip it) but
# has none of the keys cftscal's calibration classes actually read, so it
# still needs migrating.
# A value can be a single key or a tuple of keys, all of which must be
# present -- ``microphone`` requires both, since an earlier version of this
# script only recovered ``pistonphone`` and folders it already touched
# would otherwise look "fully migrated" and never get ``sensor_id``
# backfilled on a later run.
MARKER_KEYS = {
    'microphone': ('sensor_id', 'pistonphone'),
    'microphone_generic': 'measurement_microphone',
    'speaker': 'microphone',
    'starship': 'microphone',
    'input_amplifier': 'total_gain',
    'input-recording': 'generator',
    'inear': 'starship',
    'ir-sensor': 'input_name',
}


def _is_migrated(metadata, marker_key):
    '''True if ``metadata`` already has the cftscal sidecar fields.'''
    if 'datetime' not in metadata:
        return False
    if marker_key is None:
        return True
    keys = (marker_key,) if isinstance(marker_key, str) else marker_key
    return all(key in metadata for key in keys)


def _iter_calibration_folders(base):
    '''
    Yield every leaf calibration directory under ``base``.

    The usual layout is ``<base>/<object_name>/<calibration_folder>/`` (two
    levels deep), but users can nest calibration objects under arbitrary
    organizational folders (e.g. to group by lab/study, or a ``hide``
    folder to tuck away retired calibrations from the tree view -- see
    ``CalibratedObject.folder`` / ``CFTSBaseLoader._walk_objects`` in
    :mod:`cftscal.objects`), so a calibration folder can sit at any depth
    under ``base``.  We identify one the same way ``_parse_datetime`` does:
    by a leading ``YYYYMMDD-HHMMSS`` timestamp in the directory name, rather
    than assuming a fixed nesting depth.

    Returns a list, not a generator: callers rename these directories in
    place as they process them, and mutating a directory tree while
    ``rglob`` is still lazily walking it is unsafe.
    '''
    if not base.exists():
        return []
    found = []
    for cal_dir in base.rglob('*'):
        if not cal_dir.is_dir():
            continue
        try:
            _parse_datetime(cal_dir.name)
        except ValueError:
            continue
        found.append(cal_dir)
    return found


def migrate(root, dry_run=False, overwrite=False):
    '''
    Walk every calibration folder under ``root``, write ``metadata.json``,
    and rename folders down to their bare timestamp once migrated.

    Parameters
    ----------
    root : Path
        Root of the calibration tree (typically ``CAL_ROOT``).
    dry_run : bool
        If True, log what would be written/renamed without touching the
        filesystem.
    overwrite : bool
        If True, re-derive and rewrite metadata.json from the directory
        name even for folders already considered migrated (as long as
        they still carry a legacy name to derive it from -- see below).
        Otherwise such folders are left alone.

    Returns
    -------
    dict
        Counters: ``wrote``, ``skipped_exists``, ``skipped_error``,
        ``renamed``, ``rename_conflicts``.
    '''
    counts = {
        'wrote': 0, 'skipped_exists': 0, 'skipped_error': 0,
        'renamed': 0, 'rename_conflicts': 0,
    }
    for subfolder, parser in PARSERS.items():
        base = root / subfolder
        marker_key = MARKER_KEYS[subfolder]
        for cal_dir in _iter_calibration_folders(base):
            meta_file = cal_dir / METADATA_FILENAME
            existing = {}
            if meta_file.exists():
                try:
                    existing = json.loads(meta_file.read_text())
                except (OSError, json.JSONDecodeError) as e:
                    print(f'SKIP  {cal_dir}: could not read existing '
                          f'{METADATA_FILENAME} ({e})')
                    counts['skipped_error'] += 1
                    continue

            date_only_name = cal_dir.name.split('_', 1)[0]
            has_legacy_name = cal_dir.name != date_only_name

            if not has_legacy_name:
                # Already at the bare-timestamp layout -- nothing left in
                # the directory name to (re-)derive. metadata.json, if it
                # already has this type's fields, is authoritative; if not,
                # that information can no longer be recovered here.
                if _is_migrated(existing, marker_key):
                    counts['skipped_exists'] += 1
                else:
                    print(f'SKIP  {cal_dir}: no usable {METADATA_FILENAME} '
                          f'and the directory name carries no recoverable '
                          f'metadata (already renamed?)')
                    counts['skipped_error'] += 1
                continue

            # The directory name still carries legacy metadata. It must be
            # captured into metadata.json now, regardless of --overwrite --
            # otherwise the rename below would discard it for good. Only
            # an already fully-migrated file is exempt, unless --overwrite
            # is given to force a re-derive/rewrite anyway.
            if overwrite or not _is_migrated(existing, marker_key):
                try:
                    parsed = parser(cal_dir)
                except Exception as e:
                    print(f'SKIP  {cal_dir}: could not parse ({e})')
                    counts['skipped_error'] += 1
                    continue
                # Folder-name-derived fields win on key collisions -- they're
                # what cftscal's calibration classes read -- but any foreign
                # fields already in the file (e.g. psiexperiment's own
                # hostname/timestamp/version provenance) are kept alongside
                # them rather than being clobbered.
                metadata = {**existing, **parsed}
                if dry_run:
                    verb = 'merge into' if existing else 'write'
                    print(f'WOULD {verb} {meta_file}: {metadata}')
                else:
                    meta_file.write_text(
                        json.dumps(metadata, indent=2, sort_keys=True)
                    )
                    print(f'WROTE {meta_file}')
                counts['wrote'] += 1
            else:
                counts['skipped_exists'] += 1

            new_path = cal_dir.parent / date_only_name
            if new_path.exists():
                print(f'SKIP  rename {cal_dir} -> {new_path.name}: '
                      f'target already exists')
                counts['rename_conflicts'] += 1
            elif dry_run:
                print(f'WOULD RENAME {cal_dir} -> {new_path}')
                counts['renamed'] += 1
            else:
                cal_dir.rename(new_path)
                print(f'RENAMED {cal_dir} -> {new_path}')
                counts['renamed'] += 1
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
        help='Print what would be written/renamed without touching the filesystem.'
    )
    parser.add_argument(
        '--overwrite', action='store_true',
        help='Re-derive metadata.json from the directory name even for '
             'already-migrated folders (default: skip them). Only affects '
             'folders that still carry a legacy name.'
    )
    args = parser.parse_args()

    print(f'Migrating calibration metadata under {args.root}')
    counts = migrate(args.root, dry_run=args.dry_run, overwrite=args.overwrite)
    verb = 'Would write' if args.dry_run else 'Wrote'
    rename_verb = 'Would rename' if args.dry_run else 'Renamed'
    print(
        f'\nDone. {verb} {counts["wrote"]} metadata file(s); '
        f'skipped {counts["skipped_exists"]} existing, '
        f'{counts["skipped_error"]} unrecoverable. '
        f'{rename_verb} {counts["renamed"]} folder(s); '
        f'{counts["rename_conflicts"]} rename conflict(s) left untouched.'
    )


if __name__ == '__main__':
    main()
