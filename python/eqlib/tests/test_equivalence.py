"""Layer 1: equivalence between the libeqapi.so replay and the Phase 0
Fortran baseline, compared at tolerance 1e-10.

For each case (``eq_iter01``, ``eq_tst2``):

1. open an :class:`eqlib.Eq` handle (loads ``eq/libeqapi.so``),
2. replay the registered subset of the namelist fixture via
   :py:meth:`~eqlib.Eq.set_param` /
   :py:meth:`~eqlib.Eq.set_param_str`,
3. drive ``eq_run`` with the fixture's ``MODE`` (default 1 == real
   EQDSK load),
4. serialise the resulting :class:`~eqlib.state.EqState` via
   :py:meth:`~eqlib.state.EqState.to_dict`,
5. compare against ``test_run/baselines/<case>/metrics.json`` using
   ``test_run/scripts/compare_metrics.py`` with tolerance ``1e-10``.

Skip gates (all must pass for the class to run):

* libeqapi.so is importable via :func:`eqlib._ffi._candidate_paths`
  (covers both ``eq/libeqapi.so`` and ``lib/libeqapi.so`` and an
  explicit ``EQLIB_PATH`` override),
* eqlib python package is importable,
* compare_metrics.py is reachable.

The fixture's eqdata file (``KNAMEQ``) must live under
``test_run/test_output/<case>/`` -- if not, the per-test
``_check_case`` emits a ``self.skipTest`` with instructions to run
``test_run/run_tests.sh <case>`` first.

History: previously this class was also gated behind ``EQ_RUN_OK=1``
because the L-5 ``EqState`` schema was thought to diverge from the
Phase 0 baseline. In practice ``compare_metrics.py`` only enforces
the ``_DIMENSION_KEYS`` / ``scalars`` / ``profile`` overlap, all of
which the L-5 ``EqState.to_dict`` already emits, so the gate is no
longer needed: tolerance 1e-10 PASSes today.
"""
from __future__ import annotations

import contextlib
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
TEST_OUTPUT_DIR = REPO / "test_run" / "test_output"
COMPARE_SCRIPT = REPO / "test_run" / "scripts" / "compare_metrics.py"


@contextlib.contextmanager
def _pushd(target: Path):
    """chdir to ``target`` inside a ``with`` block, restore on exit.

    EQRTSK / EQDSK loads in eqfile.f90 open ``KNAMEQ`` relative to the
    current working directory, so MODELG=3/5/8/15 fixtures must run
    from ``test_run/test_output/<case>/`` where the eqdata file lives.
    """
    prev = Path.cwd()
    os.chdir(target)
    try:
        yield target
    finally:
        os.chdir(prev)

# Make ``import eqlib`` work whether tests are launched from the repo
# root (PYTHONPATH=python) or from inside python/eqlib/tests/.
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from eqlib import _ffi  # noqa: E402


def _any_so_exists() -> bool:
    """True if libeqapi.so is present at any known candidate path.

    Also honours ``EQLIB_PATH`` so a user-built .so outside the repo
    is picked up without changing the test.
    """
    env = os.environ.get("EQLIB_PATH")
    if env and Path(env).exists():
        return True
    return any(p.exists() for p in _ffi._candidate_paths())


def _eqlib_importable() -> bool:
    """Importable check for eqlib -- libeqapi.so is loaded lazily so
    we only verify the Python package."""
    try:
        import eqlib  # noqa: F401
    except Exception:
        return False
    return True


def _run_case(apply_fn, mode: int, cwd: Path | None = None) -> dict:
    """Drive a single libeqapi.so cycle and return the to_dict payload.

    Keeping this outside ``TestEquivalence`` lets Layer 4 reuse the
    same replay helper without importing a TestCase class.

    ``cwd`` is the directory eq's file I/O resolves ``KNAMEQ`` against;
    pass the test_output directory that holds the eqdata file.
    """
    from eqlib import Eq  # noqa: WPS433 (intentional local import)

    if cwd is None:
        ctx = contextlib.nullcontext()
    else:
        ctx = _pushd(cwd)

    with ctx:
        with Eq() as eq:
            apply_fn(eq)
            eq.run(mode=int(mode))
            state = eq.get_state()
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
    "libeqapi.so not built at any candidate path "
    "(eq/libeqapi.so or lib/libeqapi.so); "
    "run `make -C eq libeqapi.so`",
)
@unittest.skipUnless(_eqlib_importable(), "python/eqlib not importable")
@unittest.skipUnless(COMPARE_SCRIPT.exists(), f"{COMPARE_SCRIPT} missing")
class TestEquivalence(unittest.TestCase):
    """Layer 1: match Phase 0 Fortran baseline at 1e-10."""

    # The tolerance is deliberately exposed as a class attribute so a
    # derived test (e.g. a softer-tol CI job) can override it without
    # re-implementing the body.
    TOLERANCE = "1e-10"

    def _check_case(self, fixture_module) -> None:
        """Run one fixture and diff vs its baseline.

        The fixture module must expose ``apply`` / ``MODE`` /
        ``BASELINE_NAME`` (see :mod:`fixtures.eq_iter01_params`).

        When the fixture ships a STRINGS dict with KNAMEQ, the replay
        runs inside ``test_run/test_output/<case>/`` so that the
        eqdata file referenced by KNAMEQ is reachable via a relative
        open. The Phase-0 runner writes that directory as a side
        effect of running ``./run_tests.sh <case>``.
        """
        cwd = None
        knameq = getattr(fixture_module, "STRINGS", {}).get("KNAMEQ")
        if knameq:
            candidate = TEST_OUTPUT_DIR / fixture_module.BASELINE_NAME
            if not (candidate / knameq).exists():
                self.skipTest(
                    f"eqdata '{knameq}' missing under {candidate}; "
                    "run `./test_run/run_tests.sh "
                    f"{fixture_module.BASELINE_NAME}` first."
                )
            cwd = candidate
        actual = _run_case(
            fixture_module.apply,
            mode=fixture_module.MODE,
            cwd=cwd,
        )
        _compare_with_baseline(
            actual, fixture_module.BASELINE_NAME, self.TOLERANCE,
        )

    def test_eq_iter01(self):
        # Local import so collection works even if the fixture is
        # syntactically invalid (failure reported per-test, not globally).
        from eqlib.tests.fixtures import eq_iter01_params as f
        self._check_case(f)

    def test_eq_tst2(self):
        from eqlib.tests.fixtures import eq_tst2_params as f
        self._check_case(f)


if __name__ == "__main__":
    unittest.main()
