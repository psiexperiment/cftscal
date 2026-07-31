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


# ---------------------------------------------------------------------------
# CalibrationSettings._make_path
# ---------------------------------------------------------------------------

class TestMakePath:
    '''
    _make_path takes group_path as a required positional arg — no more
    plugin-wide fallback.  Callers pass whichever target's group_path is
    active (ai.group_path, ao.group_path, starship.group_path, etc.).
    '''

    def _make_settings(self, tmp_path):
        from cftscal.plugins.settings import CalibrationSettings
        s = CalibrationSettings()
        s.data_path = tmp_path
        return s

    def test_empty_group_path_uses_legacy_layout(self, tmp_path):
        # No target folder → device_name segment preserved so first-time
        # users see the old on-disk layout.
        s = self._make_settings(tmp_path)
        result = s._make_path('microphone', '', 'MMM0', '20260701_MMM0_PP')
        assert result == tmp_path / 'microphone' / 'MMM0' / '20260701_MMM0_PP'

    def test_group_path_drops_device_name(self, tmp_path):
        s = self._make_settings(tmp_path)
        result = s._make_path(
            'microphone', 'Lab1', 'MMM0', '20260701_MMM0_PP',
        )
        assert result == tmp_path / 'microphone' / 'Lab1' / '20260701_MMM0_PP'

    def test_nested_group_path(self, tmp_path):
        s = self._make_settings(tmp_path)
        result = s._make_path(
            'microphone', 'Lab1/study_1', 'MMM0', '20260701_MMM0_PP',
        )
        assert result == (
            tmp_path / 'microphone' / 'Lab1' / 'study_1' / '20260701_MMM0_PP'
        )

    def test_group_path_normalized(self, tmp_path):
        s = self._make_settings(tmp_path)
        result = s._make_path(
            'microphone', '/Lab1/', 'MMM0', '20260701_MMM0_PP',
        )
        assert result == tmp_path / 'microphone' / 'Lab1' / '20260701_MMM0_PP'

    def test_group_path_is_required(self, tmp_path):
        # ``group_path`` is a required positional so callers can't silently
        # fall back to a plugin-wide default that no longer exists.
        s = self._make_settings(tmp_path)
        with pytest.raises(TypeError):
            s._make_path('microphone')


class TestSensorHierarchy:
    '''
    SensorReference and SensorDevice are the two roles a sensor picker
    can play — reference (auto-populated list of calibration paths, used
    to LOAD a calibration) or device (user-managed list of physical
    device identifiers, tracked as metadata).  Their persistence keys
    are distinct so a slot that changes role between versions doesn't
    inherit stale data from its predecessor.
    '''

    def test_reference_and_device_are_distinct(self):
        from cftscal.plugins.settings import (
            SensorSettings, SensorReference, SensorDevice,
        )
        assert issubclass(SensorReference, SensorSettings)
        assert issubclass(SensorDevice, SensorSettings)
        assert not issubclass(SensorReference, SensorDevice)
        assert not issubclass(SensorDevice, SensorReference)

    def test_sensor_device_starts_empty(self):
        from cftscal.plugins.settings import SensorDevice
        d = SensorDevice()
        # No disk seeding — user-managed only.
        assert d.available_devices == []
        assert d.name == ''

    def test_sensor_device_additions_persist(self):
        from cftscal.plugins.settings import SensorDevice
        d = SensorDevice()
        d.available_devices = ['SN001', 'SN002']
        # Round-trip via persistence.
        data = d.get_persistence()
        assert data['available_devices'] == ['SN001', 'SN002']

        d2 = SensorDevice()
        d2.set_persistence(data)
        assert d2.available_devices == ['SN001', 'SN002']

    def test_sensor_device_ignores_stale_available_references(self):
        # If a JSON has an ``available_references`` key from a slot
        # that used to hold a SensorReference, SensorDevice ignores it
        # (no such tagged field on SensorDevice).
        from cftscal.plugins.settings import SensorDevice
        d = SensorDevice()
        d.set_persistence({
            'name': 'SN001',
            'available_references': ['Bramhall/MMM', 'Lab1/MMM'],
        })
        assert d.name == 'SN001'
        assert d.available_devices == []  # not polluted


