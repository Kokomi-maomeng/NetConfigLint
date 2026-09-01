from __future__ import annotations

import json
import zipfile
from pathlib import Path

from scripts.validate_huawei_archive import validate_archive


def test_archive_validator_reports_only_aggregate_results(tmp_path: Path) -> None:
    archive_path = tmp_path / "synthetic.zip"
    source = """sysname PRIVATE-DEVICE
telnet server enable
snmp-agent community read PRIVATE-COMMUNITY
interface Vlanif100
 ip address 192.0.2.1 255.255.255.0
"""
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("export/Huawei_华为/private-device.cfg", source)

    result = validate_archive(archive_path, minimum_size=1)
    rendered = json.dumps(result, ensure_ascii=False)

    assert result["candidate_configs"] == 1
    assert result["analyzed_configs"] == 1
    assert result["failed_configs"] == 0
    assert "HUA-SEC-002" in result["rule_hits"]
    assert "PRIVATE-DEVICE" not in rendered
    assert "PRIVATE-COMMUNITY" not in rendered
    assert "192.0.2.1" not in rendered
    assert "private-device.cfg" not in rendered
