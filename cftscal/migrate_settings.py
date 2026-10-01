'''
Move cftscal's settings from its old JSON files into psi's ``config.toml``.

cftscal used to keep its own settings in the psi configuration folder
(``~/psi``, or wherever the ``PSI_CONFIG`` environment variable pointed):

- ``cfts/workspace.json`` for the calibration folder, hardware, audio
  device and sample rate, and
- ``cfts/calibration/<plugin>.json`` for each plugin's last-used values.

They are ordinary psi settings in ``config.toml`` now (see
``docs/reference/configuration.md``). ``psi-config migrate`` converts them
(it calls `collect_legacy_settings` through cftscal's ``psi.migrations``
entry point), with or without a ``config.py`` beside them. So that nobody
has to know to run it, cftscal also offers to import them when it starts
(`startup_check`), and from Workspace > Settings at any time.

Nothing is written to ``config.toml`` without asking. The startup import
only fills in settings that ``config.toml`` does not have yet, so it never
overwrites anything set since. Once the old settings have been imported or
declined, a note (``cfts/MIGRATED.txt``) is written beside them saying what
happened. The note also stops cftscal from asking again, which matters if
someone later removes a setting from ``config.toml`` on purpose: the old
value must not quietly come back. The old files are left in place,
untouched.

Run ``python -m cftscal.migrate_settings`` to see what would be imported
without changing anything.
'''
import datetime as dt
import json
import logging
from pathlib import Path

from psi.config import get_config_file, load_config, save_config
from psi.config_migrate import default_legacy_folder


log = logging.getLogger(__name__)


#: Written beside the old files once they have been migrated.
MARKER_FILENAME = 'MIGRATED.txt'


def get_legacy_folder():
    '''
    The folder cftscal used to keep its settings in.

    Returns
    -------
    folder : pathlib.Path
        The folder named by the ``PSI_CONFIG`` environment variable, or
        ``~/psi`` if it is not set. This is psi's legacy configuration
        folder (`psi.config_migrate.default_legacy_folder`), so cftscal and
        ``psi-config migrate`` always look in the same place.
    '''
    return default_legacy_folder()


def collect_legacy_settings(folder):
    '''
    Read cftscal's settings from a legacy configuration folder.

    cftscal kept a ``workspace.json`` and one JSON per plugin under
    ``<folder>/cfts``, beside (but independent of) ``config.py``. A machine
    that only ever ran cftscal has these and no ``config.py`` at all, so
    they can be collected on their own; cftscal does exactly that on
    startup (`migrate_legacy_settings`). ``psi-config migrate`` runs it
    too, through cftscal's ``psi.migrations`` entry point, when converting
    a ``config.py``.

    Parameters
    ----------
    folder : path-like
        The legacy configuration folder (``~/psi``, or whatever the
        ``PSI_CONFIG`` environment variable named).

    Returns
    -------
    updates : dict
        Settings to write, under their new names.
    notes : list of str
        Human-readable notes about what was and was not carried over.
    '''
    folder = Path(folder).expanduser()
    updates = {}
    notes = []

    workspace = folder / 'cfts' / 'workspace.json'
    if workspace.exists():
        ws_updates, ws_notes = collect_workspace(workspace)
        updates.update(ws_updates)
        notes.extend(ws_notes)

    plugins, plugin_notes = collect_plugins(folder / 'cfts' / 'calibration')
    if plugins:
        updates['CFTSCAL_PLUGIN'] = plugins
        notes.extend(plugin_notes)

    return updates, notes


def collect_plugins(directory):
    '''
    Read the per-plugin calibration settings files.

    cftscal used to write one JSON per plugin into the psi config folder.
    They are one table each under ``CFTSCAL_PLUGIN`` now, keyed by the
    same filename stem the plugin already used.
    '''
    plugins = {}
    notes = []
    if not directory.exists():
        return plugins, notes

    for path in sorted(directory.glob('*.json')):
        try:
            data = json.loads(path.read_text(encoding='utf-8-sig'))
        except (OSError, ValueError) as e:
            notes.append(f'{path.name}: could not be read ({e}); skipped')
            continue
        # Keyed by the full filename, extension included, because that is
        # what cftscal looks up: CalibrationSettings.settings_filename is
        # 'microphone-measurement.json' and is used verbatim as the key.
        # Keying by the stem wrote a table nothing ever read, so every
        # plugin silently reverted to defaults -- and the note said it had
        # migrated.
        plugins[path.name] = data
        notes.append(f'{path.name} -> CFTSCAL_PLUGIN."{path.name}"')
    return plugins, notes


