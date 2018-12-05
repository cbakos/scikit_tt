#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import scipy.linalg as la


def als(operator, initial_guess, right_hand_side, repeats=1, solver='solve'):
    """Alternating linear scheme

    Approximates the solution of a system of linear equations in the TT format. For details, see [1]_.

    Parameters
    ----------
    operator: instance of TT class
        TT operator
    initial_guess: instance of TT class
        initial guess for the solution of operator @ x = right_hand_side
    right_hand_side: instance of TT class
        right hand side of the system of linear equations
    repeats: int, optional
        number of repeats of the ALS, default is 1
    solver: string, optional
        algorithm for obtaining the solutions of the micro systems, can be 'solve' or 'lu', default is 'solve'

    Returns
    -------
    solution: instance of TT class
        approximated solution of the system of linear equations

    References
    ----------
    ..[1] S. Holtz, T. Rohwedder, R. Schneider, "The Alternating Linear Scheme for Tensor Optimization in the Tensor
          Train Format", SIAM Journal on Scientific Computing 34 (2), 2012
    """

    # define solution tensor
    solution = initial_guess.copy()

    # define stacks
    stack_left_op = [None] * operator.order
    stack_left_rhs = [None] * operator.order
    stack_right_op = [None] * operator.order
    stack_right_rhs = [None] * operator.order

    # construct right stacks for the left- and right-hand side
    for i in range(operator.order - 1, -1, -1):
        construct_stack_right_op(i, stack_right_op, operator, solution)
        construct_stack_right_rhs(i, stack_right_rhs, right_hand_side, solution)

    # define iteration number
    current_iteration = 1

    # begin ALS
    while current_iteration <= repeats:

        # first half sweep
        for i in range(operator.order):

            # update left stacks for the left- and right-hand side
            construct_stack_left_op(i, stack_left_op, operator, solution)
            construct_stack_left_rhs(i, stack_left_rhs, right_hand_side, solution)

            if i < operator.order - 1:
                # construct micro system
                micro_op = construct_micro_matrix_als(i, stack_left_op, stack_right_op, operator, solution)
                micro_rhs = construct_micro_rhs_als(i, stack_left_rhs, stack_right_rhs, right_hand_side, solution)

                # update solution
                update_core_als(i, micro_op, micro_rhs, solution, solver, 'forward')

        # second half sweep
        for i in range(operator.order - 1, -1, -1):
            # update right stacks for the left- and right-hand side
            construct_stack_right_op(i, stack_right_op, operator, solution)
            construct_stack_right_rhs(i, stack_right_rhs, right_hand_side, solution)

            # construct micro system
            micro_op = construct_micro_matrix_als(i, stack_left_op, stack_right_op, operator, solution)
            micro_rhs = construct_micro_rhs_als(i, stack_left_rhs, stack_right_rhs, right_hand_side, solution)

            # update solution
            update_core_als(i, micro_op, micro_rhs, solution, solver, 'backward')

        # increase iteration number
        current_iteration += 1

    return solution


