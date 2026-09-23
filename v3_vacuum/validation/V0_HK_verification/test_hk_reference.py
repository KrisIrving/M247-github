#!/usr/bin/env python3
import math
import unittest

import hk_reference as hk


class TestHKReference(unittest.TestCase):
    def setUp(self):
        self.P0 = 1e5
        self.Tb = 3186.0
        self.M = 0.060
        self.Lv = 6.3e6

    def test_psat_at_boiling_point_equals_reference_pressure(self):
        self.assertAlmostEqual(
            hk.psat_source(self.Tb, self.P0, self.Tb, self.M, self.Lv),
            self.P0,
            places=10,
        )

    def test_net_flux_is_zero_at_equilibrium(self):
        T = 2500.0
        p_eq = hk.psat_source(T, self.P0, self.Tb, self.M, self.Lv)
        flux = hk.hk_net_mass_flux_source(
            T, p_eq, self.P0, self.Tb, self.M, self.Lv
        )
        self.assertAlmostEqual(flux, 0.0, places=12)

    def test_tsat_inverts_psat_without_pressure_floor(self):
        for p in (1e5, 1e3, 10.0, 1.0, 0.6, 0.1):
            T = hk.tsat_source(
                p, self.P0, self.Tb, self.M, self.Lv, p_small_sat=0.0
            )
            recovered = hk.psat_source(T, self.P0, self.Tb, self.M, self.Lv)
            self.assertTrue(math.isclose(recovered, p, rel_tol=2e-12, abs_tol=1e-12))

    def test_upstream_one_pascal_floor_changes_point_six_pascal_tsat(self):
        no_floor = hk.tsat_source(
            0.6, self.P0, self.Tb, self.M, self.Lv, p_small_sat=0.0
        )
        upstream = hk.tsat_source(
            0.6, self.P0, self.Tb, self.M, self.Lv, p_small_sat=1.0
        )
        self.assertGreater(upstream, no_floor)
        self.assertAlmostEqual(upstream - no_floor, 34.259, delta=0.02)

    def test_argon_target_density(self):
        rho = hk.ideal_gas_density(0.6, 1343.15, 0.039948)
        self.assertAlmostEqual(rho, 2.1462859870811836e-6, delta=1e-15)


if __name__ == "__main__":
    unittest.main(verbosity=2)
