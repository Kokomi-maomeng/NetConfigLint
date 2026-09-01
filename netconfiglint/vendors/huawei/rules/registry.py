from netconfiglint.rules import Rule
from netconfiglint.vendors.huawei.rules.advanced_policy import (
    BroadPermitAclRule,
    EmptyReferencedAclRule,
    MissingRedistributionPolicyRule,
)
from netconfiglint.vendors.huawei.rules.bgp import (
    BgpNetworkCandidateRule,
    BgpPeerOperationalStateRule,
    MissingBgpPeerGroupRule,
    MissingBgpPeerRemoteAsRule,
)
from netconfiglint.vendors.huawei.rules.evpn import (
    DuplicateBridgeDomainVniRule,
    InvalidVniRule,
    MissingEvpnVniDefinitionRule,
)
from netconfiglint.vendors.huawei.rules.interface import (
    InvalidInterfaceAddressRule,
    LinkTypeMismatchRule,
    MissingEthTrunkRule,
    MissingVlanifVlanRule,
    OperationalInterfaceDownRule,
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
    LocalUserTelnetRule,
    PlaintextPasswordRule,
    SensitiveConfigurationRule,
    SnmpCommunityRule,
    SshAllInterfacesRule,
    TelnetServerRule,
    UnauthenticatedNtpRule,
    VtyInboundProtocolRule,
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
    UnusedVlanRule,
)
from netconfiglint.vendors.huawei.rules.vpn import MissingBgpVpnRule, MissingInterfaceVpnRule

HUAWEI_RULES: tuple[Rule, ...] = (
    MissingTrunkVlanRule(),
    MissingAccessVlanRule(),
    MissingHybridVlanRule(),
    MissingPvidVlanRule(),
    UnusedVlanRule(),
    ShutdownWithBusinessConfigRule(),
    LinkTypeMismatchRule(),
    MissingEthTrunkRule(),
    InvalidInterfaceAddressRule(),
    MissingVlanifVlanRule(),
    OperationalInterfaceDownRule(),
    IPv6StaticRouteFormatRule(),
    IPv6InterfaceAddressRule(),
    StaticRouteFormatRule(),
    AbnormalNextHopRule(),
    MissingStaticRouteVpnRule(),
    MissingBgpRoutePolicyRule(),
    MissingPrefixListRule(),
    BgpNetworkCandidateRule(),
    BgpPeerOperationalStateRule(),
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
    InvalidVniRule(),
    MissingEvpnVniDefinitionRule(),
    DuplicateBridgeDomainVniRule(),
    MissingBpduProtectionRule(),
    SensitiveConfigurationRule(),
    TelnetServerRule(),
    FtpServerRule(),
    PlaintextPasswordRule(),
    SnmpCommunityRule(),
    UnauthenticatedNtpRule(),
    SshAllInterfacesRule(),
    LocalUserTelnetRule(),
    VtyInboundProtocolRule(),
    VtyPasswordAuthenticationRule(),
)
