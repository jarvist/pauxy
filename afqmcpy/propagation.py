'''Routines for performing propagation of a walker'''

import random
import numpy
import scipy.linalg
import afqmcpy.utils as utils
import afqmcpy.estimators as estimators
from cmath import exp, phase, sqrt


def discrete_hubbard(walker, state):
    '''Propagate by potential term using discrete HS transform.

Parameters
----------
walker : :class:`Walker`
    Walker object to be updated. On output we have acted on |phi_i> by B_V and
    updated the weight appropriately. Updates inplace.
auxf : :class:`numpy.ndarray`
    Possible values of the exponential discrete auxilliary fields.
nbasis : int
    Number of single-particle basis functions (2M for spin).
trial : :class:`numpy.ndarray`
    Trial wavefunction.
'''
    # Construct random auxilliary field.
    delta = state.auxf - 1
    for i in range(0, state.system.nbasis):
        # Ratio of determinants for the two choices of auxilliary fields
        probs = 0.5 * numpy.array([(1+delta[0][0]*walker.G[0][i,i])*(1+delta[0][1]*walker.G[1][i,i]),
                                (1+delta[1][0]*walker.G[0][i,i])*(1+delta[1][1]*walker.G[1][i,i])])
        norm = sum(probs)
        walker.weight = walker.weight * norm
        r = random.random()
        # Is this necessary?
        if walker.weight > 0:
            if r < probs[0]/norm:
                vtup = walker.phi[0][i,:] * delta[0, 0]
                vtdown = walker.phi[1][i,:] * delta[0, 1]
                walker.phi[0][i,:] = walker.phi[0][i,:] + vtup
                walker.phi[1][i,:] = walker.phi[1][i,:] + vtdown
                walker.ot = 2 * walker.ot * probs[0]
            else:
                vtup = walker.phi[0][i,:] * delta[1, 0]
                vtdown = walker.phi[1][i,:] * delta[1, 1]
                walker.phi[0][i,:] = walker.phi[0][i,:] + vtup
                walker.phi[1][i,:] = walker.phi[1][i,:] + vtdown
                walker.ot = 2 * walker.ot * probs[1]
        walker.inv_ovlp[0] = utils.sherman_morrison(walker.inv_ovlp[0],
                                                    state.psi_trial[0].T[:,i],
                                                    vtup)
        walker.inv_ovlp[1] = utils.sherman_morrison(walker.inv_ovlp[1],
                                                    state.psi_trial[1].T[:,i],
                                                    vtdown)
        walker.greens_function(state.psi_trial)


def continuous_hubbard(walker, state):
    '''Continuous Hubbard-Statonovich transformation for Hubbard model.

    Only requires M auxiliary fields.

Parameters
----------
walker : :class:`walker.Walker`
    Walker object to be updated. On output we have acted on |phi_i> by B_V and
    updated the weight appropriately. Updates inplace.
state : :class:`state.State`
    Simulation state.
'''
    for i in range(0, state.system.nbasis):
        # For convenience..
        x_i = sqrt((-2.0*state.system.U*state.dt)) * numpy.random.normal(0.0, 1.0)
        delta = exp(x_i) - 1
        # Check speed here with numpy
        if walker.weight > 0:
            vtup = walker.phi[0][i,:] * delta
            vtdown = walker.phi[1][i,:] * delta
            walker.phi[0][i,:] = walker.phi[0][i,:] + vtup
            walker.phi[1][i,:] = walker.phi[1][i,:] + vtdown
            walker.inv_ovlp[0] = utils.sherman_morrison(walker.inv_ovlp[0],
                                                        state.psi_trial[0].T[:,i],
                                                        vtup)
            walker.inv_ovlp[1] = utils.sherman_morrison(walker.inv_ovlp[1],
                                                        state.psi_trial[1].T[:,i],
                                                        vtdown)
            walker.greens_function(state.psi_trial)
            E_L = estimators.local_energy(state.system, walker.G).real
            ot_new = walker.calc_otrial(state.psi_trial)
            dtheta = phase(ot_new/walker.ot)
            walker.weight = (walker.weight * exp(-0.5*state.dt*(walker.E_L-E_L))
                                           * max(0, dtheta))
            walker.E_L = E_L
            walker.ot = ot_new


def generic_continuous(walker, state):
    '''Continuous HS transformation

    This form assumes nothing about the form of the two-body Hamiltonian and
    is thus quite slow, particularly if the matrix is M^2xM^2.

Parameters
----------
walker : :class:`Walker`
    Walker object to be updated. On output we have acted on |phi_i> by
    B_V(x-x')/2 and updated the weight appropriately. Updates inplace.
U : :class:`numpy.ndarray`
    Matrix containing eigenvectors of gamma (times :math:`\sqrt{-\lambda}`.
trial : numpy.ndarray
    Trial wavefunction.
nmax_exp : int
    Maximum expansion order of matrix exponential.
'''

    # iterate over spins
    for i in range(0, 2):
        # Generate ~M^2 normally distributed auxiliary fields.
        sigma = state.dt**0.5 * numpy.random.normal(0.0, 1.0, len(state.U))
        # Construct HS potential, V_HS = sigma dot U
        V_HS = numpy.einsum('ij,j->i', sigma, state.U)
        # Reshape so we can apply to MxN Slater determinant.
        V_HS = numpy.reshape(V_HS, (M,M))
        for n in range(1, nmax_exp+1):
            walker.phi[i] += numpy.factorial(n) * np.dot(V_HS, phi)

    # Update inverse and green's function
    walker.inverse_overlap(trial)
    walker.greens_function(trial)
    # Perform importance sampling, phaseless and real local energy approximation and update
    E_L = estimators.local_energy(system, walker.G).real
    ot_new = walker.calc_otrial(trial)
    dtheta = phase(ot_new/walker.ot)
    walker.weight = (walker.weight * exp(-0.5*system.dt*(walker.E_L-E_L))
                                  * max(0, dtheta))
    walker.E_L = E_L
    walker.ot = ot_new


def kinetic_direct(walker, state):
    '''Propagate by the kinetic term by direct matrix multiplication.

Parameters
----------
walker : :class:`Walker`
    Walker object to be updated. On output we have acted on |phi_i> by B_K/2 and
    updated the weight appropriately. Updates inplace.
bk2 : :class:`numpy.ndarray`
    Exponential of the kinetic propagator :math:`e^{-\Delta\tau/2 \hat{K}}`
trial : :class:`numpy.ndarray`
    Trial wavefunction
'''
    walker.phi[0] = state.projectors.bt2.dot(walker.phi[0])
    walker.phi[1] = state.projectors.bt2.dot(walker.phi[1])
    # Update inverse overlap
    walker.inverse_overlap(state.psi_trial)
    # Update walker weight
    ot_new = walker.calc_otrial(state.psi_trial)
    walker.greens_function(state.psi_trial)
    if ot_new/walker.ot > 1e-16:
        walker.weight = walker.weight * (ot_new/walker.ot)
        walker.ot = ot_new
    else:
        walker.weight = 0.0


_function_dict = {
    'kinetic': kinetic_direct,
    'potential': {
        'Hubbard': {
            'discrete': discrete_hubbard,
            'continuous': generic_continuous,
            'opt_continuous': continuous_hubbard,
        }
    }
}

class Projectors:
    '''Base projector class'''

    def __init__(self, model, hs_type, dt, T):
        self.bt2 = scipy.linalg.expm(-0.5*dt*T)
        self.kinetic = _function_dict['kinetic']
        self.potential = _function_dict['potential'][model][hs_type]
