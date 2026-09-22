"""Small static guard for the Windows installer OS compatibility check."""

from pathlib import Path
from xml.etree import ElementTree


def test_windows_msi_checks_actual_build_number() -> None:
    source = Path(__file__).resolve().parents[2] / "installer" / "NetConfigLint.wxs"
    root = ElementTree.parse(source).getroot()
    namespace = {"w": "http://schemas.microsoft.com/wix/2006/wi"}
    search = root.find(".//w:Property[@Id='OSBUILDNUMBER']/w:RegistrySearch", namespace)
    assert search is not None
    assert search.attrib["Name"] == "CurrentBuildNumber"
    assert search.attrib["Win64"] == "yes"
    conditions = root.findall(".//w:Product/w:Condition", namespace)
    assert any("OSBUILDNUMBER >= 10240" in (condition.text or "") for condition in conditions)
    assert all("WindowsBuild" not in (condition.text or "") for condition in conditions)
