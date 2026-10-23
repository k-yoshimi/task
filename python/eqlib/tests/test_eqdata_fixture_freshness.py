"""The committed eqdata fixtures must not drift out of date against eqinit.f90.

``eq/eqfile.f90`` writes ``NSGMAX..NTVMAX`` into the blob and ``EQRTSK`` reads
``NTVMAX`` back OUT, overwriting the in-memory value. So a committed fixture is
not inert data -- it is a parameter injector that wins over ``eqinit.f90``, and
a stale one silently reverts the parameter for every test that loads it,
including the 1e-10 gates meant to catch exactly that kind of change. See
``docs/baseline-policy.md`` and the commit that added this file.

Every expected value is parsed from ``eq/eqinit.f90`` rather than hardcoded, so
this fires in both directions: a stale fixture against current source, and a
bumped source against current fixtures. ``regen-baselines.yml``'s collect step
uses the same rule -- they must not diverge, or the remediation this test
directs people to would reject a correctly regenerated blob.

Checks are file decoding, so they also produce a verdict on macOS, where the
1e-10 gates skip (#213). For ``eqdata-HT6M`` and ``eqdata.demo2014`` they are
the ONLY gate: both CI jobs generate tier-1 eqdata and
``_isolated_cwd_with_eqdata`` copies tier 1 unconditionally, so the committed
copies are shadowed in every numerical test, and their other in-CI consumer
(``test_mono_bpsd_smoke.py``) asserts return codes.

Collection imports ``eqlib`` (this module lives in that package), so it needs
``PYTHONPATH=python`` -- but not the built ``.so``.
"""
from __future__ import annotations

import re
import struct
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve()
REPO = _HERE.parents[3]

# The six committed paths are FOUR distinct blobs: eqlib/ and trlib/ hold
# byte-identical copies of ITER01 and TST-2 (asserted below).
FIXTURES = [
    REPO / "python" / "eqlib" / "tests" / "fixtures" / "eqdata.ITER01",
    REPO / "python" / "eqlib" / "tests" / "fixtures" / "eqdata.TST-2",
    REPO / "python" / "trlib" / "tests" / "fixtures" / "eqdata.ITER01",
    REPO / "python" / "trlib" / "tests" / "fixtures" / "eqdata.TST-2",
    REPO / "python" / "totlib" / "tests" / "fixtures" / "eqdata-HT6M",
    REPO / "python" / "totlib" / "tests" / "fixtures" / "eqdata.demo2014",
]

DUPLICATE_PAIRS = [
    ("eqdata.ITER01", REPO / "python" / "eqlib" / "tests" / "fixtures" / "eqdata.ITER01",
     REPO / "python" / "trlib" / "tests" / "fixtures" / "eqdata.ITER01"),
    ("eqdata.TST-2", REPO / "python" / "eqlib" / "tests" / "fixtures" / "eqdata.TST-2",
     REPO / "python" / "trlib" / "tests" / "fixtures" / "eqdata.TST-2"),
]

EQINIT = REPO / "eq" / "eqinit.f90"

# Index of the NSGMAX..NTVMAX record and the position of NTVMAX within it,
# both fixed by eq/eqfile.f90's WRITE order. Named rather than searched, so a
# grid size that happened to make some REAL(8) array 32 bytes long cannot be
# mistaken for the header (the "exactly one" assertion below is the backstop).
HEADER_FIELDS = ("NSGMAX", "NTGMAX", "NUGMAX", "NRMAX", "NTHMAX",
                 "NSUMAX", "NRVMAX", "NTVMAX")


def _records(path: Path) -> list[bytes]:
    """Split a gfortran unformatted-sequential file into its record payloads.

    Each record is int32 length, payload, int32 length. Native-endian; '<' is
    correct on every platform this repo targets (all little-endian).
    """
    data = path.read_bytes()
    out: list[bytes] = []
    off = 0
    while off < len(data):
        if len(data) - off < 8:
            raise AssertionError(
                f"{path}: truncated at byte {off} -- no room for a record header"
            )
        (n,) = struct.unpack("<i", data[off:off + 4])
        if n < 0 or len(data) - off < 8 + n:
            raise AssertionError(
                f"{path}: record {len(out)} declares {n} bytes, "
                f"{len(data) - off - 8} remain"
            )
        (trailer,) = struct.unpack("<i", data[off + 4 + n:off + 8 + n])
        if trailer != n:
            raise AssertionError(
                f"{path}: record {len(out)} trailer {trailer} != header {n} "
                "-- file is corrupt or was written by a different writer"
            )
        out.append(data[off + 4:off + 4 + n])
        off += n + 8
    return out


