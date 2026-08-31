from typing import Protocol

from netconfiglint.core.analyzer.models import AnalysisMode, VendorDetection
from netconfiglint.core.model import DeviceConfig


class ConfigParser(Protocol):
    def parse(self, source: str, mode: AnalysisMode, detection: VendorDetection) -> DeviceConfig: ...
