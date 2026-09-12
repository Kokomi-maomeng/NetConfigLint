from netconfiglint.core.analyzer import VendorDetection
from netconfiglint.vendors.huawei.profiles import ProfileDatabase


def test_profile_catalog_has_valid_official_evidence_links() -> None:
    database = ProfileDatabase()
    assert database.schema_version == "1.0"
    assert len(database.sources) >= 7
    assert all(source.url.startswith("https://") for source in database.sources.values())
    assert all(
        source.url.startswith(
            ("https://support.huawei.com/", "https://info.support.huawei.com/", "https://support.huawei.cn/")
        )
        for source in database.sources.values()
    )


def test_profile_resolution_is_conservative_without_explicit_evidence() -> None:
    database = ProfileDatabase()
    generic = database.resolve(VendorDetection("Huawei", "Unknown", "Unknown", "Unknown", 0.8))
    assert generic.profile.profile_id == "huawei-vrp-base"
    assert generic.confidence == "GENERIC"


def test_documented_profile_inherits_base_feature_facts() -> None:
    database = ProfileDatabase()
    features = database.effective_features("cloudengine-v200r024")
    feature_names = {feature.feature for feature in features}
    assert "snapshot.ipv4_rib" in feature_names
    assert "snapshot.ipv6_rib" in feature_names
    assert all(feature.confidence == "DOCUMENTED" for feature in features)
