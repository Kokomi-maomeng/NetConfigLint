from netconfiglint.rules import Rule
from netconfiglint.vendors.h3c.rules.advanced_policy import (
    BroadPermitAclRule,
    EmptyReferencedAclRule,
    MissingRedistributionPolicyRule,
)
from netconfiglint.vendors.h3c.rules.aggregation import AggregationModeEvidenceRule
from netconfiglint.vendors.h3c.rules.basic_security import (
    FtpServerRule,
    SensitiveConfigurationRule,
    TelnetServerRule,
    UnauthenticatedNtpRule,
)
from netconfiglint.vendors.h3c.rules.bgp import MissingBgpPeerGroupRule, MissingBgpPeerRemoteAsRule
from netconfiglint.vendors.h3c.rules.interface import (
    InvalidInterfaceAddressRule,
    LinkTypeMismatchRule,
    ShutdownWithBusinessConfigRule,
)
from netconfiglint.vendors.h3c.rules.ipv6 import IPv6InterfaceAddressRule, IPv6StaticRouteFormatRule
from netconfiglint.vendors.h3c.rules.isis import MissingIsisNetworkEntityRule, MissingIsisProcessRule
from netconfiglint.vendors.h3c.rules.layer2 import MissingBpduProtectionRule
from netconfiglint.vendors.h3c.rules.operational import H3COperationalEvidenceRule
from netconfiglint.vendors.h3c.rules.ospf import (
    MissingInterfaceOspfProcessRule,
    OspfAreaAssociationRule,
    OspfNoParticipatingInterfaceRule,
)
from netconfiglint.vendors.h3c.rules.policy import (
    MissingAclRule,
    MissingBgpRoutePolicyRule,
    MissingPrefixListRule,
    UnusedRoutePolicyRule,
)
from netconfiglint.vendors.h3c.rules.routes import (
    AbnormalNextHopRule,
    MissingStaticRouteVpnRule,
    StaticRouteFormatRule,
)
from netconfiglint.vendors.h3c.rules.security import (
    H3COspfAuthenticationRule,
    H3COspfExposureRule,
    H3CSnmpCommunityRule,
    H3CVtyAuthenticationRule,
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
from netconfiglint.vendors.h3c.rules.traffic_policy import (
    MissingAppliedTrafficPolicyRule,
    MissingTrafficPolicyComponentRule,
)
from netconfiglint.vendors.h3c.rules.vlan import (
    MissingAccessVlanRule,
    MissingHybridVlanRule,
    MissingPvidVlanRule,
    MissingTrunkVlanRule,
)
from netconfiglint.vendors.h3c.rules.vpn import MissingBgpVpnRule, MissingInterfaceVpnRule

_COMWARE_RULES: tuple[Rule, ...] = (
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
)

H3C_RULES: tuple[Rule, ...] = (
    *_COMWARE_RULES,
    MissingBridgeAggregationRule(),
    AggregationModeEvidenceRule(),
    MissingVlanInterfaceVlanRule(),
    PlaintextPasswordRule(),
    LocalUserTelnetRule(),
    H3CSnmpCommunityRule(),
    H3CVtyInboundProtocolRule(),
    H3CVtyAuthenticationRule(),
    LegacyTlsVersionRule(),
    H3COspfExposureRule(),
    H3COspfAuthenticationRule(),
    H3COperationalEvidenceRule(),
    UnsupportedCommandSummaryRule(),
)
