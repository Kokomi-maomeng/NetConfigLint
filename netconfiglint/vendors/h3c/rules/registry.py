from netconfiglint.rules import Rule
from netconfiglint.vendors.h3c.rules.adapter import H3CAdaptedRule
from netconfiglint.vendors.h3c.rules.operational import H3COperationalEvidenceRule
from netconfiglint.vendors.h3c.rules.security import (
    H3COspfAuthenticationRule,
    H3COspfExposureRule,
    H3CSnmpCommunityRule,
    H3CVtyInboundProtocolRule,
    LegacyTlsVersionRule,
    LocalUserTelnetRule,
    PlaintextPasswordRule,
)
from netconfiglint.vendors.h3c.rules.structural import (
    MissingBridgeAggregationRule,
    MissingVlanInterfaceVlanRule,
    UnsupportedCommandSummaryRule,
)
from netconfiglint.vendors.huawei.rules.advanced_policy import (
    BroadPermitAclRule,
    EmptyReferencedAclRule,
    MissingRedistributionPolicyRule,
)
from netconfiglint.vendors.huawei.rules.bgp import MissingBgpPeerGroupRule, MissingBgpPeerRemoteAsRule
from netconfiglint.vendors.huawei.rules.interface import (
    InvalidInterfaceAddressRule,
    LinkTypeMismatchRule,
    ShutdownWithBusinessConfigRule,
)
from netconfiglint.vendors.huawei.rules.ipv6 import IPv6InterfaceAddressRule, IPv6StaticRouteFormatRule
from netconfiglint.vendors.huawei.rules.isis import MissingIsisNetworkEntityRule, MissingIsisProcessRule
from netconfiglint.vendors.huawei.rules.layer2 import MissingBpduProtectionRule
from netconfiglint.vendors.huawei.rules.ospf import (
    MissingInterfaceOspfProcessRule,
    OspfAreaAssociationRule,
    OspfNoParticipatingInterfaceRule,
)
from netconfiglint.vendors.huawei.rules.policy import (
    MissingAclRule,
    MissingBgpRoutePolicyRule,
    MissingPrefixListRule,
    UnusedRoutePolicyRule,
)
from netconfiglint.vendors.huawei.rules.routes import (
    AbnormalNextHopRule,
    MissingStaticRouteVpnRule,
    StaticRouteFormatRule,
)
from netconfiglint.vendors.huawei.rules.security import (
    FtpServerRule,
    SensitiveConfigurationRule,
    TelnetServerRule,
    UnauthenticatedNtpRule,
    VtyPasswordAuthenticationRule,
)
from netconfiglint.vendors.huawei.rules.traffic_policy import (
    MissingAppliedTrafficPolicyRule,
    MissingTrafficPolicyComponentRule,
)
from netconfiglint.vendors.huawei.rules.vlan import (
    MissingAccessVlanRule,
    MissingHybridVlanRule,
    MissingPvidVlanRule,
    MissingTrunkVlanRule,
)
from netconfiglint.vendors.huawei.rules.vpn import MissingBgpVpnRule, MissingInterfaceVpnRule

_NORMALIZED_RULES: tuple[Rule, ...] = (
    MissingTrunkVlanRule(),
    MissingAccessVlanRule(),
    MissingHybridVlanRule(),
    MissingPvidVlanRule(),
    ShutdownWithBusinessConfigRule(),
    LinkTypeMismatchRule(),
    InvalidInterfaceAddressRule(),
    IPv6StaticRouteFormatRule(),
    IPv6InterfaceAddressRule(),
    StaticRouteFormatRule(),
    AbnormalNextHopRule(),
    MissingStaticRouteVpnRule(),
    MissingBgpRoutePolicyRule(),
    MissingPrefixListRule(),
    MissingBgpPeerGroupRule(),
    MissingBgpPeerRemoteAsRule(),
    MissingIsisProcessRule(),
    MissingIsisNetworkEntityRule(),
    OspfAreaAssociationRule(),
    OspfNoParticipatingInterfaceRule(),
    MissingInterfaceOspfProcessRule(),
    MissingAclRule(),
    BroadPermitAclRule(),
    EmptyReferencedAclRule(),
    UnusedRoutePolicyRule(),
    MissingRedistributionPolicyRule(),
    MissingInterfaceVpnRule(),
    MissingBgpVpnRule(),
    MissingTrafficPolicyComponentRule(),
    MissingAppliedTrafficPolicyRule(),
    MissingBpduProtectionRule(),
    SensitiveConfigurationRule(),
    TelnetServerRule(),
    FtpServerRule(),
    UnauthenticatedNtpRule(),
    VtyPasswordAuthenticationRule(),
)

H3C_RULES: tuple[Rule, ...] = (
    *(H3CAdaptedRule(rule) for rule in _NORMALIZED_RULES),
    MissingBridgeAggregationRule(),
    MissingVlanInterfaceVlanRule(),
    PlaintextPasswordRule(),
    LocalUserTelnetRule(),
    H3CSnmpCommunityRule(),
    H3CVtyInboundProtocolRule(),
    LegacyTlsVersionRule(),
    H3COspfExposureRule(),
    H3COspfAuthenticationRule(),
    H3COperationalEvidenceRule(),
    UnsupportedCommandSummaryRule(),
)
