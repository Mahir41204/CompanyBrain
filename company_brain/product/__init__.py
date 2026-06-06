"""Product-facing API aggregators for the Company Brain UI."""

from .dashboard import DashboardService
from .coverage_view import CoverageViewService
from .evidence_explorer import EvidenceExplorerService
from .graph_view import GraphViewService
from .people_explorer import PeopleExplorerService
from .people_risk import PeopleRiskService
from .process_explorer import ProcessExplorerService
from .risk_center import RiskCenterService
from .simulation import SimulationService
from .source_dashboard import SourceDashboardService

__all__ = [
    "CoverageViewService",
    "DashboardService",
    "EvidenceExplorerService",
    "GraphViewService",
    "PeopleExplorerService",
    "PeopleRiskService",
    "ProcessExplorerService",
    "RiskCenterService",
    "SimulationService",
    "SourceDashboardService",
]