def _header(path: Path) -> dict[str, int]:
    """Return the NSGMAX..NTVMAX record as a dict."""
    hits = [r for r in _records(path) if len(r) == 32]
    assert len(hits) == 1, (
        f"{path}: expected exactly one 32-byte record (the NSGMAX..NTVMAX "
        f"header written by eq/eqfile.f90), found {len(hits)}. With more than "
        "one, the header cannot be identified unambiguously -- a REAL(8) "
        "array of 4 elements is also 32 bytes."
    )
    return dict(zip(HEADER_FIELDS, struct.unpack("<8i", hits[0])))


def _source_default(name: str) -> int:
    """Read an integer default out of eq/eqinit.f90.

    Deliberately parsed from source rather than hardcoded: that is what makes
    this a recurrence guard instead of a second place to forget to update.
    """
    # Optional trailing `! comment` is allowed: rejecting it would make an
    # innocuous source edit look like a fixture problem. Case-insensitive
    # because Fortran is, and this directory is mid-F90-modernisation.
    #
    # Known blind spot, stated rather than papered over: a single-line
    # `IF (...) NTVMAX = 800` is invisible to this parser -- it matches
    # nothing, so the assertion below fires and blocks, which is loud but
    # misattributed. A `&` continuation behaves the same way. Neither form
    # is used for these eight today (checked); if one appears, extend the
    # parser rather than the exception list.
    pattern = re.compile(rf"^\s*{name}\s*=\s*(\d+)\s*(?:!.*)?$", re.IGNORECASE)
    found = []
    for line in EQINIT.read_text().splitlines():
        stripped = line.lstrip()
        if stripped.startswith("!") or (line[:1] in ("C", "c", "*") and line[1:2] != " "):
            continue  # comment line (free-form '!' or fixed-form col-1 marker)
        m = pattern.match(line)
        if m:
            found.append(int(m.group(1)))
    assert len(found) == 1, (
        f"expected exactly one uncommented `{name} = <int>` in {EQINIT}, "
        f"found {found}. Update this test's parser alongside the source."
    )
    return found[0]


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: f"{p.parent.parent.parent.name}/{p.name}")
def test_fixture_ntvmax_matches_eqinit(path: Path):
    """A committed blob must not pin NTVMAX to a value eqinit.f90 no longer uses."""
    assert path.is_file(), f"{path} is missing"
    expected = _source_default("NTVMAX")
    actual = _header(path)["NTVMAX"]
    assert actual == expected, (
        f"{path.relative_to(REPO)} carries NTVMAX={actual} but "
        f"eq/eqinit.f90 now defaults to {expected}.\n\n"
        "EQRTSK reads NTVMAX back out of the blob and overwrites the in-memory "
        "value, so this fixture silently reverts the parameter for every test "
        "that loads it -- including the 1e-10 gates that are supposed to catch "
        "exactly this kind of change.\n\n"
        "Regenerate the fixtures AND their baselines together, from one run of "
        ".github/workflows/regen-baselines.yml on the canonical platform. See "
        "docs/baseline-policy.md."
    )


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: f"{p.parent.parent.parent.name}/{p.name}")
def test_fixture_structure_is_intact(path: Path):
    """Record framing and grid dimensions are what eq/eqfile.f90 writes.

    Catches a truncated or half-written fixture, which would otherwise surface
    as an inscrutable Fortran read error inside a test that is nominally about
    physics.
    """
    records = _records(path)
    assert len(records) == 28, (
        f"{path.relative_to(REPO)}: {len(records)} records, expected 28 "
        "(the EQSAVE record sequence in eq/eqfile.f90)"
    )
    hdr = _header(path)
    # Grid sizes are checked against eqinit.f90 too, not hardcoded. They are
    # the same kind of value as NTVMAX -- plain defaults a few lines away in
    # the same file, overridden by none of the six generating inputs -- so
    # hardcoding them would reintroduce exactly the second-place-to-forget
    # this test exists to remove. Hardcoded, an NRMAX 50->100 graft would fail
    # here on a CORRECTLY regenerated fixture, and the cheapest response
    # (edit the tuple) is indistinguishable from silencing the test.
    for field in HEADER_FIELDS:
        expected = _source_default(field)
        assert hdr[field] == expected, (
            f"{path.relative_to(REPO)}: {field}={hdr[field]}, but "
            f"eq/eqinit.f90 defaults to {expected}. Regenerate the fixtures "
            "and their baselines together -- see docs/baseline-policy.md."
        )


