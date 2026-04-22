# External BPSD patches

The TASK plasma transport modules build against
[ats-fukuyama/bpsd](https://github.com/ats-fukuyama/bpsd) at
`../../bpsd/` (i.e. a sibling clone of `task-private`). Some bugs in
upstream BPSD have been located via valgrind / dump-and-diff and
need patching before the libXapi.so builds in CI and locally.

## Patches in this directory

| File | Issue | Fix in one line |
|------|-------|-----------------|
| `bpsd-species-kid-oob-fix.patch` | #140 (PR #139) | `bpsd_setup_species_kdata` writes `kid(ndmax+1)` — change loop bound to stop at the last full triplet |
| `bpsd-plasmaf-intent-out-init.patch` | #148 | `bpsd_get_plasmaf` `INTENT(OUT)` leaves scalars undefined → garbage `nrmax` selects wrong mode → corrupt `rho` descriptor → SIGABRT. Zero-init the 3 scalar fields at routine entry |

## CI

`.github/workflows/python-tests.yml` step
`Clone BPSD + apply upstream patches (#140 species-kid, #148 plasmaf)`
runs `git clone` then both `git apply` invocations before any build
step. **The patches are applied to a freshly cloned upstream — no
changes to the BPSD repo state survive across CI runs.**

## Local developer setup

Use the helper script (idempotent — safe to re-run):

```bash
bash scripts/apply-bpsd-patches.sh
```

It will:
1. Check each `*.patch` in this directory against `../bpsd` (skips
   already-applied patches via `--reverse --check`).
2. Run `make -C ../bpsd libbpsd.a`.
3. Force-rebuild every `lib<mod>api.so` (tr / fp / ti / wrx / eq /
   tot) so the patched `bpsd_*.o` is statically linked into all of
   them — see *Why "rebuild ALL"* below.

Override the BPSD path with `BPSD_DIR=/some/other/path bash scripts/apply-bpsd-patches.sh`.

**Why "rebuild ALL libXapi.so"**: each `lib<mod>api.so` statically
links its own copy of `bpsd_*.o` from `../../bpsd/*.f90`. At runtime
the dynamic linker resolves `bpsd_get_plasmaf` etc. to whichever
`.so` was loaded first — if even one `.so` has stale BPSD code, the
old buggy version may shadow the patched one. Symptoms: tests pass
on a fresh CI but fail on a developer host that built only a subset.
This was the false-positive that masked #148 for a while.

## Removing a patch

When upstream merges an equivalent fix:

1. Delete the patch file from this directory.
2. Remove the matching `git apply` line from
   `.github/workflows/python-tests.yml`.
3. Update the table at the top of this README.
4. Update the step name in the workflow (currently
   `Clone BPSD + apply upstream patches (#140 species-kid, #148 plasmaf)`)
   to drop the obsolete reference.
