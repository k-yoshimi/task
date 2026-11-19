"""Layer 1: equivalence between the libtotapi.so replay and the Phase 0
Fortran baseline, compared at tolerance 1e-10.

For each case (``tot_demo2014_short``, ``tot_ht6m_short``):

1. open a :class:`totlib.Tot` handle (loads ``tot/libtotapi.so``),
2. replay the registered subset of the namelist fixture via
   :py:meth:`~totlib.Tot.set_param` /
   :py:meth:`~totlib.Tot.set_param_str`,
3. advance the integrated simulation for the fixture's ``NTMAX``,
4. serialise the resulting :class:`~totlib.state.TotState` via
   :py:meth:`~totlib.state.TotState.to_dict`,
5. compare against ``test_run/baselines/<case>/metrics.json`` using
   ``test_run/scripts/compare_metrics.py`` with tolerance ``1e-10``.

Skip gates (all must pass for the class to run):

* ``libtotapi.so`` is importable via :func:`totlib._ffi._candidate_paths`
  (covers both ``tot/libtotapi.so`` and ``lib/libtotapi.so`` and an
  explicit ``TOTLIB_PATH`` override),
* the baseline JSON exists under ``test_run/baselines/``.

L-6 status: ``tot_init`` / ``tot_run`` / ``tot_get_state`` /
``tot_finalize`` are now wired to the per-module ``*_api_*`` fan-out
(tr + ti + fp + wrx), so the equivalence diff runs end-to-end. The
``TOT_RUN_OK`` opt-in gate that previously guarded these tests has
been retired (mirrors what was done for ``EQ_RUN_OK`` earlier).

See ``docs/superpowers/plans/2026-04-18-tot-library-L6-test-4layers.md``
Task 4 for the iteration protocol when the 1e-10 match is not yet met.
"""
from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
PYTHON_ROOT = REPO / "python"
BASELINES_DIR = REPO / "test_run" / "baselines"
FIXTURES_DIR = HERE.parent / "fixtures"
COMPARE_SCRIPT = REPO / "test_run" / "scripts" / "compare_metrics.py"

# Make ``import totlib`` work whether tests are launched from the repo
# root (PYTHONPATH=python) or from inside python/totlib/tests/.
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from totlib import _ffi  # noqa: E402


def _any_so_exists() -> bool:
    """True if libtotapi.so is present at any known candidate path.

    Honours ``TOTLIB_PATH`` so a user-built .so outside the repo is
    picked up without changing the test.
    """
    env = os.environ.get("TOTLIB_PATH")
    if env and Path(env).exists():
        return True
    return any(p.exists() for p in _ffi._candidate_paths())


def _totlib_importable() -> bool:
    """Importable check for totlib -- libtotapi.so is loaded lazily so
    we only verify the Python package."""
    try:
        import totlib  # noqa: F401
    except Exception:
        return False
    return True


@contextlib.contextmanager
def _isolated_cwd_with_eqdata(case_name: str):
    """chdir into a temp dir; pre-populate it with the case's eqdata.

    Some fixtures (e.g. tot_ht6m_short) load an eqdata file from cwd
    via KNAMEQ. When the equivalence test runs from the repo root that
    file is absent. We mirror what the run_tests.sh framework does for
    the standalone binary: stage a temp cwd and seed it with any
    eqdata-* / eqdata.* file the Phase 0 baseline run produced under
    ``test_run/test_output/<case>/``. Cases that need no eqdata
    (e.g. tot_demo2014_short which generates its own via the eq prep
    path) still benefit from the isolated cwd because totregress's
    dump file does not pollute the repo root.

    Two-tier eqdata source (mirrors eqlib/trlib test_equivalence):
    prefer dev-generated eqdata under ``test_run/test_output/<case>/``,
    fall back to the committed fixture under ``FIXTURES_DIR``. This
    keeps the local-regen-then-test loop honoring fresh data while
    letting CI / fresh checkouts run without depending on the upstream
    ``tot/tot`` staging step (CLAUDE.md §Test-suite discipline,
    feedback_equivalence_must_pass.md).
    """
    src = REPO / "test_run" / "test_output" / case_name
    prev_cwd = Path.cwd()
    with tempfile.TemporaryDirectory(prefix=f"totlib_eq_{case_name}_") as tmpd:
        if src.is_dir():
            for pat in ("eqdata-*", "eqdata.*"):
                for f in src.glob(pat):
                    shutil.copy2(f, Path(tmpd) / f.name)
        if FIXTURES_DIR.is_dir():
            for pat in ("eqdata-*", "eqdata.*"):
                for f in FIXTURES_DIR.glob(pat):
                    target = Path(tmpd) / f.name
                    if not target.exists():
                        shutil.copy2(f, target)
        try:
            os.chdir(tmpd)
            yield Path(tmpd)
        finally:
            os.chdir(prev_cwd)


def _run_case(apply_fn, ntmax: int, case_name: str = "default") -> dict:
    """Drive a single libtotapi.so cycle and return the to_dict payload.

    Keeping this outside ``TestEquivalence`` lets Layer 4 reuse the
    same replay helper without importing a TestCase class.
    """
    from totlib import Tot  # noqa: WPS433 (intentional local import)

    with _isolated_cwd_with_eqdata(case_name):
        with Tot() as tot:
            apply_fn(tot)
            tot.run(int(ntmax))
            state = tot.get_state()
    return state.to_dict()


