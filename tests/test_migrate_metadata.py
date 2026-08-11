'''
Tests for :mod:`cftscal.migrate_metadata` — parsers that recover metadata
from legacy calibration directory names.  These are one-shot recovery
code, so tests exist mainly to prevent someone touching the module from
silently breaking migration of already-acquired data.
'''
import datetime as dt
import json
from pathlib import Path

import pytest
import yaml

from cftscal import migrate_metadata as mm


def _folder(name):
    '''Parsers only touch ``folder.name``, so a Path stub is enough.'''
    return Path(name)


class TestParseDatetime:

    def test_valid_prefix(self):
        assert mm._parse_datetime('20260701-123456_anything') == (
            dt.datetime(2026, 7, 1, 12, 34, 56).isoformat()
        )

    def test_missing_prefix_raises(self):
        with pytest.raises(ValueError):
            mm._parse_datetime('no-timestamp-here')


class TestMicrophoneMeasurement:

    def test_extracts_sensor_id_and_pistonphone(self):
        result = mm._parse_microphone_measurement(
            _folder('20260701-123456_MMM0_PP1')
        )
        assert result == {
            'datetime': dt.datetime(2026, 7, 1, 12, 34, 56).isoformat(),
            'sensor_id': 'MMM0',
            'pistonphone': 'PP1',
        }


class TestMicrophoneGeneric:

    def test_extracts_measurement_mic_and_stimulus(self):
        result = mm._parse_microphone_generic(
            _folder('20260701-123456_generic_MMM0_golay')
        )
        assert result['microphone'] == 'MMM0'
        assert result['stimulus'] == 'golay'


class TestSpeaker:

    def test_extracts_microphone_and_method(self):
        result = mm._parse_speaker(
            _folder('20260701-123456_SPK1_MMM0_tone')
        )
        assert result['microphone'] == 'MMM0'
        assert result['method'] == 'tone'


class TestStarship:

    def test_extracts_microphone_coupler_stimulus(self):
        result = mm._parse_starship(
            _folder('20260701-123456_SS1_MMM0_coupler-A_golay')
        )
        assert result['microphone'] == 'MMM0'
        assert result['coupler'] == 'coupler-A'
        assert result['stimulus'] == 'golay'


class TestInputAmplifier:

    def test_extracts_gain_and_filter_fields(self):
        result = mm._parse_input_amplifier(
            _folder('20260701-123456_AMP1_1000x_10-10000Hz-filt-60Hz-input')
        )
        assert result == {
            'datetime': dt.datetime(2026, 7, 1, 12, 34, 56).isoformat(),
            'total_gain': 1000.0,
            'freq_lb': 10.0,
            'freq_ub': 10000.0,
            'filt_60Hz': 'on',
        }

    def test_fractional_frequencies_and_output_filter(self):
        result = mm._parse_input_amplifier(
            _folder('20260701-123456_AMP1_10x_0.1-20000.5Hz-filt-60Hz-output')
        )
        assert result['total_gain'] == 10.0
        assert result['freq_lb'] == 0.1
        assert result['freq_ub'] == 20000.5
        assert result['filt_60Hz'] == 'off'

    def test_unrecognized_format_raises(self):
        with pytest.raises(ValueError):
            mm._parse_input_amplifier(_folder('20260701-123456_AMP1'))


class TestInputRecording:

    def test_extracts_generator_and_sensor(self):
        result = mm._parse_input_recording(
            _folder('20260701-123456_chirp_MMM0')
        )
        assert result['generator'] == 'chirp'
        assert result['sensor'] == 'MMM0'


class TestInear:

    def test_extracts_coupler_and_starship(self):
        result = mm._parse_inear(
            _folder('20260701-123456_left_SS1')
        )
        assert result['coupler'] == 'left'
        assert result['starship'] == 'SS1'
        # No longer guessed from the filename -- see TestEnrichInear.
        assert 'output' not in result

    def test_secondary_suffix_stripped_from_coupler(self):
        result = mm._parse_inear(
            _folder('20260701-123456_C1-secondary_MMM5')
        )
        assert result['coupler'] == 'C1'
        assert result['starship'] == 'MMM5'
        assert 'output' not in result


class TestIrSensor:

    def test_extracts_input_name(self):
        result = mm._parse_ir_sensor(
            _folder('20260701-123456_ai0')
        )
        assert result['input_name'] == 'ai0'


def _make_cal_dir(tmp_path, subfolder, object_name, cal_name, metadata=None):
    '''Create ``<tmp_path>/<subfolder>/<object_name>/<cal_name>/``, optionally
    with a pre-existing ``metadata.json``, mirroring the on-disk layout
    ``migrate()`` walks.'''
    cal_dir = tmp_path / subfolder / object_name / cal_name
    cal_dir.mkdir(parents=True)
    if metadata is not None:
        (cal_dir / 'metadata.json').write_text(json.dumps(metadata))
    return cal_dir


ZERO = {'wrote': 0, 'enriched': 0, 'skipped_exists': 0, 'skipped_error': 0,
        'renamed': 0, 'rename_conflicts': 0}


def _counts(**overrides):
    return {**ZERO, **overrides}


