# tr/: Heap-reuse leak across `tr_finalize` → `tr_init` cycles

- Status: open (latent on master; symptomatic only when `tr/` is loaded as a shared library and re-init'd in the same process)
- Audit date: 2026-04-20
- Reporter: k-yoshimi <k-yoshimi@g.ecc.u-tokyo.ac.jp>
- Sister report: [REPORT.md](REPORT.md) (NSM-vs-NSMAX uninitialized-read bug class)

## Executive summary

`tr/trcomm_profile.f90:allocate_trcomm_profile` allocates ~80 profile arrays (`BP`, `EZOH`, `RDP`, `AJ`, `QP`, `RHOTR`, `AR1RHOG`, `AKDWD`, …) but never assigns initial values to any of them. With the standalone `trmain` binary this is invisible because Linux fills brk-based pages with zero on first touch. **As soon as `tr/` is exposed as a shared library** (`libtrapi.so`, the C ABI added in Phase L-2..L-4) **and re-initialized in the same process** (`tr_finalize` → `tr_init` → `ALLOCATE_TRCOMM`), glibc `malloc` may return the same chunk that the previous run just freed, so the new "uninit" allocation contains the *previous run's final values*.

Because some MDL flags short-circuit the per-step recompute (e.g. `tr_prof_current` runs only when `MODELG=2`; the EQ→TR plasma-field copy depends on `MDLEQB`/`MDLEQN`), stale values in the leaked chunk silently leak into the next case's run loop and cascade to NaN in `RT`, tripping `XX ERROR : NEGATIVE TEMPERATURE AT STEP 0` in `tr/trexec.f90:1134` — even though every individual variable in NSM/NSMAX terms is correctly sized and assigned.

## Reproduction

Two TASK fixtures driven through `libtrapi.so` in one Python process, in either order:

```python
from trlib import Trlib
from trlib.tests.fixtures import tr_tst2_params as f1
from trlib.tests.fixtures import tr_iter01_params as f2

# Either order produces NaN in the second case:
for fixture, ntmax in [(f1, 10), (f2, 100)]:
    with Trlib() as tr:
        fixture.apply(tr)        # set_param + set_param_str
        tr.run(ntmax)
        # 2nd iteration: TE/TD become NaN at step 1; RT goes negative
```

Each fixture passes Layer-1 (1e-10 vs Phase-0 baseline) when run **alone** in a fresh process.

## Root-cause walkthrough

1. First fixture (`tr_tst2`) runs cleanly. At final step, `tr/trcomm_profile.f90` arrays hold real, finite poloidal-field, ohmic-field, equilibrium and transport-coefficient values (for the small TST-2 device).
2. `Trlib.__exit__` calls `tr_finalize` → `tr/trcomm.f90:DEALLOCATE_TRCOMM` → `deallocate_trcomm_profile` releases all chunks back to glibc.
3. Second fixture (`tr_iter01`) constructs a new `Trlib()` → `tr_init` → `ALLOCATE_TRCOMM` → `allocate_trcomm_profile` re-allocates the same arrays. glibc returns the same chunks (or chunks within the same fastbin) — the memory still holds tst2's last-step values.
4. The fresh `tr_prep` calls `tr_prof`, `tr_set_metric`, `tr_bpsd_init`, `tr_bpsd_put`, `tr_prof_impurity` and (only when `MODELG=2`) `tr_prof_current`. For `MODELG=3` cases (`tr_tst2`, `tr_iter01`) `tr_prof_current` is **skipped**, so `BP`, `EZOH`, `AJ`, `QP` and the equilibrium metric arrays are not re-zeroed.
5. `tr_loop` then enters `trcalc` which reads (and only conditionally writes) those leaked arrays. The cascade is most visible in `BP=AR1RHOG*RDP/RR` (`tr/trcalc.f90:66`): `BP` is overwritten every step, but it is computed *from* `RDP`, which itself is leaked.

The dump-diff fingerprint at end of the second `tr_prep`:

```
< BP(1)= 6.557832130380034E-319          # iter01 alone (cold heap)
< BP(25)= 7.867643223642326E-311
< BP(50)= 7.867643224274730E-311
---
> BP(1)= 0.000000000000000E+000          # iter01 after-tst2-zero-init (this fix)
> BP(25)= 0.000000000000000E+000
> BP(50)= 0.000000000000000E+000
```

Without the fix, the `>` side reads `BP(25) = 0.7201..., BP(50) = 1.4549...` — the *iter01-after-tst2 values from the prior run*.

## Why the binary `trmain` does not see this

`trmain.f90` is a one-shot program: `pl_init / eq_init / tr_init / pl_parm / eq_parm / tr_parm / tr_setup_kv / tr_menu / DEALLOCATE_TRCOMM / STOP`. There is no in-process `ALLOCATE → DEALLOCATE → ALLOCATE` cycle, so glibc's chunk reuse is irrelevant. The arrays start zero (kernel-zeroed brk pages) and end at exit time.

The C ABI (`tr/tr_api.f90`, Phase L-2 onward) explicitly supports `tr_init / tr_finalize / tr_init` cycles for re-use of the library across multiple input cases — this is the documented contract of the API. Any caller that exercises that contract hits the bug.

## Impact assessment

| Caller | Affected? | Why |
| ------ | --------- | --- |
| Standalone `trmain` (`tr2`) binary | NO | One init/run/finalize cycle per process |
| `libtrapi.so` C ABI single-init/single-finalize per process | NO | Same as above |
| `libtrapi.so` C ABI re-init cycle (Phase L-6 4-layer tests) | **YES** | Fixed-cost hit: NaN in 2nd case |
| `libtrapi.so` from MCP server long-running process (planned) | **YES** | Multi-tenant servers will see NaN on every 2nd request after the first |
| Future per-case sweep tooling (`Xlib config.toml` deferred) | **YES** | Each case in the sweep would corrupt the next |

## Recommended fix

Append a defensive `array(:) = 0.D0` sweep to the end of `allocate_trcomm_profile`. This makes the post-`ALLOCATE_TRCOMM` state invariant (always zero) regardless of the underlying heap chunk's history. The patch is non-invasive:

- Does not change any physics path.
- Does not change any DO loop bounds.
- Does not affect the binary `trmain` (kernel-zeroed pages are already zero).
- Eliminates a documented future pain point for any library-mode caller.

The patch covers all NRMAX-bounded 1D, NRMAX×N 2D, and NSTM-bounded edge-saved arrays declared in `tr/trcomm_profile.f90`. It is provided as `tr-heap-reuse-leak.patch`.

A more general alternative — using Fortran 2003 `ALLOCATE(name(N), SOURCE=0.D0)` syntax everywhere — would change every existing `ALLOCATE` line and is not proposed here. The defensive trailing sweep is the minimum-diff fix.

## Verification

Layer 1 4-layer tests (`python/trlib/tests/test_equivalence.py`):

| Order | Pre-patch | Post-patch |
| ----- | --------- | ---------- |
| `test_tst2` alone | PASS | PASS |
| `test_iter01` alone | PASS | PASS |
| `test_tst2 → test_iter01` (pytest default order) | **FAIL** (NaN cascade) | **PASS** |
| `test_iter01 → test_tst2` (reverse) | **FAIL** (NaN cascade) | **PASS** |

Phase-0 binary regression (`test_run/run_tests.sh tr_tst2 tr_iter01 tr_m0904`):

| Test | Pre-patch | Post-patch |
| ---- | --------- | ---------- |
| `tr_tst2` | PASS | PASS |
| `tr_iter01` | PASS | PASS |
| `tr_m0904` | PASS | PASS |

## How this was found

The env-gated `tr/tr_dump_state.f90` dump module (introduced 2026-04-20 as a permanent diagnostic, controlled by `TR_DUMP_STATE=path`) was used to dump the same set of TRCOMM state at the end of `tr_prep` for two consecutive `Trlib()` instances inside one Python process. The diff of "iter01 alone" vs "iter01 after tst2" pinpointed `BP` and `EZOH` as holding tst2's leftover values rather than fresh-heap garbage — leading directly to the heap-reuse-leak hypothesis. After zero-init'ing those two, more arrays revealed themselves; the comprehensive sweep is what the patch ships.

## Generalisation to sister modules

The same allocate-without-zero-init pattern exists in:

- `fp/fpcomm.f90` (and analogous `allocate_fpcomm_*` helpers) — reachable via `libfpapi.so` re-init
- `wr/wrcomm.f90`, `wrx/wrxcomm.f90` — reachable via `libwrapi.so` / `libwrxapi.so` re-init
- `eq/eqcomm.f90` — reachable via `libeqapi.so` re-init
- `ti/ticomm.f90` — reachable via `libtiapi.so` re-init

A separate patch for each is planned. The same diagnostic recipe (env-gated dump + 2-instance script) applies; the same defensive sweep at end of the allocate routine is the minimum fix. Tracking each as a follow-up to this report.

## Key file paths referenced

- `tr/trcomm_profile.f90:137-339` — `allocate_trcomm_profile` (this is the patch site)
- `tr/trcomm.f90:35-94` — `ALLOCATE_TRCOMM` (caller; unchanged)
- `tr/tr_api.f90:65-111` — `tr_api_init` (calls `ALLOCATE_TRCOMM` after `tr_finalize`)
- `tr/tr_api.f90:329-346` — `tr_api_finalize` (calls `DEALLOCATE_TRCOMM`)
- `tr/trcalc.f90:66` — `BP=AR1RHOG*RDP/RR` (downstream consumer of leaked `RDP`)
- `tr/trcalc.f90:1060` — `EZOH=ETA*AJOH` (downstream consumer; benign on its own but symptomatic)
- `tr/trprep.f90:67-92` — `tr_prep` callers; only calls `tr_prof_current` when `MODELG=2`
- `tr/tr_dump_state.f90` — env-gated dump module used to localise this bug
