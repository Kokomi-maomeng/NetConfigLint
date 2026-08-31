"""Conservative Huawei VRP signature detector."""

from __future__ import annotations

import re

from netconfiglint.core.analyzer.models import VendorDetection


class HuaweiDetector:
    _strong = (
        re.compile(r"^Huawei Versatile Routing Platform", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^VRP \(R\) software", re.MULTILINE | re.IGNORECASE),
    )
    _signals = (
        re.compile(r"^sysname\s+\S+", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^display current-configuration", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^port\s+(?:link-type|trunk allow-pass|default vlan)", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^ip route-static\s+", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^undo shutdown$", re.MULTILINE | re.IGNORECASE),
    )

    def detect(self, source: str) -> VendorDetection:
        evidence: list[str] = []
        strong = sum(bool(pattern.search(source)) for pattern in self._strong)
        signals = sum(bool(pattern.search(source)) for pattern in self._signals)
        if strong:
            evidence.append("VRP version banner")
        if signals:
            evidence.append(f"{signals} Huawei-style configuration signatures")
        confidence = min(0.99, 0.55 + strong * 0.30 + signals * 0.06) if strong or signals else 0.10

        platform = "Unknown"
        if re.search(r"\bCloudEngine\b|\bCE\d{4,}\b", source, re.IGNORECASE):
            platform = "CloudEngine"
            confidence = min(0.99, confidence + 0.05)

        version_match = re.search(r"\bV(?:ersion)?\s*(V\d{3}R\d{3}[^\s,]*)", source, re.IGNORECASE)
        return VendorDetection(
            vendor="Huawei" if strong or signals else "Unknown",
            os="VRP" if strong or signals else "Unknown",
            platform_family=platform,
            model="Unknown",
            version=version_match.group(1) if version_match else "Unknown",
            confidence=round(confidence, 2),
            evidence=tuple(evidence),
        )