def mals(operator, initial_guess, right_hand_side, repeats=1, solver='solve', threshold=1e-12, max_rank=np.infty):
    """Modified alternating linear scheme for solving systems of linear equations in the TT format.

    Approximates the solution of a system of linear equations in the TT format. For details, see [1]_.

    Parameters
    ----------
    operator: instance of TT class
        TT operator
    initial_guess: instance of TT class
        initial guess for the solution of operator @ x = right_hand_side
    right_hand_side: instance of TT class
        right hand side of the system of linear equations
    repeats: int, optional
        number of repeats of the MALS, default is 1
    solver: string, optional
        algorithm for obtaining the solutions of the micro systems, can be 'solve' or 'lu', default is 'solve'
    threshold: float, optional
        threshold for reduced SVD decompositions, default is 1e-12
    max_rank: int, optional
        maximum rank of the solution, default is infinity

    Returns
    -------
    solution: instance of TT class
        approximated solution of the system of linear equations

    References
    ----------
    ..[1] S. Holtz, T. Rohwedder, R. Schneider, "The Alternating Linear Scheme for Tensor Optimization in the Tensor
          Train Format", SIAM Journal on Scientific Computing 34 (2), 2012
    """

    # define solution tensor
    solution = initial_guess.copy()

    # define stacks
    stack_left_op = [None] * operator.order
    stack_left_rhs = [None] * operator.order
    stack_right_op = [None] * operator.order
    stack_right_rhs = [None] * operator.order

    # construct right stacks for the left- and right-hand side
    for i in range(operator.order - 1, 0, -1):
        construct_stack_right_op(i, stack_right_op, operator, solution)
        construct_stack_right_rhs(i, stack_right_rhs, right_hand_side, solution)

    # define iteration number
    current_iteration = 1

    # begin MALS
    while current_iteration <= repeats:

        # first half sweep
        for i in range(operator.order - 1):

            # update left stacks for the left- and right-hand side
            construct_stack_left_op(i, stack_left_op, operator, solution)
            construct_stack_left_rhs(i, stack_left_rhs, right_hand_side, solution)

            if i < operator.order - 2:
                # construct micro system
                micro_op = construct_micro_matrix_mals(i, stack_left_op, stack_right_op, operator, solution)
                micro_rhs = construct_micro_rhs_mals(i, stack_left_rhs, stack_right_rhs, right_hand_side, solution)

                # update solution
                update_core_mals(i, micro_op, micro_rhs, solution, solver, 'forward', threshold, max_rank)

        # second half sweep
        for i in range(operator.order - 2, -1, -1):
            # update right stacks for the left- and right-hand side
            construct_stack_right_op(i + 1, stack_right_op, operator, solution)
            construct_stack_right_rhs(i + 1, stack_right_rhs, right_hand_side, solution)

            # construct micro system
            micro_op = construct_micro_matrix_mals(i, stack_left_op, stack_right_op, operator, solution)
            micro_rhs = construct_micro_rhs_mals(i, stack_left_rhs, stack_right_rhs, right_hand_side, solution)

            # update solution
            update_core_mals(i, micro_op, micro_rhs, solution, solver, 'backward', threshold, max_rank)

        # increase iteration number
        current_iteration += 1

    return solution


def construct_stack_left_op(i, stack_left_op, operator, solution):
    """Construct left stack for left-hand side

    Parameters
    ----------
    i: int
        core index
    stack_left_op: list of ndarrays
        left stack for left-hand side
    operator: instance of TT class
        TT operator of the system of linear equations
    solution: instance of TT class
        approximated solution of the system of linear equations
    """

    if i == 0:

        # first stack element is 1
        stack_left_op[i] = np.array([1], ndmin=3)
    else:

        # contract previous stack element with solution and operator cores
        stack_left_op[i] = np.tensordot(stack_left_op[i - 1], solution.cores[i - 1][:, :, 0, :], axes=(0, 0))
        stack_left_op[i] = np.tensordot(stack_left_op[i], operator.cores[i - 1], axes=([0, 2], [0, 2]))
        stack_left_op[i] = np.tensordot(stack_left_op[i], solution.cores[i - 1][:, :, 0, :], axes=([0, 2], [0, 1]))


def construct_stack_left_rhs(i, stack_left_rhs, right_hand_side, solution):
    """Construct left stack for right-hand side

    Parameters
    ----------
    i: int
        core index
    stack_left_rhs: list of ndarrays
        left stack for right-hand side
    right_hand_side: instance of TT class
        right-hand side of the system of linear equations
    solution: instance of TT class
        approximated solution of the system of linear equations
    """

    if i == 0:

        # first stack element is 1
        stack_left_rhs[i] = np.array([1], ndmin=2)
    else:

        # contract previous stack element with solution and right-hand side cores
        stack_left_rhs[i] = np.tensordot(stack_left_rhs[i - 1], right_hand_side.cores[i - 1][:, :, 0, :], axes=(0, 0))
        stack_left_rhs[i] = np.tensordot(stack_left_rhs[i], solution.cores[i - 1][:, :, 0, :], axes=([0, 1], [0, 1]))


