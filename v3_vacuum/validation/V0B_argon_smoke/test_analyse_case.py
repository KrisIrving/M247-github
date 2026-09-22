import tempfile
import unittest
from pathlib import Path
from analyse_case import analyse, field_values, RHO_TARGET


class TestSmokeAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.case = Path(self.tmp.name)
        (self.case/'system').mkdir()
        (self.case/'constant').mkdir()
        (self.case/'system/controlDict').write_text('endTime 2e-8;')
        (self.case/'constant/thermophysicalProperties').write_text('pMin 0.06;')
        (self.case/'2e-08').mkdir()
        for name, value in {'p': 0.6, 'p_rgh': 0.6, 'rho': RHO_TARGET,
                            'T': 1343.15, 'alpha.air': 1, 'alpha.metal1': 0,
                            'alpha.metal1vapour': 0}.items():
            (self.case/'2e-08'/name).write_text(f'class volScalarField; internalField uniform {value};')
        (self.case/'2e-08/U').write_text('class volVectorField; internalField uniform (0 0 0);')
        (self.case/'log.compressibleLaserbeamFoam').write_text(
            'sigFpe : Enabling floating point exception trapping (FOAM_SIGFPE).\n'
            'Floating point exception trapping enabled (FOAM_SIGFPE).\n'
            'deltaT = 1e-10\nTime = 2e-08\nEnd\n')

    def test_completed_stationary_fields_pass(self):
        self.assertEqual(analyse(self.case)['status'], 'PASS')

    def test_partial_run_is_not_a_pass(self):
        (self.case/'log.compressibleLaserbeamFoam').write_text('Time = 1e-08\nEnd\n')
        self.assertEqual(analyse(self.case)['status'], 'FAIL')

    def test_nonuniform_pressure_floor_is_detected(self):
        (self.case/'2e-08/p').write_text('class volScalarField; internalField nonuniform List<scalar> 2 (0.6 1);')
        self.assertEqual(analyse(self.case)['status'], 'FAIL')

    def test_missing_density_is_not_replaced_with_ideal_gas(self):
        (self.case/'2e-08/rho').unlink()
        self.assertEqual(analyse(self.case)['status'], 'FAIL')

    def test_fatal_error_overrides_end_marker(self):
        with (self.case/'log.compressibleLaserbeamFoam').open('a') as f:
            f.write('Floating point exception (core dumped)\n')
        self.assertEqual(analyse(self.case)['status'], 'FAIL')

    def test_vector_magnitudes_and_components(self):
        p = self.case/'2e-08/U'
        p.write_text('class volVectorField; internalField nonuniform List<vector> 2 ((3 4 0) (0 0 0));')
        self.assertEqual(field_values(p), [5, 0])
        self.assertEqual(field_values(p, magnitude=False), [3, 4, 0, 0, 0, 0])

    def test_nonfinite_field_rejected(self):
        p = self.case/'2e-08/rho'
        p.write_text('class volScalarField; internalField uniform nan;')
        self.assertEqual(analyse(self.case)['status'], 'FAIL')


if __name__ == '__main__':
    unittest.main()
