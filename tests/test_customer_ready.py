import tempfile
import unittest
from pathlib import Path

from company_brain.connectors import NotionConnector
from company_brain.core.graph import BrainGraph
from company_brain.discovery import LLMDiscoveryEngine
from company_brain.memory.ingestion import MemoryIngestionService
from company_brain.product import DashboardService, EvidenceExplorerService, PeopleExplorerService, ProcessExplorerService
from company_brain.storage import (
    DiscoveryRepository,
    EdgeRepository,
    EntityRepository,
    EvidenceRepository,
    LLMDiscoveryRepository,
    SnapshotRepository,
    SourceSyncRepository,
)


class FakeProvider:
    name = "fake_llm"

    def available(self):
        return True

    def discover(self, record, evidence_id):
        return {
            "entities": [
                {"name": "Incident Review", "type": "process", "confidence": 0.91, "evidence": [evidence_id]},
                {"name": "Ops Team", "type": "team", "confidence": 0.89, "evidence": [evidence_id]},
                {"name": "PagerDuty", "type": "tool", "confidence": 0.88, "evidence": [evidence_id]},
            ],
            "relationships": [
                {
                    "source": "Ops Team",
                    "target": "Incident Review",
                    "relation": "owns",
                    "confidence": 0.86,
                    "evidence": [evidence_id],
                }
            ],
            "processes": [
                {
                    "name": "Incident Review",
                    "owner": "Ops Team",
                    "steps": ["open", "triage", "review", "close"],
                    "dependencies": [],
                    "tools": ["PagerDuty"],
                    "policies": [],
                    "exceptions": ["SLA breach"],
                    "confidence": 0.9,
                    "evidence": [evidence_id],
                }
            ],
            "policies": [],
        }


class CustomerReadyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def graph(self):
        return BrainGraph(
            EntityRepository(self.data_dir).list_entities(),
            EdgeRepository(self.data_dir).list_edges(),
            EvidenceRepository(self.data_dir).list_evidence(),
        )

    def test_llm_discovery_pipeline_persists_entities_relationships_and_evidence(self):
        service = MemoryIngestionService(self.data_dir)
        service.llm_discovery = LLMDiscoveryEngine(FakeProvider())

        result = service.ingest_record(
            {
                "source": "meeting_incidents",
                "content": "Ops owns incident review in PagerDuty.",
                "metadata": {"source_type": "meeting", "id": "meeting-1"},
            }
        )

        graph = self.graph()
        relations = {edge.relation for edge in graph.edges.values()}
        llm_results = LLMDiscoveryRepository(self.data_dir).list_results()

        self.assertTrue(result["llm_discovery"]["entities"])
        self.assertIn("process_incident_review", graph.entities)
        self.assertIn("team_ops_team", graph.entities)
        self.assertIn("owns", relations)
        self.assertEqual(llm_results[0]["provider"], "fake_llm")
        self.assertEqual(len(EvidenceRepository(self.data_dir).list_evidence()), 1)

    def test_notion_connector_syncs_payload_records_and_tracks_source_status(self):
        connector = NotionConnector(data_dir=self.data_dir)
        result = connector.sync(
            {
                "records": [
                    {
                        "id": "page-1",
                        "title": "Refund SOP",
                        "content": "Support process uses Notion. Finance approves refunds above $500.",
                    }
                ]
            }
        )

        sources = SourceSyncRepository(self.data_dir).list_sources()
        evidence = EvidenceRepository(self.data_dir).list_evidence()

        self.assertEqual(result["documents_processed"], 1)
        self.assertEqual(sources[0]["status"], "connected")
        self.assertEqual(evidence[0].source_type, "notion")
        self.assertGreater(result["knowledge_extracted"], 0)

    def test_customer_explorers_return_process_people_and_evidence_views(self):
        MemoryIngestionService(self.data_dir).ingest_record(
            {
                "source": "wiki",
                "content": "Finance approves refunds above $500. Refund process depends on Zendesk workflow.",
            }
        )
        graph = self.graph()
        processes = ProcessExplorerService(
            graph,
            DiscoveryRepository(self.data_dir).list_discoveries(),
            LLMDiscoveryRepository(self.data_dir).list_results(),
        ).build()
        evidence = EvidenceExplorerService(graph, LLMDiscoveryRepository(self.data_dir).list_results()).build()
        people = PeopleExplorerService(graph).build()

        self.assertTrue(processes["processes"])
        self.assertTrue(evidence["evidence"][0]["insights"])
        self.assertTrue(people["people_and_teams"])

    def test_dashboard_does_not_fabricate_trends_or_deltas(self):
        graph = BrainGraph()
        dashboard = DashboardService(graph, SnapshotRepository(self.data_dir).list_snapshots(), {}).build()

        self.assertIsNone(dashboard["kpis"]["knowledge_risk_score"]["delta"])
        self.assertFalse(dashboard["coverage_trend"]["available"])
        self.assertEqual(dashboard["coverage_trend"]["message"], "Insufficient historical data.")


if __name__ == "__main__":
    unittest.main()