def construct_stack_right_op(i, stack_right_op, operator, solution):
    """Construct right stack for left-hand side

    Parameters
    ----------
    i: int
        core index
    stack_right_op: list of ndarrays
        right stack for left-hand side
    operator: instance of TT class
        TT operator side of the system of linear equations
    solution: instance of TT class
        approximated solution of the system of linear equations
    """

    if i == operator.order - 1:

        # last stack element is 1
        stack_right_op[i] = np.array([1], ndmin=3)

    else:

        # contract previous stack element with solution and operator cores
        stack_right_op[i] = np.tensordot(solution.cores[i + 1][:, :, 0, :], stack_right_op[i + 1], axes=(2, 2))
        stack_right_op[i] = np.tensordot(operator.cores[i + 1], stack_right_op[i], axes=([1, 3], [1, 3]))
        stack_right_op[i] = np.tensordot(solution.cores[i + 1][:, :, 0, :], stack_right_op[i], axes=([1, 2], [1, 3]))


def construct_stack_right_rhs(i, stack_right_rhs, right_hand_side, solution):
    """Construct right stack for right-hand side

    Parameters
    ----------
    i: int
        core index
    stack_right_rhs: list of ndarrays
        right stack for right-hand side
    right_hand_side: instance of TT class
        right-hand side of the system of linear equations
    solution: instance of TT class
        approximated solution of the system of linear equations
    """

    if i == right_hand_side.order - 1:

        # last stack element is 1
        stack_right_rhs[i] = np.array([1], ndmin=2)

    else:

        # contract previous stack element with solution and right-hand side cores
        stack_right_rhs[i] = np.tensordot(solution.cores[i + 1][:, :, 0, :], stack_right_rhs[i + 1], axes=(2, 1))
        stack_right_rhs[i] = np.tensordot(right_hand_side.cores[i + 1][:, :, 0, :], stack_right_rhs[i],
                                          axes=([1, 2], [1, 2]))


def construct_micro_matrix_als(i, stack_left_op, stack_right_op, operator, solution):
    """Construct micro matrix for ALS

    Parameters
    ----------
    i: int
        core index
    stack_left_op: list of ndarrays
        left stack for left-hand side
    stack_right_op: list of ndarrays
        right stack for left-hand side
    operator: instance of TT class
        TT operator of the system of linear equations
    solution: instance of TT class
        approximated solution of the system of linear equations

    Returns
    -------
    micro_op: ndarray
        ith micro matrix
    """

    # contract stack elements and operator core
    micro_op = np.tensordot(stack_left_op[i], operator.cores[i], axes=(1, 0))
    micro_op = np.tensordot(micro_op, stack_right_op[i], axes=(4, 1))

    # transpose and reshape micro matrix
    micro_op = micro_op.transpose([1, 2, 5, 0, 3, 4]).reshape(
        solution.ranks[i] * operator.row_dims[i] * solution.ranks[i + 1],
        solution.ranks[i] * operator.col_dims[i] * solution.ranks[i + 1])

    return micro_op


def construct_micro_matrix_mals(i, stack_left_op, stack_right_op, operator, solution):
    """Construct micro matrix for MALS

    Parameters
    ----------
    i: int
        core index
    stack_left_op: list of ndarrays
        left stack for left-hand side
    stack_right_op: list of ndarrays
        right stack for left-hand side
    operator: instance of TT class
        TT operator of the system of linear equations
    solution: instance of TT class
        approximated solution of the system of linear equations

    Returns
    -------
    micro_op: ndarray
        ith micro matrix
    """

    # contract stack elements and operator cores
    micro_op = np.tensordot(stack_left_op[i], operator.cores[i], axes=(1, 0))
    micro_op = np.tensordot(micro_op, operator.cores[i + 1], axes=(4, 0))
    micro_op = np.tensordot(micro_op, stack_right_op[i + 1], axes=(6, 1))

    # transpose and reshape micro matrix
    micro_op = micro_op.transpose([1, 2, 4, 7, 0, 3, 5, 6]).reshape(
        solution.ranks[i] * operator.row_dims[i] * operator.row_dims[i + 1] * solution.ranks[i + 2],
        solution.ranks[i] * operator.col_dims[i] * operator.col_dims[i + 1] * solution.ranks[i + 2])

    return micro_op


