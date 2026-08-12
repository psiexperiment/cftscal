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
    CFTSGenericMicrophoneCalibration,
    CFTSInEarCalibration,
    CFTSInEarLoader,
    CFTSInputAmplifierCalibration,
    CFTSInputRecording,
    CFTSMeasurementMicrophoneCalibration,
    CFTSSpeakerCalibration,
    CFTSStarshipCalibration,
    _CURRENT_MARKER,
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
# CalibratedObject.get_current_calibration -- pinning
# ---------------------------------------------------------------------------

class _PinTestLoader(_WalkOnlyLoader):
    class cal_class:
        def __init__(self, name, filename):
            self.name = name
            self.filename = filename


class TestCurrentCalibration:
    '''
    get_current_calibration() always requires an explicit pin -- no
    fallback to "most recent by datetime" for any calibration type.
    Silently picking whatever's newest risked an unintended (e.g. test/
    debug) calibration going live unnoticed.
    '''

    def _make_object(self, tmp_path, cal_names, folder=''):
        for cal_name in cal_names:
            _make_calibration(tmp_path / 'MMM0' / cal_name)
        loader = _PinTestLoader(tmp_path)
        return CalibratedObject('MMM0', [loader], folder=folder)

    def test_no_pin_raises(self, tmp_path):
        obj = self._make_object(tmp_path, ['20260701-abc', '20260702-def'])
        with pytest.raises(LookupError):
            obj.get_current_calibration()

    def test_pin_wins_over_newer_unpinned(self, tmp_path):
        obj = self._make_object(tmp_path, ['20260701-abc', '20260702-def'])
        older = next(c for c in obj.list_calibrations()
                     if c.filename.name == '20260701-abc')
        obj.set_current_calibration(older)
        # 20260702-def sorts later but was never pinned -- must not win.
        assert obj.get_current_calibration().filename.name == '20260701-abc'

    def test_get_pinned_calibration_roundtrip(self, tmp_path):
        obj = self._make_object(tmp_path, ['20260701-abc'])
        assert obj.get_pinned_calibration() is None

        cal = obj.list_calibrations()[0]
        obj.set_current_calibration(cal)
        pinned = obj.get_pinned_calibration()
        assert pinned is not None
        assert pinned.filename == cal.filename

        obj.clear_current_calibration()
        assert obj.get_pinned_calibration() is None

    def test_marker_file_written_at_object_dir(self, tmp_path):
        obj = self._make_object(tmp_path, ['20260701-abc'])
        cal = obj.list_calibrations()[0]
        obj.set_current_calibration(cal)
        marker = tmp_path / 'MMM0' / _CURRENT_MARKER
        assert marker.exists()
        assert json.loads(marker.read_text()) == {'current': '20260701-abc'}

    def test_pinned_entry_deleted_from_disk_falls_back_to_none(self, tmp_path):
        import shutil

        obj = self._make_object(tmp_path, ['20260701-abc'])
        cal = obj.list_calibrations()[0]
        obj.set_current_calibration(cal)

        shutil.rmtree(tmp_path / 'MMM0' / '20260701-abc')

        assert obj.get_pinned_calibration() is None
        with pytest.raises(LookupError):
            obj.get_current_calibration()

    def test_folder_none_cannot_be_pinned(self, tmp_path):
        # folder=None is CalibrationManager.get_object()'s "any folder"
        # mode -- ambiguous, so there's no single directory to pin
        # against.
        _make_calibration(tmp_path / 'MMM0' / '20260701-abc')
        loader = _PinTestLoader(tmp_path)
        obj = CalibratedObject('MMM0', [loader], folder=None)
        assert obj.get_pinned_calibration() is None
        with pytest.raises(ValueError):
            obj.set_current_calibration(obj.list_calibrations()[0])

    def test_non_cftsbaseloader_cannot_be_pinned(self):
        # A loader with no real per-object directory (e.g.
        # EPLStarshipLoader's flat .calib files) has nowhere to put a
        # marker.
        loader = _FakeLoader([('', 'MMM0')])
        obj = CalibratedObject('MMM0', [loader], folder='')
        assert obj.get_pinned_calibration() is None
        with pytest.raises(ValueError):
            obj.set_current_calibration(object())


