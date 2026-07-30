'''
Tests for the object-and-loader identity model in :mod:`cftscal.objects`.

Focus on the branchy pieces that would silently regress if someone
touched them: path parsing, folder/name matching in ``get_object``, and
the on-disk walk that discovers organizational nesting.
'''
import json
from pathlib import Path

import pytest

from cftscal.objects import (
    CalibratedObject,
    CalibrationLoader,
    CalibrationManager,
    CFTSBaseLoader,
    CFTSInEarLoader,
)


class _FakeLoader(CalibrationLoader):
    '''Loader stub that reports a fixed set of ``(folder, name)`` pairs.'''

    def __init__(self, objects):
        # ``objects`` is a list of (folder, name) tuples the loader
        # pretends to know about.
        self._objects = list(objects)

    def list_names(self):
        return [n for _, n in self._objects]

    def list_objects(self):
        return list(self._objects)

    def list_calibrations(self, name, folder=None):
        return []


def _make_manager(loader_objects):
    manager = CalibrationManager(object_class=CalibratedObject)
    manager.loaders = [_FakeLoader(loader_objects)]
    return manager


class TestParsePath:

    def test_bare_name(self):
        assert CalibrationManager._parse_path('MMM0') == ('', 'MMM0')

    def test_single_folder(self):
        assert CalibrationManager._parse_path('Lab1/MMM0') == ('Lab1', 'MMM0')

    def test_nested_folders(self):
        assert CalibrationManager._parse_path('Lab1/study_1/MMM0') == (
            'Lab1/study_1', 'MMM0'
        )


class TestCalibratedObjectPath:

    def test_root_object_path_is_bare_name(self):
        obj = CalibratedObject(name='MMM0', loaders=[], folder='')
        assert obj.path == 'MMM0'

    def test_none_folder_path_is_bare_name(self):
        # folder=None means "any folder" for the aggregate case; path
        # collapses to just the name for display.
        obj = CalibratedObject(name='MMM0', loaders=[], folder=None)
        assert obj.path == 'MMM0'

    def test_folder_object_path_is_joined(self):
        obj = CalibratedObject(name='MMM0', loaders=[], folder='Lab1')
        assert obj.path == 'Lab1/MMM0'

    def test_nested_folder(self):
        obj = CalibratedObject(name='MMM0', loaders=[], folder='Lab1/study_1')
        assert obj.path == 'Lab1/study_1/MMM0'


class TestGetObject:

    def test_root_object_by_bare_name(self):
        manager = _make_manager([('', 'MMM0')])
        obj = manager.get_object('MMM0')
        assert obj.name == 'MMM0'
        assert obj.folder == ''
        assert len(obj.loaders) == 1

    def test_nested_object_by_full_path(self):
        manager = _make_manager([('Lab1', 'MMM0')])
        obj = manager.get_object('Lab1/MMM0')
        assert obj.name == 'MMM0'
        assert obj.folder == 'Lab1'

    def test_bare_name_does_not_match_nested(self):
        # Only Lab1/MMM0 exists; asking for the bare name (which parses to
        # folder='', name='MMM0') must not find it.  Otherwise labs would
        # accidentally share each other's calibrations.
        manager = _make_manager([('Lab1', 'MMM0')])
        with pytest.raises(LookupError):
            manager.get_object('MMM0')

    def test_wrong_folder_prefix_raises(self):
        manager = _make_manager([('Lab1', 'MMM0')])
        with pytest.raises(LookupError):
            manager.get_object('Lab2/MMM0')

    def test_multiple_labs_same_name_are_distinct(self):
        manager = _make_manager([
            ('Lab1', 'MMM0'),
            ('Lab2', 'MMM0'),
        ])
        obj1 = manager.get_object('Lab1/MMM0')
        obj2 = manager.get_object('Lab2/MMM0')
        assert obj1.folder == 'Lab1'
        assert obj2.folder == 'Lab2'


