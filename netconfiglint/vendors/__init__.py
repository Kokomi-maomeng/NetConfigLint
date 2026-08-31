"""Vendor extension registry."""

from netconfiglint.vendors.registry import (
    VENDOR_PLUGINS,
    VendorPlugin,
    detect_vendor_plugin,
    get_vendor_plugin,
)

__all__ = ["VENDOR_PLUGINS", "VendorPlugin", "detect_vendor_plugin", "get_vendor_plugin"]