# ---------------------------------------------------------------------------
# CFTSInEarLoader — groups by folder, same as every other CFTS loader
# ---------------------------------------------------------------------------

class _InEarStub(CFTSInEarLoader):
    '''Bypass CFTSInEarLoader.__init__ so tests can point at tmp_path.'''

    def __init__(self, base_path):
        self.base_path = Path(base_path)


class TestInEarLoader:
    '''
    CFTSInEarLoader no longer overrides ``_walk_objects`` -- it inherits
    ``CFTSBaseLoader``'s generic, folder-based grouping, same as
    starship/speaker/microphone_generic/input_amplifier, so a lab can
    reorganize inear calibrations via the target-folder picker
    independent of device, the same as every other plugin. The device
    identity that used to drive grouping is still available via
    ``CFTSInEarCalibration.starship`` (surfaced as the tree's own
    "Device" column) -- it just no longer controls tree position.
    '''

    def test_groups_by_folder(self, tmp_path):
        _make_calibration(
            tmp_path / 'SS1' / '20260701-abc',
            metadata={'coupler': 'C1', 'starship': 'SS1', 'datetime': ''},
        )
        _make_calibration(
            tmp_path / 'SS2' / '20260702-def',
            metadata={'coupler': 'C1', 'starship': 'SS2', 'datetime': ''},
        )
        loader = _InEarStub(tmp_path)
        result = loader._walk_objects()
        assert set(result) == {('', 'SS1'), ('', 'SS2')}

    def test_folder_wins_over_diverging_metadata(self, tmp_path):
        # A calibration filed under a target folder that doesn't match
        # its own metadata['starship'] -- same as every other plugin:
        # the folder (tree position) and the explicit Device field are
        # allowed to disagree, which is exactly why Device is surfaced
        # as its own column instead of being trusted implicitly.
        _make_calibration(
            tmp_path / 'Lab1' / '20260701-abc',
            metadata={'coupler': 'C1', 'starship': 'SS1', 'datetime': ''},
        )
        loader = _InEarStub(tmp_path)
        result = loader._walk_objects()
        assert set(result) == {('', 'Lab1')}

    def test_included_even_with_missing_or_corrupt_metadata(self, tmp_path):
        # Grouping no longer depends on reading metadata.json content at
        # all -- matches every other plugin's loader, none of which
        # validate metadata contents before including a folder.
        cal_dir = tmp_path / 'SS1' / '20260701-abc'
        cal_dir.mkdir(parents=True)
        (cal_dir / 'metadata.json').write_text('not json')
        loader = _InEarStub(tmp_path)
        assert set(loader._walk_objects()) == {('', 'SS1')}

    def test_two_couplers_same_folder_are_one_object(self, tmp_path):
        # Both couplers' recordings land under the same folder, so
        # they're the same object with two calibrations.
        _make_calibration(
            tmp_path / 'SS1' / '20260701-abc',
            metadata={'coupler': 'C1', 'starship': 'SS1', 'datetime': ''},
        )
        _make_calibration(
            tmp_path / 'SS1' / '20260702-def',
            metadata={'coupler': 'C2', 'starship': 'SS1', 'datetime': ''},
        )
        loader = _InEarStub(tmp_path)
        result = loader._walk_objects()
        assert set(result) == {('', 'SS1')}
        assert len(result[('', 'SS1')]) == 2

    def test_nested_org_folder_preserved(self, tmp_path):
        # Users can drag inear cals into deeper org folders; the folder
        # path should reflect whatever sits above the leaf object
        # folder, not the object folder itself.
        _make_calibration(
            tmp_path / 'Lab1' / 'SS1' / '20260701-abc',
            metadata={'coupler': 'C1', 'starship': 'SS1', 'datetime': ''},
        )
        loader = _InEarStub(tmp_path)
        result = loader._walk_objects()
        assert list(result) == [('Lab1', 'SS1')]

    def test_starship_property_independent_of_folder(self, tmp_path):
        # CFTSInEarCalibration.starship reads straight from metadata,
        # regardless of what folder the calibration is grouped under.
        cal_dir = tmp_path / 'Lab1' / '20260701-abc'
        _make_calibration(
            cal_dir, metadata={'coupler': 'C1', 'starship': 'SS1', 'datetime': ''},
        )
        cal = CFTSInEarCalibration('Lab1', cal_dir)
        assert cal.starship == 'SS1'


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


