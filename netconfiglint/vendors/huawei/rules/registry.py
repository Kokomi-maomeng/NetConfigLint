from netconfiglint.rules import Rule
from netconfiglint.vendors.huawei.rules.bgp import BgpNetworkCandidateRule
from netconfiglint.vendors.huawei.rules.interface import (
    LinkTypeMismatchRule,
    MissingEthTrunkRule,
    ShutdownWithBusinessConfigRule,
)
from netconfiglint.vendors.huawei.rules.ospf import (
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
    StaticRouteFormatRule(),
    AbnormalNextHopRule(),
    MissingBgpRoutePolicyRule(),
    MissingPrefixListRule(),
    BgpNetworkCandidateRule(),
    OspfAreaAssociationRule(),
    OspfNoParticipatingInterfaceRule(),
    MissingAclRule(),
    UnusedRoutePolicyRule(),
    MissingInterfaceVpnRule(),
    MissingBgpVpnRule(),
    SensitiveConfigurationRule(),
)
