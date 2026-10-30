import tempfile
import unittest
from pathlib import Path

import numpy as np

from wm_maint.data import collect_transitions
from wm_maint.world_model import EnsembleWorldModel


class WorldModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = collect_transitions(n_episodes=4, episode_hours=8, seed=123)

    def test_fit_predict_and_roundtrip(self):
        model = EnsembleWorldModel(3, ensemble_size=2, hidden=8, seed=123)
        model.fit(
            self.data.states,
            self.data.actions,
            self.data.next_states,
            self.data.profits,
            self.data.productions,
            epochs=2,
            batch_size=32,
        )
        state, profit, unc = model.predict_step(self.data.states[0], np.array([2, 2, 2]))
        self.assertEqual(state.shape, self.data.states[0].shape)
        self.assertTrue(np.isfinite(profit))
        self.assertGreaterEqual(unc, 0.0)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "m.npz"
            model.save(path)
            loaded = EnsembleWorldModel.load(path)
            np.testing.assert_allclose(model.predict_step(self.data.states[0], np.array([2, 2, 2]))[0], loaded.predict_step(self.data.states[0], np.array([2, 2, 2]))[0], rtol=1e-10, atol=1e-10)


if __name__ == "__main__":
    unittest.main()
