from netconfiglint.vendors.huawei.detector import HuaweiDetector


def test_detects_huawei_without_guessing_model() -> None:
    result = HuaweiDetector().detect("sysname LAB\ninterface GigabitEthernet1/0/1\n port link-type trunk")

    assert result.vendor == "Huawei"
    assert result.os == "VRP"
    assert result.model == "Unknown"
    assert result.confidence >= 0.5


def test_unknown_text_is_not_forced_to_huawei() -> None:
    assert HuaweiDetector().detect("this is not a configuration").vendor == "Unknown"


def test_cloudengine_platform_requires_explicit_evidence() -> None:
    result = HuaweiDetector().detect("Huawei Versatile Routing Platform\nCloudEngine CE6800")
    assert result.platform_family == "CloudEngine"
