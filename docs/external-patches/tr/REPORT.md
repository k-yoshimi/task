# tr/: NSM vs NSMAX uninitialized-read bug class

- Status: open (one instance fixed in PR #119; sister arrays still vulnerable on develop)
- Branch (proposed): `docs/tr-nsm-uninit-report` (off `develop`)
- Audit date: 2026-04-19
- Reporter: k-yoshimi <k-yoshimi@g.ecc.u-tokyo.ac.jp>

## Executive summary

`tr/` has a class of latent uninitialized-read bugs caused by inconsistent use of the **compile-time** species bound `NSM = 4` (`tr/trcom0.f90:11`) and the **run-time** species count `NSMAX` (`tr/trcom0.f90:8`). Several allocatable arrays are sized `(NSTM)` or `(NSM)` and their writers populate only `1..NSMAX` (and the special impurity slots `7, 8`) entries. Their readers, however, loop `DO NS=1, NSM` or read literal indices `PNSS(3), PNSS(4)`, silently consuming uninitialized memory whenever `NSMAX < NSM`.

The bug is invisible in the standard `trmain` binary because Linux gives a fresh process a zero-page heap, but it surfaces when `tr/` is loaded as a shared library (`libtrapi.so`) into a process whose heap has already been dirtied by Python+NumPy. PR #119 fixed one instance (`PNSS`); this report enumerates the sister arrays that share the same writer/reader contract and need the identical fix.

## Bug pattern (worked example: PNSS with NSMAX=2)

```
tr/trcom0.f90:11
  INTEGER, PARAMETER :: NSM = 4, NSTM = 8       ! compile-time

tr/trcom0.f90:8
  INTEGER            :: NSMAX                   ! run-time, e.g. 2 for tst2

tr/trcomm_ctrl.f90:13-14, 59 (pre-#119)
  REAL(rkind), ALLOCATABLE :: PNSS(:)           ! sized (NSTM=8)
  ALLOCATE(PNSS(NSTM))                          ! contents = whatever the heap had

tr/trprof.f90:314-317  (writer in tr_prof_impurity, MDLUF != 3 path)
  PNSS(1)            = PNS(1)
  PNSS(2:NSMAX)      = PNS(2:NSMAX) * DILUTE     ! NSMAX=2  -> only PNSS(2)
  PNSS(7)            = PNS(7)
  PNSS(8)            = PNS(8)
  ! ==> PNSS(3) and PNSS(4) are NEVER written

tr/trcoef_turbulence.f90:170-171  (reader at NR=NRMAX)
  ANT = PNSS(3)            ! reads junk
  ANA = PNSS(4)            ! reads junk

tr/trcoef_turbulence.f90:181-186
  DO NS=2, NSM             ! NS = 2,3,4 -- hard-coded NSM, not NSMAX
     RNTP = RNTP + PNSS(NS)*PTS(NS)   ! NS=3,4 contaminates RNTP
  ENDDO
```

The junk in `PNSS(3:4)` propagates into the turbulent transport coefficient chain `ALPHA -> AKDWEL -> AK -> RT`, eventually producing `NaN` (or negative values) in `RT(NR,1)` at the boundary radii, which trips the `NEGATIVE TEMPERATURE AT STEP 0` check in `tr/trexec.f90:1134`.

PR #119 fixes this by adding `PNSS(:) = 0.D0` immediately after the `ALLOCATE` (`tr/trcomm_ctrl.f90:71`).

## Why this is dangerous

1. **Machine- and process-state dependent.** A clean `trmain` binary on Linux runs without symptoms because brk-based heap pages are zero on first touch. Loading the same code as `libtrapi.so` from Python makes the same `ALLOCATE` return memory that has been touched and re-released by NumPy/CFFI; the contents are non-zero and yield NaN.
2. **Silent.** Fortran does not initialize allocatable arrays unless the compiler is invoked with `-finit-real=...`. Production Makefiles for `tr/` do not set such a flag, so the corruption is invisible until the cascaded NaN trips a downstream check far from the cause.
3. **Indistinguishable from physics.** The first observable symptom is `XX ERROR : NEGATIVE TEMPERATURE AT STEP n`, which a maintainer would naturally chase as a numerical/physics issue.

## Discovery path

| Step | Symptom | Resolution |
| ---: | ------- | ---------- |
| 1 | NCLASS produced NaN in `rhatp/rhatt` | PR #114 zero-init NCLASS scalars |
| 2 | `libtrapi.so` `tr_tst2`: `NEGATIVE TEMPERATURE` step 0 | PR #119: `PNSS(:) = 0.D0` after allocate |
| 3 | Code reviewer flagged sister arrays in `tr/trcomm_profile.f90:237,298` | (this report) `PNSSA, PNSSO, PNSSAO, PTSO, PTSAO` |
| 4 | `trlib_tst2`: `RT(NR=37) < 0` at later step | suspected `PNSSA` cascade through `TR_EDGE_SELECTOR` |

## Affected arrays — full audit

Arrays declared in `tr/trcomm_profile.f90`, sized `(NSTM)` or `(NSM)`, with writer/reader asymmetry:

| Array | Allocation site | Writer (slot coverage) | Reader loop bound | Risk when NSMAX<4 |
| ----- | --------------- | ---------------------- | ----------------- | :---------------: |
| `PNSS` | `tr/trcomm_ctrl.f90:59` | `tr/trprof.f90:314-317` writes {1, 2..NSMAX, 7, 8} | `tr/trcoef_turbulence.f90:170-186` `DO NS=2,NSM` and literal `PNSS(3)/PNSS(4)` | **HIGH** (fixed in PR #119) |
| `PNSSA` | `tr/trcomm_profile.f90:237` | `tr/trprof.f90:319-322,329-331`; `tr/trufile.f90:1029-1034,...` writes {1, 2..NSMAX, 7, 8} | `tr/trprof.f90:684,699,723` `DO NS=1,NSM`; `tr/trexec.f90:1731,1772` indexed by NEQ | **HIGH** when `RHOA<1` |
| `PNSSO` | `tr/trcomm_profile.f90:298` | `tr/trprof.f90:681,696` `DO NS=1,NSM` (saves `PNSS(NS)`) | `tr/trprof.f90:689,704` `DO NS=1,NSM` (restores into `PNSS`) | **HIGH** if `PNSS(3:4)` is junk: PNSS junk flows to PNSSO and back |
| `PNSSAO` | `tr/trcomm_profile.f90:298` | `tr/trprof.f90:716,721` `DO NS=1,NSM` (TR_EDGE_DETERMINER) | `tr/trprof.f90:684,723` `DO NS=1,NSM` | **HIGH** (NSW=0 path uses `PNSSAO(NS)` for NS=3,4) |
| `PTSO` | `tr/trcomm_profile.f90:298` | `tr/trprof.f90:682,697` `DO NS=1,NSM` | `tr/trprof.f90:690,705` `DO NS=1,NSM` | LOW (PTS has trinit defaults) — defense-in-depth |
| `PTSAO` | `tr/trcomm_profile.f90:298` | `tr/trprof.f90:717,722` `DO NS=1,NSM` | `tr/trprof.f90:685,724` `DO NS=1,NSM` | LOW — defense-in-depth |
| `PNSA` | `tr/trcomm_profile.f90:239` | `tr/trufile.f90:336-339,420-423,…`; `tr/tr_ufile_task.f90:171-174,…`. **Never** initialized when MDLUF=0 | `tr/trprof.f90:319-322,329-331` reads {1, 2..NSMAX, 7, 8} only when `RHOA≠1` | LOW in default flow (`RHOA=1.0`); HIGH if user sets `RHOA<1.0` and `MDLUF=0` |
| `PTSA` | `tr/trcomm_profile.f90:239` | `tr/trufile.f90:268,300-302,970,981`; `tr/tr_ufile_task.f90:120,138`. **Never** initialized when MDLUF=0 (default tst2 path) | `tr/trprof.f90:700,724` `DO NS=1,NSM` (`PTS(NS)=PTSA(NS)`); `tr/trexec.f90:1751` `RTV=PTSA(NS)`; `tr/trexec.f90:1772` `RPV=PNSSA(NS)*PTSA(NS)` | **HIGH** — confirmed via dump-diff between binary tr2 and libtrapi.so on 2026-04-20: tst2 ZEFF0 16% drift then NaN cascade until PTSA was zero-init'd |

### Update 2026-04-20: PTSA confirmed as the actual cascade source

Initial PR #119 (PNSS) and the supplemental sister-array sweep (PNSSA, PNSA, PNSSO, PTSO, PNSSAO, PTSAO) reduced but did not eliminate the libtrapi.so tst2 failure. A side-by-side dump of TRCOMM state at the end of `tr_prep` between binary `tr2` and `libtrapi.so` (env-gated dump module `tr/tr_dump_state.f90`, controlled by `TR_DUMP_STATE=path`) showed `PTSA(1..8)` filled with heap garbage on both paths — neither writer touches it in the default (`MDLUF=0`) flow. After adding `PTSA(:) = 0.D0` to the same ALLOCATE-block sweep, `trlib_tst2` PASSES Layer 1 at 1e-10. PTSA is therefore added to **Tier 1** below.

## Recommended fix strategy

**Tier 1 (this patch — minimal-risk, matches PR #119):**
Add `PNSSA(:) = 0.D0`, `PNSA(:) = 0.D0`, `PTSA(:) = 0.D0`, `PNSSO(:) = 0.D0`, `PNSSAO(:) = 0.D0`, `PTSO(:) = 0.D0`, `PTSAO(:) = 0.D0` immediately after `ALLOCATE` in `tr/trcomm_profile.f90:allocate_trcomm_profile`. This eliminates the latent UB without touching physics paths or loop bounds.

**Tier 2 (deferred — needs reviewer judgment):** see `READER-FIX-PROPOSAL.md`.

**Tier 3 (long-term — code health):**
Switch the array dimensions from `(NSTM)` to `(NSMAX+NSZMAX+NSNMAX)` across the board, or add an explicit named PARAMETER block documenting the slot allocation (slots 1..4 = bulk; 5..6 = impurity; 7..8 = neutral).

## Verification (expected)

| Test | Pre-patch | Post-patch (expected) |
| ---- | --------- | --------------------- |
| `tr_iter01` | OK | OK |
| `tr_tst2` | OK (process heap is zero) | OK |
| `tr_m0904` | OK | OK |
| `trlib_iter01` | OK with #119 | OK |
| `trlib_tst2` | NEGATIVE TEMPERATURE step 0 (pre-#119); after #119, sometimes NEGATIVE at NR=37 | OK |

## Key file paths referenced

- `tr/trcom0.f90` — defines `NSM=4`, `NSTM=8`, `NSMAX`
- `tr/trcomm_ctrl.f90:59` — PNSS allocation (zero-init in PR #119)
- `tr/trcomm_profile.f90:237,239,298` — sister allocations (PNSSA, PNSA, PNSSO/PTSO/PNSSAO/PTSAO)
- `tr/trprof.f90:314-332` — writers for PNSS/PNSSA (only fill 1, 2..NSMAX, 7, 8)
- `tr/trprof.f90:666-730` — `TR_EDGE_SELECTOR` / `TR_EDGE_DETERMINER` (readers using `DO NS=1,NSM`)
- `tr/trcoef_turbulence.f90:170-186` — original PNSS literal-index reader
- `tr/trinit.f90:64-110` — PT/PTS/PN/PNS namelist defaults (explains why PTS escapes)
- `tr/trexec.f90:1134` — `XX ERROR : NEGATIVE TEMPERATURE` check site
