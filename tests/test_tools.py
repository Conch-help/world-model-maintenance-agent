import unittest

import numpy as np

from wm_maint.plant import MODE_FULL
from wm_maint.tools import MaintenanceAgent, TraceLedger


class TraceLedgerTest(unittest.TestCase):
    def test_hash_chain_detects_tampering(self):
        ledger = TraceLedger()
        ledger.append("a", {"x": 1})
        ledger.append("b", {"x": 2})
        self.assertTrue(ledger.verify())
        ledger.events[0]["payload"]["x"] = 999
        self.assertFalse(ledger.verify())


class VerifiedPlanExecutionTest(unittest.TestCase):
    def test_full_plan_runs_in_strict_order(self):
        agent = MaintenanceAgent(seed=654)
        plan = agent.world_model_plan(horizon=12)
        verified = agent.highfidelity_verify(plan["plan_id"])
        self.assertTrue(verified["all_pass"])
        pending = agent.execute_verified_plan(plan["plan_id"], approved=False)
        self.assertEqual(pending["status"], "approval_required")
        result = agent.execute_verified_plan(plan["plan_id"], approved=True)
        self.assertEqual(result["status"], "executed_plan")
        self.assertEqual(result["executed_steps"], list(range(12)))
        self.assertEqual(len(result["results"]), 12)
        self.assertTrue(all(item["status"] == "executed" for item in result["results"]))
        self.assertIn("actual_vs_verified", result)
        self.assertEqual(result["actual_vs_verified"]["actual_failures"], result["total_failures"])
        self.assertGreaterEqual(result["actual_vs_verified"]["shield_adjustments"], 0)
        self.assertEqual(agent.calibration_status()["n_runs"], 1)
        self.assertTrue(agent.trace.verify())


class ApprovalGateTest(unittest.TestCase):
    def test_action_requires_verification_and_approval(self):
        agent = MaintenanceAgent(seed=321)
        plan = agent.world_model_plan(horizon=8)
        blocked = agent.request_maintenance_action(plan["plan_id"], 0, approved=False)
        self.assertEqual(blocked["status"], "approval_required")
        # A plan cannot execute before independent verification.
        blocked2 = agent.request_maintenance_action(plan["plan_id"], 0, approved=True)
        self.assertEqual(blocked2["status"], "blocked")
        verified = agent.highfidelity_verify(plan["plan_id"])
        self.assertTrue(verified["all_pass"])
        result = agent.request_maintenance_action(plan["plan_id"], 0, approved=True)
        self.assertEqual(result["status"], "executed")
        self.assertTrue(agent.trace.verify())


if __name__ == "__main__":
    unittest.main()