class TestMigrate:
    '''
    Covers the skip-vs-migrate decision in ``migrate()`` itself, not just
    the folder-name parsers.  A calibration folder can have no
    ``metadata.json`` at all, an already cftscal-format one, or a *foreign*
    one written by something else (e.g. psiexperiment/psidata's own run
    provenance file) that happens to share the same filename but none of
    the keys cftscal reads.  It can also still carry its legacy,
    metadata-encoding name, or already be renamed down to a bare timestamp.
    '''

    def test_writes_and_renames_when_no_metadata_file(self, tmp_path):
        cal_dir = _make_cal_dir(
            tmp_path, 'microphone', 'MMM0', '20260701-123456_MMM0_PP1',
        )
        counts = mm.migrate(tmp_path)
        assert counts == _counts(wrote=1, renamed=1)

        new_dir = tmp_path / 'microphone' / 'MMM0' / '20260701-123456'
        assert new_dir.exists()
        assert not cal_dir.exists()
        metadata = json.loads((new_dir / 'metadata.json').read_text())
        assert metadata['sensor_id'] == 'MMM0'
        assert metadata['pistonphone'] == 'PP1'

    def test_bare_named_already_migrated_is_fully_skipped(self, tmp_path):
        # The true modern steady-state: already renamed, already has
        # cftscal-format metadata -- nothing to parse, nothing to rename.
        cal_dir = _make_cal_dir(
            tmp_path, 'microphone', 'MMM0', '20260701-123456',
            metadata={'datetime': '2026-07-01T12:34:56', 'sensor_id': 'MMM0',
                      'pistonphone': 'PP1'},
        )
        counts = mm.migrate(tmp_path)
        assert counts == _counts(skipped_exists=1)
        assert cal_dir.exists()

    def test_legacy_named_already_migrated_skips_write_but_still_renames(
        self, tmp_path,
    ):
        # Already fully migrated (has every field its marker requires) --
        # metadata.json is not rewritten, but the folder still carries its
        # legacy name and must be renamed regardless. Uses 'speaker' (a
        # single-key marker) so this is independent of microphone's
        # two-key marker special case, covered separately below.
        cal_dir = _make_cal_dir(
            tmp_path, 'speaker', 'SPK1', '20260701-123456_SPK1_MMM0_tone',
            metadata={'datetime': '2026-07-01T12:34:56', 'microphone': 'MMM0',
                      'method': 'tone'},
        )
        counts = mm.migrate(tmp_path)
        # wrote=0 (already fully migrated per the marker key, no re-parse
        # of legacy-name-derived fields), but enriched=1 -- the
        # folder-derived 'speaker' device backfill still applies
        # regardless of has_legacy_name, and since it changed the file,
        # this does NOT fall into the skipped_exists bucket either.
        assert counts == _counts(enriched=1, renamed=1)

        new_dir = tmp_path / 'speaker' / 'SPK1' / '20260701-123456'
        assert new_dir.exists()
        metadata = json.loads((new_dir / 'metadata.json').read_text())
        assert metadata == {'datetime': '2026-07-01T12:34:56', 'microphone': 'MMM0',
                             'method': 'tone', 'speaker': 'SPK1'}

    def test_merges_into_foreign_metadata_file(self, tmp_path):
        '''A metadata.json that exists but lacks cftscal's fields (e.g.
        psiexperiment's own hostname/timestamp/version provenance file)
        must still be migrated, with its existing fields preserved.'''
        _make_cal_dir(
            tmp_path, 'microphone', 'MMM0', '20260701-123456_MMM0_PP1',
            metadata={'hostname': 'rig1', 'version': {'psi': '0.6.4'}},
        )
        counts = mm.migrate(tmp_path)
        assert counts == _counts(wrote=1, renamed=1)

        new_dir = tmp_path / 'microphone' / 'MMM0' / '20260701-123456'
        metadata = json.loads((new_dir / 'metadata.json').read_text())
        assert metadata['sensor_id'] == 'MMM0'
        assert metadata['pistonphone'] == 'PP1'
        assert metadata['hostname'] == 'rig1'
        assert metadata['version'] == {'psi': '0.6.4'}

    def test_overwrite_remerges_legacy_named_already_migrated_file(self, tmp_path):
        _make_cal_dir(
            tmp_path, 'microphone', 'MMM0', '20260701-123456_MMM0_PP1',
            metadata={'datetime': 'stale', 'pistonphone': 'stale',
                      'hostname': 'rig1'},
        )
        counts = mm.migrate(tmp_path, overwrite=True)
        assert counts == _counts(wrote=1, renamed=1)

        new_dir = tmp_path / 'microphone' / 'MMM0' / '20260701-123456'
        metadata = json.loads((new_dir / 'metadata.json').read_text())
        assert metadata['pistonphone'] == 'PP1'
        assert metadata['sensor_id'] == 'MMM0'
        assert metadata['hostname'] == 'rig1'

    def test_overwrite_is_a_noop_for_bare_named_folders(self, tmp_path):
        # Nothing left in the name to re-derive -- --overwrite must not
        # blow away a perfectly good, already-renamed calibration.
        cal_dir = _make_cal_dir(
            tmp_path, 'microphone', 'MMM0', '20260701-123456',
            metadata={'datetime': '2026-07-01T12:34:56', 'sensor_id': 'MMM0',
                      'pistonphone': 'PP1'},
        )
        counts = mm.migrate(tmp_path, overwrite=True)
        assert counts == _counts(skipped_exists=1)
        assert json.loads((cal_dir / 'metadata.json').read_text()) == {
            'datetime': '2026-07-01T12:34:56', 'sensor_id': 'MMM0',
            'pistonphone': 'PP1',
        }

    def test_dry_run_does_not_write_or_rename(self, tmp_path):
        cal_dir = _make_cal_dir(
            tmp_path, 'microphone', 'MMM0', '20260701-123456_MMM0_PP1',
            metadata={'hostname': 'rig1'},
        )
        counts = mm.migrate(tmp_path, dry_run=True)
        assert counts == _counts(wrote=1, renamed=1)
        assert cal_dir.exists()
        assert json.loads((cal_dir / 'metadata.json').read_text()) == {
            'hostname': 'rig1',
        }
        assert not (tmp_path / 'microphone' / 'MMM0' / '20260701-123456').exists()

    def test_unparseable_legacy_name_skipped_as_error(self, tmp_path):
        # Has a legacy-looking suffix, but too few segments for the
        # starship parser (needs mic/coupler/stimulus) -- must not be
        # renamed, since that would destroy the unrecovered data.
        cal_dir = _make_cal_dir(tmp_path, 'starship', 'SS1', '20260701-123456_SS1')
        counts = mm.migrate(tmp_path)
        assert counts == _counts(skipped_error=1)
        assert cal_dir.exists()

    def test_bare_name_without_metadata_is_unrecoverable_error(self, tmp_path):
        # Already renamed (or never had a legacy name), but has no
        # metadata.json either -- nothing left to recover it from.
        cal_dir = _make_cal_dir(tmp_path, 'microphone', 'MMM0', '20260701-123456')
        counts = mm.migrate(tmp_path)
        assert counts == _counts(skipped_error=1)
        assert cal_dir.exists()

    def test_folder_without_timestamp_prefix_ignored(self, tmp_path):
        # Not even a candidate calibration folder (e.g. stray non-cal
        # directory a user created) -- silently not visited, not an error.
        cal_dir = _make_cal_dir(tmp_path, 'microphone', 'MMM0', 'not-a-timestamp')
        counts = mm.migrate(tmp_path)
        assert counts == _counts()
        assert cal_dir.exists()

    def test_corrupt_existing_file_skipped_as_error(self, tmp_path):
        cal_dir = _make_cal_dir(
            tmp_path, 'microphone', 'MMM0', '20260701-123456_MMM0_PP1',
        )
        (cal_dir / 'metadata.json').write_text('not json')
        counts = mm.migrate(tmp_path)
        assert counts == _counts(skipped_error=1)
        assert cal_dir.exists()

    def test_finds_and_renames_calibrations_nested_under_org_folders(self, tmp_path):
        '''e.g. ``starship/MMM0/hide/<cal>/`` -- an extra organizational
        folder (here, one used to tuck away retired calibrations) between
        the object folder and the calibration folder. The rename must only
        touch the leaf folder, preserving that nesting.'''
        _make_cal_dir(
            tmp_path, 'starship', 'MMM0',
            'hide/20260701-123456_MMM0_GRAS-40DP_tube-0mm_golay',
        )
        counts = mm.migrate(tmp_path)
        # enriched=1: the folder-derived 'starship' device backfill sees
        # 'hide' as the object folder here (whatever sits directly above
        # the leaf calibration folder -- same convention
        # CFTSBaseLoader._walk_objects uses), matching how this
        # fixture's grouping already works; 'MMM0' is the organizational
        # folder wrapping it in this specific test layout.
        assert counts == _counts(wrote=1, enriched=1, renamed=1)

        new_dir = (
            tmp_path / 'starship' / 'MMM0' / 'hide' / '20260701-123456'
        )
        assert new_dir.exists()
        metadata = json.loads((new_dir / 'metadata.json').read_text())
        assert metadata['microphone'] == 'GRAS-40DP'
        assert metadata['starship'] == 'hide'

    def test_rename_conflict_leaves_both_untouched_but_still_writes_metadata(
        self, tmp_path,
    ):
        # Pathological case: two calibrations that would collide on
        # rename. Neither should be silently clobbered. The pre-existing
        # bare-named dir is itself a valid (if empty, metadata-less)
        # calibration folder that migrate() will separately visit and
        # report as unrecoverable -- it isn't touched or deleted either.
        cal_dir = _make_cal_dir(
            tmp_path, 'microphone', 'MMM0', '20260701-123456_MMM0_PP1',
        )
        conflict_dir = tmp_path / 'microphone' / 'MMM0' / '20260701-123456'
        conflict_dir.mkdir()

        counts = mm.migrate(tmp_path)
        assert counts == _counts(wrote=1, rename_conflicts=1, skipped_error=1)
        assert cal_dir.exists()
        assert conflict_dir.exists()
        assert not (conflict_dir / 'metadata.json').exists()
        metadata = json.loads((cal_dir / 'metadata.json').read_text())
        assert metadata['pistonphone'] == 'PP1'

    def test_backfills_sensor_id_for_previously_migrated_folder(self, tmp_path):
        # Simulates a folder touched by an earlier version of this script
        # that only recovered 'pistonphone' -- 'sensor_id' must still be
        # backfilled on a later run (no --overwrite needed), since the
        # folder still carries a legacy name and 'sensor_id' is now part
        # of what "fully migrated" means for this type.
        _make_cal_dir(
            tmp_path, 'microphone', 'MMM0', '20260701-123456_MMM0_PP1',
            metadata={'datetime': '2026-07-01T12:34:56', 'pistonphone': 'PP1'},
        )
        counts = mm.migrate(tmp_path)
        assert counts == _counts(wrote=1, renamed=1)

        new_dir = tmp_path / 'microphone' / 'MMM0' / '20260701-123456'
        metadata = json.loads((new_dir / 'metadata.json').read_text())
        assert metadata['sensor_id'] == 'MMM0'
        assert metadata['pistonphone'] == 'PP1'

    def test_input_amplifier_extracts_and_renames(self, tmp_path):
        _make_cal_dir(
            tmp_path, 'input_amplifier', 'AMP1',
            '20260701-123456_AMP1_1000x_10-10000Hz-filt-60Hz-input',
        )
        counts = mm.migrate(tmp_path)
        # enriched=1: the folder-derived 'sensor_id' device backfill.
        assert counts == _counts(wrote=1, enriched=1, renamed=1)

        new_dir = tmp_path / 'input_amplifier' / 'AMP1' / '20260701-123456'
        metadata = json.loads((new_dir / 'metadata.json').read_text())
        assert metadata['total_gain'] == 1000.0
        assert metadata['freq_lb'] == 10.0
        assert metadata['freq_ub'] == 10000.0
        assert metadata['filt_60Hz'] == 'on'
        assert metadata['sensor_id'] == 'AMP1'

    def test_inear_reparents_under_starship_folder(self, tmp_path):
        # inear is special-cased via REPARENT_KEY: the master folder for
        # a migrated calibration is the starship (device ID) parsed from
        # the legacy leaf name, not the coupler folder it's nested under
        # today.
        cal_dir = _make_cal_dir(
            tmp_path, 'inear', 'C1-secondary',
            '20260701-123456_C1-secondary_MMM5',
        )
        counts = mm.migrate(tmp_path)
        # No final.preferences sidecar in this fixture, so 'output' is
        # never recovered, but 'gain' is still filled in as 40 (the fixed
        # historical value) since it was simply missing -- that's the
        # enrichment step, folded into this same migrate() pass.
        assert counts == _counts(wrote=1, enriched=1, renamed=1)

        new_dir = tmp_path / 'inear' / 'MMM5' / '20260701-123456'
        assert new_dir.exists()
        assert not cal_dir.exists()
        # The now-empty old coupler folder is cleaned up.
        assert not (tmp_path / 'inear' / 'C1-secondary').exists()

        metadata = json.loads((new_dir / 'metadata.json').read_text())
        assert metadata['coupler'] == 'C1'
        assert metadata['starship'] == 'MMM5'
        assert metadata['gain'] == 40
        # No final.preferences sidecar in this fixture -- output is no
        # longer guessed from the filename, so it's simply absent.
        assert 'output' not in metadata

    def test_inear_reparent_preserves_org_folder_nesting(self, tmp_path):
        # A calibration organized under an extra lab/study folder above
        # the coupler folder keeps that nesting -- only the coupler
        # segment is replaced by the starship.
        cal_dir = _make_cal_dir(
            tmp_path, 'inear', 'Lab1/C1',
            '20260701-123456_C1_MMM5',
        )
        counts = mm.migrate(tmp_path)
        assert counts == _counts(wrote=1, enriched=1, renamed=1)

        new_dir = tmp_path / 'inear' / 'Lab1' / 'MMM5' / '20260701-123456'
        assert new_dir.exists()
        assert not cal_dir.exists()
        assert not (tmp_path / 'inear' / 'Lab1' / 'C1').exists()

    def test_inear_reparent_conflict_is_reported_not_overwritten(self, tmp_path):
        # Two different coupler folders whose calibrations happen to
        # share the exact same timestamp both resolve to the same
        # inear/MMM5/<timestamp>/ destination -- must be reported as a
        # conflict, not silently clobbered.
        cal_dir_1 = _make_cal_dir(
            tmp_path, 'inear', 'C1', '20260701-123456_C1_MMM5',
        )
        cal_dir_2 = _make_cal_dir(
            tmp_path, 'inear', 'C2', '20260701-123456_C2_MMM5',
        )
        counts = mm.migrate(tmp_path)
        # Enrichment (gain=40) runs before the move-conflict check, so
        # both folders get it -- even the one whose move ultimately fails.
        assert counts == _counts(wrote=2, enriched=2, renamed=1, rename_conflicts=1)

        new_dir = tmp_path / 'inear' / 'MMM5' / '20260701-123456'
        assert new_dir.exists()
        # Exactly one of the two source folders got moved out; the other
        # is left in place (with its metadata.json already written) for
        # the user to resolve by hand.
        assert cal_dir_1.exists() != cal_dir_2.exists()


