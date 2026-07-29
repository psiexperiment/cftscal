'''
One-time migration script.

Older CFTS calibrations encoded metadata (datetime, sensor names, stimulus,
etc.) in the calibration directory name itself.  Newer calibrations store
that same information in a ``metadata.json`` sidecar file inside the
calibration directory, and the calibration classes in :mod:`cftscal.objects`
read from that file rather than parsing the directory name.

This script walks an existing calibration tree, parses the legacy directory
names per calibration type, and writes a ``metadata.json`` file into each
calibration folder that does not already have one.  The directory names
themselves are left untouched.

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
    return {
        'datetime': _parse_datetime(folder.name),
        'pistonphone': folder.name.rsplit('_', 1)[1],
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


def _parse_input_amplifier(folder):
    # Filename encodes many fields but the current reader only needs datetime.
    return {'datetime': _parse_datetime(folder.name)}


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


def _iter_calibration_folders(base):
    '''
    Yield every leaf calibration directory under ``base``.

    The convention is ``<base>/<object_name>/<calibration_folder>/`` (two
    levels deep), so we iterate accordingly.
    '''
    if not base.exists():
        return
    for object_dir in base.iterdir():
        if not object_dir.is_dir():
            continue
        for cal_dir in object_dir.iterdir():
            if cal_dir.is_dir():
                yield cal_dir


def migrate(root, dry_run=False, overwrite=False):
    '''
    Walk every calibration folder under ``root`` and write ``metadata.json``.

    Parameters
    ----------
    root : Path
        Root of the calibration tree (typically ``CAL_ROOT``).
    dry_run : bool
        If True, log what would be written without touching the filesystem.
    overwrite : bool
        If True, replace existing metadata.json files.  Otherwise skip them.

    Returns
    -------
    dict
        Counters: ``wrote``, ``skipped_exists``, ``skipped_error``.
    '''
    counts = {'wrote': 0, 'skipped_exists': 0, 'skipped_error': 0}
    for subfolder, parser in PARSERS.items():
        base = root / subfolder
        for cal_dir in _iter_calibration_folders(base):
            meta_file = cal_dir / METADATA_FILENAME
            if meta_file.exists() and not overwrite:
                counts['skipped_exists'] += 1
                continue
            try:
                metadata = parser(cal_dir)
            except Exception as e:
                print(f'SKIP  {cal_dir}: could not parse ({e})')
                counts['skipped_error'] += 1
                continue
            if dry_run:
                print(f'WOULD {meta_file}: {metadata}')
            else:
                meta_file.write_text(
                    json.dumps(metadata, indent=2, sort_keys=True)
                )
                print(f'WROTE {meta_file}')
            counts['wrote'] += 1
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
        help='Print what would be written without touching the filesystem.'
    )
    parser.add_argument(
        '--overwrite', action='store_true',
        help='Replace existing metadata.json files (default: skip them).'
    )
    args = parser.parse_args()

    print(f'Migrating calibration metadata under {args.root}')
    counts = migrate(args.root, dry_run=args.dry_run, overwrite=args.overwrite)
    verb = 'Would write' if args.dry_run else 'Wrote'
    print(
        f'\nDone. {verb} {counts["wrote"]} file(s); '
        f'skipped {counts["skipped_exists"]} existing, '
        f'{counts["skipped_error"]} unparseable.'
    )


if __name__ == '__main__':
    main()
