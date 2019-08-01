import numpy
from mpi4py import MPI
import unittest
from pauxy.systems.hubbard import Hubbard
from pauxy.trial_density_matrices.onebody import OneBody
from pauxy.thermal_propagation.hubbard import ThermalDiscrete
from pauxy.walkers.thermal import ThermalWalker
from pauxy.utils.misc import dotdict, update_stack

class TestThermalHubbard(unittest.TestCase):

    def test_hubbard(self):
        options = {'nx': 4, 'ny': 4, 'U': 4, 'mu': 1.0, 'nup': 7, 'ndown': 7}
        system = Hubbard(options, verbose=True)
        comm = MPI.COMM_WORLD
        beta = 2.0
        dt = 0.05
        nslice = int(round(beta/dt))
        try:
            trial = OneBody(comm, {}, system, beta, dt)
        except TypeError:
            trial = OneBody({}, system, beta, dt)
        numpy.random.seed(7)
        qmc = dotdict({'dt': dt, 'nstblz': 10})
        prop = ThermalDiscrete({}, qmc, system, trial, verbose=True)
        walker1 = ThermalWalker({'stack_size': 1}, system, trial, verbose=True)
        for ts in range(0,nslice):
            prop.propagate_walker(system, walker1, ts, 0)
            walker1.weight /= 1.0e6
        numpy.random.seed(7)
        walker2 = ThermalWalker({'stack_size': 10}, system, trial, verbose=True)
        energies = []
        for ts in range(0,nslice):
            prop.propagate_walker(system, walker2, ts, 0)
            walker2.weight /= 1.0e6
            # if ts % 10 == 0:
                # energies.append(walker2.local_energy(system)[0])
        # import matplotlib.pyplot as pl
        # pl.plot(energies, markersize=2)
        # pl.show()
        self.assertAlmostEqual(walker1.weight,walker2.weight)
        self.assertAlmostEqual(numpy.linalg.norm(walker1.G-walker2.G),0.0)
        self.assertAlmostEqual(walker1.local_energy(system)[0],
                               walker2.local_energy(system)[0])

    def test_propagate_walker(self):
        options = {'nx': 4, 'ny': 4, 'U': 4, 'mu': 1.0, 'nup': 7, 'ndown': 7}
        system = Hubbard(options, verbose=True)
        comm = MPI.COMM_WORLD
        beta = 2.0
        dt = 0.05
        nslice = int(round(beta/dt))
        try:
            # trial = OneBody(comm, {'mu': 1.0}, system, beta, dt)
            trial = OneBody(comm, {}, system, beta, dt)
        except TypeError:
            # trial = OneBody({'mu': 1.0}, system, beta, dt)
            trial = OneBody({}, system, beta, dt)
        numpy.random.seed(7)
        qmc = dotdict({'dt': dt, 'nstblz': 1})
        prop = ThermalDiscrete({}, qmc, system, trial, verbose=True)
        walker1 = ThermalWalker({'stack_size': 1}, system, trial, verbose=True)
        walker2 = ThermalWalker({'stack_size': 1}, system, trial, verbose=True)
        rands = numpy.random.random(system.nbasis)
        I = numpy.eye(system.nbasis)
        BV = numpy.zeros((2,system.nbasis))
        BV[0] = 1.0
        BV[1] = 1.0
        walker2.greens_function(trial, slice_ix=0)
        walker1.greens_function(trial, slice_ix=0)
        for it in range(0,nslice):
            rands = numpy.random.random(system.nbasis)
            BV = numpy.zeros((2,system.nbasis))
            BV[0] = 1.0
            BV[1] = 1.0
            for i in range(system.nbasis):
                if rands[i] > 0.5:
                    xi = 0
                else:
                    xi = 1
                BV[0,i] = prop.auxf[xi,0]
                BV[1,i] = prop.auxf[xi,1]
                # Check overlap ratio
                if it % 20 == 0:
                    probs1 = prop.calculate_overlap_ratio(walker1,i)
                    G2old = walker2.greens_function(trial, slice_ix=it, inplace=False)
                    B = numpy.einsum('ki,kij->kij', BV, prop.BH1)
                    walker2.stack.stack[it] = B
                    walker2.greens_function(trial, slice_ix=it)
                    G2 = walker2.G
                    pdirect = numpy.linalg.det(G2old[0])/numpy.linalg.det(G2[0])
                    pdirect *= 0.5*numpy.linalg.det(G2old[1])/numpy.linalg.det(G2[1])
                    self.assertAlmostEqual(pdirect,probs1[xi])
                prop.update_greens_function(walker1, i, xi)
            B = numpy.einsum('ki,kij->kij', BV, prop.BH1)
            walker1.stack.update(B)
            if it % prop.nstblz == 0:
                walker1.greens_function(None,
                                        walker1.stack.time_slice-1)
            walker2.stack.stack[it] = B
            walker2.greens_function(trial, slice_ix=it)
            self.assertAlmostEqual(numpy.linalg.norm(walker1.G-walker2.G),0.0)
            prop.propagate_greens_function(walker1)

if __name__ == '__main__':
    unittest.main()