class TestSensorReferencePersistence:
    '''
    SensorReference.set_persistence() must re-merge freshly-discoverable
    references after restoring the persisted selection -- the inherited
    PersistentSettings.set_persistence() sets available_references to
    exactly the persisted list, which would otherwise silently discard
    anything discoverable now but not yet present in a config saved
    before it existed (e.g. a newly-recorded calibration). That isn't a
    one-time gap either: it would happen fresh on *every* load, since
    set_persistence() runs every time settings load, not just once. See
    SensorReference.set_persistence.
    '''

    def _make_reference(self, monkeypatch, available):
        from cftscal.plugins.settings import SensorReference
        monkeypatch.setattr(
            SensorReference, 'get_available_references', lambda self: list(available),
        )
        return SensorReference()

    def test_set_persistence_restores_now_missing_entries(self, monkeypatch):
        ref = self._make_reference(monkeypatch, ['BK-4138', 'Demo', 'unity'])
        assert 'MMM5' not in ref.available_references

        # A newly-recorded calibration shows up in what's freshly
        # discoverable...
        monkeypatch.setattr(
            type(ref), 'get_available_references',
            lambda self: ['BK-4138', 'Demo', 'unity', 'MMM5'],
        )
        # ...but the persisted config predates it.
        ref.set_persistence({
            'name': '', 'gain': 0.0,
            'available_references': ['BK-4138', 'Demo', 'unity'],
        })
        assert 'MMM5' in ref.available_references

    def test_set_persistence_preserves_selected_name_and_gain(self, monkeypatch):
        ref = self._make_reference(monkeypatch, ['BK-4138', 'Demo', 'unity'])
        ref.set_persistence({
            'name': 'Demo', 'gain': 3.0,
            'available_references': ['BK-4138', 'Demo', 'unity'],
        })
        assert ref.name == 'Demo'
        assert ref.gain == 3.0

    def test_set_persistence_keeps_user_added_entries(self, monkeypatch):
        # A '+' addition from a prior session, no longer discoverable on
        # disk (e.g. renamed/moved) -- must not be dropped either; the
        # merge is a union, not a replace-with-fresh.
        ref = self._make_reference(monkeypatch, ['BK-4138', 'unity'])
        ref.set_persistence({
            'name': '', 'gain': 0.0,
            'available_references': ['BK-4138', 'unity', 'Custom/Added'],
        })
        assert 'Custom/Added' in ref.available_references
        assert 'BK-4138' in ref.available_references


