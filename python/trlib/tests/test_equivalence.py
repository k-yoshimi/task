"""Layer 1: equivalence between the libtrapi.so replay and the Phase 0
Fortran baseline, compared at tolerance 1e-10.

For each case (``tr_iter01``, ``tr_tst2``):

1. open a :class:`trlib.Trlib` handle (loads ``tr/libtrapi.so``),
2. replay the registered subset of the namelist fixture via
   :py:meth:`~trlib.Trlib.set_param` /
   :py:meth:`~trlib.Trlib.set_param_str`,
3. advance the simulation for the fixture's ``NTMAX``,
4. serialise the resulting :class:`~trlib.state.TrState` via
   :py:meth:`~trlib.state.TrState.to_dict`,
5. compare against ``test_run/baselines/<case>/metrics.json`` using
   ``test_run/scripts/compare_metrics.py`` with tolerance ``1e-10``.

If ``libtrapi.so`` has not been built (or ``python/trlib`` is not
available) the whole class is skipped -- this matches the design
contract that Layer 1 is an *integration* test gated on L-4 + L-5.

MODELG=3 cases (tr_iter01 / tr_tst2) read ``eqdata.<DEV>`` from the
process's current working directory. The Phase-0 baselines are
generated from ``test_run/test_output/<case>/`` with the corresponding
eqdata file pre-copied; we honor the same convention here by changing
into that directory for each replay. If the eqdata file is missing,
the test is skipped with a message that points at the Phase-0 runner.

See ``docs/superpowers/plans/2026-04-18-tr-library-L6-test-4layers.md``
Task 2 for the iteration protocol when the 1e-10 match is not yet met.
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

import pytest

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
PYTHON_ROOT = REPO / "python"
BASELINES_DIR = REPO / "test_run" / "baselines"
TEST_OUTPUT_DIR = REPO / "test_run" / "test_output"
FIXTURES_DIR = HERE.parent / "fixtures"
COMPARE_SCRIPT = REPO / "test_run" / "scripts" / "compare_metrics.py"
DEFAULT_SO = REPO / "tr" / "libtrapi.so"


@contextlib.contextmanager
def _pushd(target: Path):
    """chdir to ``target`` inside a ``with`` block, restore on exit."""
    prev = Path.cwd()
    os.chdir(target)
    try:
        yield target
    finally:
        os.chdir(prev)

# Make ``import trlib`` work whether tests are launched from the repo
# root (PYTHONPATH=python) or from inside python/trlib/tests/.
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))


def _run_case(apply_fn, ntmax: int, cwd: Path | None = None) -> dict:
    """Drive a single libtrapi.so cycle and return the metrics dict.

    Parameters
    ----------
    apply_fn:
        Callable that takes a :class:`trlib.Trlib` handle and sets all
        fixture parameters via ``set_param`` / ``set_param_str``.
    ntmax:
        Number of time steps to advance.
    cwd:
        If provided, :func:`os.chdir` into this directory for the whole
        replay. MODELG=3 cases need the directory to contain the
        ``eqdata.<DEV>`` file referenced by ``KNAMEQ``.

    Keeping this outside ``TestEquivalence`` lets Layer 4 reuse the
    same replay helper without importing a TestCase class.
    """
    from trlib import Trlib  # noqa: WPS433 (intentional local import)

    if cwd is None:
        ctx = contextlib.nullcontext()
    else:
        ctx = _pushd(cwd)

    with ctx:
        with Trlib() as tr:
            apply_fn(tr)
            tr.run(int(ntmax))
            state = tr.get_state()
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


def _trlib_importable() -> bool:
    """Importable check for trlib -- libtrapi.so is loaded lazily so we
    only verify the Python package."""
    try:
        import trlib  # noqa: F401
    except Exception:
        return False
    return True


@unittest.skipUnless(
    DEFAULT_SO.exists(),
    f"libtrapi.so not built at {DEFAULT_SO}; run `make -C tr libtrapi.so`",
)
@unittest.skipUnless(_trlib_importable(), "python/trlib not importable")
@unittest.skipUnless(COMPARE_SCRIPT.exists(), f"{COMPARE_SCRIPT} missing")
class TestEquivalence(unittest.TestCase):
    """Layer 1: match Phase 0 Fortran baseline at 1e-10."""

    # The tolerance is deliberately exposed as a class attribute so a
    # derived test (e.g. a softer-tol CI job) can override it without
    # re-implementing the body.
    TOLERANCE = "1e-10"

    def _check_case(self, fixture_module) -> None:
        """Run one fixture and diff vs its baseline.

        The fixture module must expose ``apply`` / ``NTMAX`` /
        ``BASELINE_NAME`` (see :mod:`fixtures.tr_iter01_params`).

        When the fixture ships a STRINGS dict with ``KNAMEQ``, the
        replay runs inside ``test_run/test_output/<case>/`` so that
        the referenced eqdata file is visible to tr_prep. The Phase-0
        runner writes that directory as a side effect of running
        ``./run_tests.sh <case>``.
        """
        cwd = None
        knameq = getattr(fixture_module, "STRINGS", {}).get("KNAMEQ")
        if knameq:
            candidate = TEST_OUTPUT_DIR / fixture_module.BASELINE_NAME
            if (candidate / knameq).exists():
                # Prefer dev-generated eqdata (Phase-0 runner output)
                # so local-regen-then-test workflows see their freshly
                # generated data instead of the committed reference.
                cwd = candidate
            elif (FIXTURES_DIR / knameq).exists():
                # CI / fresh checkout: fall back to the committed
                # fixture so the equivalence test runs instead of
                # silently skipping (CLAUDE.md §Test-suite discipline,
                # feedback_equivalence_must_pass.md).
                cwd = FIXTURES_DIR
            else:
                self.skipTest(
                    f"eqdata '{knameq}' missing under {candidate} or "
                    f"{FIXTURES_DIR}; run "
                    f"`./test_run/run_tests.sh {fixture_module.BASELINE_NAME}` first."
                )
        actual = _run_case(fixture_module.apply, ntmax=fixture_module.NTMAX, cwd=cwd)
        _compare_with_baseline(actual, fixture_module.BASELINE_NAME, self.TOLERANCE)

    def test_iter01(self):
        # Local import so collection works even if the fixture is
        # syntactically invalid (failure reported per-test, not globally).
        from trlib.tests.fixtures import tr_iter01_params as f
        self._check_case(f)

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "#190: tr_tst2 baseline at test_run/baselines/tr_tst2/metrics.json "
            "is missing AJRFT (pre-AJRFT 13-scalar shape). PR #187 added AJRFT "
            "to TR's dump path; #193 regenerated tr_iter01 baseline but tr_tst2 "
            "baseline regen is blocked by upstream eq_tst2 drift (~3e-9 > 1e-10). "
            "Remove this xfail when #190 closes."
        ),
    )
    def test_tst2(self):
        from trlib.tests.fixtures import tr_tst2_params as f
        self._check_case(f)


if __name__ == "__main__":
    unittest.main()