def _compare_with_baseline(actual: dict, case_name: str, tol: str = "1e-10") -> None:
    """Write ``actual`` to a temp JSON and diff it vs the baseline.

    Raises :class:`AssertionError` on any drift so the unittest framework
    reports it as a FAIL rather than an ERROR.

    When ``REGEN_OUTPUT_DIR`` is set (CI baseline-capture mode) the freshly
    computed ``actual`` is ALSO written to
    ``$REGEN_OUTPUT_DIR/<case>/metrics.json`` so the CI compiler's values can be
    downloaded and committed as the new baseline. The diff/assert below is
    unchanged — this is purely additive capture.
    """
    # NOTE: keep this capture block in sync with the wrxlib copy.
    regen_dir = os.environ.get("REGEN_OUTPUT_DIR")
    if regen_dir:
        try:
            out_path = Path(regen_dir) / case_name / "metrics.json"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(actual, indent=2))
        except OSError:
            pass  # capture is best-effort; never let it change pass/fail
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


IS_LINUX = sys.platform.startswith("linux")


@unittest.skipUnless(
    IS_LINUX,
    "Equivalence tests are Linux-canonical. The 1e-10 baselines "
    "live in test_run/baselines/<case>/metrics.json and were "
    "generated on Linux gfortran 13.x (Ubuntu CI runner). macOS / "
    "non-Linux dev runs the libtotapi.so via the Python wrapper; "
    "correctness is verified by Linux CI on every push. See "
    "docs/baseline-policy.md.",
)
@unittest.skipUnless(
    _any_so_exists(),
    "libtotapi.so not built at any candidate path "
    "(tot/libtotapi.so or lib/libtotapi.so); "
    "run `make -C tot libtotapi.so`",
)
@unittest.skipUnless(_totlib_importable(), "python/totlib not importable")
@unittest.skipUnless(COMPARE_SCRIPT.exists(), f"{COMPARE_SCRIPT} missing")
class TestEquivalence(unittest.TestCase):
    """Layer 1: match Phase 0 Fortran baseline at 1e-10."""

    # Tolerance is exposed as a class attribute so a derived test
    # (e.g. a softer-tol CI job) can override it without re-implementing
    # the body.
    TOLERANCE = "1e-10"

    def _check_case(self, fixture_module) -> None:
        """Run one fixture and diff vs its baseline.

        The fixture module must expose ``apply`` / ``NTMAX`` /
        ``BASELINE_NAME`` (see :mod:`fixtures.tot_demo2014_params`).

        When the fixture references a KNAMEQ eqdata file, accept it
        from either ``test_run/test_output/<case>/`` (dev-generated,
        preferred) or ``FIXTURES_DIR`` (committed fallback); skip
        cleanly only if both locations are missing. Same two-tier
        pattern as ``trlib/tests/test_equivalence.py`` and
        ``eqlib/tests/test_equivalence.py``. Without this guard CI
        without baseline data would SIGABRT deep inside eq_load and
        crash the pytest-forked worker, producing an
        ``INTERNALERROR>`` instead of an actionable skip.
        """
        # Look for any KNAMEQ entry in STRINGS (eq:KNAMEQ or tr:KNAMEQ);
        # all tot equivalence fixtures that need eqdata set both.
        knameq = None
        for key in ("eq:KNAMEQ", "tr:KNAMEQ"):
            v = getattr(fixture_module, "STRINGS", {}).get(key)
            if v:
                knameq = v
                break
        if knameq:
            candidate = REPO / "test_run" / "test_output" / fixture_module.BASELINE_NAME
            if (candidate / knameq).exists():
                # Prefer dev-generated eqdata (Phase-0 runner output)
                # so local-regen-then-test workflows see their freshly
                # generated data instead of the committed reference.
                pass
            elif (FIXTURES_DIR / knameq).exists():
                # CI / fresh checkout: fall back to the committed
                # fixture so the equivalence test runs instead of
                # silently skipping (CLAUDE.md §Test-suite discipline,
                # feedback_equivalence_must_pass.md). Verbatim structural
                # mirror of eqlib/trlib test_equivalence two-tier gate.
                pass
            else:
                self.skipTest(
                    f"eqdata '{knameq}' missing under {candidate} or "
                    f"{FIXTURES_DIR}; run "
                    f"`./test_run/run_tests.sh "
                    f"{fixture_module.BASELINE_NAME}` first."
                )
        actual = _run_case(
            fixture_module.apply,
            ntmax=fixture_module.NTMAX,
            case_name=fixture_module.BASELINE_NAME,
        )
        _compare_with_baseline(
            actual, fixture_module.BASELINE_NAME, self.TOLERANCE,
        )

    def test_tot_demo2014_short(self):
        # Local import so collection works even if the fixture is
        # syntactically invalid (failure reported per-test, not globally).
        from totlib.tests.fixtures import tot_demo2014_params as f
        self._check_case(f)

    def test_tot_ht6m_short(self):
        from totlib.tests.fixtures import tot_ht6m_params as f
        self._check_case(f)


if __name__ == "__main__":
    unittest.main()
