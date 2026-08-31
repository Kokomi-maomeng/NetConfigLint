from PySide6.QtCore import QModelIndex

from netconfiglint.core.diagnostics import Confidence, Diagnostic, Severity, SourceRange
from netconfiglint.gui.models import DiagnosticListModel
from netconfiglint.gui.models.diagnostics import DiagnosticRole


def test_analysis_result_maps_to_qml_roles() -> None:
    model = DiagnosticListModel()
    model.replace(
        (
            Diagnostic(
                Severity.WARNING,
                "HUA-TEST-001",
                SourceRange(14, 16),
                "GigabitEthernet1/0/1",
                "message",
                "explanation",
                "fix",
                Confidence.GENERIC,
            ),
        )
    )
    index = model.index(0, 0, QModelIndex())

    assert model.data(index, DiagnosticRole.SEVERITY) == "WARNING"
    assert model.data(index, DiagnosticRole.LINE) == 14
    assert model.data(index, DiagnosticRole.END_LINE) == 16
    assert model.data(index, DiagnosticRole.RULE_ID) == "HUA-TEST-001"
    assert model.data(index, DiagnosticRole.CONFIDENCE) == "GENERIC"


def test_invalid_model_index_returns_none() -> None:
    assert DiagnosticListModel().data(QModelIndex(), DiagnosticRole.LINE) is None
