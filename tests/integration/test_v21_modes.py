from pathlib import Path

from netconfiglint import analyze
from netconfiglint.gui.models import HistoryStore


def test_h3c_irf_commands_and_peer_port_inference() -> None:
    source = (
        "sys\n说明\uff1a两台设备示例\nirf member 1 priority 32\n"
        "irf-port 1/1\n port group interface Ten-GigabitEthernet1/0/1\n#\n"
        "irf member 1 renumber 2\nirf-port 2/1\n"
        " port group interface Ten-GigabitEthernet2/0/1\n"
    )
    result = analyze(source, "snippet", "h3c")
    assert "H3C-IRF-001" in {item.rule_id for item in result.diagnostics}
    assert result.coverage["unsupported"] == 0
    assert result.coverage["unparsed"] == 0
    assert result.coverage["ignored"] >= 2
    correct = analyze(source.replace("irf-port 1/1", "irf-port 1/2"), "snippet", "h3c")
    assert "H3C-IRF-001" not in {item.rule_id for item in correct.diagnostics}


def test_message_and_view_modes_have_distinct_evidence() -> None:
    event = analyze("IRF port link down", "message", "h3c")
    assert [item.rule_id for item in event.diagnostics] == ["MSG-IRF-LINK"]
    assert event.diagnostics[0].confidence.value == "INFERRED"
    view = analyze(
        "<H3C>display ip routing-table all-routes\nDestinations : 3 Routes : 3",
        "view",
        "h3c",
    )
    assert "H3C-OPS-000" in {item.rule_id for item in view.diagnostics}
    assert not view.config.blocks
    assert not view.config.interfaces


def test_full_mode_combines_config_and_display_without_counting_output_as_commands() -> None:
    h3c = analyze(
        "sysname SYNTHETIC\nirf-port 1/2\n"
        " port group interface Ten-GigabitEthernet1/0/1\n"
        "<H3C>display ip routing-table all-routes\nDestinations : 3 Routes : 3\n"
        "IRF port link down\n",
        "full",
        "h3c",
    )
    assert h3c.coverage["analysis_scope_lines"] == 3
    assert h3c.coverage["excluded_operational_lines"] == 3
    assert h3c.coverage["unsupported"] == 0
    ids = {item.rule_id for item in h3c.diagnostics}
    assert "H3C-OPS-000" in ids
    assert "MSG-IRF-LINK" in ids

    huawei = analyze(
        "sysname SYNTHETIC\n<HUA>display ip routing-table\nRoute Flags: R - relay, D - download to fib\n",
        "full",
        "huawei",
    )
    assert huawei.coverage["analysis_scope_lines"] == 1
    assert huawei.coverage["excluded_operational_lines"] == 2
    assert huawei.config.snapshot.ipv4_rib_present


def test_view_mode_extracts_source_linked_lldp_edges_for_both_vendors() -> None:
    h3c = analyze(
        "<H3C>display lldp neighbor-information list\n"
        "Local Interface Chassis ID Port ID System Name\n"
        "XGE1/0/1 000f-e25d-ee91 Ten-GigabitEthernet1/0/1 PEER-A\n",
        "view",
        "h3c",
    )
    h3c_edge = next(item for item in h3c.diagnostics if item.rule_id == "H3C-OPS-013")
    assert h3c_edge.source.line == 3
    assert "PEER-A" in h3c_edge.message

    huawei = analyze(
        "<HUA> display lldp neighbor brief\n"
        "Local Intf Neighbor Dev Neighbor Intf Exptime (sec)\n"
        "Gigabitethernet 0/1/0 DeviceB Gigabitethernet 0/1/1 101\n",
        "view",
        "huawei",
    )
    huawei_edge = next(item for item in huawei.diagnostics if item.rule_id == "HUA-VIEW-003")
    assert huawei_edge.source.line == 3
    assert "DeviceB" in huawei_edge.message


def test_history_preserves_original_and_new_revision(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.json", enabled=True, persist_settings=False)
    original = "sysname SYNTHETIC-ONE\n"
    modified = "sysname SYNTHETIC-TWO\n"
    store.append(analyze(original, vendor="huawei"), original, "huawei")
    first_id = store.entries[0].entry_id
    store.append(analyze(modified, vendor="huawei"), modified, "huawei")
    assert [item.source_text for item in store.entries] == [modified, original]
    assert store.get(first_id) is not None
    assert store.get(first_id).source_text == original
    reloaded = HistoryStore(store.path, enabled=True, persist_settings=False)
    assert [item.entry_id for item in reloaded.entries] == [store.entries[0].entry_id, first_id]
    reloaded.set_enabled(False)
    assert not store.path.exists()
