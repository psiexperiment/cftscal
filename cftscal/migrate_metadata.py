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

import yaml


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
        'microphone': folder.name.rsplit('_', 2)[1],
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


#: Legacy folders encode the notch-filter switch position as
#: 'input'/'output' (the physical switch's "IN circuit"/"OUT of circuit"
#: labeling); InputAmplifierReference.filt_60Hz now uses the clearer
#: 'on'/'off', so translate on the way in to keep migrated metadata
#: consistent with everything recorded going forward.
_FILT_60HZ_LEGACY_MAP = {'input': 'on', 'output': 'off'}


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
        'filt_60Hz': _FILT_60HZ_LEGACY_MAP[m['filt_60Hz']],
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
    # Filename: {date_time}_{coupler}_{starship}, where {coupler} may
    # carry a '-secondary' suffix (e.g. 'C1-secondary') left over from
    # when this was the only way to tell primary/secondary apart. The
    # suffix is stripped from the recovered coupler name, but no longer
    # used to guess `output` -- _enrich_inear_from_preferences reads that
    # from final.preferences instead, which is authoritative.
    ear_token = folder.name.split('_', 2)[1]
    coupler = ear_token.removesuffix('-secondary')
    return {
        'datetime': _parse_datetime(folder.name),
        'coupler': coupler,
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
# A value can be a single key, a tuple of keys (all of which must be
# present -- ``microphone`` requires both, since an earlier version of this
# script only recovered ``pistonphone`` and folders it already touched
# would otherwise look "fully migrated" and never get ``sensor_id``
# backfilled on a later run), or a list of alternatives (any one of which
# being satisfied counts as migrated) -- ``microphone_generic`` accepts
# either the current ``microphone`` key or the legacy ``measurement_microphone``
# key it was renamed from, so calibrations migrated before the rename
# still read as migrated rather than getting flagged as unrecoverable
# once their directory has already been renamed to a bare timestamp.
MARKER_KEYS = {
    'microphone': ('sensor_id', 'pistonphone'),
    'microphone_generic': ['microphone', 'measurement_microphone'],
    'speaker': 'microphone',
    'starship': 'microphone',
    'input_amplifier': 'total_gain',
    'input-recording': 'generator',
    'inear': ('starship', 'coupler'),
    'ir-sensor': 'input_name',
}


# Subfolder -> parsed-metadata key whose value should become the leaf
# calibration's new immediate parent folder, replacing whatever coupler/ear
# folder it's nested under today -- the "master folder" for that subfolder
# becomes the device ID rather than whatever the leaf happened to be filed
# under historically. Every other subfolder type is absent here and keeps
# the plain rename-in-place behavior.
REPARENT_KEY = {
    'inear': 'starship',
}


def _is_migrated(metadata, marker_key):
    '''True if ``metadata`` already has the cftscal sidecar fields.'''
    if 'datetime' not in metadata:
        return False
    if marker_key is None:
        return True
    # A list means "any one of these alternatives is enough" (each
    # alternative itself a single key or an all-required tuple, same as
    # the non-list form) -- see MARKER_KEYS['microphone_generic'].
    if isinstance(marker_key, list):
        return any(_is_migrated(metadata, alt) for alt in marker_key)
    keys = (marker_key,) if isinstance(marker_key, str) else marker_key
    return all(key in metadata for key in keys)


def _enrich_inear_from_preferences(cal_dir, metadata, overwrite=False):
    '''
    Recover inear fields that live in the run's ``final.preferences``
    sidecar (a YAML file psiexperiment writes for every run) rather than
    the calibration directory name.

    ``output`` (primary/secondary) is always overwritten from
    ``final.preferences`` when available -- it's authoritative, replacing
    the old filename-suffix guess this script used to make. ``gain`` is
    only filled in when missing (``overwrite`` does not affect this):
    every historical inear recording was actually made at a fixed 40 dB
    gain but never had it recorded in metadata.json, whereas current
    recordings write a real (user-selected, possibly 20 dB) gain via
    ``InEarCalibrationSettings.run_cal`` that must never be clobbered,
    even when the user is deliberately forcing a re-derive of something
    else via ``--overwrite``.
    '''
    enrichment = {}
    if 'gain' not in metadata:
        enrichment['gain'] = 40
    prefs_file = cal_dir / 'final.preferences'
    if prefs_file.exists():
        try:
            prefs = yaml.safe_load(prefs_file.read_text())
            enrichment['output'] = (
                prefs['context']['parameters']['system_starship_settings']
                ['system_output']['selected']
            )
        except (OSError, yaml.YAMLError, KeyError, TypeError):
            pass
    return enrichment


def _load_io_json(cal_dir):
    io_file = cal_dir / 'io.json'
    if not io_file.exists():
        return None
    try:
        return json.loads(io_file.read_text())
    except (OSError, json.JSONDecodeError):
        return None


#: io.json is a serialized dump of the full psiexperiment IO manifest, not
#: just the handful of "input"/"output" channels cftscal cares about -- it
#: includes e.g. position encoders (NIDAQHardwareCIAngPosEncoderChannel)
#: that psiexperiment's own list_inputs()/list_connections() (cftscal/
#: util.py) already filter out via isinstance(obj, HardwareAIChannel) /
#: HardwareAOChannel. A channel left permanently wired/active in the DAQ
#: engine config (e.g. a turntable position encoder on older rigs) shows
#: up "active" right alongside the real microphone channel, breaking the
#: "exactly one active entry" disambiguation for no good reason -- exclude
#: non-audio channel types the same way util.py does before ever counting
#: candidates.
_IO_JSON_TYPE_SUFFIX = {'input': 'AIChannel', 'output': 'AOChannel'}


def _real_hw_channels(io_data, direction):
    '''Active entries in ``io_data[direction]`` that are genuine hardware
    analog channels (excludes counters/encoders/digital channels).'''
    suffix = _IO_JSON_TYPE_SUFFIX[direction]
    return [
        (k, v) for k, v in io_data.get(direction, {}).items()
        if v.get('active') and suffix in (v.get('__type__') or '')
    ]


def _enrich_channels_from_io(input_field=None, output_field=None,
                              input_prefer_keys=(), gain_field=None):
    '''
    Build an enricher that recovers input/output channel labels (and,
    optionally, the resolved input channel's own gain) from the run's
    ``io.json`` sidecar (a JSON dump of the full IO manifest
    psiexperiment writes for every run).

    Each ``io.json`` entry carries its manifest ``name`` (the dict key,
    e.g. ``"starship_A_microphone"``), a human-readable ``label`` (e.g.
    ``"Starship A (microphone)"``) -- the same ``label`` every plugin's
    ``settings.py`` writes into these fields for new recordings
    (``ai.input_label``/``ao.output_label``/``ear.connection_label``) --
    and its own ``gain`` (the channel's configured hardware preamp gain,
    the same concept as e.g. ``CFTSMeasurementMicrophoneCalibration.gain``).

    ``io.json`` marks each configured channel ``active: true/false``; the
    channel(s) active for a given direction (after excluding non-audio
    types via ``_real_hw_channels``) are the one(s) actually used for
    that recording. Usually unambiguous once exactly one real channel is
    active. When two or more real channels are simultaneously active
    (e.g. starship recordings always have both the starship's own probe
    mic and a separate reference/calibration mic active at once),
    ``input_prefer_keys`` breaks the tie for the *input* direction only:
    if exactly one active candidate's key is in ``input_prefer_keys``,
    that one wins. The reference/calibration mic's channel key is not
    consistently spelled across this lab's history (both
    ``"microphone_calibration"`` and ``"calibration_microphone"`` appear,
    in different eras) -- pass every known spelling. Still-ambiguous
    cases are left blank rather than risking a wrong guess.

    Normally only fills a field that's still blank -- but with
    ``overwrite=True`` recomputes it regardless of what's already there,
    so a bad value (e.g. one written by an earlier, buggy version of this
    enricher) can be corrected by re-running with ``--overwrite`` instead
    of needing the field manually cleared first.
    '''
    def enrich(cal_dir, metadata, overwrite=False):
        io_data = _load_io_json(cal_dir)
        if io_data is None:
            return {}
        result = {}
        resolved_input = None
        for direction, field in (('input', input_field), ('output', output_field)):
            if field is None:
                continue
            candidates = _real_hw_channels(io_data, direction)
            chosen = None
            if len(candidates) == 1:
                chosen = candidates[0]
            elif direction == 'input' and input_prefer_keys:
                preferred = [c for c in candidates if c[0] in input_prefer_keys]
                if len(preferred) == 1:
                    chosen = preferred[0]
            if chosen is None:
                continue  # 0 or 2+ active candidates -- still ambiguous
            if direction == 'input':
                resolved_input = chosen[1]
            if metadata.get(field) and not overwrite:
                continue  # already have a real value
            result[field] = chosen[1].get('label') or chosen[0]
        if (gain_field is not None and resolved_input is not None
                and (overwrite or not metadata.get(gain_field))):
            gain = resolved_input.get('gain')
            if gain is not None:
                result[gain_field] = gain
        return result
    return enrich


#: The starship's *own* probe-tube mic channel -- distinct from the
#: reference/calibration mic (see _enrich_channels_from_io's
#: input_prefer_keys docstring). Both are real, simultaneously-active AI
#: channels in a starship recording's io.json, each with its own
#: separate gain; this one backs CFTSStarshipCalibration.gain (the
#: starship device's own gain switch), not the reference mic's.
_STARSHIP_MIC_RE = re.compile(r'^starship_\w+_microphone$')


def _enrich_starship_gain_from_io(cal_dir, metadata, overwrite=False):
    '''Recover the starship's own device gain (not the reference mic's --
    see _STARSHIP_MIC_RE) from io.json, when unambiguous.'''
    if metadata.get('gain') and not overwrite:
        return {}
    io_data = _load_io_json(cal_dir)
    if io_data is None:
        return {}
    candidates = [
        v for k, v in _real_hw_channels(io_data, 'input')
        if _STARSHIP_MIC_RE.match(k)
    ]
    if len(candidates) == 1 and candidates[0].get('gain') is not None:
        return {'gain': candidates[0]['gain']}
    return {}


def _enrich_input_recording_from_io(cal_dir, metadata, overwrite=False):
    '''
    Recover a real channel label (and gain) for legacy single-channel
    input-recording metadata.

    Recordings made before multi-channel support have a bare ``sensor``
    key and no ``sensors`` dict -- CFTSInputRecording.sensors's fallback
    synthesizes ``{'selected_input': {'label': 'selected_input', ...}}``,
    showing that literal placeholder in the tree since no real label was
    ever recorded. When io.json has exactly one active real input
    channel, write a proper ``sensors`` dict with its actual label (and
    gain, if present) so CFTSInputRecording.sensors reads real data
    instead of synthesizing the placeholder. A no-op once metadata
    already has a ``sensors`` dict, whether from a genuinely
    multi-channel recording or a prior run of this enricher.
    '''
    if 'sensors' in metadata or 'sensor' not in metadata:
        return {}
    io_data = _load_io_json(cal_dir)
    if io_data is None:
        return {}
    candidates = _real_hw_channels(io_data, 'input')
    if len(candidates) != 1:
        return {}
    _, v = candidates[0]
    entry = {'label': v.get('label') or 'selected_input', 'sensor': metadata['sensor']}
    if v.get('gain') is not None:
        entry['gain'] = v['gain']
    return {'sensors': {'selected_input': entry}}


def _fix_input_amplifier_total_gain(cal_dir, metadata, overwrite=False):
    '''
    Some historical input_amplifier recordings have ``total_gain``
    recorded 100x too small (e.g. 500 instead of 50000) -- a genuine
    historical bug in an old version of the acquisition program itself
    (confirmed against the original filenames), not a parsing artifact
    here, so it can't be fixed by re-parsing. Self-validates against the
    recording's own independently-measured ``amplifier_gain.json``
    instead: only corrects when ``measured / total_gain`` lands close to
    100, so a recording genuinely configured at a different gain (whose
    own measurement would corroborate its recorded value) is never
    touched. Always checked, regardless of ``overwrite`` -- this is
    correcting a value already known to be wrong, not filling a blank.
    '''
    total_gain = metadata.get('total_gain')
    if not total_gain:
        return {}
    gain_file = cal_dir / 'amplifier_gain.json'
    if not gain_file.exists():
        return {}
    try:
        measured = json.loads(gain_file.read_text()).get('gain mean (linear)')
    except (OSError, json.JSONDecodeError):
        return {}
    if measured is None:
        return {}
    ratio = measured / total_gain
    if 90 <= ratio <= 110:
        return {'total_gain': total_gain * 100}
    return {}


def _compose(*enrichers):
    '''Combine several enrichers into one, run in sequence with each
    seeing the metadata as enriched by those before it.'''
    def combined(cal_dir, metadata, overwrite=False):
        result = {}
        merged = metadata
        for enricher in enrichers:
            extra = enricher(cal_dir, merged, overwrite=overwrite)
            if extra:
                merged = {**merged, **extra}
                result = {**result, **extra}
        return result
    return combined


#: Both spellings of this lab's one reference/calibration mic channel
#: appear across the real data -- the naming convention changed at some
#: point in this rig's history. Neither is a typo; both must be checked.
_REFERENCE_MIC_KEYS = ('microphone_calibration', 'calibration_microphone')


def _enrich_device_from_folder(field):
    '''
    Build an enricher that backfills ``field`` (e.g. ``starship``/
    ``speaker``/``sensor_id``) from the calibration's own on-disk
    location, for subfolders with no REPARENT_KEY: ``cal_dir.parent`` is
    always the device-name folder (CFTSBaseLoader._walk_objects's
    convention -- whatever sits directly above the leaf calibration
    folder is the object, everything above *that* is an organizational
    folder), true for both already-bare-timestamp and still-legacy-named
    folders alike, since only the leaf folder's name is ever affected by
    migration.

    Only a *backfill* for existing data, not something new recordings
    need -- every plugin's settings.py already writes this field
    directly at record time. Confirmed safe to use folder-derived
    identity here specifically because no data has been acquired since
    the target-folder-redirection feature existed, so there's no
    historical case where the folder and the actual device diverge (see
    CFTSStarshipCalibration.starship's docstring for why that divergence
    is possible *going forward*, which is exactly why new recordings
    don't rely on this).
    '''
    def enrich(cal_dir, metadata, overwrite=False):
        if metadata.get(field) and not overwrite:
            return {}
        return {field: cal_dir.parent.name}
    return enrich


# Subfolder -> function(cal_dir, metadata) -> dict of fields to merge in.
# Runs on every calibration folder migrate() visits (not just ones with a
# legacy name still to parse), since io.json/final.preferences are present
# regardless of a folder's migration status. Absent here (ir-sensor) means
# no enrichment is attempted for that type.
ENRICHERS = {
    'inear': _compose(
        _enrich_inear_from_preferences,
        _enrich_channels_from_io(output_field='starship_channel'),
    ),
    'microphone': _enrich_channels_from_io(
        input_field='input_channel', input_prefer_keys=_REFERENCE_MIC_KEYS,
        gain_field='gain'),
    'speaker': _compose(
        _enrich_channels_from_io(
            input_field='microphone_channel', input_prefer_keys=_REFERENCE_MIC_KEYS,
            output_field='output_channel', gain_field='gain'),
        _enrich_device_from_folder('speaker'),
    ),
    'starship': _compose(
        _enrich_channels_from_io(
            input_field='microphone_channel', input_prefer_keys=_REFERENCE_MIC_KEYS,
            output_field='starship_channel', gain_field='microphone_gain'),
        _enrich_starship_gain_from_io,
        _enrich_device_from_folder('starship'),
    ),
    'input_amplifier': _compose(
        _enrich_channels_from_io(input_field='input_channel'),
        _fix_input_amplifier_total_gain,
        _enrich_device_from_folder('sensor_id'),
    ),
    'input-recording': _enrich_input_recording_from_io,
    'microphone_generic': _enrich_device_from_folder('sensor_id'),
}


def _apply_enrichment(cal_dir, metadata, enricher, overwrite=False):
    '''Run ``enricher`` (if any) and return ``(new_metadata, changed)``.'''
    if enricher is None:
        return metadata, False
    extra = enricher(cal_dir, metadata, overwrite=overwrite)
    if not extra:
        return metadata, False
    merged = {**metadata, **extra}
    return merged, merged != metadata


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
        Otherwise such folders are left alone. Also forces io.json-derived
        channel fields (see ``_enrich_channels_from_io``) to be
        recomputed even when already populated -- e.g. to correct values
        written by an earlier, buggy version of an enricher -- rather
        than only filling ones that are still blank. Does not affect
        inear's gain gap-fill (see ``_enrich_inear_from_preferences``),
        which must never overwrite a real recorded gain regardless of
        this flag.

    Returns
    -------
    dict
        Counters: ``wrote``, ``enriched``, ``skipped_exists``,
        ``skipped_error``, ``renamed``, ``rename_conflicts``.
    '''
    counts = {
        'wrote': 0, 'enriched': 0, 'skipped_exists': 0, 'skipped_error': 0,
        'renamed': 0, 'rename_conflicts': 0,
    }
    for subfolder, parser in PARSERS.items():
        base = root / subfolder
        marker_key = MARKER_KEYS[subfolder]
        enricher = ENRICHERS.get(subfolder)
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
                # that information can no longer be recovered here. Either
                # way, io.json/final.preferences enrichment still applies --
                # those sidecars are independent of migration status.
                if _is_migrated(existing, marker_key):
                    counts['skipped_exists'] += 1
                    metadata, changed = _apply_enrichment(
                        cal_dir, existing, enricher, overwrite=overwrite)
                    if changed:
                        if dry_run:
                            print(f'WOULD enrich {meta_file}: {metadata}')
                        else:
                            meta_file.write_text(
                                json.dumps(metadata, indent=2, sort_keys=True)
                            )
                            print(f'ENRICHED {meta_file}')
                        counts['enriched'] += 1
                else:
                    print(f'SKIP  {cal_dir}: no usable {METADATA_FILENAME} '
                          f'and the directory name carries no recoverable '
                          f'metadata (already renamed?)')
                    counts['skipped_error'] += 1
                continue

            # The directory name still carries legacy metadata -- parse it
            # now. Needed both for the metadata write below (unless
            # already migrated and not --overwrite) and, for subfolders in
            # REPARENT_KEY, to know the new parent folder -- so this
            # happens unconditionally rather than only in the write branch.
            try:
                parsed = parser(cal_dir)
            except Exception as e:
                print(f'SKIP  {cal_dir}: could not parse ({e})')
                counts['skipped_error'] += 1
                continue

            # It must be captured into metadata.json now, regardless of
            # --overwrite -- otherwise the move/rename below would discard
            # it for good. Only an already fully-migrated file is exempt,
            # unless --overwrite is given to force a re-derive/rewrite
            # anyway.
            wrote = overwrite or not _is_migrated(existing, marker_key)
            if wrote:
                # Folder-name-derived fields win on key collisions -- they're
                # what cftscal's calibration classes read -- but any foreign
                # fields already in the file (e.g. psiexperiment's own
                # hostname/timestamp/version provenance) are kept alongside
                # them rather than being clobbered.
                metadata = {**existing, **parsed}
            else:
                metadata = existing

            # io.json/final.preferences enrichment runs unconditionally,
            # on the same pass as the legacy-name parse above -- not a
            # separate pass/flag -- so a single migrate() run recovers
            # everything recoverable for a folder in one go.
            metadata, enriched = _apply_enrichment(
                cal_dir, metadata, enricher, overwrite=overwrite)

            if wrote or enriched:
                if dry_run:
                    verb = 'merge into' if existing else 'write'
                    print(f'WOULD {verb} {meta_file}: {metadata}')
                else:
                    meta_file.write_text(
                        json.dumps(metadata, indent=2, sort_keys=True)
                    )
                    print(f'WROTE {meta_file}')
                if wrote:
                    counts['wrote'] += 1
                if enriched:
                    counts['enriched'] += 1
            else:
                counts['skipped_exists'] += 1

            reparent_key = REPARENT_KEY.get(subfolder)
            old_parent = cal_dir.parent
            if reparent_key is not None:
                new_path = old_parent.parent / str(parsed[reparent_key]) / date_only_name
            else:
                new_path = old_parent / date_only_name
            move_verb, moved_verb = (
                ('MOVE', 'MOVED') if reparent_key is not None
                else ('RENAME', 'RENAMED')
            )

            if new_path.exists():
                print(f'SKIP  {move_verb.lower()} {cal_dir} -> {new_path}: '
                      f'target already exists')
                counts['rename_conflicts'] += 1
            elif dry_run:
                print(f'WOULD {move_verb} {cal_dir} -> {new_path}')
                counts['renamed'] += 1
            else:
                if reparent_key is not None:
                    new_path.parent.mkdir(parents=True, exist_ok=True)
                cal_dir.rename(new_path)
                print(f'{moved_verb} {cal_dir} -> {new_path}')
                counts['renamed'] += 1
                # Clean up the now-vestigial old coupler/ear folder once
                # its last calibration has moved out of it.
                if (reparent_key is not None and old_parent.exists()
                        and not any(old_parent.iterdir())):
                    old_parent.rmdir()
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
             'already-migrated folders (default: skip them; only affects '
             'folders that still carry a legacy name), and force io.json '
             'channel fields to be recomputed even if already populated '
             '(e.g. to correct values from an earlier buggy run).'
    )
    args = parser.parse_args()

    print(f'Migrating calibration metadata under {args.root}')
    counts = migrate(args.root, dry_run=args.dry_run, overwrite=args.overwrite)
    verb = 'Would write' if args.dry_run else 'Wrote'
    enrich_verb = 'Would enrich' if args.dry_run else 'Enriched'
    rename_verb = 'Would rename' if args.dry_run else 'Renamed'
    print(
        f'\nDone. {verb} {counts["wrote"]} metadata file(s); '
        f'{enrich_verb} {counts["enriched"]} from io.json/final.preferences; '
        f'skipped {counts["skipped_exists"]} existing, '
        f'{counts["skipped_error"]} unrecoverable. '
        f'{rename_verb} {counts["renamed"]} folder(s); '
        f'{counts["rename_conflicts"]} rename conflict(s) left untouched.'
    )


if __name__ == '__main__':
    main()
