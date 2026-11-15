"""ITER01 parameters mirroring ``eq/in/eq.ITER01.in`` (``&eq`` block).

Reproduces the namelist values verbatim so Layer 1 (equivalence) and
Layer 4 (sweep) tests can replay the same physics case via
``libeqapi.so`` without invoking the ``eq`` Fortran driver.

Registered in ``eq/eq_param_registry.f90`` (Phase L-3):
    RR, RA, RKAP, RDLT, RB, BB, RIP, MDLEQF, KNAMEQ (string).

Edit cautiously: changing values invalidates the Layer 1 equivalence
test against ``test_run/baselines/eq_iter01/metrics.json``.
"""
from __future__ import annotations

import warnings

# Scalar parameters that ``eq_param_registry`` accepts via
# ``eq_set_param``. Values copied verbatim from eq/in/eq.ITER01.in.
SCALARS = {
    # MODELG=3 selects EQRTSK (TASK/EQ binary file format) per
    # eq/eqfile.f90:108 (EQ_READ dispatch). The .in menu-driven flow
    # implicitly selects this via the 'r' command after typing 'f';
    # the C ABI bypasses the menu so we set MODELG explicitly here.
    "MODELG": 3,
    "RR":   6.2,
    "RA":   2.0,
    "RKAP": 1.7,
    "RDLT": 0.33,
    "RB":   2.1,
    "BB":   5.3,
    "RIP":  15.0,
}

# Array elements (0-origin for PSIB; 1-origin for everything else).
ARRAYS: dict = {
    # No array entries in the ITER01 namelist.
}

# String-valued parameters routed through ``eq_set_param_str``.
STRINGS = {
    "KNAMEQ": "eqdata.ITER01",
}

# Namelist variables present in eq.ITER01.in but not yet in the
# registry. Add the corresponding CASE in ``eq_param_registry.f90`` to
# move a key from this list into ``SCALARS`` / ``ARRAYS`` / ``STRINGS``.
UNREGISTERED_KEYS: tuple = ()

# Source input file this fixture mirrors (relative to repo root).
SOURCE_INPUT = "eq/in/eq.ITER01.in"

# ``eq.run(mode=...)`` argument. mode=1 is the file load via
# ``equnit::eq_load``.
MODE = 1

# Name of the Phase-0 baseline directory under ``test_run/baselines/``.
BASELINE_NAME = "eq_iter01"


def _apply_array(eq, name, arr) -> None:
    """Set ``NAME[i]`` for each element of ``arr`` (list or {idx: val} dict).

    Lists are 1-origin to match Fortran convention; dicts use the
    explicit subscript so 0-origin arrays (``PSIB(0:5)``) remain
    expressible.
    """
    if isinstance(arr, dict):
        for i, v in arr.items():
            eq.set_param(f"{name}[{int(i)}]", float(v))
    else:
        for i, v in enumerate(arr, start=1):
            eq.set_param(f"{name}[{i}]", float(v))


def apply(eq) -> None:
    """Apply all registered ITER01 parameters to an :class:`eqlib.Eq` handle.

    Keys listed in :data:`UNREGISTERED_KEYS` are skipped silently;
    keys that the registry rejects (because they are not yet exposed
    in L-3) emit a warning and continue so a partial fixture still
    produces useful diagnostics.
    """
    from eqlib import EqlibError  # local import to avoid hard dep at collect time

    for name, value in STRINGS.items():
        if name in UNREGISTERED_KEYS:
            continue
        try:
            eq.set_param_str(name, str(value))
        except EqlibError as exc:
            warnings.warn(
                f"eq_iter01 fixture: STRING {name} not registered yet: {exc}; "
                "move it to UNREGISTERED_KEYS or extend eq_param_registry.f90"
            )
    for name, value in SCALARS.items():
        if name in UNREGISTERED_KEYS:
            continue
        try:
            eq.set_param(name, float(value))
        except EqlibError as exc:
            warnings.warn(
                f"eq_iter01 fixture: SCALAR {name} not registered yet: {exc}; "
                "move it to UNREGISTERED_KEYS or extend eq_param_registry.f90"
            )
    for name, arr in ARRAYS.items():
        if name in UNREGISTERED_KEYS:
            continue
        try:
            _apply_array(eq, name, arr)
        except EqlibError as exc:
            warnings.warn(
                f"eq_iter01 fixture: ARRAY {name} not registered yet: {exc}"
            )