#: workspace.json key -> setting name.
WORKSPACE_KEYS = {
    'data_path': 'CFTSCAL_ROOT',
    'selected_device_name': 'CFTSCAL_DEVICE_NAME',
    'selected_device_hostapi': 'CFTSCAL_DEVICE_HOSTAPI',
    'sample_rate': 'CFTSCAL_SAMPLE_RATE',
    'enabled_plugins': 'CFTSCAL_ENABLED_PLUGINS',
}


#: workspace.json keys that together chose the IO manifest. They are the
#: one setting CFTSCAL_IO now, holding what psi's --io is given.
IO_WORKSPACE_KEYS = ('hw_mode', 'custom_io_path', 'custom_io_class')


def _io_from_workspace(config):
    if config['hw_mode'] == 'Sound Card':
        return 'sound-card'
    path = str(config.get('custom_io_path', '')).strip()
    if not path or not path.endswith('.enaml'):
        # A dotted module path names its class itself.
        return path or None
    klass = str(config.get('custom_io_class', '')).strip() or 'IOManifest'
    return f'{path}::{klass}'


def _convert_hw_configuration(value):
    # Either 'Sound Card' or exactly what was passed to psi's --io.
    if value == 'Sound Card':
        return {'CFTSCAL_IO': 'sound-card'}
    return {'CFTSCAL_IO': value} if value else {}


def _convert_selected_device(value):
    # The device name alone, from before the host API was recorded too.
    return {'CFTSCAL_DEVICE_NAME': value} if value else {}


#: workspace.json keys from before the current ones, and how to convert
#: each into settings.
LEGACY_WORKSPACE_KEYS = {
    'hw_configuration': _convert_hw_configuration,
    'selected_device': _convert_selected_device,
}


def collect_workspace(path):
    '''
    Read a cftscal ``workspace.json`` and return what should be written.
    '''
    path = Path(path)
    updates = {}
    notes = []
    try:
        config = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as e:
        # As with the per-plugin files: one unreadable input must not
        # abort the conversion of everything else. A rig only runs this
        # once, and failing at the end of a long report is the worst
        # moment to discover a truncated file.
        notes.append(f'{path.name}: could not be read ({e}); skipped')
        return updates, notes
    for key, value in config.items():
        if key in LEGACY_WORKSPACE_KEYS or key in IO_WORKSPACE_KEYS:
            continue
        setting = WORKSPACE_KEYS.get(key)
        if setting is None:
            notes.append(f'{path.name}: dropped unknown key {key}')
            continue
        updates[setting] = value
        notes.append(f'{path.name}: {key} -> {setting}')

    if 'hw_mode' in config:
        io = _io_from_workspace(config)
        if io is None:
            notes.append(f'{path.name}: hw_mode named a custom IO manifest '
                         'but no file was selected; CFTSCAL_IO is left to '
                         'its default')
        else:
            updates['CFTSCAL_IO'] = io
            notes.append(f'{path.name}: hw_mode, custom_io_path, '
                         'custom_io_class -> CFTSCAL_IO')

    # Keys from before cftscal split them up. Its own loader converted
    # these for as long as it read workspace.json, so a machine that has
    # not been updated since still depends on them. The current keys win
    # when both are present, as they did in that loader.
    for key, convert in LEGACY_WORKSPACE_KEYS.items():
        if key not in config:
            continue
        converted = {s: v for s, v in convert(config[key]).items()
                     if s not in updates}
        updates.update(converted)
        if converted:
            notes.append(f'{path.name}: legacy key {key} -> '
                         f'{", ".join(sorted(converted))}')
        else:
            notes.append(f'{path.name}: dropped legacy key {key} '
                         '(superseded by the current keys)')

    if updates.get('CFTSCAL_IO') == 'sound-card':
        notes.extend(_sound_card_notes())
    return updates, notes


def _sound_card_notes():
    # The experiment launchers used to ignore cftscal's hardware setting
    # and run on this machine's own IO manifest. They follow CFTSCAL_IO
    # now, so a rig that calibrated on the sound card but ran experiments
    # on its own manifest would quietly switch -- say so.
    from psi.application import get_default_io
    try:
        default = get_default_io()
    except ValueError:
        return []
    return [f'CFTSCAL_IO is sound-card, so the cfts, abts and noise-exp '
            f'launchers now run on the sound card too, rather than on '
            f'{default}. Set CFTSCAL_IO to default to keep using that.']


