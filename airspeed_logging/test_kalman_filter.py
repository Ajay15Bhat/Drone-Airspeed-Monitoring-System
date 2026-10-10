import unittest
from kalman_filter import filter_pressure


class PressureKalmanTests(unittest.TestCase):
    def test_constant_and_negative_preserved(self):
        self.assertEqual(filter_pressure([0, 1, 2], [-2, -2, -2]), [-2, -2, -2])

    def test_known_update(self):
        self.assertEqual(filter_pressure([0, 1], [0, 10], 0, 1), [0, 5])
        self.assertAlmostEqual(filter_pressure([0, 2], [0, 10], 1, 1)[1], 7.5)

    def test_causal(self):
        self.assertEqual(filter_pressure([0, 1, 2], [0, 10, 20])[:2],
                         filter_pressure([0, 1], [0, 10]))

    def test_step_response(self):
        out = filter_pressure(range(200), [0] + [10] * 199)
        self.assertTrue(all(0 <= x <= 10 for x in out))
        self.assertAlmostEqual(out[-1], 10, places=6)

    def test_invalid_inputs(self):
        for t, p in [([0, 0], [1, 2]), ([1, 0], [1, 2]),
                     ([0], [float('nan')]), ([0], [])]:
            with self.assertRaises(ValueError):
                filter_pressure(t, p)
        for q, r in [(-1, 1), (1, 0), (1, float('inf'))]:
            with self.assertRaises(ValueError):
                filter_pressure([0], [1], q, r)

    def test_empty(self):
        self.assertEqual(filter_pressure([], []), [])


if __name__ == '__main__':
    unittest.main()
