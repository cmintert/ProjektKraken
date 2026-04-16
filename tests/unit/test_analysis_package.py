"""Tests for the analysis package structure and imports.

Verifies that the analysis widget package is properly organized and
all public/private imports work correctly after the refactor to
src/gui/widgets/analysis/.
"""



def test_package_import() -> None:
    """Verify that MainAnalysisPanel can be imported via the package __init__."""
    from src.gui.widgets.analysis import MainAnalysisPanel

    assert MainAnalysisPanel is not None


def test_submodule_imports() -> None:
    """Verify that all analysis submodules can be imported directly."""
    from src.gui.widgets.analysis._analysis_utils import make_analysis_table
    from src.gui.widgets.analysis.analysis_panel import AnalysisPanel
    from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel
    from src.gui.widgets.analysis.temporal_panel import TemporalPanel

    assert all(
        x is not None
        for x in [AnalysisPanel, IntelligencePanel, TemporalPanel, make_analysis_table]
    )


def test_main_analysis_panel_instantiation() -> None:
    """Verify MainAnalysisPanel can be instantiated after the move."""
    from src.gui.widgets.analysis import MainAnalysisPanel

    panel = MainAnalysisPanel()
    assert panel is not None
    assert hasattr(panel, "validation_panel")
    assert hasattr(panel, "temporal_panel")
    assert hasattr(panel, "intelligence_panel")