# Every input that can carry an `&eq` namelist for the four blob-producing
# cases. All eight header names are `/EQ/` members (eq/eqinit.f90:446,448), so
# any of these files legitimately could override one.
#
# eq.injt60 writes eqdata.jt60, which is NOT committed -- it is here as
# defence, not because it produces a fixture.
#
# tot_ht6m_short.trparm is deliberately EXCLUDED, on two independent
# grounds -- neither of them an observed failure; the risk is latent:
#   - it is an `&tr` file (tr/trparm.f90:86 declares NAMELIST /TR/ and nothing
#     else), so it cannot set /EQ/ at all;
#   - and scanning non-`&eq` inputs invites a false positive: NRMAX is also
#     a /TR/ member (tr/trparm.f90:92) and a /FP/ one (fp_iter01.in:15),
#     NTHMAX is /FP/ (fp_iter01.in:21), and ti_ar.in:17 sets NRMAX again.
#     Setting a transport or kinetic radial grid there is entirely normal.
#
#     Note it does NOT follow that such a value cannot reach the blob:
#     tr/trmetric.f90:33-38 pushes `nrmax+1`, `nthmax=64` and `nsumax=0`
#     INTO the /EQ/ namelist via eq_parm(2,...) whenever modelg is 3, 5 or
#     8 -- and tot_ht6m_short.trparm:2 sets modelg=3, so that branch is
#     live for this very case. Two things make the exclusion safe anyway,
#     and the second does not depend on ordering:
#       (i) tot_ht6m_short.in runs the eq sub-menu through `s` (EQSAVE,
#           eq/eqmenu.f90:97) and `q` before it ever enters `tr`, so
#           eqdata-HT6M is written before trmetric can propagate anything;
#      (ii) and for MODELG=3, trmetric's own eq_load path reaches EQRTSK,
#           where eq/eqfile.f90:162 READS all eight header names back out
#           of the blob -- overwriting whatever eq_parm just pushed. The
#           blob dictates these values; it does not receive them.
#     (i) alone would lapse if someone added a post-`tr` eq/`s` to re-save
#     the evolved equilibrium, and nothing asserts that it has not been.
GENERATING_INPUTS = [
    REPO / "eq" / "in" / "eq.ITER01.in",
    REPO / "eq" / "in" / "eq.TST-2.in",
    REPO / "eq" / "in" / "eq.injt60",
    REPO / "test_run" / "inputs" / "tot_ht6m_short.eqparm",
    # The menu stdin for tot_ht6m_short -- the case that writes eqdata-HT6M.
    # It can carry a `p` + `&eq ... &end` block exactly as
    # tot_demo2014_short.in does, so omitting it left the guard blind to the
    # likeliest override site for that blob.
    REPO / "test_run" / "inputs" / "tot_ht6m_short.in",
    REPO / "test_run" / "inputs" / "tot_demo2014_short.in",
]


@pytest.mark.parametrize("src", GENERATING_INPUTS, ids=lambda p: p.name)
def test_generating_inputs_do_not_override_header_fields(src: Path):
    """Guard the invariant the header assertions rest on.

    If an input ever sets one of these, a CORRECTLY regenerated fixture would
    fail those assertions and their advice ("regenerate") would not fix it.
    Failing here instead names the actual cause.
    """
    if not src.is_file():
        pytest.skip(f"{src} not present")
    text = src.read_text(errors="replace")
    offenders = []
    for field in HEADER_FIELDS:
        for n, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("!"):
                continue
            if re.search(rf"\b{field}\s*=", line, re.IGNORECASE):
                offenders.append(f"{src.name}:{n}: {line.strip()}")
    assert not offenders, (
        "a generating input now sets a header field that "
        "test_fixture_structure_is_intact compares against eq/eqinit.f90's "
        "global default:\n  " + "\n  ".join(offenders) + "\n\n"
        "Either drop the override, or make the header assertions read it "
        "instead of the eqinit default."
    )


@pytest.mark.parametrize("name,a,b", DUPLICATE_PAIRS, ids=[p[0] for p in DUPLICATE_PAIRS])
def test_duplicated_fixtures_stay_identical(name: str, a: Path, b: Path):
    """eqlib/ and trlib/ hold the same artefact; regenerating must update both.

    They are two copies of one blob produced by one eq run (eq_iter01 /
    eq_tst2). If a regeneration refreshes one and misses the other, eqlib and
    trlib silently start testing different equilibria.
    """
    assert a.read_bytes() == b.read_bytes(), (
        f"{a.relative_to(REPO)} and {b.relative_to(REPO)} differ. They are "
        f"copies of the same {name} artefact; regenerate both from the same run."
    )
