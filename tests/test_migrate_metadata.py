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
        assert result['measurement_microphone'] == 'MMM0'
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
        assert result['output'] == 'primary'
        assert result['starship'] == 'SS1'

    def test_secondary_suffix_sets_output(self):
        result = mm._parse_inear(
            _folder('20260701-123456_C1-secondary_MMM5')
        )
        assert result['coupler'] == 'C1'
        assert result['output'] == 'secondary'
        assert result['starship'] == 'MMM5'


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


ZERO = {'wrote': 0, 'skipped_exists': 0, 'skipped_error': 0,
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
        assert counts == _counts(skipped_exists=1, renamed=1)

        new_dir = tmp_path / 'speaker' / 'SPK1' / '20260701-123456'
        assert new_dir.exists()
        metadata = json.loads((new_dir / 'metadata.json').read_text())
        assert metadata == {'datetime': '2026-07-01T12:34:56', 'microphone': 'MMM0',
                             'method': 'tone'}

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
        assert counts == _counts(wrote=1, renamed=1)

        new_dir = (
            tmp_path / 'starship' / 'MMM0' / 'hide' / '20260701-123456'
        )
        assert new_dir.exists()
        metadata = json.loads((new_dir / 'metadata.json').read_text())
        assert metadata['microphone'] == 'GRAS-40DP'

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
        assert counts == _counts(wrote=1, renamed=1)

        new_dir = tmp_path / 'input_amplifier' / 'AMP1' / '20260701-123456'
        metadata = json.loads((new_dir / 'metadata.json').read_text())
        assert metadata['total_gain'] == 1000.0
        assert metadata['freq_lb'] == 10.0
        assert metadata['freq_ub'] == 10000.0
        assert metadata['filt_60Hz'] == 'on'

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
        assert counts == _counts(wrote=1, renamed=1)

        new_dir = tmp_path / 'inear' / 'MMM5' / '20260701-123456'
        assert new_dir.exists()
        assert not cal_dir.exists()
        # The now-empty old coupler folder is cleaned up.
        assert not (tmp_path / 'inear' / 'C1-secondary').exists()

        metadata = json.loads((new_dir / 'metadata.json').read_text())
        assert metadata['coupler'] == 'C1'
        assert metadata['output'] == 'secondary'
        assert metadata['starship'] == 'MMM5'

    def test_inear_reparent_preserves_org_folder_nesting(self, tmp_path):
        # A calibration organized under an extra lab/study folder above
        # the coupler folder keeps that nesting -- only the coupler
        # segment is replaced by the starship.
        cal_dir = _make_cal_dir(
            tmp_path, 'inear', 'Lab1/C1',
            '20260701-123456_C1_MMM5',
        )
        counts = mm.migrate(tmp_path)
        assert counts == _counts(wrote=1, renamed=1)

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
        assert counts == _counts(wrote=2, renamed=1, rename_conflicts=1)

        new_dir = tmp_path / 'inear' / 'MMM5' / '20260701-123456'
        assert new_dir.exists()
        # Exactly one of the two source folders got moved out; the other
        # is left in place (with its metadata.json already written) for
        # the user to resolve by hand.
        assert cal_dir_1.exists() != cal_dir_2.exists()
