"""Parameter dict equivalent to test_run/inputs/fp_iter01.in.

Parameter names here must be uppercase strings that match the L-3
``fp_param_registry.f90`` SELECT CASE table. They fall into two groups:

* ``MODELG, NSMAX, PA, PN, PNS, PTPR, PTPP`` -> ``plcomm_parm``
* ``NSAMAX, NSBMAX, NS_NSA, NS_NSB, MODELC, MODELR, NRMAX, NPMAX, NTHMAX,
  NTMAX, DELT, PMAX, RMIN, RMAX, PABS_WR`` -> ``fpcomm_parm``

L-3 adds explicit ``USE plcomm_parm, ONLY: ...`` in
``fp_param_registry.f90`` so both groups are settable via the single C
ABI entry point.
"""

ITER01_PARAMS = {
    # --- plcomm_parm scalar int ---
    "MODELG": 3,
    "NSMAX": 3,
    # --- plcomm_parm species arrays (NSM 1-origin) ---
    "PA":  {2: 2.0, 3: 3.0},
    "PN":  {1: 0.8, 2: 0.4, 3: 0.4},
    "PNS": {1: 0.01, 2: 0.005, 3: 0.005},
    "PTPR": {1: 20.0, 2: 20.0, 3: 20.0},
    "PTPP": {1: 20.0, 2: 20.0, 3: 20.0},
    # --- fpcomm_parm mesh / radial ---
    "NRMAX": 40,
    "RMIN":  0.4,
    "RMAX":  0.8,
    "NTMAX": 2,
    "PMAX":  {1: 10.0, 2: 10.0, 3: 10.0},
    "NPMAX":  50,
    "NTHMAX": 50,
    # --- fpcomm_parm model switches ---
    "MODELC": {1: 4, 2: 4, 3: 4},
    "MODELR": 1,
    # --- fpcomm_parm time / species count / mapping ---
    "DELT":   1.0e-3,
    "NSAMAX": 1,
    "NSBMAX": 3,
    "NS_NSA": {1: 1},
    "NS_NSB": {1: 1, 2: 2, 3: 3},
    # --- fpcomm_parm wave heating ---
    "PABS_WR": 1.0,
}