class TestMultiTypeSensorReference:
    '''
    MultiTypeSensorReference (used by input_recording) picks a
    calibration *type* first, then an instance scoped to that type's own
    manager -- switching type must not leak the old type's selection or
    option list into the new one, and resolve_object()/
    get_available_references() must always route through the currently
    selected type's manager.
    '''

    def _make_reference(self):
        from cftscal.plugins.settings import MultiTypeSensorReference
        return MultiTypeSensorReference()

    def test_defaults_to_measurement_mic(self):
        ref = self._make_reference()
        assert ref.sensor_type == 'Meas. Mic.'

    def test_available_references_matches_default_type_manager(self):
        from cftscal.objects import measurement_microphone_manager
        ref = self._make_reference()
        assert set(ref.available_references) == set(
            measurement_microphone_manager.list_names(),
        )

    def test_switch_type_scopes_available_references_to_new_type(self):
        from cftscal.objects import starship_manager
        ref = self._make_reference()
        ref.switch_type('Starship')
        assert ref.sensor_type == 'Starship'
        assert set(ref.available_references) == set(starship_manager.list_names())

    def test_switch_type_clears_name(self):
        ref = self._make_reference()
        ref.name = 'BK-4138'
        ref.switch_type('Starship')
        assert ref.name == ''

    def test_resolve_object_routes_through_selected_type(self, monkeypatch):
        from cftscal.objects import starship_manager
        calls = []
        # Patching the attribute on the manager *object* itself (not
        # rebinding a module-level name) -- MultiTypeSensorReference.
        # TYPE_MANAGERS already holds a direct reference to this same
        # object, captured at class-definition time.
        monkeypatch.setattr(
            starship_manager, 'get_object',
            lambda name: calls.append(name) or 'a-starship-object',
        )
        ref = self._make_reference()
        ref.switch_type('Starship')
        ref.name = 'SS1'
        assert ref.resolve_object() == 'a-starship-object'
        assert calls == ['SS1']


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

    def test_inear_inherits_group_path(self, monkeypatch):
        from cftscal.plugins.settings import InEarSettings
        # Avoid touching the real on-disk inear tree, which may still
        # carry pre-migration metadata (the coupler/output rename is
        # applied by the migration script, not retroactively assumed
        # here) -- this test only cares about group_path inheritance.
        monkeypatch.setattr(InEarSettings, 'get_available_couplers', lambda self: [])
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

    def test_inear_available_couplers_is_persistent_list(self, monkeypatch):
        from cftscal.plugins.settings import InEarSettings
        # Same isolation concern as test_inear_inherits_group_path above.
        monkeypatch.setattr(InEarSettings, 'get_available_couplers', lambda self: [])
        e = InEarSettings()
        assert isinstance(e.available_couplers, list)
        e.available_couplers = sorted(set(e.available_couplers) | {'C1_v2'})
        data = e.get_persistence()
        assert 'C1_v2' in data['available_couplers']

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

class TestInputRecordingSensors:
    '''
    CFTSInputRecording.sensors normalizes both the new multi-channel
    metadata shape (``{'sensors': {...}}``) and the legacy single-channel
    shape (``{'sensor': '...'}``, no ``'sensors'`` key) to the same
    ``{channel_name: {'label': ..., 'sensor': ...}}`` dict, so callers
    never need to branch on which era a recording came from.
    '''

    def test_new_schema_returned_unchanged(self, tmp_path):
        _make_calibration(tmp_path, metadata={
            'datetime': '2026-07-01T00:00:00',
            'generator': 'pistonphone',
            'sensors': {
                'ai0': {'label': 'Ch 0', 'sensor': 'MMM0'},
                'ai1': {'label': 'Ch 1', 'sensor': 'MMM1'},
            },
        })
        cal = CFTSInputRecording('rec', tmp_path)
        assert cal.sensors == {
            'ai0': {'label': 'Ch 0', 'sensor': 'MMM0'},
            'ai1': {'label': 'Ch 1', 'sensor': 'MMM1'},
        }

    def test_legacy_schema_synthesizes_selected_input_key(self, tmp_path):
        # Recordings made before multi-channel support always recorded
        # exactly one channel under the fixed array name `selected_input`
        # (see the pre-multi-channel `Input` manifest in
        # cftscal/paradigms/objects.enaml) -- that name, not the real
        # hardware channel (never stored), is what `.load()`-based code
        # needs to look up the recorded signal. No real channel label
        # was ever recorded for these, so `label` falls back to that
        # same synthesized name.
        _make_calibration(tmp_path, metadata={
            'datetime': '2026-07-01T00:00:00',
            'generator': 'pistonphone',
            'sensor': 'MMM0',
        })
        cal = CFTSInputRecording('rec', tmp_path)
        assert cal.sensors == {
            'selected_input': {'label': 'selected_input', 'sensor': 'MMM0'},
        }


