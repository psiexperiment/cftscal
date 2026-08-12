'''
Tests for :mod:`cftscal.paradigms.default_state` -- seeding
psiexperiment's per-paradigm default layout/preferences files from
cftscal's own packaged copies.
'''
import pytest

from cftscal.paradigms import default_state as ds


def _write(path, text='fake content'):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class TestSeedDefaultState:

    def _make_config(self, monkeypatch, layout_root, preferences_root):
        roots = {'LAYOUT_ROOT': str(layout_root), 'PREFERENCES_ROOT': str(preferences_root)}
        monkeypatch.setattr(ds, 'get_config', lambda key: roots[key])

    def test_copies_when_destination_missing(self, tmp_path, monkeypatch):
        resource_root = tmp_path / 'resources'
        layout_root = tmp_path / 'layout'
        preferences_root = tmp_path / 'preferences'
        monkeypatch.setattr(ds, 'RESOURCE_ROOT', resource_root)
        self._make_config(monkeypatch, layout_root, preferences_root)

        _write(resource_root / 'layout' / 'demo' / 'default.layout', 'LAYOUT')
        _write(resource_root / 'preferences' / 'demo' / 'default.preferences', 'PREFS')

        ds.seed_default_state('demo')

        assert (layout_root / 'demo' / 'default.layout').read_text() == 'LAYOUT'
        assert (preferences_root / 'demo' / 'default.preferences').read_text() == 'PREFS'

    def test_does_not_overwrite_existing_destination(self, tmp_path, monkeypatch):
        resource_root = tmp_path / 'resources'
        layout_root = tmp_path / 'layout'
        preferences_root = tmp_path / 'preferences'
        monkeypatch.setattr(ds, 'RESOURCE_ROOT', resource_root)
        self._make_config(monkeypatch, layout_root, preferences_root)

        _write(resource_root / 'layout' / 'demo' / 'default.layout', 'PACKAGED')
        _write(layout_root / 'demo' / 'default.layout', 'USER SAVED')

        ds.seed_default_state('demo')

        assert (layout_root / 'demo' / 'default.layout').read_text() == 'USER SAVED'

    def test_noop_when_nothing_packaged(self, tmp_path, monkeypatch):
        resource_root = tmp_path / 'resources'
        layout_root = tmp_path / 'layout'
        preferences_root = tmp_path / 'preferences'
        monkeypatch.setattr(ds, 'RESOURCE_ROOT', resource_root)
        self._make_config(monkeypatch, layout_root, preferences_root)

        ds.seed_default_state('demo')

        assert not (layout_root / 'demo').exists()
        assert not (preferences_root / 'demo').exists()

    def test_only_copies_whichever_is_packaged(self, tmp_path, monkeypatch):
        # Layout packaged, preferences not -- only layout should land.
        resource_root = tmp_path / 'resources'
        layout_root = tmp_path / 'layout'
        preferences_root = tmp_path / 'preferences'
        monkeypatch.setattr(ds, 'RESOURCE_ROOT', resource_root)
        self._make_config(monkeypatch, layout_root, preferences_root)

        _write(resource_root / 'layout' / 'demo' / 'default.layout', 'LAYOUT')

        ds.seed_default_state('demo')

        assert (layout_root / 'demo' / 'default.layout').read_text() == 'LAYOUT'
        assert not (preferences_root / 'demo').exists()


class TestSeedAllDefaultState:

    def _make_config(self, monkeypatch, layout_root, preferences_root):
        roots = {'LAYOUT_ROOT': str(layout_root), 'PREFERENCES_ROOT': str(preferences_root)}
        monkeypatch.setattr(ds, 'get_config', lambda key: roots[key])

    def test_discovers_and_seeds_every_packaged_paradigm(self, tmp_path, monkeypatch):
        resource_root = tmp_path / 'resources'
        layout_root = tmp_path / 'layout'
        preferences_root = tmp_path / 'preferences'
        monkeypatch.setattr(ds, 'RESOURCE_ROOT', resource_root)
        self._make_config(monkeypatch, layout_root, preferences_root)

        # layout-only, preferences-only, and both -- three distinct
        # paradigm names, discovered purely from what's on disk.
        _write(resource_root / 'layout' / 'layout_only' / 'default.layout', 'L1')
        _write(resource_root / 'preferences' / 'prefs_only' / 'default.preferences', 'P1')
        _write(resource_root / 'layout' / 'both' / 'default.layout', 'L2')
        _write(resource_root / 'preferences' / 'both' / 'default.preferences', 'P2')

        ds.seed_all_default_state()

        assert (layout_root / 'layout_only' / 'default.layout').read_text() == 'L1'
        assert not (preferences_root / 'layout_only').exists()
        assert (preferences_root / 'prefs_only' / 'default.preferences').read_text() == 'P1'
        assert not (layout_root / 'prefs_only').exists()
        assert (layout_root / 'both' / 'default.layout').read_text() == 'L2'
        assert (preferences_root / 'both' / 'default.preferences').read_text() == 'P2'

    def test_existing_destination_left_untouched(self, tmp_path, monkeypatch):
        resource_root = tmp_path / 'resources'
        layout_root = tmp_path / 'layout'
        preferences_root = tmp_path / 'preferences'
        monkeypatch.setattr(ds, 'RESOURCE_ROOT', resource_root)
        self._make_config(monkeypatch, layout_root, preferences_root)

        _write(resource_root / 'layout' / 'demo' / 'default.layout', 'PACKAGED')
        _write(layout_root / 'demo' / 'default.layout', 'USER SAVED')

        ds.seed_all_default_state()

        assert (layout_root / 'demo' / 'default.layout').read_text() == 'USER SAVED'

    def test_missing_resource_root_is_a_noop(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ds, 'RESOURCE_ROOT', tmp_path / 'does-not-exist')
        self._make_config(monkeypatch, tmp_path / 'layout', tmp_path / 'preferences')
        ds.seed_all_default_state()  # must not raise

    def test_one_paradigm_erroring_does_not_block_the_rest(self, tmp_path, monkeypatch, caplog):
        resource_root = tmp_path / 'resources'
        layout_root = tmp_path / 'layout'
        preferences_root = tmp_path / 'preferences'
        monkeypatch.setattr(ds, 'RESOURCE_ROOT', resource_root)
        self._make_config(monkeypatch, layout_root, preferences_root)

        _write(resource_root / 'layout' / 'bad' / 'default.layout', 'L')
        _write(resource_root / 'layout' / 'good' / 'default.layout', 'L')

        real_seed = ds.seed_default_state
        def flaky_seed(name):
            if name == 'bad':
                raise OSError('permission denied')
            return real_seed(name)
        monkeypatch.setattr(ds, 'seed_default_state', flaky_seed)

        with caplog.at_level('WARNING'):
            ds.seed_all_default_state()

        assert (layout_root / 'good' / 'default.layout').read_text() == 'L'
        assert not (layout_root / 'bad').exists()
        assert 'bad' in caplog.text