def construct_micro_rhs_als(i, stack_left_rhs, stack_right_rhs, right_hand_side, solution):
    """Construct micro right-hand side for ALS

    Parameters
    ----------
    i: int
        core index
    stack_left_rhs: list of ndarrays
        left stack for right-hand side
    stack_right_rhs: list of ndarrays
        right stack for right-hand side
    right_hand_side: instance of TT class
        right-hand side of the system of linear equations
    solution: instance of TT class
        approximated solution of the system of linear equations

    Returns
    -------
    micro_rhs: ndarray
        ith micro right-hand side
    """

    # contract stack elements and right-hand side core
    micro_rhs = np.tensordot(stack_left_rhs[i], right_hand_side.cores[i][:, :, 0, :], axes=(0, 0))
    micro_rhs = np.tensordot(micro_rhs, stack_right_rhs[i], axes=(2, 0))

    # reshape micro right-hand side
    micro_rhs = micro_rhs.reshape(solution.ranks[i] * right_hand_side.row_dims[i] * solution.ranks[i + 1], 1)

    return micro_rhs


def construct_micro_rhs_mals(i, stack_left_rhs, stack_right_rhs, right_hand_side, solution):
    """Construct micro right-hand side for MALS

    Parameters
    ----------
    i: int
        core index
    stack_left_rhs: list of ndarrays
        left stack for right-hand side
    stack_right_rhs: list of ndarrays
        right stack for right-hand side
    right_hand_side: instance of TT class
        right-hand side of the system of linear equations
    solution: instance of TT class
        approximated solution of the system of linear equations

    Returns
    -------
    micro_rhs: ndarray
        ith micro right-hand side
    """

    # contract stack elements and right-hand side cores
    micro_rhs = np.tensordot(stack_left_rhs[i], right_hand_side.cores[i][:, :, 0, :], axes=(0, 0))
    micro_rhs = np.tensordot(micro_rhs, right_hand_side.cores[i + 1][:, :, 0, :], axes=(2, 0))
    micro_rhs = np.tensordot(micro_rhs, stack_right_rhs[i + 1], axes=(3, 0))

    # reshape micro right-hand side
    micro_rhs = micro_rhs.reshape(
        solution.ranks[i] * right_hand_side.row_dims[i] * right_hand_side.row_dims[i + 1] * solution.ranks[i + 2], 1)

    return micro_rhs


def update_core_als(i, micro_op, micro_rhs, solution, solver, direction):
    """Update TT core for ALS

    Parameters
    ----------
    i: int
        core index
    micro_op: ndarray
        micro matrix for ith TT core
    micro_rhs: ndarray
        micro right-hand side for ith TT core
    solution: instance of TT class
        approximated solution of the system of linear equations
    solver: string
        algorithm for obtaining the solutions of the micro systems
    direction: string
        'forward' if first half sweep, 'backward' if second half sweep
    """

    # solve the micro system for the ith TT core
    # ------------------------------------------

    # if solver='solve'
    if solver == 'solve':
        solution.cores[i] = np.linalg.solve(micro_op, micro_rhs)

    # if solver='lu'
    if solver == 'lu':
        lu = la.lu_factor(micro_op, overwrite_a=True, check_finite=False)
        solution.cores[i] = la.lu_solve(lu, micro_rhs, trans=0, overwrite_b=True, check_finite=False)

    # reshape solution and orthonormalization
    # ---------------------------------------

    # first half sweep
    if direction == 'forward':
        # decompose solution
        [q, _] = la.qr(solution.cores[i].reshape(solution.ranks[i] * solution.row_dims[i], solution.ranks[i + 1]),
                       overwrite_a=True, mode='economic', check_finite=False)

        # set new rank
        solution.ranks[i + 1] = q.shape[1]

        # save orthonormal part
        solution.cores[i] = q.reshape(solution.ranks[i], solution.row_dims[i], 1, solution.ranks[i + 1])

    # second half sweep
    if direction == 'backward':

        if i > 0:

            # decompose solution
            [_, q] = la.rq(solution.cores[i].reshape(solution.ranks[i], solution.row_dims[i] * solution.ranks[i + 1]),
                           overwrite_a=True, mode='economic', check_finite=False)

            # set new rank
            solution.ranks[i] = q.shape[0]

            # save orthonormal part
            solution.cores[i] = q.reshape(solution.ranks[i], solution.row_dims[i], 1, solution.ranks[i + 1])

        else:

            # last iteration step
            solution.cores[i] = solution.cores[i].reshape(solution.ranks[i], solution.row_dims[i], 1,
                                                          solution.ranks[i + 1])