class TestIsMigratedAlternatives:
    '''MARKER_KEYS['microphone_generic'] uses a list of alternatives so a
    calibration migrated before the measurement_microphone -> microphone
    rename still reads as migrated.'''

    def test_either_alternative_counts_as_migrated(self):
        assert mm._is_migrated(
            {'datetime': 'x', 'measurement_microphone': 'MMM0'},
            ['microphone', 'measurement_microphone'],
        )
        assert mm._is_migrated(
            {'datetime': 'x', 'microphone': 'MMM0'},
            ['microphone', 'measurement_microphone'],
        )

    def test_neither_alternative_present_is_not_migrated(self):
        assert not mm._is_migrated(
            {'datetime': 'x'},
            ['microphone', 'measurement_microphone'],
        )


class TestEnrichInear:

    def test_fills_missing_gain_with_40(self, tmp_path):
        result = mm._enrich_inear_from_preferences(tmp_path, {})
        assert result['gain'] == 40

    def test_does_not_overwrite_existing_gain(self, tmp_path):
        # New recordings write a real, possibly non-40 gain -- migration
        # must never clobber it.
        result = mm._enrich_inear_from_preferences(tmp_path, {'gain': 20})
        assert 'gain' not in result

    def test_extracts_output_from_final_preferences(self, tmp_path):
        prefs = {
            'context': {'parameters': {'system_starship_settings': {
                'system_output': {'selected': 'secondary'},
            }}},
        }
        (tmp_path / 'final.preferences').write_text(yaml.dump(prefs))
        result = mm._enrich_inear_from_preferences(tmp_path, {'gain': 40})
        assert result == {'output': 'secondary'}

    def test_missing_final_preferences_leaves_output_unset(self, tmp_path):
        result = mm._enrich_inear_from_preferences(tmp_path, {'gain': 40})
        assert 'output' not in result

    def test_malformed_final_preferences_is_ignored(self, tmp_path):
        (tmp_path / 'final.preferences').write_text('a: [1, 2')
        result = mm._enrich_inear_from_preferences(tmp_path, {'gain': 40})
        assert 'output' not in result

    def test_final_preferences_missing_expected_keys_is_ignored(self, tmp_path):
        (tmp_path / 'final.preferences').write_text(yaml.dump({'context': {}}))
        result = mm._enrich_inear_from_preferences(tmp_path, {'gain': 40})
        assert 'output' not in result

    def test_overwrite_does_not_clobber_a_real_recorded_gain(self, tmp_path):
        # Unlike _enrich_channels_from_io's channel fields, gain must
        # never be forced back to 40 under --overwrite -- current
        # recordings write a real, possibly non-40 gain that --overwrite
        # is not meant to touch.
        result = mm._enrich_inear_from_preferences(
            tmp_path, {'gain': 20}, overwrite=True,
        )
        assert 'gain' not in result


