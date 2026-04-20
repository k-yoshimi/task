"""Ar-impurity parameters mirroring ``test_run/inputs/ti_ar.in``.

The ``ti_ar`` namelist adds a third plasma species (Argon) to the minimum
setup: NSMAX=3, NRMAX=20, NTMAX=10. It exercises the impurity-transport
code path; its baseline at ``test_run/baselines/ti_ar/metrics.json`` is
the Layer 1 equivalence target for Ar transport.

Note: the ``KID_NS(3)='Ar'`` line in the namelist cannot be replayed via
the float-only ``ti_set_param`` ABI (see ``ti_param_registry.f90``
docstring). For Layer 1 we rely on ``ti_init``'s defaults for the
char-valued fields; in practice ``KID_NS(3)='Ar'`` is recomputed from
``NPA(3)=18`` in ``tiinit.f90``, so the run still reproduces the
baseline.

Edit cautiously: changing values invalidates the Layer 1 equivalence
test against ``test_run/baselines/ti_ar/metrics.json`` (once that
baseline exists).
"""
from __future__ import annotations

SCALARS = {
    "NSMAX":   3,
    "DN0":     0.1,
    "DT0":     1.0,
    "DR0":     1.0,
    "DRS":     3.0,
    "NRMAX":   20,
    "NTSTEP":  1,
    "NGTSTEP": 1,
    "NGRSTEP": 1,
    "NTMAX":   10,
}

# 2D arrays keyed by (i, j) tuples so 1-origin subscripts stay explicit.
# MODEL_BND[1,3]=2 and BND_VALUE[1,3]=1.0 in the namelist.
MATRIX_ARRAYS = {
    "MODEL_BND": {(1, 3): 2},
    "BND_VALUE": {(1, 3): 1.0},
}

# 1D arrays: namelist uses sparse subscripts like NPA(3)=18, so we use
# {index: value} dicts rather than full lists.
ARRAYS = {
    "NPA":      {3: 18},
    "PA":       {3: 39.95},   # Argon atomic mass; namelist key is PM but
                              # ticomm exposes it as PA in the registry.
    "ID_NS":    {3: 10},
    "NZMIN_NS": {3: 15},
    "NZMAX_NS": {3: 18},
    "DN0_NS":   {1: 0.0, 2: 0.0},
}

# Namelist keys NOT in ti_param_registry.f90 (L-3 state).
# `KID_NS` is char-valued -> not settable via float ABI.
# `PM` is the namelist form of `PA` (different name in ticomm); PA is in
# ARRAYS above, so PM stays here only to document the namelist mapping.
UNREGISTERED_KEYS = (
    "KID_NS",
    "PM",  # namelist alias for PA; value is applied via PA in ARRAYS.
)

SOURCE_INPUT = "test_run/inputs/ti_ar.in"
NTMAX = 10
BASELINE_NAME = "ti_ar"


def _apply_array(ti, name, arr) -> None:
    """Set ``NAME[i]`` for each element of ``arr`` (list or {idx: val})."""
    if isinstance(arr, dict):
        for i, v in arr.items():
            try:
                ti.set_param(f"{name}[{int(i)}]", float(v))
            except Exception:  # pragma: no cover - unregistered is OK
                if name not in UNREGISTERED_KEYS:
                    raise
    else:
        for i, v in enumerate(arr, start=1):
            try:
                ti.set_param(f"{name}[{i}]", float(v))
            except Exception:  # pragma: no cover - unregistered is OK
                if name not in UNREGISTERED_KEYS:
                    raise


def apply(ti) -> None:
    """Apply all *registered* ti_ar parameters to a TiLib instance."""
    for name, value in SCALARS.items():
        try:
            ti.set_param(name, float(value))
        except Exception:
            if name not in UNREGISTERED_KEYS:
                raise
    for name, arr in ARRAYS.items():
        _apply_array(ti, name, arr)
    # 2D (i, j) subscripts.
    for name, mat in MATRIX_ARRAYS.items():
        for (i, j), v in mat.items():
            try:
                ti.set_param(f"{name}[{int(i)},{int(j)}]", float(v))
            except Exception:
                if name not in UNREGISTERED_KEYS:
                    raise
