'''
Tests for the plugin-loading logic in :mod:`cftscal.plugins.manifest`.

Focus on ``_CalibrationPluginManifest._get_available``'s two ways a
plugin can be considered available: hardware detection via
``settings_config`` probes (the original behavior), and a plugin's id
being force-enabled via ``WorkspaceSettings.enabled_plugins`` (the
settings-driven replacement for the removed ``--load-all`` CLI flag).
'''
import enaml
with enaml.imports():
    from cftscal.plugins.manifest import _CalibrationPluginManifest


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