def update_core_mals(i, micro_op, micro_rhs, solution, solver, direction, threshold, max_rank):
    """Update TT cores for MALS

    Parameters
    ----------
    i: int
        core index
    micro_op: ndarray
        micro matrix for ith and (i+1)th TT core
    micro_rhs: ndarray
        micro right-hand side for ith and (i+1)th TT core
    solution: instance of TT class
        approximated solution of the system of linear equations
    solver: string
        algorithm for obtaining the solutions of the micro systems
    direction: string
        'forward' if first half sweep, 'backward' if second half sweep
    threshold: float
        threshold for reduced SVD decompositions
    max_rank: int
        maximum rank of the solution
    """

    # solve the micro system for the ith and (i+1)th TT core
    # ------------------------------------------

    # if solver='solve'
    if solver == 'solve':
        solution.cores[i] = la.solve(micro_op, micro_rhs, overwrite_a=True, overwrite_b=True, check_finite=False)

    # if solver='lu'
    if solver == 'lu':
        lu = la.lu_factor(micro_op, overwrite_a=True, check_finite=False)
        solution.cores[i] = la.lu_solve(lu, micro_rhs, trans=0, overwrite_b=True, check_finite=False)

    # reshape solution and orthonormalization
    # ---------------------------------------

    # first half sweep
    if direction == 'forward':

        # decompose solution
        [u, s, _] = la.svd(solution.cores[i].reshape(solution.ranks[i] * solution.row_dims[i],
                                                     solution.row_dims[i + 1] * solution.ranks[i + 2]),
                           full_matrices=False, overwrite_a=True, check_finite=False, lapack_driver='gesvd')

        # rank reduction
        if threshold != 0:
            indices = np.where(s / s[0] > threshold)[0]
            u = u[:, indices]
            s = s[indices]
        if max_rank != np.infty:
            u = u[:, :np.minimum(u.shape[1], max_rank)]
            s = s[:np.minimum(s.shape[0], max_rank)]

        # set new rank
        solution.ranks[i + 1] = s.shape[0]

        # save orthonormal part
        solution.cores[i] = u.reshape(solution.ranks[i], solution.row_dims[i], 1, solution.ranks[i + 1])

    # second half sweep
    if direction == 'backward':

        # decompose solution
        [u, s, v] = la.svd(solution.cores[i].reshape(solution.ranks[i] * solution.row_dims[i],
                                                     solution.row_dims[i + 1] * solution.ranks[i + 2]),
                           full_matrices=False, overwrite_a=True, check_finite=False, lapack_driver='gesvd')

        # rank reduction
        if threshold != 0:
            indices = np.where(s / s[0] > threshold)[0]
            u = u[:, indices]
            s = s[indices]
            v = v[indices, :]
        if max_rank != np.infty:
            u = u[:, :np.minimum(u.shape[1], max_rank)]
            s = s[:np.minimum(s.shape[0], max_rank)]
            v = v[:np.minimum(v.shape[0], max_rank), :]

        # set new rank
        solution.ranks[i + 1] = s.shape[0]

        # save orthonormal part
        solution.cores[i + 1] = v.reshape(solution.ranks[i + 1], solution.row_dims[i + 1], 1, solution.ranks[i + 2])

        if i == 0:
            # last iteration step
            solution.cores[i] = (u @ np.diag(s)).reshape(solution.ranks[i], solution.row_dims[i], 1,
                                                         solution.ranks[i + 1])