class TestEnrichChannelsFromIo:
    '''
    Recovered values must be the human-readable ``label`` (e.g. "Starship
    A (microphone)"), not the raw manifest ``name``/dict key (e.g.
    "starship_A_microphone") -- that's what every plugin's settings.py
    writes into these same fields for new recordings (``ai.input_label``/
    ``ao.output_label``/etc.), and mixing the two would make the very
    columns this is for (comparing historical vs current calibrations)
    inconsistent within themselves.
    '''

    def _write_io(self, cal_dir, input_active=(), output_active=(),
                  extra_input=None, extra_output=None):
        # `input_active`/`output_active` are lists of (name, label) or
        # (name, label, gain) tuples for real-hardware-channel entries
        # marked active -- matches real io.json's shape for
        # NIDAQHardwareAIChannel/NIDAQHardwareAOChannel. `extra_input`/
        # `extra_output` are raw dicts merged in as-is, for injecting
        # non-audio channel types (e.g. a position encoder) or other
        # edge cases the (name, label[, gain]) shorthand can't express.
        def entries(active, type_):
            out = {}
            for item in active:
                name, label = item[0], item[1]
                entry = {'label': label, 'active': True, '__type__': type_}
                if len(item) > 2:
                    entry['gain'] = item[2]
                out[name] = entry
            return out
        io_data = {
            'input': {**entries(input_active, 'NIDAQHardwareAIChannel'),
                      **(extra_input or {})},
            'output': {**entries(output_active, 'NIDAQHardwareAOChannel'),
                       **(extra_output or {})},
        }
        (cal_dir / 'io.json').write_text(json.dumps(io_data))

    def test_single_active_input_recovers_label(self, tmp_path):
        self._write_io(tmp_path, input_active=[('ai0', 'Ch 1')])
        enrich = mm._enrich_channels_from_io(input_field='input_channel')
        assert enrich(tmp_path, {}) == {'input_channel': 'Ch 1'}

    def test_falls_back_to_name_when_label_missing(self, tmp_path):
        (tmp_path / 'io.json').write_text(json.dumps({
            'input': {'ai0': {'active': True, '__type__': 'NIDAQHardwareAIChannel'}},
            'output': {},
        }))
        enrich = mm._enrich_channels_from_io(input_field='input_channel')
        assert enrich(tmp_path, {}) == {'input_channel': 'ai0'}

    def test_non_audio_channel_type_excluded_from_candidates(self, tmp_path):
        # e.g. a position encoder left permanently active in the DAQ
        # engine config on older rigs -- must not count as a candidate
        # (real bug: this made microphone recordings on affected rigs
        # look ambiguous even though only one real mic channel was ever
        # active).
        self._write_io(
            tmp_path, input_active=[('ai0', 'Calibration microphone')],
            extra_input={
                'turntable_angle': {
                    'label': 'Turntable angle', 'active': True,
                    '__type__': 'NIDAQHardwareCIAngPosEncoderChannel',
                },
            },
        )
        enrich = mm._enrich_channels_from_io(input_field='input_channel')
        assert enrich(tmp_path, {}) == {'input_channel': 'Calibration microphone'}

    def test_ambiguous_active_inputs_left_blank(self, tmp_path):
        # e.g. starship's real io.json, where the starship's own probe
        # mic and the reference/calibration mic are both real, genuinely
        # simultaneously-active channels.
        self._write_io(tmp_path, input_active=[
            ('starship_A_microphone', 'Starship A (microphone)'),
            ('calibration_microphone', 'Calibration microphone'),
        ])
        enrich = mm._enrich_channels_from_io(input_field='input_channel')
        assert enrich(tmp_path, {}) == {}

    def test_prefer_keys_resolves_ambiguity(self, tmp_path):
        self._write_io(tmp_path, input_active=[
            ('starship_A_microphone', 'Starship A (microphone)'),
            ('calibration_microphone', 'Calibration microphone'),
        ])
        enrich = mm._enrich_channels_from_io(
            input_field='microphone_channel',
            input_prefer_keys=('microphone_calibration', 'calibration_microphone'),
        )
        assert enrich(tmp_path, {}) == {'microphone_channel': 'Calibration microphone'}

    def test_prefer_keys_both_spellings_checked(self, tmp_path):
        # The reference mic's channel key isn't spelled consistently
        # across this lab's history -- both orderings are real.
        self._write_io(tmp_path, input_active=[
            ('starship_A_microphone', 'Starship A (microphone)'),
            ('microphone_calibration', 'Calibration microphone'),
        ])
        enrich = mm._enrich_channels_from_io(
            input_field='microphone_channel',
            input_prefer_keys=('microphone_calibration', 'calibration_microphone'),
        )
        assert enrich(tmp_path, {}) == {'microphone_channel': 'Calibration microphone'}

    def test_prefer_keys_still_ambiguous_when_no_match(self, tmp_path):
        self._write_io(tmp_path, input_active=[
            ('starship_A_microphone', 'Starship A (microphone)'),
            ('some_other_mic', 'Some other mic'),
        ])
        enrich = mm._enrich_channels_from_io(
            input_field='microphone_channel',
            input_prefer_keys=('microphone_calibration', 'calibration_microphone'),
        )
        assert enrich(tmp_path, {}) == {}

    def test_gain_field_recovers_resolved_input_channels_gain(self, tmp_path):
        self._write_io(tmp_path, input_active=[('ai0', 'Ch 1', 20.0)])
        enrich = mm._enrich_channels_from_io(
            input_field='input_channel', gain_field='gain')
        assert enrich(tmp_path, {}) == {'input_channel': 'Ch 1', 'gain': 20.0}

    def test_gain_field_uses_prefer_keys_resolution(self, tmp_path):
        # gain must come from the SAME channel the tie-break resolved,
        # not just "whichever one happens to have a gain".
        self._write_io(tmp_path, input_active=[
            ('starship_A_microphone', 'Starship A (microphone)', 20.0),
            ('calibration_microphone', 'Calibration microphone', 0.0),
        ])
        enrich = mm._enrich_channels_from_io(
            input_field='microphone_channel',
            input_prefer_keys=('microphone_calibration', 'calibration_microphone'),
            gain_field='microphone_gain',
        )
        assert enrich(tmp_path, {}) == {
            'microphone_channel': 'Calibration microphone',
            'microphone_gain': 0.0,
        }

    def test_gain_field_does_not_overwrite_existing_value(self, tmp_path):
        self._write_io(tmp_path, input_active=[('ai0', 'Ch 1', 20.0)])
        enrich = mm._enrich_channels_from_io(
            input_field='input_channel', gain_field='gain')
        assert enrich(tmp_path, {'gain': 40}) == {'input_channel': 'Ch 1'}

    def test_gain_field_left_blank_when_input_still_ambiguous(self, tmp_path):
        self._write_io(tmp_path, input_active=[
            ('starship_A_microphone', 'Starship A (microphone)', 20.0),
            ('some_other_mic', 'Some other mic', 30.0),
        ])
        enrich = mm._enrich_channels_from_io(
            input_field='microphone_channel', gain_field='gain')
        assert enrich(tmp_path, {}) == {}

    def test_no_active_inputs_left_blank(self, tmp_path):
        self._write_io(tmp_path)
        enrich = mm._enrich_channels_from_io(input_field='input_channel')
        assert enrich(tmp_path, {}) == {}

    def test_does_not_overwrite_existing_value(self, tmp_path):
        self._write_io(tmp_path, input_active=[('ai0', 'Ch 1')])
        enrich = mm._enrich_channels_from_io(input_field='input_channel')
        assert enrich(tmp_path, {'input_channel': 'already-set'}) == {}

    def test_overwrite_recomputes_existing_value(self, tmp_path):
        # Lets a bad value (e.g. one written by an earlier, buggy
        # enricher that recovered the raw manifest name instead of the
        # label) get corrected by re-running with --overwrite, instead
        # of requiring the field to be manually cleared first.
        self._write_io(tmp_path, input_active=[('ai0', 'Ch 1')])
        enrich = mm._enrich_channels_from_io(input_field='input_channel')
        assert enrich(
            tmp_path, {'input_channel': 'ai0'}, overwrite=True,
        ) == {'input_channel': 'Ch 1'}

    def test_recovers_both_input_and_output(self, tmp_path):
        self._write_io(
            tmp_path, input_active=[('ai0', 'Ch 1')],
            output_active=[('ao0', 'Ch 0')],
        )
        enrich = mm._enrich_channels_from_io(
            input_field='microphone_channel', output_field='output_channel')
        assert enrich(tmp_path, {}) == {
            'microphone_channel': 'Ch 1', 'output_channel': 'Ch 0',
        }

    def test_missing_io_file_returns_empty(self, tmp_path):
        enrich = mm._enrich_channels_from_io(input_field='input_channel')
        assert enrich(tmp_path, {}) == {}

    def test_corrupt_io_file_returns_empty(self, tmp_path):
        (tmp_path / 'io.json').write_text('not json')
        enrich = mm._enrich_channels_from_io(input_field='input_channel')
        assert enrich(tmp_path, {}) == {}


