from netconfiglint.rules import Rule
from netconfiglint.vendors.huawei.rules.bgp import (
    BgpNetworkCandidateRule,
    BgpPeerOperationalStateRule,
    MissingBgpPeerGroupRule,
)
from netconfiglint.vendors.huawei.rules.interface import (
    LinkTypeMismatchRule,
    MissingEthTrunkRule,
    OperationalInterfaceDownRule,
    ShutdownWithBusinessConfigRule,
)
from netconfiglint.vendors.huawei.rules.ipv6 import IPv6InterfaceAddressRule, IPv6StaticRouteFormatRule
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
from netconfiglint.vendors.huawei.rules.routes import AbnormalNextHopRule, StaticRouteFormatRule
from netconfiglint.vendors.huawei.rules.security import SensitiveConfigurationRule
from netconfiglint.vendors.huawei.rules.traffic_policy import (
    MissingAppliedTrafficPolicyRule,
    MissingTrafficPolicyComponentRule,
)
from netconfiglint.vendors.huawei.rules.vlan import (
    MissingAccessVlanRule,
    MissingTrunkVlanRule,
    UnusedVlanRule,
)
from netconfiglint.vendors.huawei.rules.vpn import MissingBgpVpnRule, MissingInterfaceVpnRule

HUAWEI_RULES: tuple[Rule, ...] = (
    MissingTrunkVlanRule(),
    MissingAccessVlanRule(),
    UnusedVlanRule(),
    ShutdownWithBusinessConfigRule(),
    LinkTypeMismatchRule(),
    MissingEthTrunkRule(),
    OperationalInterfaceDownRule(),
    IPv6StaticRouteFormatRule(),
    IPv6InterfaceAddressRule(),
    StaticRouteFormatRule(),
    AbnormalNextHopRule(),
    MissingBgpRoutePolicyRule(),
    MissingPrefixListRule(),
    BgpNetworkCandidateRule(),
    BgpPeerOperationalStateRule(),
    MissingBgpPeerGroupRule(),
    OspfAreaAssociationRule(),
    OspfNoParticipatingInterfaceRule(),
    MissingInterfaceOspfProcessRule(),
    MissingAclRule(),
    UnusedRoutePolicyRule(),
    MissingInterfaceVpnRule(),
    MissingBgpVpnRule(),
    MissingTrafficPolicyComponentRule(),
    MissingAppliedTrafficPolicyRule(),
    SensitiveConfigurationRule(),
)
