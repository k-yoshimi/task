"""TST-2 parameters mirroring ``eq/in/eq.TST-2.in`` (``&eq`` block).

Reproduces the namelist values verbatim so Layer 1 (equivalence) and
Layer 4 (sweep) tests can replay the same physics case via
``libeqapi.so`` without invoking the ``eq`` Fortran driver.

Edit cautiously: changing values invalidates the Layer 1 equivalence
test against ``test_run/baselines/eq_tst2/metrics.json``.

Note: ``PP0`` is in the namelist but not yet registered in
``eq_param_registry.f90`` -- it is listed in :data:`UNREGISTERED_KEYS`
and will be skipped until a future L-3 extension adds the CASE entry.
"""
from __future__ import annotations

import warnings

# Scalar parameters that ``eq_param_registry`` accepts via
# ``eq_set_param``. Values copied verbatim from eq/in/eq.TST-2.in.
SCALARS = {
    # MODELG=3 selects EQRTSK (TASK/EQ binary file format) per
    # eq/eqfile.f90:108. The .in menu-driven flow implicitly selects
    # this via 'r' after 'f'; the C ABI needs it explicit.
    "MODELG": 3,
    "RR":   0.36,
    "RA":   0.23,
    "RKAP": 1.3,
    "RDLT": 0.2,
    "RB":   0.24,
    "BB":   0.15,
    "RIP":  0.015,
}

# Array elements (0-origin for PSIB; 1-origin for everything else).
ARRAYS: dict = {
    # No array entries in the TST-2 namelist.
}

# String-valued parameters routed through ``eq_set_param_str``.
STRINGS = {
    "KNAMEQ": "eqdata.TST-2",
}

# Namelist variables present in eq.TST-2.in but not yet exposed via
# eq_param_registry.f90. PP0 is the only such key as of L-3.
UNREGISTERED_KEYS: tuple = (
    "PP0",
)

# Source input file this fixture mirrors (relative to repo root).
SOURCE_INPUT = "eq/in/eq.TST-2.in"

# ``eq.run(mode=...)`` argument. mode=1 is the file load via
# ``equnit::eq_load``.
MODE = 1

# Name of the Phase-0 baseline directory under ``test_run/baselines/``.
BASELINE_NAME = "eq_tst2"


def _apply_array(eq, name, arr) -> None:
    """Set ``NAME[i]`` for each element of ``arr`` (list or {idx: val} dict)."""
    if isinstance(arr, dict):
        for i, v in arr.items():
            eq.set_param(f"{name}[{int(i)}]", float(v))
    else:
        for i, v in enumerate(arr, start=1):
            eq.set_param(f"{name}[{i}]", float(v))


def apply(eq) -> None:
    """Apply all registered TST-2 parameters to an :class:`eqlib.Eq` handle.

    Keys listed in :data:`UNREGISTERED_KEYS` are skipped silently;
    keys that the registry rejects emit a warning and continue.
    """
    from eqlib import EqlibError  # local import to avoid hard dep at collect time

    for name, value in STRINGS.items():
        if name in UNREGISTERED_KEYS:
            continue
        try:
            eq.set_param_str(name, str(value))
        except EqlibError as exc:
            warnings.warn(
                f"eq_tst2 fixture: STRING {name} not registered yet: {exc}"
            )
    for name, value in SCALARS.items():
        if name in UNREGISTERED_KEYS:
            continue
        try:
            eq.set_param(name, float(value))
        except EqlibError as exc:
            warnings.warn(
                f"eq_tst2 fixture: SCALAR {name} not registered yet: {exc}"
            )
    for name, arr in ARRAYS.items():
        if name in UNREGISTERED_KEYS:
            continue
        try:
            _apply_array(eq, name, arr)
        except EqlibError as exc:
            warnings.warn(
                f"eq_tst2 fixture: ARRAY {name} not registered yet: {exc}"
            )
