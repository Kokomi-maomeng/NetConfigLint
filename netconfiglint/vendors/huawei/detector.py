"""Conservative Huawei VRP signature detector."""

from __future__ import annotations

import re
from dataclasses import replace

from netconfiglint.core.analyzer.models import VendorDetection
from netconfiglint.vendors.huawei.profiles import ProfileDatabase

_PROFILES = ProfileDatabase()


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
        # An explicit foreign banner outweighs syntax shared with VRP, including mixed captures.
        foreign = re.search(
            r"(?im)^\s*(?:H3C\b|HPE Comware\b|HP Comware\b|.*Comware Software|"
            r"Cisco IOS\b|Junos:|Juniper Networks\b|Arista Networks\b)",
            source,
        )
        if foreign:
            return VendorDetection(
                vendor="Unknown",
                platform_family="Unknown",
                model="Unknown",
                version="Unknown",
                confidence=0.0,
                evidence=(
                    "Explicit unsupported or mixed vendor banner; select the intended vendor manually",
                ),
            )
        distinctive = bool(re.search(r"(?im)^\s*port (?:trunk allow-pass vlan|default vlan)\b", source))
        evidence: list[str] = []
        strong = sum(bool(pattern.search(source)) for pattern in self._strong)
        signals = sum(bool(pattern.search(source)) for pattern in self._signals)
        if distinctive:
            evidence.append("Huawei port VLAN syntax")
        if strong:
            evidence.append("VRP version banner")
        if signals:
            evidence.append(f"{signals} shared VRP-style signatures; vendor inferred, not confirmed")
        confidence = min(0.99, (0.85 if strong else 0.35) + signals * 0.04) if strong or signals else 0.10

        platform = "Unknown"
        model = "Unknown"
        if re.search(r"\bCloudEngine\b|\bCE\d{4,}\b", source, re.IGNORECASE):
            platform = "CloudEngine"
            confidence = min(0.99, confidence + 0.05)
            model_match = re.search(r"\b(CE(?:5|6|8|9)\d{3}[A-Z0-9-]*)\b", source, re.IGNORECASE)
            if model_match:
                model = model_match.group(1).upper()
        else:
            model_match = re.search(r"\b(S77\d{2}[A-Z0-9-]*)\b", source, re.IGNORECASE)
            if model_match:
                platform = "S-Series"
                model = model_match.group(1).upper()
                confidence = min(0.99, confidence + 0.05)

        version_match = re.search(r"\b(V\d{3}R\d{3}C\d{2}(?:SPC\d{3})?)\b", source, re.IGNORECASE)
        detection = VendorDetection(
            vendor="Huawei" if strong or distinctive else "Unknown",
            platform_family=platform,
            model=model,
            version=version_match.group(1).upper() if version_match else "Unknown",
            confidence=round(confidence, 2),
            evidence=tuple(evidence),
        )
        resolution = _PROFILES.resolve(detection)
        return replace(
            detection,
            profile_id=resolution.profile.profile_id,
            profile_confidence=resolution.confidence,
        )