class TestEnrichStarshipGainFromIo:
    '''
    The starship's own device gain comes from its own probe-mic channel
    (e.g. "starship_A_microphone"), never the reference/calibration mic's
    -- these are two different, simultaneously-active real channels with
    their own separate gains in the same io.json.
    '''

    def _write_io(self, cal_dir, entries):
        # entries: dict of name -> (label, type_, active, gain)
        io_data = {'input': {}, 'output': {}}
        for name, (label, type_, active, gain) in entries.items():
            entry = {'label': label, 'active': active, '__type__': type_}
            if gain is not None:
                entry['gain'] = gain
            io_data['input'][name] = entry
        (cal_dir / 'io.json').write_text(json.dumps(io_data))

    def test_recovers_starship_mic_gain_not_reference_mic_gain(self, tmp_path):
        self._write_io(tmp_path, {
            'starship_A_microphone': (
                'Starship A (microphone)', 'NIDAQHardwareAIChannel', True, 20.0),
            'microphone_calibration': (
                'Calibration microphone', 'NIDAQHardwareAIChannel', True, 0.0),
        })
        result = mm._enrich_starship_gain_from_io(tmp_path, {})
        assert result == {'gain': 20.0}

    def test_ignores_non_audio_channel_types(self, tmp_path):
        self._write_io(tmp_path, {
            'starship_A_microphone': (
                'Starship A (microphone)', 'NIDAQHardwareAIChannel', True, 20.0),
            'turntable_angle': (
                'Turntable angle', 'NIDAQHardwareCIAngPosEncoderChannel', True, None),
        })
        result = mm._enrich_starship_gain_from_io(tmp_path, {})
        assert result == {'gain': 20.0}

    def test_ambiguous_when_two_starship_connections_active(self, tmp_path):
        self._write_io(tmp_path, {
            'starship_A_microphone': (
                'Starship A (microphone)', 'NIDAQHardwareAIChannel', True, 20.0),
            'starship_B_microphone': (
                'Starship B (microphone)', 'NIDAQHardwareAIChannel', True, 40.0),
        })
        result = mm._enrich_starship_gain_from_io(tmp_path, {})
        assert result == {}

    def test_does_not_overwrite_existing_gain(self, tmp_path):
        self._write_io(tmp_path, {
            'starship_A_microphone': (
                'Starship A (microphone)', 'NIDAQHardwareAIChannel', True, 20.0),
        })
        result = mm._enrich_starship_gain_from_io(tmp_path, {'gain': 40})
        assert result == {}

    def test_overwrite_recomputes(self, tmp_path):
        self._write_io(tmp_path, {
            'starship_A_microphone': (
                'Starship A (microphone)', 'NIDAQHardwareAIChannel', True, 20.0),
        })
        result = mm._enrich_starship_gain_from_io(
            tmp_path, {'gain': 40}, overwrite=True)
        assert result == {'gain': 20.0}

    def test_missing_io_file_returns_empty(self, tmp_path):
        assert mm._enrich_starship_gain_from_io(tmp_path, {}) == {}