def has_legacy_files(folder=None):
    '''
    Whether the legacy folder holds any of cftscal's old settings files.

    Parameters
    ----------
    folder : {None, path-like}
        Legacy configuration folder. Defaults to `get_legacy_folder`.
    '''
    folder = get_legacy_folder() if folder is None else Path(folder)
    cfts = folder / 'cfts'
    return (cfts / 'workspace.json').exists() \
        or any((cfts / 'calibration').glob('*.json'))


def is_migrated(folder=None):
    '''
    Whether the old settings have been dealt with: imported, or declined.

    Parameters
    ----------
    folder : {None, path-like}
        Legacy configuration folder. Defaults to `get_legacy_folder`.
    '''
    folder = get_legacy_folder() if folder is None else Path(folder)
    return (folder / 'cfts' / MARKER_FILENAME).exists()


def plan_migration(folder=None, force=False, replace=False):
    '''
    Work out what `migrate_legacy_settings` would write, without writing it.

    Parameters
    ----------
    folder : {None, path-like}
        Legacy configuration folder. Defaults to `get_legacy_folder`.
    force : bool
        If True, plan the import even if it was already done or declined
        (see `is_migrated`).
    replace : bool
        If True, settings already in ``config.toml`` are replaced by the old
        values. Otherwise they are kept, and only missing ones are filled in.

    Returns
    -------
    updates : dict
        Settings to write to ``config.toml``. Empty if there is nothing to
        migrate, or if it has already been migrated.
    notes : list of str
        What was found and what will (or will not) be carried over. Empty
        if there were no old settings files, or they were already
        migrated.
    '''
    folder = get_legacy_folder() if folder is None else Path(folder)
    if not force and is_migrated(folder):
        return {}, []

    collected, notes = collect_legacy_settings(folder)
    existing = load_config()
    config_file = get_config_file()
    kept = 'replaced it' if replace else 'kept it'

    updates = {}
    for name, value in collected.items():
        if name == 'CFTSCAL_PLUGIN':
            # One table per plugin. Carry over the plugins that do not have
            # a table yet; the ones that do are kept, unless replacing.
            current = existing.get(name, {})
            for plugin in sorted(set(value) & set(current)):
                notes.append(f'CFTSCAL_PLUGIN."{plugin}" is already in '
                             f'{config_file}; {kept}')
            if replace:
                updates[name] = {**current, **value}
            elif set(value) - set(current):
                updates[name] = {**value, **current}
        elif name in existing:
            notes.append(f'{name} is already in {config_file}; {kept}')
            if replace:
                updates[name] = value
        else:
            updates[name] = value
    return updates, notes


def prompt_text(folder=None):
    r'''
    The question asked before importing the old settings.

    Built here rather than in the dialog: an enaml file shows the escape
    sequences in an f-string (such as ``\n``) literally rather than
    turning them into line breaks.

    Parameters
    ----------
    folder : {None, path-like}
        Legacy configuration folder. Defaults to `get_legacy_folder`.
    '''
    folder = get_legacy_folder() if folder is None else Path(folder)
    return '\n'.join([
        'Settings from an older version of cftscal were found in',
        f'    {folder / "cfts"}',
        '',
        'Import them into',
        f'    {get_config_file()}?',
    ])


def describe_plan(updates, notes):
    '''
    Describe a plan from `plan_migration` for someone deciding whether to
    import it.

    Returns
    -------
    text : str
        The settings that will be written, then the notes.
    '''
    lines = []
    if updates:
        lines.append('These settings will be written:')
        for name in sorted(updates):
            value = updates[name]
            if name == 'CFTSCAL_PLUGIN':
                # The tables are long and only the GUI reads them; which
                # plugins they belong to is what matters here.
                value = ', '.join(sorted(value))
                lines.append(f'    {name}: saved values for {value}')
            else:
                lines.append(f'    {name} = {value!r}')
    else:
        lines.append('Nothing new to import: every setting is already in '
                     f'{get_config_file()}.')
    if notes:
        lines += ['', 'Details:'] + [f'    {note}' for note in notes]
    return '\n'.join(lines)


