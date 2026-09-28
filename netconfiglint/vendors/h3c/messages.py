"""Comware-specific message hypotheses; no VRP message/CLI translation."""

from netconfiglint.core.analyzer.messages import EventDefinition
from netconfiglint.core.diagnostics import Severity

H3C_EVENTS: tuple[EventDefinition, ...] = (
    (
        r"(?:MAD|multi-active).{0,70}(?:recovery|split|faulty)",
        "MAD-RECOVERY",
        Severity.ERROR,
        "IRF multi-active detection event",
        "MAD may have placed a split IRF fabric in recovery and shut down service ports.",
        "Check display mad verbose, IRF links, member identity and surviving forwarding fabric.",
    ),
    (
        r"IRF.{0,70}(?:link|port).{0,35}(?:down|failed|inactive)|"
        r"IRF.{0,45}(?:split|merge failed)",
        "IRF-LINK",
        Severity.WARNING,
        "IRF link or fabric event",
        "An IRF link/fabric problem is reported. Possible causes include peer-port numbering, "
        "physical link, member ID and activation state.",
        "Compare display irf, display irf link, both members' IRF port bindings and physical link state.",
    ),
)
