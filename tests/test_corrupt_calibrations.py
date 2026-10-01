'''
A damaged calibration folder (e.g., an unreadable ``metadata.json``, or one
missing required fields) must not prevent a workspace from opening. The
damaged calibration is still listed, but marked as having a problem.
'''
import datetime as dt
import json
from pathlib import Path

import enaml
import pytest

from cftscal.objects import (
    CalibrationManager, CFTSSpeakerCalibration, CFTSSpeakerLoader,
    CorruptCalibrationError, Speaker, UnityInputCalibration,
)
from cftscal.plugins.object_collection import ObjectCollection


GOOD_METADATA = {
    'datetime': '2026-01-01T00:00:00',
    'microphone': 'MIC1',
    'method': 'golay',
    'coupler': 'C1',
}

#: Contents of ``metadata.json`` for each kind of damage, and the text the
#: resulting problem description should contain.
DAMAGED = {
    'invalid_json': ('not json', 'Could not read metadata.json'),
    'empty': ('', 'Could not read metadata.json'),
    'not_object': ('[]', 'does not contain a JSON object'),
    'no_datetime': (
        json.dumps({'microphone': 'MIC1', 'method': 'golay'}),
        'missing required field(s): datetime',
    ),
    'bad_datetime': (
        json.dumps({**GOOD_METADATA, 'datetime': 'yesterday'}),
        'invalid datetime',
    ),
    'missing_field': (
        json.dumps({'datetime': '2026-01-07T00:00:00'}),
        'missing required field(s): microphone, method',
    ),
}


def _write_cal(path, text):
    path.mkdir(parents=True)
    (path / 'metadata.json').write_text(text)
    return path


class _SpeakerLoader(CFTSSpeakerLoader):
    '''Bypass CFTSBaseLoader.__init__ so tests can point at tmp_path.'''

    def __init__(self, base_path):
        self.base_path = Path(base_path)


@pytest.fixture
def speaker_manager(tmp_path):
    '''
    A speaker manager with one good calibration and one of each kind of
    damaged calibration, all under the same speaker.
    '''
    _write_cal(tmp_path / 'SPK1' / '20260101-000000_good',
               json.dumps(GOOD_METADATA))
    for i, (key, (text, _)) in enumerate(DAMAGED.items()):
        _write_cal(tmp_path / 'SPK1' / f'2026010{i + 2}-000000_{key}', text)
    manager = CalibrationManager(Speaker)
    manager.loaders.append(_SpeakerLoader(tmp_path))
    return manager


class TestCalibrationProblem:

    def test_good_calibration_has_no_problem(self, tmp_path):
        path = _write_cal(tmp_path / 'good', json.dumps(GOOD_METADATA))
        assert CFTSSpeakerCalibration('SPK1', path).problem is None

    @pytest.mark.parametrize('key', DAMAGED)
    def test_damaged_calibration_reports_problem(self, tmp_path, key):
        text, expected = DAMAGED[key]
        path = _write_cal(tmp_path / key, text)
        problem = CFTSSpeakerCalibration('SPK1', path).problem
        assert expected in problem

    def test_missing_field_and_bad_datetime_both_reported(self, tmp_path):
        path = _write_cal(tmp_path / 'cal', json.dumps({'datetime': 'x'}))
        problem = CFTSSpeakerCalibration('SPK1', path).problem
        assert 'missing required field(s): microphone, method' in problem
        assert 'invalid datetime' in problem

    def test_missing_metadata_file_reports_problem(self, tmp_path):
        path = tmp_path / 'cal'
        path.mkdir()
        problem = CFTSSpeakerCalibration('SPK1', path).problem
        assert 'Missing metadata.json' in problem

    @pytest.mark.parametrize('key', ['invalid_json', 'not_object',
                                     'no_datetime', 'bad_datetime'])
    def test_datetime_raises_corrupt_calibration_error(self, tmp_path, key):
        path = _write_cal(tmp_path / key, DAMAGED[key][0])
        with pytest.raises(CorruptCalibrationError):
            CFTSSpeakerCalibration('SPK1', path).datetime

    def test_non_file_calibration_has_no_problem(self):
        assert UnityInputCalibration().problem is None


