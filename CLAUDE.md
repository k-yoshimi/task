# CLAUDE.md

Operational discipline for this repository. Auto-loaded at session start.
**User instructions and CLAUDE.md override default behaviour.**

## Pre-push gate (NON-NEGOTIABLE)

Before every `git push` (no exceptions, including pushes that fix Bugbot
comments or trivial 1-line CI tweaks):

1. **Local test**: run the relevant `pytest` locally with the SAME flags
   the CI workflow uses (`--forked --timeout=120 --timeout-method=signal`
   for this repo). A passing local run is required for tests that changed
   or that exercise the same module as the changed Fortran.
2. **Code review**: launch `Agent(subagent_type="feature-dev:code-reviewer",
   …)` on the diff since the last reviewed commit. Paste its HIGH /
   MED findings back to the user before pushing.
3. **Write a pre-push marker**: `touch .git/REVIEW_OK_$(git rev-parse HEAD)`
   — the pre-push hook blocks push without it.

The hook exists at `.git/hooks/pre-push` (see `scripts/pre-push.sh`). If
you rewrite history with `git commit --amend` or `git rebase`, the SHA
changes — re-review and re-marker.

## Test-suite discipline (NON-NEGOTIABLE)

- **Never use `--ignore-glob`, `--deselect`, or `pytest.mark.skip` to
  cover up a broken test.** If a test fails in CI, fix the bug or mark
  `@pytest.mark.xfail(strict=True, reason="#<issue>")`. `strict=True`
  makes XPASS fail CI red, which automates marker removal once the fix
  lands.
- **Equivalence tests at 1e-10 tolerance MUST pass.** A SKIPped
  equivalence test is not verification — it is invisibility.
- **Commit a minimal fixture (≤100 KB) if CI cannot generate it**,
  rather than letting tests skipTest on missing data. Add an explicit
  `.gitignore` negation (`!path/to/fixture`) if the default rule would
  swallow it.

## Approach discipline

- **Never `ignore` warnings as a workaround.** If pytest reports 300+
  warnings, the root cause is real. Investigate (often the warning is
  flagging the same bug class CI is failing on, as in the fork-
  after-thread case on 2026-04-21).
- **Never skip hooks** (`--no-verify`, `--no-gpg-sign`) or `--admin`
  merges. Wait for Bugbot COMPLETED before merging.
- **For memory-corruption / heap-reuse / SIGABRT / uninit-read bugs**:
  use `valgrind` (installed on this machine). Fortran `-ffpe-trap`
  catches only float traps; valgrind catches heap-layout bugs without
  perturbing the heap.
- **Long-running pytest output must be bounded**: `timeout <N>` +
  `head -c 1M` on the pipe. Do NOT `pytest 2>&1 | tail | tee` — the
  upstream pipe isn't bounded and can fill the disk (see 2026-04-20
  incident: 1.6 TB in `/tmp`).

## Fortran library discipline

- **Library-reachable `STOP`** aborts the host process (pytest /
  Python / MCP server). Replace with `ierr = <code>; RETURN` and
  propagate. Tracked in issue #142.
- **Parameter validation should be batch + pre-run**, not scattered
  at `set_param` / `allocate` / `run` time. Tracked in issue #143.
- **Module-level state doesn't fully reset** between `finalize` and
  the next `init`. For tests that reinitialize in-process, use
  `--forked` isolation; for production reinit, add explicit
  `DEALLOCATE` / zero-init in `finalize`.

## Cross-references

The detailed memory entries (full context, past incidents) live in
`$CLAUDE_MEMORY_DIR/memory/` — this file is the actionable subset.
If you catch yourself about to violate a rule above, stop and re-read
the matching memory file:

- Pre-push gate → `feedback_review_before_push.md`
- Test-suite discipline → `feedback_never_skip_tests.md`,
  `feedback_equivalence_must_pass.md`
- Warnings-are-real → (this file; new rule as of 2026-04-22)
- Bugbot protocol → `feedback_bugbot_wait.md`,
  `feedback_cursor_review.md`
- Disk safety → `feedback_pytest_disk_runaway.md`
