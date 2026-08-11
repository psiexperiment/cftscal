'''
Tests for :mod:`cftscal.migrate_thevenin` -- the one-off script that
reorganizes Thevenin-equivalent inear calibrations (coupler starting with
``TH-``) into ``inear/Thevenin/<starship>/<timestamp>/``.
'''
import json

from cftscal import migrate_thevenin as mt


def _make_inear_cal(root, starship, cal_name, coupler, extra=None):
    cal_dir = root / 'inear' / starship / cal_name
    cal_dir.mkdir(parents=True)
    metadata = {'datetime': '2026-07-01T12:34:56', 'starship': starship,
                'coupler': coupler}
    if extra:
        metadata.update(extra)
    (cal_dir / 'metadata.json').write_text(json.dumps(metadata))
    return cal_dir


ZERO = {'moved': 0, 'already_organized': 0, 'move_conflicts': 0,
        'skipped_error': 0}


def _counts(**overrides):
    return {**ZERO, **overrides}


class TestMoveTheveninCalibrations:

    def test_moves_thevenin_coupler_calibration(self, tmp_path):
        cal_dir = _make_inear_cal(tmp_path, 'MMM0', '20260701-123456', 'TH-32')
        counts = mt.move_thevenin_calibrations(tmp_path)
        assert counts == _counts(moved=1)

        new_dir = tmp_path / 'inear' / 'Thevenin' / 'MMM0' / '20260701-123456'
        assert new_dir.exists()
        assert not cal_dir.exists()
        metadata = json.loads((new_dir / 'metadata.json').read_text())
        assert metadata['coupler'] == 'TH-32'

    def test_old_starship_folder_cleaned_up_when_empty(self, tmp_path):
        _make_inear_cal(tmp_path, 'MMM0', '20260701-123456', 'TH-32')
        mt.move_thevenin_calibrations(tmp_path)
        assert not (tmp_path / 'inear' / 'MMM0').exists()

    def test_old_starship_folder_kept_when_other_calibrations_remain(self, tmp_path):
        _make_inear_cal(tmp_path, 'MMM0', '20260701-123456', 'TH-32')
        _make_inear_cal(tmp_path, 'MMM0', '20260701-654321', 'C1')
        mt.move_thevenin_calibrations(tmp_path)
        assert (tmp_path / 'inear' / 'MMM0' / '20260701-654321').exists()

    def test_non_thevenin_coupler_left_in_place(self, tmp_path):
        cal_dir = _make_inear_cal(tmp_path, 'MMM0', '20260701-123456', 'C1')
        counts = mt.move_thevenin_calibrations(tmp_path)
        assert counts == _counts()
        assert cal_dir.exists()

    def test_already_organized_is_skipped(self, tmp_path):
        cal_dir = _make_inear_cal(
            tmp_path, 'Thevenin/MMM0', '20260701-123456', 'TH-32',
        )
        counts = mt.move_thevenin_calibrations(tmp_path)
        assert counts == _counts(already_organized=1)
        assert cal_dir.exists()

    def test_second_run_is_a_noop(self, tmp_path):
        _make_inear_cal(tmp_path, 'MMM0', '20260701-123456', 'TH-32')
        mt.move_thevenin_calibrations(tmp_path)
        counts = mt.move_thevenin_calibrations(tmp_path)
        assert counts == _counts(already_organized=1)

    def test_move_conflict_leaves_both_untouched(self, tmp_path):
        cal_dir = _make_inear_cal(tmp_path, 'MMM0', '20260701-123456', 'TH-32')
        conflict_dir = tmp_path / 'inear' / 'Thevenin' / 'MMM0' / '20260701-123456'
        conflict_dir.mkdir(parents=True)

        counts = mt.move_thevenin_calibrations(tmp_path)
        assert counts == _counts(move_conflicts=1)
        assert cal_dir.exists()
        assert not (conflict_dir / 'metadata.json').exists()

    def test_missing_starship_reported_as_error(self, tmp_path):
        cal_dir = tmp_path / 'inear' / 'MMM0' / '20260701-123456'
        cal_dir.mkdir(parents=True)
        (cal_dir / 'metadata.json').write_text(
            json.dumps({'datetime': '2026-07-01T12:34:56', 'coupler': 'TH-32'})
        )
        counts = mt.move_thevenin_calibrations(tmp_path)
        assert counts == _counts(skipped_error=1)
        assert cal_dir.exists()

    def test_corrupt_metadata_reported_as_error(self, tmp_path):
        cal_dir = tmp_path / 'inear' / 'MMM0' / '20260701-123456'
        cal_dir.mkdir(parents=True)
        (cal_dir / 'metadata.json').write_text('not json')
        counts = mt.move_thevenin_calibrations(tmp_path)
        assert counts == _counts(skipped_error=1)
        assert cal_dir.exists()

    def test_missing_inear_folder_returns_zero_counts(self, tmp_path):
        counts = mt.move_thevenin_calibrations(tmp_path)
        assert counts == _counts()

    def test_dry_run_does_not_move(self, tmp_path):
        cal_dir = _make_inear_cal(tmp_path, 'MMM0', '20260701-123456', 'TH-32')
        counts = mt.move_thevenin_calibrations(tmp_path, dry_run=True)
        assert counts == _counts(moved=1)
        assert cal_dir.exists()
        assert not (tmp_path / 'inear' / 'Thevenin').exists()

    def test_org_folder_nesting_preserved_in_source(self, tmp_path):
        # A Thevenin calibration nested under an extra lab/study folder
        # above the starship folder still gets found and moved -- only
        # the destination path changes (device ID as master folder,
        # matching the rest of the inear tree's convention). The org
        # folder (Lab1) is separate from the metadata's own `starship`
        # field (MMM0), same as real on-disk data.
        cal_dir = tmp_path / 'inear' / 'Lab1' / 'MMM0' / '20260701-123456'
        cal_dir.mkdir(parents=True)
        (cal_dir / 'metadata.json').write_text(json.dumps({
            'datetime': '2026-07-01T12:34:56', 'starship': 'MMM0',
            'coupler': 'TH-32',
        }))
        counts = mt.move_thevenin_calibrations(tmp_path)
        assert counts == _counts(moved=1)
        assert not cal_dir.exists()
        new_dir = tmp_path / 'inear' / 'Thevenin' / 'MMM0' / '20260701-123456'
        assert new_dir.exists()

    def test_multiple_starships_grouped_separately(self, tmp_path):
        _make_inear_cal(tmp_path, 'MMM0', '20260701-111111', 'TH-32')
        _make_inear_cal(tmp_path, 'MMM1', '20260701-222222', 'TH-16')
        counts = mt.move_thevenin_calibrations(tmp_path)
        assert counts == _counts(moved=2)
        assert (tmp_path / 'inear' / 'Thevenin' / 'MMM0' / '20260701-111111').exists()
        assert (tmp_path / 'inear' / 'Thevenin' / 'MMM1' / '20260701-222222').exists()
