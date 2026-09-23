"""Conservative H3C/HPE Comware signature detector."""

from __future__ import annotations

import re

from netconfiglint.core.analyzer.models import VendorDetection


class H3CDetector:
    """Identify H3C Comware without treating shared VRP-like syntax as proof."""

    _strong = (
        re.compile(r"^\s*H3C\b.*(?:Comware|Software)", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^\s*(?:HPE|HP)\s+Comware\s+Software", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^\s*Comware\s+Software,?\s+Version", re.MULTILINE | re.IGNORECASE),
    )
    _distinctive = (
        re.compile(r"^\s*port\s+trunk\s+permit\s+vlan\b", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^\s*port\s+link-aggregation\s+group\s+\d+", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^\s*interface\s+Vlan-interface\s*\d+", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^\s*local-user\s+\S+\s+class\s+(?:manage|network)", re.MULTILINE | re.IGNORECASE),
    )
    _shared = (
        re.compile(r"^\s*sysname\s+\S+", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^\s*ip\s+route-static\s+", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^\s*undo\s+shutdown$", re.MULTILINE | re.IGNORECASE),
    )

    def detect(self, source: str) -> VendorDetection:
        if re.search(
            r"(?im)^\s*(?:Huawei Versatile Routing Platform|VRP \(R\) software|"
            r"Cisco IOS\b|Junos:|Juniper Networks\b|Arista Networks\b)",
            source,
        ):
            return VendorDetection("Unknown", "Unknown", "Unknown", "Unknown", 0.0)

        strong = sum(bool(pattern.search(source)) for pattern in self._strong)
        distinctive = sum(bool(pattern.search(source)) for pattern in self._distinctive)
        shared = sum(bool(pattern.search(source)) for pattern in self._shared)
        identified = bool(strong or distinctive)
        evidence: list[str] = []
        if strong:
            evidence.append("H3C/HPE Comware software banner")
        if distinctive:
            evidence.append(f"{distinctive} distinctive Comware configuration signature(s)")
        if shared:
            evidence.append(f"{shared} shared network configuration signature(s)")

        identity_lines = "\n".join(
            line.strip()
            for line in source.splitlines()
            if re.search(r"(?i)\b(?:H3C|HPE|HP|Comware Software|Software Version)\b", line)
        )
        models = {
            value.upper()
            for value in re.findall(
                r"\b((?:S|MSR|WX|CR|F|M)[0-9][A-Z0-9-]{2,})\b", identity_lines, re.IGNORECASE
            )
        }
        releases = {
            value.upper()
            for value in re.findall(r"\b(Release\s+[A-Z0-9.]+)\b", identity_lines, re.IGNORECASE)
        }
        versions = {
            value.upper()
            for value in re.findall(
                r"\bVersion\s+([0-9]+(?:\.[0-9A-Z]+){1,3})", identity_lines, re.IGNORECASE
            )
        }
        model = next(iter(models)) if len(models) == 1 else "Unknown"
        version_parts = sorted({*releases, *(f"VERSION {value}" for value in versions)})
        version = " / ".join(version_parts) if len(version_parts) <= 2 and version_parts else "Unknown"
        comware7 = bool(
            re.search(
                r"(?i)(?:Comware\s+(?:Software,?\s+)?Version\s+7|Version\s+7\.)",
                identity_lines,
            )
        )
        platform = "Comware 7" if comware7 else "Comware"
        confidence = min(0.99, (0.88 if strong else 0.70) + distinctive * 0.05 + shared * 0.01)
        return VendorDetection(
            vendor="H3C" if identified else "Unknown",
            platform_family=platform if identified else "Unknown",
            model=model,
            version=version,
            confidence=round(confidence if identified else min(0.25, 0.08 + shared * 0.04), 2),
            evidence=tuple(evidence),
            profile_id="h3c-comware7-generic" if comware7 else "h3c-comware-generic",
            profile_confidence="DOCUMENTED" if comware7 and strong else "GENERIC",
        )