class TestEnrichInputRecordingFromIo:

    def _write_io(self, cal_dir, active):
        # active: list of (name, label, gain)
        entries = {}
        for name, label, gain in active:
            entry = {'label': label, 'active': True,
                     '__type__': 'NIDAQHardwareAIChannel'}
            if gain is not None:
                entry['gain'] = gain
            entries[name] = entry
        (cal_dir / 'io.json').write_text(
            json.dumps({'input': entries, 'output': {}}))

    def test_recovers_real_label_and_gain_for_legacy_shape(self, tmp_path):
        self._write_io(tmp_path, [('ai0', 'Ch 2', 20.0)])
        result = mm._enrich_input_recording_from_io(
            tmp_path, {'sensor': 'MMM0'})
        assert result == {
            'sensors': {'selected_input': {
                'label': 'Ch 2', 'sensor': 'MMM0', 'gain': 20.0,
            }},
        }

    def test_no_gain_key_when_io_lacks_gain(self, tmp_path):
        self._write_io(tmp_path, [('ai0', 'Ch 2', None)])
        result = mm._enrich_input_recording_from_io(
            tmp_path, {'sensor': 'MMM0'})
        assert result['sensors']['selected_input'] == {
            'label': 'Ch 2', 'sensor': 'MMM0',
        }

    def test_noop_when_sensors_dict_already_present(self, tmp_path):
        self._write_io(tmp_path, [('ai0', 'Ch 2', 20.0)])
        metadata = {'sensors': {'ai0': {'label': 'Ch 2', 'sensor': 'MMM0'}}}
        assert mm._enrich_input_recording_from_io(tmp_path, metadata) == {}

    def test_noop_when_no_legacy_sensor_key(self, tmp_path):
        self._write_io(tmp_path, [('ai0', 'Ch 2', 20.0)])
        assert mm._enrich_input_recording_from_io(tmp_path, {}) == {}

    def test_noop_when_ambiguous(self, tmp_path):
        self._write_io(tmp_path, [('ai0', 'Ch 2', 20.0), ('ai1', 'Ch 3', 0.0)])
        result = mm._enrich_input_recording_from_io(
            tmp_path, {'sensor': 'MMM0'})
        assert result == {}

    def test_missing_io_file_returns_empty(self, tmp_path):
        assert mm._enrich_input_recording_from_io(
            tmp_path, {'sensor': 'MMM0'}) == {}


