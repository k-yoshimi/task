# BPSD external patches

This directory holds **diagnostic patches against the upstream BPSD library**
(https://github.com/ats-fukuyama/bpsd, expected to live at `../../bpsd`
relative to this `task` repository).

BPSD is a separate git repository — these patches are **not** applied
automatically by anything in `task`. Apply them by hand to your local
BPSD checkout while we coordinate with the upstream maintainers.

## Patches

### `bpsd-species-kid-oob-fix.patch`

**Severity**: HIGH (silent heap corruption — causes downstream SIGABRT
in any caller that lands the smashed bytes on a critical malloc chunk)

**Affected**: `bpsd_species.f90:38` `subroutine bpsd_setup_species_kdata`

**Bug summary**
The loop iterates `nd = 0, ndmax-1, 3` and writes `kid(nd+3)`. With
`ndmax = nsmax*5` (line 82) but stride 3, the last iteration's
`nd+3` exceeds the array bound:
- `nsmax = 4` -> `ndmax = 20`, last `nd = 18`, write `kid(21)` (overflow by 1)
- `nsmax = 2` -> `ndmax = 10`, last `nd = 9`, write `kid(12)` (overflow by 2)

`kid` and `kunit` are `CHARACTER(LEN=32)`, so each OOB write smashes
**32 bytes** of the next adjacent malloc chunk's metadata. This typically
manifests as `corrupted size vs. prev_size` from glibc, raised on the
*next* `malloc/free` — far away from the actual cause.

**Why discovered now**
TASK's standalone `tr2` driver hits the same bug on every `tr_bpsd_init
-> bpsd_put_species` call, but its process-wide heap layout happens to
land the smash on inert padding. The new `libtrapi.so` Python wrapper
loads with a fundamentally different heap layout (Python + numpy +
ctypes mallocs precede the Fortran calls) and the smashed bytes hit a
chunk that is later free()'d, which is when glibc trips the assertion
and SIGABRTs.

**Fix**
Stop the loop at the last *full* triplet:
```fortran
do nd=0,speciesx%ndmax-3,3   ! was: ndmax-1
```
This preserves the layout of `kid`/`kunit` (still sized to `ndmax`),
just leaves the trailing slack untouched. Mirror inconsistency at
line 82 (`*5`) and line 138 (`/5`) is functionally OK because the
array data itself is sized large enough; only the loop bound needed
fixing.

**Verification**
After applying:
1. `cd ../../bpsd && make clean && make libbpsd.a`
2. `cd ../task && make -C tr clean_pic libtrapi.so`
3. `PYTHONPATH=python pytest python/trlib/tests/test_equivalence.py -v`
4. `test_iter01` and `test_tst2` no longer SIGABRT (they may still FAIL
   on numerical mismatch, but that is a separate Layer 1 baseline issue,
   not a heap corruption.)

## How to apply

```bash
cd ../../bpsd     # adjust path if your BPSD checkout is elsewhere
git apply $TASK_REPO/docs/external-patches/bpsd/bpsd-species-kid-oob-fix.patch
make clean && make libbpsd.a
```

To remove later: `git apply --reverse $TASK_REPO/docs/external-patches/bpsd/bpsd-species-kid-oob-fix.patch`

## Upstreaming
This fix should be sent to https://github.com/ats-fukuyama/bpsd as a
PR. Once upstream merges, this patch directory entry can be dropped.
