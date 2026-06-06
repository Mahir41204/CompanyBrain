import unittest

from company_brain.core.edges import Edge
from company_brain.core.entities import Entity, EntityType
from company_brain.core.evidence import Evidence
from company_brain.core.graph import BrainGraph
from company_brain.product import PeopleRiskService


class PeopleRiskMVPTest(unittest.TestCase):
    def test_people_risk_packages_departure_simulation_with_evidence(self):
        evidence = Evidence(
            id="evidence_support",
            source_type="slack",
            source_ref="support/escalations",
            text="Sarah Kim owns refund escalation and Maya Rao is the backup candidate.",
            timestamp="2026-05-29",
            confidence=0.9,
        )
        graph = BrainGraph(
            entities=[
                Entity(
                    id="person_sarah_kim",
                    type=EntityType.PERSON,
                    name="Sarah Kim",
                    attributes={"role": "Head of Support"},
                    confidence=0.91,
                    sources=[evidence.id],
                ),
                Entity(
                    id="person_maya_rao",
                    type=EntityType.PERSON,
                    name="Maya Rao",
                    attributes={"role": "Support Ops Lead"},
                    confidence=0.78,
                    sources=[evidence.id],
                ),
                Entity(
                    id="process_refund_process",
                    type=EntityType.PROCESS,
                    name="refund process",
                    confidence=0.88,
                    sources=[evidence.id],
                ),
                Entity(
                    id="tool_zendesk",
                    type=EntityType.TOOL,
                    name="Zendesk",
                    confidence=0.9,
                    sources=[evidence.id],
                ),
            ],
            edges=[
                Edge(
                    source_id="person_sarah_kim",
                    target_id="process_refund_process",
                    relation="owns",
                    confidence=0.9,
                    evidence=[evidence.id],
                ),
                Edge(
                    source_id="process_refund_process",
                    target_id="tool_zendesk",
                    relation="uses",
                    confidence=0.88,
                    evidence=[evidence.id],
                ),
                Edge(
                    source_id="person_maya_rao",
                    target_id="person_sarah_kim",
                    relation="backs_up",
                    confidence=0.72,
                    evidence=[evidence.id],
                ),
            ],
            evidence=[evidence],
        )

        result = PeopleRiskService(graph).build("Sarah")

        self.assertEqual(result["positioning"]["category"], "People Risk Intelligence")
        self.assertEqual(result["selected_person"]["name"], "Sarah Kim")
        self.assertEqual(result["selected_person"]["controlled_processes"][0]["name"], "refund process")
        self.assertTrue(result["departure_simulation"]["affected"]["processes"])
        self.assertTrue(result["proof_points"])
        self.assertIn("Maya Rao", result["selected_person"]["backup_status"])


if __name__ == "__main__":
    unittest.main()
