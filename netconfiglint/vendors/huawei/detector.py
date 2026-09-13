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

        # Only version-output/banner positions can activate device-specific facts.
        # Free-form descriptions, usernames, policy names and addresses are not device evidence.
        identity_lines = [
            line.strip()
            for line in source.splitlines()
            if re.match(
                r"^(?:Huawei(?:\s|$)|CloudEngine(?:\s|$)|Version V\d|VRP \(R\) software|"
                r"(?:CE[5689]\d{3}|S\d{4})[A-Z0-9-]*(?:\s|$)|!Software Version)",
                line,
                re.I,
            )
        ]
        identity_source = "\n".join(identity_lines)
        models = {
            value.upper()
            for value in re.findall(r"\b((?:CE[5689]\d{3}|S\d{4})[A-Z0-9-]*)\b", identity_source, re.I)
        }
        versions = {
            value.upper()
            for value in re.findall(r"\b(V\d{3}R\d{3}C\d{2}(?:SPC\d{3})?)\b", identity_source, re.I)
        }
        model = next(iter(models)).upper() if len(models) == 1 else "Unknown"
        version = next(iter(versions)).upper() if len(versions) == 1 else "Unknown"
        platform = (
            "CloudEngine" if model.startswith("CE") else "S-Series" if model.startswith("S") else "Unknown"
        )
        detection = VendorDetection(
            vendor="Huawei" if strong or distinctive else "Unknown",
            platform_family=platform,
            model=model,
            version=version,
            confidence=round(confidence, 2),
            evidence=tuple(evidence),
        )
        resolution = _PROFILES.resolve(detection)
        return replace(
            detection,
            profile_id=resolution.profile.profile_id,
            profile_confidence=resolution.confidence,
        )
