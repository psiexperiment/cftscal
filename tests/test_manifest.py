'''
Tests for the plugin-loading logic in :mod:`cftscal.plugins.manifest`.

Focus on ``_CalibrationPluginManifest._get_available``'s two ways a
plugin can be considered available: hardware detection via
``settings_config`` probes (the original behavior), and a plugin's id
being force-enabled via ``WorkspaceSettings.enabled_plugins`` (the
settings-driven replacement for the removed ``--load-all`` CLI flag).
Also covers ``rank``, which keeps the Workspace menu's plugin order
matching ``TO_REGISTER`` regardless of registration timing.
'''
import enaml
with enaml.imports():
    from cftscal.plugins.manifest import (
        CalibrationPluginManifest, TO_REGISTER, _CalibrationPluginManifest,
    )


def _make_manifest(plugin_id, hardware_available):
    return _CalibrationPluginManifest(
        id=plugin_id,
        settings_config={'probe': lambda raise_error=True: hardware_available},
    )


class TestCalibrationPluginManifestAvailable:

    def test_available_when_hardware_probe_succeeds(self):
        manifest = _make_manifest('some-plugin', hardware_available=True)
        assert manifest.available is True

    def test_unavailable_when_hardware_probe_fails(self):
        manifest = _make_manifest('some-plugin', hardware_available=False)
        assert manifest.available is False

    def test_enabled_plugins_forces_availability(self, monkeypatch):
        # Even though the hardware probe fails, this plugin's id is
        # force-enabled in WorkspaceSettings -- e.g. a review-only
        # machine without the matching hardware.
        class _FakeSettings:
            enabled_plugins = ['forced-plugin']

        monkeypatch.setattr(
            'cftscal.plugins.manifest.WorkspaceSettings',
            lambda: _FakeSettings(),
        )

        forced = _make_manifest('forced-plugin', hardware_available=False)
        other = _make_manifest('other-plugin', hardware_available=False)

        assert forced.available is True
        assert other.available is False


class TestCalibrationPluginManifestRank:
    '''
    Every plugin's ActionItem-contributing Extension defaults to the
    same rank (0), so without an explicit rank, enaml.workbench.ui
    breaks ties by registration order -- which can silently drift from
    TO_REGISTER's order (e.g. reload_plugins() may register a plugin
    later than others after a settings change). ``rank`` (set by
    main.py/reload_plugins() from each plugin's TO_REGISTER position)
    fixes the Workspace menu's order deterministically.
    '''

    def _actions_extension(self, manifest):
        return next(
            e for e in manifest.children
            if getattr(e, 'id', '') == manifest.id + '.actions'
        )

    def test_rank_propagates_to_actions_extension(self):
        manifest = CalibrationPluginManifest(id='some-plugin', rank=3)
        assert self._actions_extension(manifest).rank == 3

    def test_default_rank_is_zero(self):
        manifest = CalibrationPluginManifest(id='some-plugin')
        assert self._actions_extension(manifest).rank == 0

    def test_ranks_match_to_register_order_for_every_real_plugin(self):
        # Mirrors exactly how main.py/reload_plugins() construct each
        # plugin -- rank=i from enumerate(TO_REGISTER) -- and confirms
        # it reaches the Extension for every real plugin module, not
        # just a synthetic one.
        import importlib
        with enaml.imports():
            for i, (module_name, class_name) in enumerate(TO_REGISTER):
                module = importlib.import_module(module_name)
                instance = getattr(module, class_name)(rank=i)
                assert self._actions_extension(instance).rank == i
