"""Layer 1: equivalence between the libwrxapi.so replay and the Phase 0
Fortran baseline, compared at tolerance 1e-10.

For each case (``wrx_iter01``, ``wrx_demo``):

1. open a :class:`wrxlib.Wrxlib` handle (loads ``wrx/libwrxapi.so``),
2. replay the registered subset of the namelist fixture via
   :py:meth:`~wrxlib.Wrxlib.set_param`,
3. drive ``wrx_run`` via :py:meth:`~wrxlib.Wrxlib.run` with the
   fixture's ``NRAY_REQUEST``,
4. serialise the resulting :class:`~wrxlib.state.WrxState` via
   :py:meth:`~wrxlib.state.WrxState.to_dict`,
5. compare against ``test_run/baselines/<case>/metrics.json`` using
   ``test_run/scripts/compare_metrics.py`` with tolerance ``1e-10``.

Triple-skip gates (all must pass for the class to run):

* libwrxapi.so is importable via
  :func:`wrxlib._ffi._candidate_paths` (covers both
  ``wrx/libwrxapi.so`` and ``lib/libwrxapi.so``),
* the baseline JSON exists under ``test_run/baselines/``,
* ``WRX_RUN_OK=1`` is set in the environment.

The ``WRX_RUN_OK`` gate is required because ``wrx_run`` on the current
L-4 build pulls ``libgrf::grd1d`` via ``wrcalpwr`` and may segfault
inside the shared library; see ``python/wrxlib/README.md`` (Known
Limitation) and ``wrx/tests/c_abi/test_run_so.c`` (which skips
wrx_run for the same reason).

See ``docs/superpowers/plans/2026-04-18-wrx-library-L6-test-4layers.md``
Task 3 for the iteration protocol when the 1e-10 match is not yet met.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
PYTHON_ROOT = REPO / "python"
BASELINES_DIR = REPO / "test_run" / "baselines"
COMPARE_SCRIPT = REPO / "test_run" / "scripts" / "compare_metrics.py"

# Make ``import wrxlib`` work whether tests are launched from the repo
# root (PYTHONPATH=python) or from inside python/wrxlib/tests/.
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from wrxlib import _ffi  # noqa: E402


# See test_wrxlib.py for context: gate defaults ON post-2026-04-20.
RUN_OK = os.environ.get("WRX_RUN_OK", "1") != "0"


def _any_so_exists() -> bool:
    """True if libwrxapi.so is present at any known candidate path."""
    return any(p.exists() for p in _ffi._candidate_paths())


def _wrxlib_importable() -> bool:
    """Importable check for wrxlib -- libwrxapi.so is loaded lazily so
    we only verify the Python package."""
    try:
        import wrxlib  # noqa: F401
    except Exception:
        return False
    return True


def _run_case(apply_fn, nray_request: int) -> dict:
    """Drive a single libwrxapi.so cycle and return the to_dict payload.

    Keeping this outside ``TestEquivalence`` lets Layer 4 reuse the
    same replay helper without importing a TestCase class.
    """
    from wrxlib import Wrxlib  # noqa: WPS433 (intentional local import)
    with Wrxlib() as wrx:
        apply_fn(wrx)
        wrx.run(int(nray_request))
        state = wrx.get_state()
    return state.to_dict()


def _compare_with_baseline(actual: dict, case_name: str, tol: str = "1e-10") -> None:
    """Write ``actual`` to a temp JSON and diff it vs the baseline.

    Raises :class:`AssertionError` on any drift so the unittest framework
    reports it as a FAIL rather than an ERROR.
    """
    baseline_json = BASELINES_DIR / case_name / "metrics.json"
    if not baseline_json.exists():
        raise unittest.SkipTest(f"baseline missing: {baseline_json}")
    with tempfile.NamedTemporaryFile(
        "w", suffix=f"_{case_name}_actual.json", delete=False
    ) as fh:
        json.dump(actual, fh)
        actual_path = Path(fh.name)
    try:
        res = subprocess.run(
            [
                sys.executable,
                str(COMPARE_SCRIPT),
                "--baseline", str(baseline_json),
                "--actual",   str(actual_path),
                "--tolerance", str(tol),
            ],
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            # Echo full stdout so test output shows *which* fields drifted.
            raise AssertionError(
                f"compare_metrics FAIL for {case_name}:\n"
                f"--- stdout ---\n{res.stdout}\n"
                f"--- stderr ---\n{res.stderr}"
            )
    finally:
        try:
            actual_path.unlink()
        except OSError:
            pass


@unittest.skipUnless(
    _any_so_exists(),
    "libwrxapi.so not built at any candidate path "
    "(wrx/libwrxapi.so or lib/libwrxapi.so); "
    "run `make -C wrx libwrxapi.so`",
)
@unittest.skipUnless(_wrxlib_importable(), "python/wrxlib not importable")
@unittest.skipUnless(COMPARE_SCRIPT.exists(), f"{COMPARE_SCRIPT} missing")
@unittest.skipUnless(
    RUN_OK,
    "WRX_RUN_OK=1 required: wrx_run may segfault on libgrf::grd1d "
    "in the current L-4 build (see README.md Known limitation).",
)
class TestEquivalence(unittest.TestCase):
    """Layer 1: match Phase 0 Fortran baseline at 1e-10."""

    # The tolerance is deliberately exposed as a class attribute so a
    # derived test (e.g. a softer-tol CI job) can override it without
    # re-implementing the body.
    TOLERANCE = "1e-10"

    def _check_case(self, fixture_module) -> None:
        """Run one fixture and diff vs its baseline.

        The fixture module must expose ``apply`` / ``NRAY_REQUEST`` /
        ``BASELINE_NAME`` (see :mod:`fixtures.wrx_iter01_params`).
        """
        actual = _run_case(
            fixture_module.apply,
            nray_request=fixture_module.NRAY_REQUEST,
        )
        _compare_with_baseline(
            actual, fixture_module.BASELINE_NAME, self.TOLERANCE,
        )

    def test_iter01(self):
        # Local import so collection works even if the fixture is
        # syntactically invalid (failure reported per-test, not globally).
        from wrxlib.tests.fixtures import wrx_iter01_params as f
        self._check_case(f)

    def test_demo(self):
        from wrxlib.tests.fixtures import wrx_demo_params as f
        self._check_case(f)


if __name__ == "__main__":
    unittest.main()
