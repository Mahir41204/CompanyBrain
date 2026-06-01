import tempfile
import unittest
from pathlib import Path

from company_brain.core.graph import BrainGraph
from company_brain.memory.health import MemoryHealth
from company_brain.memory.ingestion import MemoryIngestionService
from company_brain.reasoning import BrainQueryEngine, OrganizationalEvolution, OrganizationalSimulator
from company_brain.storage import EdgeRepository, EntityRepository, EvidenceRepository, SnapshotRepository


class QueryHealthEvolutionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def graph(self):
        return BrainGraph(
            entities=EntityRepository(self.data_dir).list_entities(),
            edges=EdgeRepository(self.data_dir).list_edges(),
            evidence=EvidenceRepository(self.data_dir).list_evidence(),
        )

    def test_query_engine_finds_owner_dependencies_affected_and_timeline(self):
        ingestion = MemoryIngestionService(self.data_dir)
        ingestion.ingest_record(
            {
                "source": "slack",
                "content": "Finance approves refunds above $500. Refund process depends on Zendesk workflow.",
                "metadata": {"timestamp": "2025-01-01T00:00:00Z"},
            },
            skill_id="refund_decision",
        )

        engine = BrainQueryEngine(self.graph(), SnapshotRepository(self.data_dir).list_snapshots())
        owner = engine.find_owner("refund policy")
        dependencies = engine.find_dependencies("refund process")
        affected = engine.find_affected("Zendesk")
        timeline = engine.timeline("policy_refund_policy")

        self.assertEqual(owner["owners"][0]["entity"]["name"], "Finance Team")
        self.assertTrue(any(row["entity"]["name"] == "Zendesk" for row in dependencies["dependencies"]))
        self.assertTrue(any(row["entity"]["name"] == "refund process" for row in affected["affected"]))
        self.assertTrue(timeline["timeline"])

    def test_memory_health_marks_old_memory_expired(self):
        ingestion = MemoryIngestionService(self.data_dir)
        ingestion.ingest_record(
            {
                "source": "wiki",
                "content": "Refund process uses Zendesk.",
                "metadata": {"timestamp": "2025-01-01T00:00:00Z"},
            }
        )

        health = MemoryHealth(
            EntityRepository(self.data_dir).list_entities(),
            EvidenceRepository(self.data_dir).list_evidence(),
            SnapshotRepository(self.data_dir).list_snapshots(),
        ).assess(as_of="2026-06-01T00:00:00Z", expired_after_days=365)

        self.assertGreater(health["summary"]["expired"], 0)
        self.assertTrue(all("decayed_confidence" in row for row in health["items"]))

    def test_evolution_explains_policy_threshold_change(self):
        ingestion = MemoryIngestionService(self.data_dir)
        ingestion.ingest_record(
            {
                "source": "slack",
                "content": "Finance approves refunds above $500 in Zendesk.",
                "metadata": {"timestamp": "2025-01-01T00:00:00Z"},
            }
        )
        ingestion.ingest_record(
            {
                "source": "wiki",
                "content": "Finance approves refunds above $700 in Zendesk.",
                "metadata": {"timestamp": "2026-01-01T00:00:00Z"},
            }
        )

        result = OrganizationalEvolution(
            self.graph(),
            SnapshotRepository(self.data_dir).list_snapshots(),
        ).timeline("policy_refund_policy")
        changed = [
            row for row in result["changes"]
            if "approval_threshold_usd" in row["diff"]["changed"]
        ]

        self.assertTrue(changed)
        self.assertIn("Approval routing", changed[0]["impact"][0])

    def test_simulator_propagates_transitive_dependency_impact(self):
        ingestion = MemoryIngestionService(self.data_dir)
        ingestion.ingest_record(
            {
                "source": "wiki",
                "content": (
                    "Finance approves refunds above $500. "
                    "Refund process depends on Zendesk workflow. "
                    "Enterprise customers skip review."
                ),
            },
            skill_id="refund_decision",
        )

        result = OrganizationalSimulator(self.graph()).simulate_removal("Zendesk")

        self.assertGreater(result["blast_radius"]["transitive_affected"], 1)
        self.assertTrue(result["affected_processes"])
        self.assertTrue(result["affected_policies"])


if __name__ == "__main__":
    unittest.main()
