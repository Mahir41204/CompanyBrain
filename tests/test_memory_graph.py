import tempfile
import unittest
from pathlib import Path

from company_brain.core.graph import BrainGraph
from company_brain.execution.planner import ExecutionPlanner
from company_brain.memory.event_store import Event
from company_brain.memory.ingestion import MemoryIngestionService
from company_brain.memory.process_mining import discover_flow
from company_brain.storage import EdgeRepository, EntityRepository, EvidenceRepository


class MemoryGraphTest(unittest.TestCase):
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

    def test_ingestion_extracts_entities_edges_and_evidence(self):
        service = MemoryIngestionService(self.data_dir)
        result = service.ingest_record(
            {
                "source": "slack_thread_refunds",
                "content": (
                    "Enterprise refunds above $500 require finance approval. "
                    "Handled in Zendesk. Escalate to Sarah if SLA > 3 days."
                ),
                "metadata": {"id": "thread-1", "source_type": "slack"},
            },
            skill_id="refund_enterprise",
        )

        entity_names = {entity["name"].lower() for entity in result["entities"]}
        relations = {edge["relation"] for edge in result["edges"]}

        self.assertIn("refund process", entity_names)
        self.assertIn("Zendesk".lower(), entity_names)
        self.assertIn("Sarah".lower(), entity_names)
        self.assertIn("Finance Team".lower(), entity_names)
        self.assertIn("uses", relations)
        self.assertIn("requires_approval", relations)
        self.assertIn("implements", relations)
        self.assertEqual(len(EvidenceRepository(self.data_dir).list_evidence()), 1)

    def test_graph_explain_and_plan_use_relationships(self):
        service = MemoryIngestionService(self.data_dir)
        service.ingest_record(
            {
                "source": "wiki_refunds",
                "content": "Refund process uses Zendesk and requires finance approval for enterprise exceptions.",
            },
            skill_id="refund_decision",
        )

        graph = self.graph()
        explanation = graph.explain("refund process")
        plan = ExecutionPlanner(graph).build_plan("refund process")
        actions = [step["action"] for step in plan["steps"]]

        self.assertEqual(explanation["matched_entity"]["id"], "process_refund_process")
        self.assertIn("uses", explanation["relations"])
        self.assertIn("requires_approval", explanation["relations"])
        self.assertIn("open_tool", actions)
        self.assertIn("notify_approver", actions)
        self.assertIn("attach_evidence", actions)

    def test_process_mining_discovers_transitions(self):
        events = [
            Event("2026-05-21T10:00:00Z", "agent", "refund_opened", "ticket_1"),
            Event("2026-05-21T10:05:00Z", "finance", "finance_review", "ticket_1"),
            Event("2026-05-21T10:10:00Z", "finance", "approval", "ticket_1"),
            Event("2026-05-21T10:12:00Z", "agent", "payout", "ticket_1"),
        ]

        flow = discover_flow(events)
        transitions = {(row["from"], row["to"]): row["count"] for row in flow["transitions"]}

        self.assertEqual(transitions[("refund_opened", "finance_review")], 1)
        self.assertEqual(transitions[("finance_review", "approval")], 1)
        self.assertEqual(flow["objects_observed"], 1)


if __name__ == "__main__":
    unittest.main()
