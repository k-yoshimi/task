"""HT6M parameters mirroring ``test_run/inputs/tot_ht6m_short.in``.

The standalone ``tot`` driver consumes the ``.in`` script (a sequence
of interactive menu commands) and reads the companion namelists from
``tot_ht6m_short.eqparm`` and ``tot_ht6m_short.trparm`` (loaded by the
`r` -- read namelist -- step inside the menu).

For the L-6 equivalence test we replay the same physics through
``libtotapi.so`` via the ``Tot`` orchestrator. Every key MUST carry
an ``<ns>:`` namespace prefix; bare names are rejected.

L-3 / L-4 / L-5 stub status: ``tot_init`` / ``tot_run`` /
``tot_get_state`` / ``tot_finalize`` all currently return
``TOT_ERR_NOT_IMPL`` (rc=4). Layer 1 therefore auto-skips until the
L-6 fan-out lands. ``set_param`` / ``set_param_str`` work today.

Edit cautiously: if you change values here you must regenerate
``test_run/baselines/tot_ht6m_short/metrics.json``. See
``docs/superpowers/plans/2026-04-18-tot-library-L6-test-4layers.md``
for the iteration protocol.
"""
from __future__ import annotations

import warnings

# Namespaced scalar parameters. Values copied verbatim from:
#   - test_run/inputs/tot_ht6m_short.eqparm  (&eq block)
#   - test_run/inputs/tot_ht6m_short.trparm  (&tr block)
SCALARS = {
    # --- &eq block ---
    "eq:RR":   0.65,
    "eq:RA":   0.20,
    "eq:RKAP": 1.0,
    "eq:RDLT": 0.1,
    "eq:RIP":  0.02,
    "eq:BB":   1.5,
    # eq:PP0 is registered but adding it does not lift the rc=3
    # CALCULATION_FAILED in tot_run for this case — there's a deeper
    # divergence between the Python pipeline's replay of the .trparm
    # block and what the standalone tot driver actually does. Leave
    # ht6m gated behind its missing eqdata-HT6M baseline (no CI
    # generation) until the divergence is investigated separately.

    # --- &tr block ---
    "tr:MODELG": 3,
    "tr:NSMAX":  2,
    "tr:DT":     0.0001,
    "tr:NTMAX":  1000,
    "tr:NTSTEP": 100,
    "tr:NGRSTP": 100,
}

# Array parameters: 1-origin lists (or {idx: val} dicts).
ARRAYS: dict = {
    # &tr: PA(2)=1.D0, PZ(2)=1.D0 -- explicit subscript via dict.
    "tr:PA":  {2: 1.0},
    "tr:PZ":  {2: 1.0},
    # &tr: pn  = 0.01, 0.01
    "tr:PN":  [0.01, 0.01],
    # &tr: pns = 0.001, 0.001
    "tr:PNS": [0.001, 0.001],
    # &tr: pt  = 0.01, 0.01, 1e-6, 1e-6
    "tr:PT":  [0.01, 0.01, 1.0e-6, 1.0e-6],
    # &tr: pts = 0.001, 0.001, 1e-6, 1e-6
    "tr:PTS": [0.001, 0.001, 1.0e-6, 1.0e-6],
}

# String-valued parameters routed through tot_set_param_str.
STRINGS = {
    "eq:KNAMEQ": "eqdata-HT6M",
    "tr:KNAMEQ": "eqdata-HT6M",
}

# Namelist variables present in the .eqparm / .trparm files but not
# yet routable through any per-module registry. The ``apply`` helper
# silently skips these so a partial fixture still works.
#
# - eq:PP0 : not yet in eq_param_registry.f90 (geometry pressure
#   coefficient). Add a CASE in eq_param_registry to migrate it out.
UNREGISTERED_KEYS: tuple = ()

# Source input files this fixture mirrors (relative to repo root).
SOURCE_INPUTS = (
    "test_run/inputs/tot_ht6m_short.in",
    "test_run/inputs/tot_ht6m_short.eqparm",
    "test_run/inputs/tot_ht6m_short.trparm",
)

# ``tot.run(ntmax=...)`` argument used by Layer 1. The trparm sets
# NTMAX=1000 so the standalone tot driver runs 1000 transport steps;
# we mirror that here for byte-for-byte comparison.
NTMAX = 1000

# Name of the Phase 0 baseline directory under ``test_run/baselines/``.
BASELINE_NAME = "tot_ht6m_short"


def _apply_array(tot, name: str, arr) -> None:
    """Set ``NAME[i]`` for each element of ``arr`` (list or {idx: val} dict)."""
    if isinstance(arr, dict):
        for i, v in arr.items():
            tot.set_param(f"{name}[{int(i)}]", float(v))
    else:
        for i, v in enumerate(arr, start=1):
            tot.set_param(f"{name}[{i}]", float(v))


def apply(tot) -> None:
    """Apply all registered HT6M parameters to a :class:`totlib.Tot` handle.

    Keys in :data:`UNREGISTERED_KEYS` are skipped silently. Keys that
    the per-module registry rejects (e.g. because they are not yet
    exposed in the relevant ``*_param_set``) emit a warning and we
    continue, so a partial fixture still produces useful diagnostics.
    """
    from totlib import TotlibError  # local import: avoid hard dep at collect

    for name, value in STRINGS.items():
        if name in UNREGISTERED_KEYS:
            continue
        try:
            tot.set_param_str(name, str(value))
        except TotlibError as exc:
            warnings.warn(
                f"tot_ht6m fixture: STRING {name} not registered yet: "
                f"{exc}; move it to UNREGISTERED_KEYS or extend the "
                "per-module registry."
            )
    for name, value in SCALARS.items():
        if name in UNREGISTERED_KEYS:
            continue
        try:
            tot.set_param(name, float(value))
        except TotlibError as exc:
            warnings.warn(
                f"tot_ht6m fixture: SCALAR {name} not registered yet: "
                f"{exc}; move it to UNREGISTERED_KEYS or extend the "
                "per-module registry."
            )
    for name, arr in ARRAYS.items():
        if name in UNREGISTERED_KEYS:
            continue
        try:
            _apply_array(tot, name, arr)
        except TotlibError as exc:
            warnings.warn(
                f"tot_ht6m fixture: ARRAY {name} not registered yet: {exc}"
            )