class TestFixInputAmplifierTotalGain:

    def _write_gain(self, cal_dir, measured):
        (cal_dir / 'amplifier_gain.json').write_text(
            json.dumps({'gain mean (linear)': measured}))

    def test_corrects_when_ratio_near_100(self, tmp_path):
        self._write_gain(tmp_path, 50373.45)
        result = mm._fix_input_amplifier_total_gain(
            tmp_path, {'total_gain': 500.0})
        assert result == {'total_gain': 50000.0}

    def test_leaves_alone_when_ratio_near_1(self, tmp_path):
        self._write_gain(tmp_path, 50598.22)
        result = mm._fix_input_amplifier_total_gain(
            tmp_path, {'total_gain': 50000.0})
        assert result == {}

    def test_leaves_alone_without_amplifier_gain_file(self, tmp_path):
        result = mm._fix_input_amplifier_total_gain(
            tmp_path, {'total_gain': 500.0})
        assert result == {}

    def test_leaves_alone_without_total_gain(self, tmp_path):
        self._write_gain(tmp_path, 50373.45)
        assert mm._fix_input_amplifier_total_gain(tmp_path, {}) == {}

    def test_leaves_alone_when_ratio_unrelated(self, tmp_path):
        # e.g. the one real ~10,100 outlier that isn't part of the 100x
        # pattern -- must not get "corrected" into nonsense.
        self._write_gain(tmp_path, 10103.66)
        result = mm._fix_input_amplifier_total_gain(
            tmp_path, {'total_gain': 500.0})
        assert result == {}

    def test_corrupt_amplifier_gain_file_leaves_alone(self, tmp_path):
        (tmp_path / 'amplifier_gain.json').write_text('not json')
        result = mm._fix_input_amplifier_total_gain(
            tmp_path, {'total_gain': 500.0})
        assert result == {}

    def test_runs_regardless_of_overwrite_flag(self, tmp_path):
        # Corrects a known-wrong value -- not gated by --overwrite, same
        # as inear's `output`.
        self._write_gain(tmp_path, 50373.45)
        result = mm._fix_input_amplifier_total_gain(
            tmp_path, {'total_gain': 500.0}, overwrite=False)
        assert result == {'total_gain': 50000.0}


class TestEnrichDeviceFromFolder:
    '''
    Backfill-only: real settings.py already writes the device field
    directly for new recordings. Safe to derive from cal_dir.parent for
    historical data specifically because no data has been acquired since
    the target-folder-redirection feature existed (confirmed with user),
    so there's no historical case where the folder and the actual
    device diverge.
    '''

    def test_recovers_device_from_parent_folder(self, tmp_path):
        cal_dir = tmp_path / 'MMM6' / '20260701-123456'
        cal_dir.mkdir(parents=True)
        enrich = mm._enrich_device_from_folder('starship')
        assert enrich(cal_dir, {}) == {'starship': 'MMM6'}

    def test_does_not_overwrite_existing_value(self, tmp_path):
        cal_dir = tmp_path / 'MMM6' / '20260701-123456'
        cal_dir.mkdir(parents=True)
        enrich = mm._enrich_device_from_folder('starship')
        assert enrich(cal_dir, {'starship': 'MMM5'}) == {}

    def test_overwrite_recomputes(self, tmp_path):
        cal_dir = tmp_path / 'MMM6' / '20260701-123456'
        cal_dir.mkdir(parents=True)
        enrich = mm._enrich_device_from_folder('starship')
        assert enrich(cal_dir, {'starship': 'MMM5'}, overwrite=True) == {
            'starship': 'MMM6',
        }

    def test_field_name_is_configurable(self, tmp_path):
        cal_dir = tmp_path / 'SPK1' / '20260701-123456'
        cal_dir.mkdir(parents=True)
        enrich = mm._enrich_device_from_folder('speaker')
        assert enrich(cal_dir, {}) == {'speaker': 'SPK1'}


class TestCompose:

    def test_runs_each_enricher_and_merges_results(self):
        def a(cal_dir, metadata, overwrite=False):
            return {'x': 1}
        def b(cal_dir, metadata, overwrite=False):
            return {'y': 2}
        combined = mm._compose(a, b)
        assert combined(None, {}) == {'x': 1, 'y': 2}

    def test_later_enricher_sees_earlier_enrichers_output(self):
        def a(cal_dir, metadata, overwrite=False):
            return {'x': 1}
        def b(cal_dir, metadata, overwrite=False):
            return {'saw_x': metadata.get('x')}
        combined = mm._compose(a, b)
        assert combined(None, {}) == {'x': 1, 'saw_x': 1}

    def test_enricher_returning_nothing_is_skipped(self):
        def a(cal_dir, metadata, overwrite=False):
            return {}
        def b(cal_dir, metadata, overwrite=False):
            return {'y': 2}
        combined = mm._compose(a, b)
        assert combined(None, {}) == {'y': 2}


