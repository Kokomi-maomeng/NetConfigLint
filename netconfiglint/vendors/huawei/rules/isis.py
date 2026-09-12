from __future__ import annotations

from netconfiglint.core.analyzer.control import checkpoint
from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity
from netconfiglint.rules import RuleContext, RuleMetadata
from netconfiglint.vendors.huawei.rules.helpers import missing_reference_diagnostic


def _process_id(header: str) -> str:
    tokens = header.split()
    return tokens[1] if len(tokens) > 1 and tokens[1].isdigit() else "1"


class MissingIsisProcessRule:
    metadata = RuleMetadata("HUA-ISIS-001", "Undefined IS-IS process", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        defined = {
            _process_id(block.header)
            for block in context.config.blocks
            if block.header.lower() == "isis" or block.header.lower().startswith("isis ")
        }
        result = []
        for interface in context.config.interfaces.values():
            checkpoint()
            for text, source in interface.raw_commands:
                checkpoint()
                tokens = text.lower().split()
                if tokens[:2] != ["isis", "enable"]:
                    continue
                process_id = tokens[2] if len(tokens) > 2 and tokens[2].isdigit() else "1"
                if process_id in defined:
                    continue
                result.append(
                    missing_reference_diagnostic(
                        context,
                        rule_id=self.metadata.rule_id,
                        source=source,
                        object_name=interface.name,
                        full_message=f"Interface references undefined IS-IS process {process_id}.",
                        snippet_message=f"IS-IS process {process_id} was not found in the snippet.",
                        explanation="The interface enables a process absent from the supplied configuration.",
                        suggested_fix=f"Define IS-IS process {process_id} or correct the interface binding.",
                    )
                )
        return tuple(result)


class MissingIsisNetworkEntityRule:
    metadata = RuleMetadata("HUA-ISIS-002", "IS-IS process without NET", Severity.ERROR, "Huawei")

    def evaluate(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        if context.mode.value == "snippet":
            return ()
        return tuple(
            Diagnostic(
                Severity.ERROR,
                self.metadata.rule_id,
                block.source,
                f"IS-IS {_process_id(block.header)}",
                f"IS-IS process {_process_id(block.header)} has no network-entity.",
                "A NET identifies the IS-IS area and local system ID; without it the process is incomplete.",
                "Configure a unique, design-approved network-entity in the IS-IS process.",
                Confidence.DOCUMENTED,
            )
            for block in context.config.blocks
            if (block.header.lower() == "isis" or block.header.lower().startswith("isis "))
            and not any(command.text.lower().startswith("network-entity ") for command in block.commands)
        )
