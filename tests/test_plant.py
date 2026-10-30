import unittest
import numpy as np

from wm_maint.plant import MODE_FULL, MODE_MAINTENANCE, ProductionPlant


class PlantTest(unittest.TestCase):
    def test_reset_is_reproducible(self):
        a = ProductionPlant(seed=7, episode_hours=24)
        b = ProductionPlant(seed=7, episode_hours=24)
        np.testing.assert_allclose(a.observation(), b.observation())
        np.testing.assert_allclose(a.state.health, b.state.health)

    def test_maintenance_starts_and_restores_health(self):
        p = ProductionPlant(seed=7, episode_hours=24)
        p.state.health[:] = 0.4
        _, _, _, info = p.step([MODE_MAINTENANCE, MODE_FULL, MODE_FULL])
        self.assertEqual(info.maintenances, 1)
        self.assertEqual(p.state.maintenance_remaining[0], 2.0)
        p.step([MODE_MAINTENANCE, MODE_FULL, MODE_FULL])
        p.step([MODE_MAINTENANCE, MODE_FULL, MODE_FULL])
        self.assertAlmostEqual(float(p.state.health[0]), 1.0, places=7)

    def test_action_shape_is_validated(self):
        p = ProductionPlant(seed=1, episode_hours=2)
        with self.assertRaises(ValueError):
            p.step([MODE_FULL])


if __name__ == "__main__":
    unittest.main()
