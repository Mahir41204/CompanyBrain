import unittest

from company_brain.decision_engine import DecisionEngine


class DecisionEngineTest(unittest.TestCase):
    def setUp(self):
        self.engine = DecisionEngine()
        self.skill = {
            "skill_id": "refund_decision",
            "version": "1.0.0",
            "confidence_score": 0.84,
            "description": "Refund policy",
            "inputs": [
                {"name": "customer_tier", "required": True},
                {"name": "days_since_purchase", "required": True},
                {"name": "previous_refund_requests", "required": True},
            ],
            "decision_tree": [
                {
                    "if": {
                        "all": [
                            {"field": "customer_tier", "operator": "==", "value": "enterprise"},
                            {"field": "days_since_purchase", "operator": "<=", "value": 90},
                            {"field": "previous_refund_requests", "operator": "==", "value": 0},
                        ]
                    },
                    "then": {"action": "approve_refund", "requires_approval": False},
                    "reasoning": "Enterprise first request within grace period.",
                },
                {
                    "else": {"action": "escalate", "requires_approval": True},
                    "reasoning": "No approval rule matched.",
                },
            ],
        }

    def test_executes_matching_rule(self):
        result = self.engine.execute(
            self.skill,
            {
                "customer_tier": "enterprise",
                "days_since_purchase": 75,
                "previous_refund_requests": 0,
            },
        )

        self.assertEqual(result["action"], "approve_refund")
        self.assertFalse(result["requires_approval"])
        self.assertEqual(result["matched_rule_index"], 0)

    def test_uses_fallback(self):
        result = self.engine.execute(
            self.skill,
            {
                "customer_tier": "startup",
                "days_since_purchase": 75,
                "previous_refund_requests": 0,
            },
        )

        self.assertEqual(result["action"], "escalate")
        self.assertTrue(result["requires_approval"])
        self.assertEqual(result["matched_rule_index"], 1)

    def test_missing_required_inputs_lower_confidence(self):
        result = self.engine.execute(self.skill, {"customer_tier": "enterprise"})

        self.assertEqual(result["action"], "escalate")
        self.assertLessEqual(result["confidence"], 0.4)
        self.assertEqual(result["missing_inputs"], ["days_since_purchase", "previous_refund_requests"])

    def test_supports_any_and_between(self):
        condition = {
            "any": [
                {"field": "risk", "operator": "in", "value": ["high", "critical"]},
                {"field": "score", "operator": "between", "value": [80, 100]},
            ]
        }

        self.assertTrue(self.engine.evaluate(condition, {"risk": "low", "score": 91}))
        self.assertFalse(self.engine.evaluate(condition, {"risk": "low", "score": 60}))


if __name__ == "__main__":
    unittest.main()
