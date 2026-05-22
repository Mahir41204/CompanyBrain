import tempfile
import unittest
from pathlib import Path

from company_brain.core.graph import BrainGraph
from company_brain.decision_engine import DecisionEngine
from company_brain.discovery import DiscoveryEngine
from company_brain.learning import LearningService
from company_brain.memory.ingestion import MemoryIngestionService
from company_brain.reasoning import ConflictDetector, OrganizationalSimulator
from company_brain.repository import SkillRepository
from company_brain.runtime import AgentRuntime
from company_brain.storage import EdgeRepository, EntityRepository, EvidenceRepository, SnapshotRepository


class DiscoveryReasoningRuntimeTest(unittest.TestCase):
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

    def test_discovery_extracts_structured_process_memory(self):
        discovery = DiscoveryEngine().discover(
            {
                "source": "slack",
                "content": (
                    "Finance approves refunds above $500. Use Zendesk workflow. "
                    "VIP customers skip review."
                ),
            },
            evidence_id="evidence_1",
        )

        self.assertEqual(discovery.process, "refund")
        self.assertEqual(discovery.owner, "Finance Team")
        self.assertEqual(discovery.tool, "Zendesk")
        self.assertIn("VIP customer", discovery.exceptions)
        self.assertEqual(discovery.policies["approval_threshold_usd"], 500)
        self.assertIn("review", discovery.steps)

    def test_temporal_snapshots_and_conflicts_capture_policy_drift(self):
        service = MemoryIngestionService(self.data_dir)
        service.ingest_record(
            {
                "source": "slack_refunds",
                "content": "Finance approves refunds above $500 in Zendesk.",
                "metadata": {"timestamp": "2025-01-01T00:00:00Z"},
            }
        )
        service.ingest_record(
            {
                "source": "wiki_refunds",
                "content": "Finance approves refunds above $700 in Zendesk.",
                "metadata": {"timestamp": "2026-01-01T00:00:00Z"},
            }
        )

        snapshots = SnapshotRepository(self.data_dir).list_snapshots("policy_refund_policy")
        conflicts = ConflictDetector().detect(snapshots)

        self.assertGreaterEqual(len(snapshots), 2)
        self.assertTrue(any(conflict.attribute == "approval_threshold_usd" for conflict in conflicts))

    def test_simulator_reports_breakage_when_person_leaves(self):
        MemoryIngestionService(self.data_dir).ingest_record(
            {
                "source": "meeting",
                "content": "Escalate enterprise refund cases to Sarah if SLA > 3 days. Use Zendesk.",
            }
        )

        result = OrganizationalSimulator(self.graph()).simulate_removal("Sarah")

        self.assertEqual(result["removed_entity"]["name"], "Sarah")
        self.assertTrue(result["replacement_needed"])
        self.assertTrue(result["affected_processes"])

    def test_agent_runtime_plans_executes_and_learns(self):
        repository = SkillRepository(self.data_dir)
        repository.save_skill(
            {
                "skill_id": "refund_decision",
                "version": "1.0.0",
                "description": "Refund policy",
                "confidence_score": 0.5,
                "decision_tree": [
                    {
                        "if": {"field": "customer_tier", "operator": "==", "value": "enterprise"},
                        "then": {"action": "approve_refund", "requires_approval": False},
                    }
                ],
            }
        )
        MemoryIngestionService(self.data_dir).ingest_record(
            {
                "source": "wiki",
                "content": "Enterprise refund policy uses Zendesk and requires finance approval.",
            },
            skill_id="refund_decision",
        )

        runtime = AgentRuntime(
            self.graph(),
            repository,
            DecisionEngine(),
            LearningService(repository),
        )
        task = runtime.run("refund policy", {"customer_tier": "enterprise"})
        learning = runtime.learn(task, "success")

        self.assertEqual(task.status, "completed")
        self.assertTrue(any(result["type"] == "skill_execution" for result in task.results))
        self.assertTrue(learning["feedback"])


if __name__ == "__main__":
    unittest.main()