class TestListNames:

    def test_root_names_are_bare(self):
        manager = _make_manager([('', 'MMM0'), ('', 'MMM1')])
        assert set(manager.list_names()) == {'MMM0', 'MMM1'}

    def test_nested_names_include_folder_prefix(self):
        manager = _make_manager([('Lab1', 'MMM0'), ('Lab2', 'MMM0')])
        assert set(manager.list_names()) == {'Lab1/MMM0', 'Lab2/MMM0'}


# ---------------------------------------------------------------------------
# CFTSBaseLoader on-disk walk
# ---------------------------------------------------------------------------

class _WalkOnlyLoader(CFTSBaseLoader):
    '''
    Subclass that bypasses ``CFTSBaseLoader.__init__`` (which is hard-wired
    to ``CAL_ROOT / subfolder``) so tests can point at a ``tmp_path``.
    '''
    cal_class = None  # unused by _walk_objects

    def __init__(self, base_path):
        self.base_path = Path(base_path)


def _make_calibration(dir_path, metadata=None):
    '''Create a fake calibration dir with a ``metadata.json`` inside it.'''
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / 'metadata.json').write_text(json.dumps(metadata or {}))


class TestWalkObjects:

    def test_empty_base_path(self, tmp_path):
        loader = _WalkOnlyLoader(tmp_path)
        assert loader._walk_objects() == {}

    def test_missing_base_path(self, tmp_path):
        loader = _WalkOnlyLoader(tmp_path / 'does_not_exist')
        assert loader._walk_objects() == {}

    def test_flat_layout(self, tmp_path):
        _make_calibration(tmp_path / 'MMM0' / '20260701-abc')
        _make_calibration(tmp_path / 'MMM0' / '20260702-def')
        _make_calibration(tmp_path / 'MMM1' / '20260703-ghi')
        loader = _WalkOnlyLoader(tmp_path)
        result = loader._walk_objects()
        assert set(result) == {('', 'MMM0'), ('', 'MMM1')}
        assert len(result[('', 'MMM0')]) == 2
        assert len(result[('', 'MMM1')]) == 1

    def test_one_level_of_org_nesting(self, tmp_path):
        _make_calibration(tmp_path / 'Lab1' / 'MMM0' / '20260701-abc')
        _make_calibration(tmp_path / 'Lab2' / 'MMM0' / '20260702-def')
        loader = _WalkOnlyLoader(tmp_path)
        result = loader._walk_objects()
        assert set(result) == {('Lab1', 'MMM0'), ('Lab2', 'MMM0')}

    def test_deep_org_nesting(self, tmp_path):
        _make_calibration(
            tmp_path / 'Lab1' / 'study_1' / 'MMM0' / '20260701-abc'
        )
        loader = _WalkOnlyLoader(tmp_path)
        result = loader._walk_objects()
        assert list(result) == [('Lab1/study_1', 'MMM0')]

    def test_mixed_flat_and_nested(self, tmp_path):
        _make_calibration(tmp_path / 'MMM0' / '20260701-abc')
        _make_calibration(tmp_path / 'Lab1' / 'MMM0' / '20260702-def')
        loader = _WalkOnlyLoader(tmp_path)
        result = loader._walk_objects()
        # Same bare name at root and in Lab1 → two distinct keys.
        assert set(result) == {('', 'MMM0'), ('Lab1', 'MMM0')}

    def test_empty_org_folder_is_ignored(self, tmp_path):
        # An empty organizational folder shouldn't fabricate a phantom object;
        # object discovery is driven entirely by metadata.json presence.
        (tmp_path / 'empty_lab').mkdir()
        loader = _WalkOnlyLoader(tmp_path)
        assert loader._walk_objects() == {}


