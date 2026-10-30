import unittest

from wm_maint.adapters.plc_contract import InMemoryPLC, PLCCommandFrame, validate_command
from wm_maint.plant import MODE_DERATE, MODE_FULL, MODE_MAINTENANCE


class PLCContractTest(unittest.TestCase):
    def test_safe_command_is_accepted(self):
        plc = InMemoryPLC()
        result = plc.write(PLCCommandFrame([MODE_DERATE, MODE_FULL, MODE_MAINTENANCE], "A-1", "T-1"))
        self.assertTrue(result.accepted)
        self.assertIsNotNone(plc.last_command)

    def test_emergency_stop_blocks_command(self):
        plc = InMemoryPLC()
        plc.state.emergency_stop = True
        result = plc.write(PLCCommandFrame([MODE_FULL, MODE_FULL, MODE_FULL], "A-1", "T-1"))
        self.assertFalse(result.accepted)
        self.assertIn("emergency_stop_active", result.reasons)

    def test_missing_approval_is_rejected(self):
        plc = InMemoryPLC()
        result = plc.write(PLCCommandFrame([MODE_FULL], "", "T-1"))
        self.assertFalse(result.accepted)
        self.assertIn("approval_id_missing", result.reasons)


if __name__ == "__main__":
    unittest.main()
