"""Vendor plugin registry used by the shared analyzer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from netconfiglint.core.analyzer.messages import EventDefinition
from netconfiglint.core.analyzer.models import VendorDetection
from netconfiglint.core.detector import VendorDetector
from netconfiglint.core.model import SnapshotEvidence
from netconfiglint.core.parser import ConfigParser
from netconfiglint.rules import Rule
from netconfiglint.vendors.h3c import H3C_RULES, H3CConfigParser, H3CDetector
from netconfiglint.vendors.h3c.messages import H3C_EVENTS
from netconfiglint.vendors.h3c.parser.snapshot_parser import H3CSnapshotParser
from netconfiglint.vendors.h3c.parser.source_input import configuration_preview
from netconfiglint.vendors.h3c.rules.operational import H3COperationalEvidenceRule
from netconfiglint.vendors.huawei.detector import HuaweiDetector
from netconfiglint.vendors.huawei.parser import HuaweiConfigParser
from netconfiglint.vendors.huawei.parser.snapshot_parser import HuaweiSnapshotParser
from netconfiglint.vendors.huawei.rules import HUAWEI_RULES
from netconfiglint.vendors.huawei.rules.operational import HuaweiOperationalViewRule


class SnapshotParser(Protocol):
    def parse(self, source: str) -> SnapshotEvidence: ...


@dataclass(frozen=True, slots=True)
class VendorPlugin:
    key: str
    vendor_name: str
    aliases: tuple[str, ...]
    detector: VendorDetector
    parser: ConfigParser
    rules: tuple[Rule, ...]
    snapshot_parser: SnapshotParser
    view_rules: tuple[Rule, ...]
    message_events: tuple[EventDefinition, ...] = ()
    input_preview: Callable[[str], tuple[str, dict[int, int]] | None] | None = None
    default_profile_id: str = "unresolved"
    default_profile_confidence: str = "GENERIC"

    def forced_detection(self) -> VendorDetection:
        return VendorDetection(
            vendor=self.vendor_name,
            platform_family="Unknown",
            model="Unknown",
            version="Unknown",
            confidence=0.5,
            evidence=("Vendor selected by user",),
            profile_id=self.default_profile_id,
            profile_confidence=self.default_profile_confidence,
        )


VENDOR_PLUGINS: tuple[VendorPlugin, ...] = (
    VendorPlugin(
        key="h3c",
        vendor_name="H3C",
        aliases=("h3c", "comware", "comware7", "hpe-comware"),
        detector=H3CDetector(),
        parser=H3CConfigParser(),
        rules=H3C_RULES,
        snapshot_parser=H3CSnapshotParser(),
        view_rules=(H3COperationalEvidenceRule(),),
        input_preview=configuration_preview,
        message_events=H3C_EVENTS,
        default_profile_id="h3c-comware-generic",
    ),
    VendorPlugin(
        key="huawei",
        vendor_name="Huawei",
        aliases=("huawei", "vrp"),
        detector=HuaweiDetector(),
        parser=HuaweiConfigParser(),
        rules=HUAWEI_RULES,
        snapshot_parser=HuaweiSnapshotParser(),
        view_rules=(HuaweiOperationalViewRule(),),
        default_profile_id="huawei-vrp-base",
    ),
)


def get_vendor_plugin(name: str) -> VendorPlugin:
    normalized = name.lower()
    for plugin in VENDOR_PLUGINS:
        if normalized == plugin.key or normalized in plugin.aliases:
            return plugin
    raise ValueError(f"Unsupported vendor: {name}")


def extract_configuration_preview(source: str) -> tuple[str, dict[int, int]] | None:
    for plugin in VENDOR_PLUGINS:
        if plugin.input_preview is not None:
            preview = plugin.input_preview(source)
            if preview is not None:
                return preview
    return None


def detect_vendor_plugin(source: str) -> tuple[VendorPlugin, VendorDetection] | None:
    candidates = ((plugin, plugin.detector.detect(source)) for plugin in VENDOR_PLUGINS)
    supported = [candidate for candidate in candidates if candidate[1].vendor != "Unknown"]
    return max(supported, key=lambda candidate: candidate[1].confidence, default=None)
