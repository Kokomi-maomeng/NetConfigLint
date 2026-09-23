"""H3C Comware vendor integration."""

from netconfiglint.vendors.h3c.detector import H3CDetector
from netconfiglint.vendors.h3c.parser import H3CConfigParser
from netconfiglint.vendors.h3c.rules import H3C_RULES

__all__ = ["H3C_RULES", "H3CConfigParser", "H3CDetector"]
