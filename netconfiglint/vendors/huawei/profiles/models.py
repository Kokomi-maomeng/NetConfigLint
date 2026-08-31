from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from netconfiglint.core.analyzer.models import VendorDetection


@dataclass(frozen=True, slots=True)
class ProfileOverlay:
    name: str
    commands: tuple[tuple[str, ...], ...] = ()
    removed_commands: tuple[tuple[str, ...], ...] = ()


@dataclass(slots=True)
class CommandProfile:
    name: str
    base_commands: set[tuple[str, ...]] = field(default_factory=set)
    overlays: list[ProfileOverlay] = field(default_factory=list)

    def effective_commands(self) -> set[tuple[str, ...]]:
        commands = set(self.base_commands)
        for overlay in self.overlays:
            commands.update(overlay.commands)
            commands.difference_update(overlay.removed_commands)
        return commands


@dataclass(frozen=True, slots=True)
class EvidenceSource:
    source_id: str
    title: str
    url: str
    document_id: str
    accessed: str


@dataclass(frozen=True, slots=True)
class FeatureFact:
    feature: str
    syntax: str
    confidence: str
    source_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class VersionProfile:
    profile_id: str
    platform_family: str
    model_patterns: tuple[str, ...]
    version_patterns: tuple[str, ...]
    inherits: tuple[str, ...]
    features: tuple[FeatureFact, ...]
    source_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProfileResolution:
    profile: VersionProfile
    match_level: str
    confidence: str


class ProfileDatabase:
    """Load auditable facts without inferring undocumented command support."""

    def __init__(self, catalog_path: Path | None = None) -> None:
        path = catalog_path or Path(__file__).with_name("catalog.json")
        raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        self.schema_version = str(raw["schema_version"])
        self.sources = {
            item["id"]: EvidenceSource(
                source_id=item["id"],
                title=item["title"],
                url=item["url"],
                document_id=item["document_id"],
                accessed=item["accessed"],
            )
            for item in raw["sources"]
        }
        self.profiles = tuple(self._profile(item) for item in raw["profiles"])
        self._by_id = {profile.profile_id: profile for profile in self.profiles}
        if len(self._by_id) != len(self.profiles):
            raise ValueError("Duplicate Huawei profile ID")
        self._validate_references()

    @staticmethod
    def _profile(item: dict[str, Any]) -> VersionProfile:
        return VersionProfile(
            profile_id=item["id"],
            platform_family=item["platform_family"],
            model_patterns=tuple(item.get("model_patterns", ())),
            version_patterns=tuple(item.get("version_patterns", ())),
            inherits=tuple(item.get("inherits", ())),
            features=tuple(
                FeatureFact(
                    feature=fact["feature"],
                    syntax=fact["syntax"],
                    confidence=fact["confidence"],
                    source_ids=tuple(fact["source_ids"]),
                )
                for fact in item.get("features", ())
            ),
            source_ids=tuple(item.get("source_ids", ())),
        )

    def _validate_references(self) -> None:
        allowed_confidence = {"VERIFIED", "DOCUMENTED", "INFERRED", "GENERIC", "LOW"}
        for profile in self.profiles:
            for parent in profile.inherits:
                if parent not in self._by_id:
                    raise ValueError(f"Unknown parent profile: {parent}")
            referenced = (*profile.source_ids, *(sid for fact in profile.features for sid in fact.source_ids))
            for source_id in referenced:
                if source_id not in self.sources:
                    raise ValueError(f"Unknown evidence source: {source_id}")
            for fact in profile.features:
                if fact.confidence not in allowed_confidence:
                    raise ValueError(f"Unsupported confidence: {fact.confidence}")

        visited: set[str] = set()
        visiting: set[str] = set()

        def visit(profile_id: str) -> None:
            if profile_id in visiting:
                raise ValueError(f"Cyclic profile inheritance: {profile_id}")
            if profile_id in visited:
                return
            visiting.add(profile_id)
            for parent in self._by_id[profile_id].inherits:
                visit(parent)
            visiting.remove(profile_id)
            visited.add(profile_id)

        for profile_id in self._by_id:
            visit(profile_id)

    def resolve(self, detection: VendorDetection) -> ProfileResolution:
        candidates: list[tuple[int, VersionProfile, str]] = []
        for profile in self.profiles:
            model_match = any(
                re.search(pattern, detection.model, re.IGNORECASE) for pattern in profile.model_patterns
            )
            version_match = any(
                re.search(pattern, detection.version, re.IGNORECASE) for pattern in profile.version_patterns
            )
            if model_match and version_match:
                candidates.append((3, profile, "model+version"))
            elif version_match and profile.platform_family == detection.platform_family:
                candidates.append((2, profile, "platform+version"))
            elif model_match:
                candidates.append((1, profile, "model"))
        if candidates:
            score, profile, level = max(candidates, key=lambda item: item[0])
            confidence = "DOCUMENTED" if score >= 2 else "INFERRED"
            return ProfileResolution(profile, level, confidence)
        return ProfileResolution(self._by_id["huawei-vrp-base"], "generic", "GENERIC")

    def effective_features(self, profile_id: str) -> tuple[FeatureFact, ...]:
        profile = self._by_id[profile_id]
        inherited = tuple(
            feature for parent in profile.inherits for feature in self.effective_features(parent)
        )
        own_by_name = {feature.feature: feature for feature in (*inherited, *profile.features)}
        return tuple(own_by_name.values())
