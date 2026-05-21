import tempfile
import unittest
from pathlib import Path

from company_brain.ingestion import IngestionService
from company_brain.learning import LearningService
from company_brain.repository import SkillRepository


class RepositoryLearningTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)
        self.repository = SkillRepository(self.data_dir)
        self.skill = {
            "skill_id": "supplier_approval",
            "version": "1.0.0",
            "description": "Supplier approval",
            "confidence_score": 0.5,
            "decision_tree": [
                {
                    "if": {"field": "iso_9001_certified", "operator": "==", "value": True},
                    "then": {"action": "auto_approve_supplier"},
                }
            ],
        }
        self.repository.save_skill(self.skill)

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_and_get_skill(self):
        loaded = self.repository.get_skill("supplier_approval")

        self.assertEqual(loaded["skill_id"], "supplier_approval")
        self.assertEqual(len(self.repository.list_skills()), 1)

    def test_learning_updates_confidence_and_logs_feedback(self):
        service = LearningService(self.repository)
        result = service.submit_outcome({"skill_id": "supplier_approval", "outcome": "success"})

        self.assertEqual(result["skill"]["confidence_score"], 0.55)
        self.assertEqual(len(self.repository.list_feedback()), 1)

    def test_ingestion_candidate_can_be_approved(self):
        ingestion = IngestionService(self.repository)
        result = ingestion.ingest(
            {
                "source": "slack",
                "content": "Approve suppliers with ISO certification and a passed audit.",
                "metadata": {"owner": "procurement_lead"},
            }
        )
        candidate_id = result["candidates"][0]["candidate_id"]
        promoted = self.repository.approve_candidate(candidate_id)

        self.assertTrue(promoted["skill_id"].startswith("procurement_candidate_"))
        self.assertEqual(self.repository.list_candidates()[0]["status"], "approved")


if __name__ == "__main__":
    unittest.main()
