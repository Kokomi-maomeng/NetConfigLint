import pytest

from netconfiglint.vendors import detect_vendor_plugin, get_vendor_plugin


def test_registry_resolves_alias_without_core_vendor_conditionals() -> None:
    assert get_vendor_plugin("vrp").key == "huawei"
    with pytest.raises(ValueError, match="Unsupported vendor"):
        get_vendor_plugin("not-supported")


def test_registry_selects_supported_detector() -> None:
    detected = detect_vendor_plugin("sysname SYNTHETIC-LAB\nport link-type trunk")
    assert detected is not None
    plugin, detection = detected
    assert plugin.key == "huawei"
    assert detection.vendor == "Huawei"
