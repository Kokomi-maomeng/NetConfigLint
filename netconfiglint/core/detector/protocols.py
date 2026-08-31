from typing import Protocol

from netconfiglint.core.analyzer.models import VendorDetection


class VendorDetector(Protocol):
    def detect(self, source: str) -> VendorDetection: ...