class TestSortDatetime:

    def test_matches_datetime_when_readable(self, tmp_path):
        path = _write_cal(tmp_path / 'cal', json.dumps(GOOD_METADATA))
        cal = CFTSSpeakerCalibration('SPK1', path)
        assert cal.sort_datetime == cal.datetime

    def test_falls_back_to_folder_name(self, tmp_path):
        path = _write_cal(tmp_path / '20250315-101112_x', 'not json')
        cal = CFTSSpeakerCalibration('SPK1', path)
        assert cal.sort_datetime == dt.datetime(2025, 3, 15, 10, 11, 12)

    def test_falls_back_to_min_for_unparseable_folder_name(self, tmp_path):
        path = _write_cal(tmp_path / 'renamed', 'not json')
        cal = CFTSSpeakerCalibration('SPK1', path)
        assert cal.sort_datetime == dt.datetime.min

    def test_damaged_and_good_calibrations_sort_together(self, speaker_manager):
        obj = speaker_manager.get_object('SPK1')
        cals = sorted(obj.list_calibrations())
        names = [c.filename.name.split('_', 1)[1] for c in cals]
        assert names == ['good'] + list(DAMAGED)

    def test_repr_does_not_raise(self, tmp_path):
        path = _write_cal(tmp_path / 'cal', 'not json')
        assert '?' in repr(CFTSSpeakerCalibration('SPK1', path))


class TestGetProperty:

    def test_skips_damaged_calibrations(self, speaker_manager):
        # `coupler` is read straight from the metadata, so every damaged
        # calibration would raise. Only the good one contributes.
        speaker_manager.loaders[0].cal_class = _CouplerSpeakerCalibration
        assert speaker_manager.get_property('coupler') == {'C1'}


class _CouplerSpeakerCalibration(CFTSSpeakerCalibration):

    @property
    def coupler(self):
        return self.metadata['coupler']


class TestObjectCollection:

    def test_builds_with_damaged_calibrations(self, speaker_manager):
        collection = ObjectCollection(speaker_manager, [])
        (group,) = collection.groups
        assert len(group.subitems) == len(DAMAGED) + 1

    def test_nodes_report_problems(self, speaker_manager):
        collection = ObjectCollection(speaker_manager, [])
        (group,) = collection.groups
        problems = {n.item.filename.name.split('_', 1)[1]: n.problem
                    for n in group.subitems}
        assert problems.pop('good') == ''
        for key, problem in problems.items():
            assert DAMAGED[key][1] in problem
        assert len(group.problems) == len(DAMAGED)

    def test_problem_cleared_after_repair(self, speaker_manager, tmp_path):
        collection = ObjectCollection(speaker_manager, [])
        path = tmp_path / 'SPK1' / '20260102-000000_invalid_json'
        (path / 'metadata.json').write_text(json.dumps(GOOD_METADATA))
        collection.update_groups()
        (node,) = [n for n in collection.groups[0].subitems
                   if n.item.filename == path]
        assert node.problem == ''

    def test_plot_failure_is_reported_on_node(self, speaker_manager):
        class FailingManager:
            def notify(self, item, selected):
                raise RuntimeError('boom')

        collection = ObjectCollection(speaker_manager, [FailingManager()])
        node = collection.groups[0].subitems[-1]
        assert node.problem == ''
        node.selected = True
        assert node.problem == 'Could not plot calibration: boom'
        # Removing it again must not raise either.
        node.selected = False


class TestTreeIndicator:

    @pytest.fixture
    def tree(self, qt_app, speaker_manager):
        with enaml.imports():
            from cftscal.plugins.fast_tree_view import FastTreeWidget
        mapping = {
            'name': {'groupby': True, 'id': True, 'to_str': lambda x: x.name},
            'datetime': {'to_str': lambda x: str(x.datetime)},
        }
        collection = ObjectCollection(speaker_manager, [])
        return FastTreeWidget(None, mapping, collection, enable_current=True)

    def _leaves(self, tree):
        group = tree.topLevelItem(0)
        return {group.child(i).text(0).split('_', 1)[1]: group.child(i)
                for i in range(group.childCount())}

    def test_damaged_leaves_are_marked(self, tree):
        leaves = self._leaves(tree)
        good = leaves.pop('good')
        assert good.icon(0).isNull()
        assert good.toolTip(0) == ''
        for key, item in leaves.items():
            assert not item.icon(0).isNull()
            assert DAMAGED[key][1] in item.toolTip(0)

    def test_group_is_marked(self, tree):
        group = tree.topLevelItem(0)
        assert not group.icon(0).isNull()
        assert group.toolTip(0).startswith(
            f'{len(DAMAGED)} calibrations with problems')

    def test_mark_follows_node_problem(self, tree):
        good_item = self._leaves(tree)['good']
        node = [n for n in tree.collection.groups[0].subitems
                if not n.problem][0]
        node.problem = 'Could not plot calibration: boom'
        assert not good_item.icon(0).isNull()
        assert good_item.toolTip(0) == 'Could not plot calibration: boom'