class TestTargetGroupPath:
    '''
    ``group_path`` lives on the target settings (InputSettings,
    OutputSettings, StarshipSettings, InEarSettings) so each channel/
    output/etc. remembers its own value across sessions.
    '''

    def test_input_settings_group_path_roundtrips(self):
        from cftscal.plugins.settings import InputSettings
        i = InputSettings(input_name='ai0', group_path='Lab1')
        assert i.get_persistence()['group_path'] == 'Lab1'
        j = InputSettings(input_name='ai0')
        j.set_persistence(i.get_persistence())
        assert j.group_path == 'Lab1'

    def test_output_settings_group_path_roundtrips(self):
        from cftscal.plugins.settings import OutputSettings
        o = OutputSettings(output_name='ao0', group_path='Lab1/study_1')
        assert o.get_persistence()['group_path'] == 'Lab1/study_1'

    def test_starship_settings_group_path_roundtrips(self):
        from cftscal.plugins.settings import StarshipSettings
        s = StarshipSettings(connection_name='ss0', group_path='Lab1')
        assert s.get_persistence()['group_path'] == 'Lab1'

    def test_inear_inherits_group_path(self):
        from cftscal.plugins.settings import InEarSettings
        e = InEarSettings(connection_name='ss0', group_path='Lab1')
        # InEar inherits StarshipSettings' group_path field.
        assert e.get_persistence()['group_path'] == 'Lab1'


class TestUnifiedPickerMechanism:
    '''
    Every reference-picker uses the same shape: a persistent
    ``available_<noun>`` list on the class, populated in ``__init__``
    via the module-level :func:`_merge_picker_list` helper (invoked from
    ``refresh_available``) with the union of disk-discovered and
    previously-persisted entries.  This test locks that convention in
    for the reference-role subclasses so someone can't quietly drift
    back to the @property approach.
    '''

    def test_speaker_uses_inherited_available_generators(self):
        # SpeakerSettings inherits GeneratorSettings.available_generators
        # rather than defining its own list — one field for the whole
        # GeneratorSettings hierarchy, populated per-subclass via
        # get_available_generators().
        from cftscal.plugins.settings import SpeakerSettings
        s = SpeakerSettings()
        assert isinstance(s.available_generators, list)
        s.available_generators = sorted(
            set(s.available_generators) | {'MySpeaker'},
        )
        data = s.get_persistence()
        assert 'MySpeaker' in data['available_generators']
        # No shadow list from a previous naming.
        assert not hasattr(s, 'available_speakers')

    def test_starship_available_is_persistent_list(self):
        from cftscal.plugins.settings import StarshipSettings
        s = StarshipSettings()
        assert isinstance(s.available_starships, list)
        s.available_starships = sorted(
            set(s.available_starships) | {'starship_X'},
        )
        data = s.get_persistence()
        assert 'starship_X' in data['available_starships']

    def test_inear_available_ears_is_persistent_list(self):
        from cftscal.plugins.settings import InEarSettings
        e = InEarSettings()
        assert isinstance(e.available_ears, list)
        e.available_ears = sorted(set(e.available_ears) | {'left_v2'})
        data = e.get_persistence()
        assert 'left_v2' in data['available_ears']

    def test_merge_helper_unions_and_sorts(self):
        from cftscal.plugins.settings import _merge_picker_list
        from cftscal.plugins.settings import PersistentSettings
        from atom.api import List

        class _Stub(PersistentSettings):
            items = List()

        s = _Stub()
        s.items = ['c', 'a']
        _merge_picker_list(s, 'items', ['b', 'a', 'd'])
        # Union of persisted + discovered, sorted, deduplicated.
        assert s.items == ['a', 'b', 'c', 'd']

    def testrefresh_available_re_merges_from_disk(self):
        # After ``refresh_available`` is called on a reference-picker
        # instance, ``available_<noun>`` reflects any newly-discovered
        # items — this is what widget observers call after a new
        # calibration is recorded.
        from cftscal.plugins.settings import SensorReference

        class _Stub(SensorReference):
            _sources = ['A']  # mutable class-level source

            def get_available_references(self):
                return list(self._sources)

        s = _Stub()
        assert s.available_references == ['A']
        # Simulate a new calibration landing on disk.
        _Stub._sources = ['A', 'B']
        s.refresh_available()
        assert s.available_references == ['A', 'B']