class TestListCalibrationsFolderFilter:

    def test_folder_none_returns_all(self, tmp_path):
        # Set up two objects both named MMM0 in different folders.
        _make_calibration(tmp_path / 'MMM0' / '20260701-abc')
        _make_calibration(tmp_path / 'Lab1' / 'MMM0' / '20260702-def')

        class _TestLoader(_WalkOnlyLoader):
            # Minimal cal_class replacement: capture the args and expose them.
            def __init__(self, base_path):
                super().__init__(base_path)

            class cal_class:
                def __init__(self, name, filename):
                    self.name = name
                    self.filename = filename

        loader = _TestLoader(tmp_path)
        results = loader.list_calibrations('MMM0', folder=None)
        # folder=None must return calibrations from BOTH folders — this is
        # the "any folder" mode used by legacy name-only lookups.
        assert len(results) == 2

    def test_folder_empty_returns_root_only(self, tmp_path):
        _make_calibration(tmp_path / 'MMM0' / '20260701-abc')
        _make_calibration(tmp_path / 'Lab1' / 'MMM0' / '20260702-def')

        class _TestLoader(_WalkOnlyLoader):
            class cal_class:
                def __init__(self, name, filename):
                    self.name = name
                    self.filename = filename

        loader = _TestLoader(tmp_path)
        results = loader.list_calibrations('MMM0', folder='')
        assert len(results) == 1
        assert results[0].filename.parent.name == 'MMM0'
        assert results[0].filename.parent.parent == tmp_path

    def test_folder_specific_returns_only_that_folder(self, tmp_path):
        _make_calibration(tmp_path / 'MMM0' / '20260701-abc')
        _make_calibration(tmp_path / 'Lab1' / 'MMM0' / '20260702-def')

        class _TestLoader(_WalkOnlyLoader):
            class cal_class:
                def __init__(self, name, filename):
                    self.name = name
                    self.filename = filename

        loader = _TestLoader(tmp_path)
        results = loader.list_calibrations('MMM0', folder='Lab1')
        assert len(results) == 1
        assert results[0].filename.parent.parent.name == 'Lab1'


# ---------------------------------------------------------------------------
# CFTSInEarLoader — starship identity from metadata, folder from disk
# ---------------------------------------------------------------------------

class _InEarStub(CFTSInEarLoader):
    '''Bypass CFTSInEarLoader.__init__ so tests can point at tmp_path.'''

    def __init__(self, base_path):
        self.base_path = Path(base_path)


class TestInEarLoader:

    def test_traditional_ear_layout(self, tmp_path):
        # inear/<ear>/<cal>/metadata.json{starship: SS1}
        _make_calibration(
            tmp_path / 'left' / '20260701-abc',
            metadata={'ear': 'left', 'starship': 'SS1', 'datetime': ''},
        )
        _make_calibration(
            tmp_path / 'right' / '20260702-def',
            metadata={'ear': 'right', 'starship': 'SS1', 'datetime': ''},
        )
        loader = _InEarStub(tmp_path)
        result = loader._walk_objects()
        # Same starship in two different ears → two distinct objects,
        # ear becomes the folder.
        assert set(result) == {('left', 'SS1'), ('right', 'SS1')}

    def test_missing_starship_skipped(self, tmp_path):
        _make_calibration(
            tmp_path / 'left' / '20260701-abc',
            metadata={'ear': 'left', 'datetime': ''},  # no starship
        )
        loader = _InEarStub(tmp_path)
        assert loader._walk_objects() == {}

    def test_bad_metadata_skipped(self, tmp_path):
        cal_dir = tmp_path / 'left' / '20260701-abc'
        cal_dir.mkdir(parents=True)
        (cal_dir / 'metadata.json').write_text('not json')
        loader = _InEarStub(tmp_path)
        assert loader._walk_objects() == {}

    def test_nested_org_folder_preserved(self, tmp_path):
        # Users can drag inear cals into deeper org folders; the folder
        # path should reflect that.
        _make_calibration(
            tmp_path / 'Lab1' / 'left' / '20260701-abc',
            metadata={'ear': 'left', 'starship': 'SS1', 'datetime': ''},
        )
        loader = _InEarStub(tmp_path)
        result = loader._walk_objects()
        assert list(result) == [('Lab1/left', 'SS1')]
