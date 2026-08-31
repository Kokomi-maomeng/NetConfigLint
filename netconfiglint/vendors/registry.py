"""Vendor plugin registry used by the shared analyzer."""

from __future__ import annotations

from dataclasses import dataclass

from netconfiglint.core.analyzer.models import VendorDetection
from netconfiglint.core.detector import VendorDetector
from netconfiglint.core.parser import ConfigParser
from netconfiglint.rules import Rule
from netconfiglint.vendors.huawei.detector import HuaweiDetector
from netconfiglint.vendors.huawei.parser import HuaweiConfigParser
from netconfiglint.vendors.huawei.rules import HUAWEI_RULES


@dataclass(frozen=True, slots=True)
class VendorPlugin:
    key: str
    vendor_name: str
    os_name: str
    aliases: tuple[str, ...]
    detector: VendorDetector
    parser: ConfigParser
    rules: tuple[Rule, ...]

    def forced_detection(self) -> VendorDetection:
        return VendorDetection(
            vendor=self.vendor_name,
            os=self.os_name,
            platform_family="Unknown",
            model="Unknown",
            version="Unknown",
            confidence=0.5,
            evidence=("Vendor selected by user",),
        )


VENDOR_PLUGINS: tuple[VendorPlugin, ...] = (
    VendorPlugin(
        key="huawei",
        vendor_name="Huawei",
        os_name="VRP",
        aliases=("huawei", "vrp"),
        detector=HuaweiDetector(),
        parser=HuaweiConfigParser(),
        rules=HUAWEI_RULES,
    ),
)


def get_vendor_plugin(name: str) -> VendorPlugin:
    normalized = name.lower()
    for plugin in VENDOR_PLUGINS:
        if normalized == plugin.key or normalized in plugin.aliases:
            return plugin
    raise ValueError(f"Unsupported vendor: {name}")


def detect_vendor_plugin(source: str) -> tuple[VendorPlugin, VendorDetection] | None:
    candidates = ((plugin, plugin.detector.detect(source)) for plugin in VENDOR_PLUGINS)
    supported = [candidate for candidate in candidates if candidate[1].vendor != "Unknown"]
    return max(supported, key=lambda candidate: candidate[1].confidence, default=None)