def _write_marker(folder, notes, imported):
    now = dt.datetime.now().isoformat(timespec='seconds')
    config_file = get_config_file()
    if imported:
        lines = [f'On {now}, cftscal moved the settings in this folder into',
                 f'    {config_file}']
    else:
        lines = [f'On {now}, cftscal was told not to import the settings in',
                 'this folder, so they were not copied into',
                 f'    {config_file}',
                 '',
                 'To import them after all, use "Import old settings..." in',
                 "cftscal's Workspace > Settings."]
    lines += [
        '',
        'cftscal no longer reads the files in this folder. They were left',
        'in place in case they are needed; they can be deleted.',
    ]
    if notes:
        lines += ['', 'Details:'] + [f'    {note}' for note in notes]
    marker = folder / 'cfts' / MARKER_FILENAME
    marker.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def migrate_legacy_settings(folder=None, force=False, replace=False):
    '''
    Move cftscal's old JSON settings into ``config.toml``.

    Does nothing if there are no old settings files, or (unless `force`)
    if they have already been migrated or declined. Writes ``MIGRATED.txt``
    beside them once done. See the module docstring for details.

    Parameters
    ----------
    folder : {None, path-like}
        Legacy configuration folder. Defaults to `get_legacy_folder`.
    force, replace : bool
        See `plan_migration`.

    Returns
    -------
    updates : dict
        The settings that were written to ``config.toml``.
    '''
    folder = get_legacy_folder() if folder is None else Path(folder)
    updates, notes = plan_migration(folder, force=force, replace=replace)
    if not updates and not notes:
        return {}

    if updates:
        save_config(updates)
    _write_marker(folder, notes, imported=True)

    log.info('Migrated %d cftscal setting(s) from %s to %s',
             len(updates), folder / 'cfts', get_config_file())
    for note in notes:
        log.info('  %s', note)
    return updates


def decline_migration(folder=None):
    '''
    Record that the old settings are not to be imported, so cftscal stops
    asking. They can still be imported later with ``force=True``.

    Parameters
    ----------
    folder : {None, path-like}
        Legacy configuration folder. Defaults to `get_legacy_folder`.
    '''
    folder = get_legacy_folder() if folder is None else Path(folder)
    _write_marker(folder, [], imported=False)
    log.info('Old cftscal settings in %s will not be imported',
             folder / 'cfts')


#: Answers to the question `startup_check` asks.
IMPORT, LATER, NEVER = 'import', 'later', 'never'


def startup_check(ask, folder=None):
    '''
    Offer to import the old settings, if there are any not yet dealt with.

    Called by cftscal once its main window is up. Nothing is written to
    ``config.toml`` without asking first.

    Parameters
    ----------
    ask : callable
        Called as ``ask(updates, notes)`` with the plan from
        `plan_migration`, and returns `IMPORT` (import them now), `LATER`
        (ask again next time) or `NEVER` (do not ask again).
    folder : {None, path-like}
        Legacy configuration folder. Defaults to `get_legacy_folder`.

    Returns
    -------
    imported : bool
        True if settings were written to ``config.toml``, in which case
        anything that already read them needs to read them again.
    '''
    folder = get_legacy_folder() if folder is None else Path(folder)
    updates, notes = plan_migration(folder)
    if not updates:
        if notes:
            # Old files, but nothing in them that config.toml lacks (or
            # nothing readable). There is no decision to ask for; record
            # what was found and stop looking.
            _write_marker(folder, notes, imported=True)
        return False

    answer = ask(updates, notes)
    if answer == IMPORT:
        return bool(migrate_legacy_settings(folder))
    if answer == NEVER:
        decline_migration(folder)
    return False


def main():
    import argparse
    parser = argparse.ArgumentParser(
        'cftscal-migrate-settings',
        description='Show what cftscal would import from its old JSON '
                    'settings files into config.toml. cftscal offers to do '
                    'this when it starts; use --apply to do it now.',
    )
    parser.add_argument('--folder', type=Path, default=None,
                        help='Legacy configuration folder (default: '
                             '$PSI_CONFIG, or ~/psi).')
    parser.add_argument('--force', action='store_true',
                        help='Plan the import even if it was already done '
                             'or declined.')
    parser.add_argument('--replace', action='store_true',
                        help='Replace settings already in config.toml '
                             'instead of keeping them.')
    parser.add_argument('--apply', action='store_true',
                        help='Write the settings instead of only showing '
                             'them.')
    args = parser.parse_args()

    folder = get_legacy_folder() if args.folder is None else args.folder
    updates, notes = plan_migration(folder, force=args.force,
                                    replace=args.replace)
    if not updates and not notes:
        if is_migrated(folder):
            print(f'Already imported (or declined); see '
                  f'{folder / "cfts" / MARKER_FILENAME}. Use --force to '
                  'import again.')
        else:
            print(f'Nothing to migrate in {folder}.')
        return
    print(f'Reading {folder / "cfts"}')
    print(f'Writing {get_config_file()}')
    print(describe_plan(updates, notes))
    if args.apply:
        migrate_legacy_settings(folder, force=args.force,
                                replace=args.replace)
        print('Done.')
    else:
        print('Nothing written. Run again with --apply to write it.')


if __name__ == '__main__':
    main()
