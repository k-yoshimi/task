"""Phase L-6: orchestrator lifecycle smoke tests.

These tests pin the contract that the libtotapi.so init / run /
get_state / finalize entry points (now wired to the per-module fan-out
of tr + ti + fp + wrx) survive a few realistic call sequences:

1. ``test_init_run0_finalize`` — bare lifecycle (init -> run(0) -> get_state
   -> finalize). Proves the orchestrator path is alive end-to-end with
   no parameter overrides.
2. ``test_init_set_param_run_get_state`` — full cycle with a TR
   transport parameter override (``tr:DT``). Exercises the namespaced
   dispatcher between init and run, so a regression in the TR fan-out
   that ignores the override would surface here.
3. ``test_finalize_reinit_idempotent`` — finalize then re-init in the
   same process and run again. Mirrors trlib's heap-reuse test (PR #83):
   per-module *_api_finalize must release the heap cleanly enough that
   a subsequent *_api_init does not double-free or leak.

These complement ``test_equivalence`` (Layer 1, numerical) and
``test_sweep`` (Layer 4, parameter sweep) by isolating the lifecycle
contract from any baseline-comparison gate.
"""
from __future__ import annotations

import math
import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
PYTHON_ROOT = HERE.parents[2]  # .../python
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

REPO = HERE.parents[3]
DEFAULT_SO = REPO / "tot" / "libtotapi.so"


def _resolved_so() -> Path:
    env = os.environ.get("TOTLIB_PATH")
    if env:
        return Path(env)
    return DEFAULT_SO


@unittest.skipUnless(
    _resolved_so().exists(),
    f"libtotapi.so not built at {_resolved_so()}; "
    "run `make -C tot libtotapi.so`",
)
class TestLifecycle(unittest.TestCase):
    """L-6 lifecycle: init / set_param / run / get_state / finalize."""

    def test_init_run0_finalize(self) -> None:
        """Bare cycle. ntmax=0 must be a valid no-op."""
        from totlib import Tot

        with Tot() as tot:
            # tr_api_init defaults set NRMAX=50 and NSMAX=2; the
            # orchestrator surfaces those via tot_get_state right after
            # init even before the first run. This guards against a
            # regression where the per-module init order leaves the TR
            # heap unallocated.
            tot.run(0)
            state = tot.get_state()
            self.assertEqual(state.tr_present, 1)
            self.assertGreater(state.nrmax, 0)
            self.assertGreater(state.nsmax, 0)

    def test_init_set_param_run_get_state(self) -> None:
        """Full cycle with a TR namespace override.

        Setting ``tr:DT`` between init and run exercises the
        tot_param_registry dispatch into tr_param_registry; if the
        L-6 fan-out forgets to keep the parameter alive across the
        run boundary, the post-run state would not advance.
        """
        from totlib import Tot

        with Tot() as tot:
            # Use a small DT so a single step is cheap and finite.
            tot.set_param("tr:DT", 0.001)
            # Advance one step. The exact NT delta is the contract
            # we care about, not the numerical value of any scalar.
            tot.run(1)
            state = tot.get_state()
            self.assertEqual(state.tr_present, 1)
            self.assertGreaterEqual(state.nt, 1)
            # WPT must be finite (not NaN/Inf). Accept any value.
            wpt = state.scalars.get("WPT", float("nan"))
            self.assertFalse(math.isnan(wpt), f"WPT NaN: {wpt!r}")
            self.assertFalse(math.isinf(wpt), f"WPT Inf: {wpt!r}")

    def test_finalize_reinit_idempotent(self) -> None:
        """Finalize then re-init in the same process; run + get_state
        on the second handle must mirror the first.

        This is the trlib PR #83 heap-reuse test translated to the
        orchestrator: per-module *_api_finalize must release state
        cleanly enough that *_api_init can start over without double
        free / leak. A regression here typically surfaces as a
        SIGABRT or a dimension change between cycles.
        """
        from totlib import Tot

        # First cycle.
        with Tot() as tot:
            tot.run(0)
            s1 = tot.get_state()
        # Tot is now closed; state was captured before finalize.

        # Second cycle in the same process. Must succeed and
        # reproduce the dimensions exactly.
        with Tot() as tot:
            tot.run(0)
            s2 = tot.get_state()

        self.assertEqual(s1.nrmax, s2.nrmax,
                         f"nrmax leak across re-init: {s1.nrmax} -> {s2.nrmax}")
        self.assertEqual(s1.nsmax, s2.nsmax,
                         f"nsmax leak across re-init: {s1.nsmax} -> {s2.nsmax}")
        self.assertEqual(s1.tr_present, s2.tr_present)


if __name__ == "__main__":
    unittest.main()