class TestSensorSettingsGuard:
    '''
    SensorSettings is abstract; only SensorReference and SensorDevice
    should be instantiated.  Constructing the bare base is a mistake
    the type system alone doesn't catch, so we assert directly.
    '''

    def test_direct_instantiation_raises(self):
        from cftscal.plugins.settings import SensorSettings
        with pytest.raises(TypeError):
            SensorSettings()

    def test_subclass_instantiation_ok(self):
        from cftscal.plugins.settings import SensorReference, SensorDevice
        SensorReference()  # no raise
        SensorDevice()     # no raise


# ---------------------------------------------------------------------------
# GroupPathPicker target discovery (_list_group_paths in widgets.enaml)
# ---------------------------------------------------------------------------

class TestListGroupPaths:
    '''
    Import from the compiled enaml module.  The classification rules are
    fiddly enough that a regression here silently breaks the acquisition
    UX (users pick an invalid target, cal lands where they don't expect
    it), so lock them down.
    '''

    def _list(self, base_path):
        import enaml
        with enaml.imports():
            from cftscal.plugins.widgets import _list_group_paths
        return _list_group_paths(base_path)

    def test_root_only(self, tmp_path):
        # Empty tree → only "(root)".
        assert self._list(tmp_path) == ['']

    def test_object_dir_listed(self, tmp_path):
        # Bramhall/MMM contains a cal → MMM is an object dir, listed.
        # Bramhall has only a subfolder → not itself pickable.
        _make_calibration(tmp_path / 'Bramhall' / 'MMM' / '20260701-abc')
        result = self._list(tmp_path)
        assert result == ['', 'Bramhall/MMM']

    def test_empty_folder_listed(self, tmp_path):
        # A fresh user-created folder with nothing in it is a valid
        # target (becomes an object on first cal).
        (tmp_path / 'Bramhall').mkdir()
        assert self._list(tmp_path) == ['', 'Bramhall']

    def test_org_folder_with_subfolders_not_listed(self, tmp_path):
        # Bramhall has an empty subfolder study_1 → Bramhall is org, not
        # pickable; study_1 is empty, pickable.
        (tmp_path / 'Bramhall' / 'study_1').mkdir(parents=True)
        result = self._list(tmp_path)
        assert result == ['', 'Bramhall/study_1']

    def test_multiple_object_dirs(self, tmp_path):
        _make_calibration(tmp_path / 'Bramhall' / 'MMM' / '20260701-abc')
        _make_calibration(tmp_path / 'Bramhall' / 'HED' / '20260702-def')
        result = self._list(tmp_path)
        assert result == ['', 'Bramhall/HED', 'Bramhall/MMM']

    def test_cal_dir_never_listed(self, tmp_path):
        # A calibration dir itself is a recording, never a target.
        _make_calibration(tmp_path / 'MMM' / '20260701-abc')
        result = self._list(tmp_path)
        assert '20260701-abc' not in ''.join(result)
        assert result == ['', 'MMM']

    def test_deep_nesting(self, tmp_path):
        # Path can be arbitrarily deep.  Lab1 and Lab1/study_1 both have
        # sub-folders (not themselves pickable); only the leaf object
        # dir is listed.
        _make_calibration(
            tmp_path / 'Lab1' / 'study_1' / 'MMM' / '20260701-abc'
        )
        result = self._list(tmp_path)
        assert result == ['', 'Lab1/study_1/MMM']