class TestDeviceChannelGainProperties:
    '''
    Device/channel/gain metadata added for cross-plugin calibration
    comparison. Old field-name fallbacks matter here: real historical
    data was recorded before some of these fields existed or under a
    different key.
    '''

    def test_measurement_microphone_gain_defaults_none_not_zero(self, tmp_path):
        # Distinguishes a truly-unknown gain from a genuinely-recorded
        # 0 dB one (matching starship/speaker's own gain properties).
        _make_calibration(tmp_path, metadata={
            'datetime': '2026-07-01T00:00:00',
            'pistonphone': 'PP1',
        })
        cal = CFTSMeasurementMicrophoneCalibration('MMM0', tmp_path)
        assert cal.gain is None

    def test_measurement_microphone_gain_recorded_value(self, tmp_path):
        _make_calibration(tmp_path, metadata={
            'datetime': '2026-07-01T00:00:00',
            'pistonphone': 'PP1',
            'gain': 0,
        })
        cal = CFTSMeasurementMicrophoneCalibration('MMM0', tmp_path)
        assert cal.gain == 0

    def test_starship_microphone_channel_and_starship_channel(self, tmp_path):
        _make_calibration(tmp_path, metadata={
            'datetime': '2026-07-01T00:00:00',
            'starship': 'MMM6',
            'microphone': 'GRAS-40DP',
            'microphone_channel': 'Ch 1',
            'microphone_gain': 0,
            'starship_channel': 'A',
            'coupler': 'tube-2mm',
            'gain': 40,
            'stimulus': 'golay',
        })
        cal = CFTSStarshipCalibration('SS1', tmp_path)
        assert cal.starship == 'MMM6'
        assert cal.microphone == 'GRAS-40DP'
        assert cal.microphone_channel == 'Ch 1'
        assert cal.microphone_gain == 0
        assert cal.starship_channel == 'A'
        assert cal.gain == 40

    def test_starship_channel_fields_default_blank_for_old_data(self, tmp_path):
        _make_calibration(tmp_path, metadata={
            'datetime': '2026-07-01T00:00:00',
            'microphone': 'GRAS-40DP',
            'coupler': 'tube-2mm',
            'stimulus': 'golay',
        })
        cal = CFTSStarshipCalibration('SS1', tmp_path)
        assert cal.starship == ''
        assert cal.microphone_channel == ''
        assert cal.microphone_gain is None
        assert cal.starship_channel == ''

    def test_starship_device_id_independent_of_folder_name(self, tmp_path):
        # A target folder can be pointed anywhere, so the explicit
        # `starship` field is deliberately allowed to disagree with
        # `.name` (folder-derived) -- that's the whole point of it.
        _make_calibration(tmp_path, metadata={
            'datetime': '2026-07-01T00:00:00',
            'starship': 'MMM6',
            'microphone': 'GRAS-40DP',
            'coupler': 'tube-2mm',
            'stimulus': 'golay',
        })
        cal = CFTSStarshipCalibration('Lab1', tmp_path)
        assert cal.name == 'Lab1'
        assert cal.starship == 'MMM6'

    def test_speaker_output_microphone_channel_and_gain(self, tmp_path):
        _make_calibration(tmp_path, metadata={
            'datetime': '2026-07-01T00:00:00',
            'speaker': 'SPK1',
            'microphone': 'GRAS-40DP',
            'microphone_channel': 'Ch 1',
            'output_channel': 'Ch 0',
            'gain': 20,
            'method': 'golay',
        })
        cal = CFTSSpeakerCalibration('SPK1', tmp_path)
        assert cal.speaker == 'SPK1'
        assert cal.microphone_channel == 'Ch 1'
        assert cal.output_channel == 'Ch 0'
        assert cal.gain == 20

    def test_speaker_channel_and_gain_default_blank_for_old_data(self, tmp_path):
        _make_calibration(tmp_path, metadata={
            'datetime': '2026-07-01T00:00:00',
            'microphone': 'GRAS-40DP',
            'method': 'golay',
        })
        cal = CFTSSpeakerCalibration('SPK1', tmp_path)
        assert cal.speaker == ''
        assert cal.microphone_channel == ''
        assert cal.output_channel == ''
        assert cal.gain is None

    def test_generic_microphone_uses_new_key(self, tmp_path):
        _make_calibration(tmp_path, metadata={
            'datetime': '2026-07-01T00:00:00',
            'sensor_id': 'GEN1',
            'microphone': 'MMM0',
            'microphone_channel': 'Ch 1',
            'input_channel': 'Ch 2',
            'gain': 10,
            'speaker': 'SPK1',
            'speaker_channel': 'Ch 0',
            'stimulus': 'golay',
        })
        cal = CFTSGenericMicrophoneCalibration('GEN1', tmp_path)
        assert cal.sensor_id == 'GEN1'
        assert cal.microphone == 'MMM0'
        assert cal.microphone_channel == 'Ch 1'
        assert cal.input_channel == 'Ch 2'
        assert cal.gain == 10
        assert cal.speaker == 'SPK1'
        assert cal.speaker_channel == 'Ch 0'

    def test_generic_microphone_falls_back_to_legacy_key(self, tmp_path):
        # Recorded before the measurement_microphone -> microphone rename.
        _make_calibration(tmp_path, metadata={
            'datetime': '2026-07-01T00:00:00',
            'measurement_microphone': 'MMM0',
            'stimulus': 'golay',
        })
        cal = CFTSGenericMicrophoneCalibration('GEN1', tmp_path)
        assert cal.sensor_id == ''
        assert cal.microphone == 'MMM0'
        assert cal.microphone_channel == ''
        assert cal.input_channel == ''
        assert cal.gain is None
        assert cal.speaker == ''
        assert cal.speaker_channel == ''

    def test_generic_microphone_new_key_wins_over_legacy(self, tmp_path):
        _make_calibration(tmp_path, metadata={
            'datetime': '2026-07-01T00:00:00',
            'microphone': 'MMM0',
            'measurement_microphone': 'STALE',
            'stimulus': 'golay',
        })
        cal = CFTSGenericMicrophoneCalibration('GEN1', tmp_path)
        assert cal.microphone == 'MMM0'

    def test_input_amplifier_channel_and_total_gain(self, tmp_path):
        _make_calibration(tmp_path, metadata={
            'datetime': '2026-07-01T00:00:00',
            'sensor_id': 'AMP1',
            'input_channel': 'Ch 3',
            'total_gain': 1000.0,
            'freq_lb': 10.0,
            'freq_ub': 10000.0,
            'filt_60Hz': 'on',
        })
        cal = CFTSInputAmplifierCalibration('AMP1', tmp_path)
        assert cal.sensor_id == 'AMP1'
        assert cal.input_channel == 'Ch 3'
        assert cal.total_gain == 1000.0

    def test_input_amplifier_defaults_blank_for_old_data(self, tmp_path):
        _make_calibration(tmp_path, metadata={
            'datetime': '2026-07-01T00:00:00',
        })
        cal = CFTSInputAmplifierCalibration('AMP1', tmp_path)
        assert cal.sensor_id == ''
        assert cal.input_channel == ''
        assert cal.total_gain is None

    def test_inear_starship_channel(self, tmp_path):
        _make_calibration(tmp_path, metadata={
            'datetime': '2026-07-01T00:00:00',
            'starship': 'MMM0',
            'coupler': 'C1',
            'starship_channel': 'B',
        })
        cal = CFTSInEarCalibration('MMM0', tmp_path)
        assert cal.starship_channel == 'B'

    def test_inear_starship_channel_defaults_blank_for_old_data(self, tmp_path):
        _make_calibration(tmp_path, metadata={
            'datetime': '2026-07-01T00:00:00',
            'starship': 'MMM0',
            'coupler': 'C1',
        })
        cal = CFTSInEarCalibration('MMM0', tmp_path)
        assert cal.starship_channel == ''


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
