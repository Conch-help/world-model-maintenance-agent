import unittest
import pandas as pd
from wm_maint.adapters.daypsci import validate_frame


class DAYPSCITest(unittest.TestCase):
    def test_valid_schema(self):
        df = pd.DataFrame({
            'timestamp': [0, 1, 2],
            'temperature': [20.0, 21.0, 22.0],
            'vibration': [0.1, 0.2, 0.3],
            'fault_active': [0, 0, 1],
        })
        result = validate_frame(df)
        self.assertTrue(result.valid)
        self.assertEqual(result.n_signals, 2)
        self.assertAlmostEqual(result.fault_rate, 1/3)

    def test_missing_label_fails_closed(self):
        df = pd.DataFrame({'timestamp': [0, 1], 'temperature': [20.0, 21.0], 'vibration': [0.1, 0.2]})
        result = validate_frame(df)
        self.assertFalse(result.valid)
        self.assertIn('missing fault label/active flag', result.reasons)


if __name__ == '__main__':
    unittest.main()