class TestMigrateEnrichment:
    '''io.json/final.preferences enrichment is folded into migrate() itself
    (not a separate pass/flag), and runs for every folder it visits --
    both already-migrated (bare-timestamp) folders and ones still being
    parsed from a legacy name in the same pass.'''

    def test_enriches_bare_named_already_migrated_inear_folder(self, tmp_path):
        cal_dir = _make_cal_dir(
            tmp_path, 'inear', 'MMM5', '20260701-123456',
            metadata={'datetime': '2026-07-01T12:34:56', 'starship': 'MMM5',
                      'coupler': 'C1'},
        )
        prefs = {
            'context': {'parameters': {'system_starship_settings': {
                'system_output': {'selected': 'secondary'},
            }}},
        }
        (cal_dir / 'final.preferences').write_text(yaml.dump(prefs))

        counts = mm.migrate(tmp_path)
        assert counts == _counts(skipped_exists=1, enriched=1)

        metadata = json.loads((cal_dir / 'metadata.json').read_text())
        assert metadata['output'] == 'secondary'
        assert metadata['gain'] == 40

    def test_enriches_legacy_named_folder_in_the_same_pass(self, tmp_path):
        cal_dir = _make_cal_dir(
            tmp_path, 'inear', 'C1', '20260701-123456_C1_MMM5',
        )
        prefs = {
            'context': {'parameters': {'system_starship_settings': {
                'system_output': {'selected': 'primary'},
            }}},
        }
        (cal_dir / 'final.preferences').write_text(yaml.dump(prefs))

        counts = mm.migrate(tmp_path)
        assert counts == _counts(wrote=1, enriched=1, renamed=1)

        new_dir = tmp_path / 'inear' / 'MMM5' / '20260701-123456'
        metadata = json.loads((new_dir / 'metadata.json').read_text())
        assert metadata['output'] == 'primary'
        assert metadata['gain'] == 40
        assert metadata['coupler'] == 'C1'
        assert metadata['starship'] == 'MMM5'

    def test_enrichment_is_idempotent_on_a_second_run(self, tmp_path):
        cal_dir = _make_cal_dir(
            tmp_path, 'inear', 'MMM5', '20260701-123456',
            metadata={'datetime': '2026-07-01T12:34:56', 'starship': 'MMM5',
                      'coupler': 'C1'},
        )
        prefs = {
            'context': {'parameters': {'system_starship_settings': {
                'system_output': {'selected': 'secondary'},
            }}},
        }
        (cal_dir / 'final.preferences').write_text(yaml.dump(prefs))

        mm.migrate(tmp_path)
        counts = mm.migrate(tmp_path)
        assert counts == _counts(skipped_exists=1)

    def test_starship_full_pipeline_resolves_both_channels_and_gains(self, tmp_path):
        # Real starship io.json always has both the starship's own probe
        # mic and the reference/calibration mic simultaneously active --
        # the prefer_keys tie-break resolves microphone_channel/
        # microphone_gain to the reference mic, while starship_channel
        # and gain come from the starship's own channels (output
        # direction and _enrich_starship_gain_from_io, respectively).
        cal_dir = _make_cal_dir(
            tmp_path, 'starship', 'SS1', '20260701-123456',
            metadata={'datetime': '2026-07-01T12:34:56', 'microphone': 'MMM0'},
        )
        io_data = {
            'input': {
                'starship_A_microphone': {
                    'label': 'Starship A (microphone)', 'active': True,
                    '__type__': 'NIDAQHardwareAIChannel', 'gain': 20.0,
                },
                'calibration_microphone': {
                    'label': 'Calibration microphone', 'active': True,
                    '__type__': 'NIDAQHardwareAIChannel', 'gain': 0.0,
                },
            },
            'output': {
                'starship_A_primary': {
                    'label': 'Starship A (primary)', 'active': True,
                    '__type__': 'NIDAQHardwareAOChannel',
                },
            },
        }
        (cal_dir / 'io.json').write_text(json.dumps(io_data))

        counts = mm.migrate(tmp_path)
        assert counts == _counts(skipped_exists=1, enriched=1)

        metadata = json.loads((cal_dir / 'metadata.json').read_text())
        # Recovers the human-readable label, matching what settings.py
        # writes for new recordings -- not the raw manifest name.
        assert metadata['microphone_channel'] == 'Calibration microphone'
        assert metadata['microphone_gain'] == 0.0
        assert metadata['starship_channel'] == 'Starship A (primary)'
        assert metadata['gain'] == 20.0

    def test_starship_microphone_channel_left_blank_without_prefer_key_match(self, tmp_path):
        cal_dir = _make_cal_dir(
            tmp_path, 'starship', 'SS1', '20260701-123456',
            metadata={'datetime': '2026-07-01T12:34:56', 'microphone': 'MMM0'},
        )
        io_data = {
            'input': {
                'starship_A_microphone': {
                    'label': 'Starship A (microphone)', 'active': True,
                    '__type__': 'NIDAQHardwareAIChannel',
                },
                'some_other_mic': {
                    'label': 'Some other mic', 'active': True,
                    '__type__': 'NIDAQHardwareAIChannel',
                },
            },
            'output': {},
        }
        (cal_dir / 'io.json').write_text(json.dumps(io_data))

        mm.migrate(tmp_path)
        metadata = json.loads((cal_dir / 'metadata.json').read_text())
        assert 'microphone_channel' not in metadata

    def test_overwrite_corrects_a_previously_wrong_channel_value(self, tmp_path):
        # Simulates real data affected by the raw-name-instead-of-label
        # bug: a plain re-run must not "fix" it (the field already looks
        # populated), but --overwrite must.
        cal_dir = _make_cal_dir(
            tmp_path, 'microphone', 'BK-4138', '20260701-123456',
            metadata={'datetime': '2026-07-01T12:34:56', 'sensor_id': 'BK-4138',
                      'pistonphone': 'PP1', 'input_channel': 'microphone_calibration'},
        )
        io_data = {
            'input': {
                'microphone_calibration': {
                    'label': 'Microphone Calibration', 'active': True,
                    '__type__': 'NIDAQHardwareAIChannel',
                },
            },
            'output': {},
        }
        (cal_dir / 'io.json').write_text(json.dumps(io_data))

        counts = mm.migrate(tmp_path)
        assert counts == _counts(skipped_exists=1)
        metadata = json.loads((cal_dir / 'metadata.json').read_text())
        assert metadata['input_channel'] == 'microphone_calibration'

        counts = mm.migrate(tmp_path, overwrite=True)
        assert counts == _counts(skipped_exists=1, enriched=1)
        metadata = json.loads((cal_dir / 'metadata.json').read_text())
        assert metadata['input_channel'] == 'Microphone Calibration'
