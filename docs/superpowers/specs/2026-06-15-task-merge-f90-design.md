# TASK — bpsi↔github Merge & F77→F90 Modernization (TRX-centered) — Design

> **For agentic workers:** This is the master DESIGN (spec). The first phase (P1 — TRX/tr
> consolidation) is turned into an executable task-by-task plan by the
> `superpowers:writing-plans` skill; execute with `superpowers:subagent-driven-development`
> or `superpowers:executing-plans`. Steps in the per-phase plans use checkbox (`- [ ]`) syntax.

**Goal:** Plan and sequence (a) the **merge** of the bpsi Kyoto development repo into the
project's github line, and (b) the **F77→F90 + COMMON→MODULE modernization** of TASK — with
the **TR/TRX module consolidation** as the first detailed phase. Every step preserves physics,
algorithms, input NAMELISTs and the C-ABI, verified by the existing **1e-10 binary-equivalence**
regression harness; the *only* deliberate result-changing step is the TRX physics port in P1,
which gets **new baselines** captured from the bpsi `trx` reference executable.

**Architecture:** Five serial phases on the **user's github fork** (never on ats-fukuyama):
`P0 Merge & baseline → P1 TRX/tr consolidation (detailed) → P2 param-dedup into plcomm →
P3 eq↔pl decoupling + F90 completion → P4 directory reorg + CMake`. A single
**1e-10 regression spine** (`test_run/`) gates every phase. Each unit of work lands as a small
PR with review + equivalence CI.

**Tech Stack:** git (note: `task-kyoshimi/` is a *linked worktree* of `task/.git`, not a separate
clone); gfortran `-ffree-form` / `-fdefault-real-8`; the `test_run/` harness
(`test_definitions.conf`: 14 `_equivalence` @1e-10 + 7 `_c_abi` + 21 `_ffi` + 7 `_wrapper`
+ 14 `_sweep`); the per-module C-ABI / `python/<m>lib` ctypes wrappers / `<m>_mcp` servers;
CMake (introduced in P4; foothold `python/trlib/CMakeLists.txt` already exists).

**Sources:**
- `docs/Refacting/Mail history.md` (Yoshimi↔Fukuyama thread — the agreed decisions).
- Decks: `2026-06-09-task-reorg-proposal.pptx`, `…-param-dedup.pptx`, `…-f90-migration.pptx`,
  `…-folder-inventory.pptx`, `TASK_TRX_study.pptx`.
- Fukuyama 2026-06-01: `TASK ライブラリ化プロジェクト現状報告.pdf`, `TASK-directory-lists.pdf`.
- `docs/official docs/1. eq_design_document_v2.pdf` (the eq↔pl data contract).
- **Live git analysis** of the three trees (real SHAs below), 2026-06-15.
- Existing plans: `2026-04-18-eq-f90-modernization.md`, `2026-04-17-tr-refactoring-phase0.md`.

**Constraints (hard):**
1. No change to physics / algorithms / input NAMELIST / C-ABI — *except* the deliberate TRX
   physics port in P1 (re-baselined against bpsi `trx`).
2. **Never push to `ats-fukuyama/task`.** All merge/test work happens on the user's fork
   (`myfork` = `github.com/HengyuLi-Ozaki-lab/task`). `ats-fukuyama/task:develop` is a *read-only
   upstream baseline*.
3. Do **not** propagate the local macOS-26 linker workaround (the uncommitted `eq/Makefile` /
   `tr/Makefile` edits dropping `../pl/libpl.a`) to Linux / the fork / upstream.
4. Precision policy: build under `-fdefault-real-8`; COMMON vars whose name starts with **`G`**
   are graphics vars and **stay single precision**.

---

## 1. Corrected repository topology (the foundation)

All three lines descend from the common ancestor **`43b2aa54`** (itself a
"Merge develop from ssh://bpsi…/task" commit). Verified live on 2026-06-15:

| Line | Ref | Tip | Relationship |
|---|---|---|---|
| **github (upstream baseline)** | `ats-fukuyama/task:develop` (`origin`) | `7eec08a7` (2025-09-14) | 2 ahead, **119 behind** bpsi |
| **bpsi (Kyoto main dev = merge SOURCE)** | `bpsi/develop` | `236893f4` | 119 ahead of github |
| **kyoshimi (user's working fork)** | `kyoshimi-develop` | `8a72b309` | = bpsi\@`8eed6fc2` + **544** Phase-L commits |

Key derived facts (these de-risk the merge dramatically):

- **The fork already contains 97 of bpsi's 119 commits.** `merge-base(kyoshimi-develop,
  bpsi/develop)` = **`8eed6fc2`** (2025-12-16) — i.e. the Phase-L fork was branched off a *recent*
  bpsi develop. Only **22 bpsi commits are newer** than the fork point.
- **github is the laggard**, missing all 119 bpsi commits. The "bpsi→github merge" Fukuyama
  asked for is mostly github catching up; we do it on the user's fork.
- **The eq/equ F90 efforts are orthogonal** (almost no collision):

  | dir | github `develop` | bpsi `develop` | kyoshimi `develop` |
  |---|---|---|---|
  | `eq/`  | 33 `.f` / 3 `.f90` (F77) | 33 `.f` / 3 `.f90` (F77) | **14 `.f` / 33 `.f90`** (kyoshimi F90'd) |
  | `equ/` | 27 `.f` / 1 `.f90` (F77) | **0 `.f` / 24 `.f90`** (bpsi F90'd) | 27 `.f` / 1 `.f90` (F77) |

  → bpsi modernized **`equ/`**; kyoshimi modernized **`eq/`**. Different directories, so the feared
  "two independent eq-f90 rewrites collide line-by-line" does **not** happen.
- **Real collision (bpsi's 22 new commits × kyoshimi's 544) = only 18 files:**
  `dp/dpfpin.f90`, `eq/eqinit.f`, `imas/ids/ids_equilibrium.f90`, `pl/Makefile`,
  `tools/check_dealloc.py`, `tools/check_dealloc_manual.md`, `tr/trcomm.f90`, `tr/trmain.f90`,
  `tr/trmenu.f90`, `trx/trcomm.f90`, `txnew/Makefile`, `txnew/txcalv.f90`, `w1/w1comm.f90`,
  `w1/w1exec11.f90`, `w1/w1mlm.f90`, `wim/wimgout.f90`, `wrx/wrcalpwr.f90`, `wrx/wrgout.f90`.
  Most are small bug-fixes (memory-leak / deallocate corrections, several literally
  *"reported by Dr. Yoshimi"*) that must be **re-applied onto the modernized files**.

### TR/TRX reality (the crux)

- **bpsi's active transport development lives in `trx`/`trm`, not `tr`** (of bpsi's 119 commits:
  38 touch `trx`, 36 touch `trm`, only **5** touch `tr`). This is exactly the "essential
  difference is trx" Fukuyama referred to: bpsi's newer fusion/RF physics is in `trx`.
- **Fukuyama's directory verdict (`TASK-directory-lists.pdf`): `tr` = KEEP, `trx`/`trm` = archive**
  ("tr is more stable"). So `tr` is the canonical *name*.
- **The user's Phase-L investment is entirely in `tr`** (C-ABI `tr_api.*`, `libtrapi.so`,
  `trcomm` split into 6 sub-modules, `trcoef`/`trrslt` splits, `python/trlib`, `tr_mcp`,
  regression baselines). `trx` in the fork is only 11 lightly-diverged files, zero library-ization.
- **Decision (confirmed with user): the canonical `tr` = the kyoshimi-modernized `tr`; hand-port
  bpsi `trx`'s newer physics into it; archive `trx` and `trm`.**

---

## 2. Master phase program

```
P0  Merge & baseline ───────────────┐  (foundation; no physics change)
P1  TRX/tr consolidation  [DETAILED] │  (the only deliberate physics change → new baselines)
P2  Param de-dup → plcomm            │  (tr-part folded into P1; then w1, tx/txnew)
P3  eq↔pl decoupling + F90 finish    │  (equ-f90 arrives via merge; convert named easy targets)
P4  Directory reorg + CMake ─────────┘  (strip-x renames, archive, CMake replaces ../ web)
```

Dependencies: P1 requires P0a (fork must hold bpsi's newest `trx` before porting from it).
The `tr` half of P2 (plcomm consolidation) is done **inside** P1 because P1 already rewrites
`tr`'s `trcomm` to absorb `trx`'s arrays. P3's `eq↔pl` move and P4's CMake are coupled
(MODULE-ization creates compile-order dependencies best expressed in CMake), but P3 can land on
the existing Makefiles first and be re-expressed in CMake during P4.

---

## P0 — Merge & baseline

**Goal:** Bring the fork current with bpsi, prepare the bpsi→fork(github-line) catch-up, and lock
the verification spine. No physics change; everything stays 1e-10 against current baselines.

### P0a — Reconcile bpsi's 22 new commits into `kyoshimi-develop`
- Create integration branch `merge/bpsi-2026-06` off `kyoshimi-develop` on `myfork`.
- Merge `bpsi/develop` (`236893f4`). Expect conflicts confined to the **18 files** in §1.
- For each colliding file, **re-apply bpsi's intent onto the modernized version** (e.g. bpsi's
  `tr/trcomm.f90` / `trmain.f90` / `trmenu.f90` deallocate fixes → onto kyoshimi's split
  `trcomm_*`/`trmain`/`trmenu`). `tools/check_dealloc.py` originated from Yoshimi → keep the fork's.
- After merge, run the full `test_run/` suite; every `_equivalence` case must stay PASS @1e-10.

### P0b — Prepare the bpsi→github catch-up **on the user's fork**
- On `myfork`, create `integrate/bpsi-into-developline` from `origin/develop` (`7eec08a7`).
- Merge `bpsi/develop` into it (github is purely behind → mostly additive). Fold github's 2 ahead
  commits (`7eec08a7` "task: update 250914", `19ff1573` "trx: update") — verify whether bpsi
  already carries equivalent `trx` changes; resolve the small `trx` overlap by hand.
- **Delivery:** push the integration branch to `myfork`; open it as a PR / hand a diff to Fukuyama
  for confirmation. **Do not push to `ats-fukuyama/task`.**

### P0c — Lock the verification spine
- Treat `test_run/test_definitions.conf` (14 `_equivalence` @1e-10 + c_abi/ffi/wrapper/sweep) as the
  gate for P1–P4. Regenerate/commit baselines on the post-P0a state.
- Confirm the CI build path (`ci/build-so-and-run-equivalence` on `myfork`) is green on the merged
  fork before P1.

### P0 guardrails
- The uncommitted `eq/Makefile` / `tr/Makefile` macOS-26 edits (dropping `../pl/libpl.a`) are
  **Mac-local build hacks** — keep them out of the fork/merge; the Linux lab build needs the
  `libpl.a` link.

---

## P1 — TRX/tr consolidation  *(first detailed phase; turned into a per-task plan via writing-plans)*

**Goal:** Make `tr` the single canonical transport module by hand-porting bpsi `trx`'s newer
physics into the kyoshimi-modernized, library-ized `tr`, then archive `trx`/`trm`. This is the one
phase that **changes results** (it adds physics), so it is verified against the **bpsi `trx`
reference executable**, not the old `tr` CLI.

### Canonical base (keep)
The kyoshimi `tr`: `tr_api.f90`/`tr_api.h`/`tr_state.f90`/`tr_param_registry.f90`, `libtrapi.so`,
the `trcomm_{const,param,ctrl,mtx,profile,globals}` split, `trcoef_{turbulence,neoclassical,
resistivity,adhoc}`, `trrslt_{files,globals,print}`, `tests/c_abi/`, `python/trlib`, `tr_mcp`,
the `f77/` originals (regression provenance), U-file I/O (`trufile`/`trufsub`/`tr_ufile_*`),
and CDBM (`trcdbm` via the bundled `tr/cytran`,`tr/nclass`,… model dirs — `tr` stays self-contained).

### Hand-port set (from the fork's `trx`, adapted to `tr`'s split-module layout)
New-physics files present in `trx` but absent from `tr`:

| File | Physics | Port notes |
|---|---|---|
| `libnf.f90` | multi-reaction fusion, `model_pnf=0..14` (renamed from `libsigma.f90`) | core of the new fusion bookkeeping; drives the species-resolved arrays below |
| `trsigmavnf.f90` | fusion reactivity ⟨σv⟩ (`sigmav_DTmm`) | depends on `libnf` framework |
| `trcoll.f90` | Coulomb collisions (`coulomb_log`, `FTAUE`, `FTAUI`) | these were split out of `trx/trcalc`; `tr/trcalc` still has the inline `COULOG/FTAUE/FTAUI` — reconcile (remove inline, adopt module) |
| `trcytran.f90` | CYTRAN cyclotron-radiation interface | uses `tr`'s bundled `cytran/` (no `trlib` dep needed) |
| `trtglf.f90` | TGLF transport-model interface | **needs a TGLF library** — confirm availability; otherwise gate behind a build flag / defer |
| `trlib.f90` | small local helper module (`COULOG`, `HY`) | distinct from the `trlib/` directory; keep namespaced to avoid clash |
| `test_libnf.f90`, `testsigma.f90` | unit tests for the fusion suite | port into `tr/tests/` |

Plus the **`trx`-evolved species-resolved arrays** that must be merged into `tr`'s `trcomm_*`, the
source/exec routines (`trpnf`, `trpnb`, `trpsc`, `trexec`), and the **results output**
(bpsi `trx/trrslt.f90` → fold into kyoshimi's `trrslt_{files,globals,print}` split): `AJNB_NSNNBNR`,
`PEC_NSNECNR`/`PLH_NSNLHNR`/`PIC_NSNICNR` (+ reduced forms), `SNFNN_NNF`/`PNFNN_NNF`,
`ANF0`/`TF0`/`ANFAV`/`TFAV`/`WFT`. These change the deallocation lists, the source assembly, and
the diagnostic output.

### Folded-in: tr's plcomm consolidation (the `tr` half of P2)
While rewriting `tr`'s `trcomm` to absorb the arrays above, adopt `trx`'s already-validated
`USE plcomm` pattern: delete `tr`'s local re-declarations of `RR,RA,RKAP,RDLT,BB,RIP,NSMAX,
PA,PZ,PN,PNS,PTPR,PTPP,PTS,PU,PUS,MODELG,model_prof,PROFN1/2,PROFT1/2,PROFU1/2,Q0,QA` and import
them from `pl/plcomm.f90 (plcomm_parm)`. Keep genuinely tr-local vars (`PT,RIPS,RIPE,PNC,PNFE,
PNNU,PNNUS,ALP,PROFJ1/2,…`) and resolve the **name-role clash** (`tr`'s `Q0`/`RIP` are
output/control vars vs pl's input params) with explicit scoping.

### Retire
- `trx` → archive (its physics now lives in `tr`).
- `trm` → archive. It is an older `trx` twin differing only by `libsigma.f90` (pre-rename `libnf`)
  + `trfixed.f90` (fixed-profile mode). **Optional port:** if the fixed-profile capability of
  `trfixed.f90` is wanted, port it as a `tr` mode; otherwise drop.

### P1 verification strategy (results legitimately change here)
- **Unported paths** (existing `tr` physics, the plcomm swap, the array-storage refactor): must
  stay **1e-10 vs the current `tr` baseline** — the plcomm swap and module reshuffle must NOT move
  numbers.
- **Ported paths** (fusion `model_pnf`, ⟨σv⟩, CYTRAN, TGLF, species-resolved sources): capture
  **new baselines** by running the **bpsi `trx`** executable on matched inputs; the merged `tr`
  must reproduce bpsi-`trx` to **1e-10** for those quantities. Add these as new `test_run/`
  `tr_*` cases with their own baselines, documented as "new physics, baselined against bpsi trx".
- NAMELIST `/TR/`: do a field-by-field diff of `tr` vs `trx` `/TR/` keys; any `trx`-only keys
  (`model_pnf`, per-class species dims) are additive with safe defaults so existing input files
  keep working unchanged.

### P1 sequencing (each = one small PR + green regression)
1. Port `trcoll` (collisions) — self-contained, low risk; reconcile against `tr/trcalc`'s inline functions.
2. Port the fusion suite (`libnf` → `trsigmavnf` → tests) + the `model_pnf` switch + species arrays into `trcomm_*`.
3. Wire the new sources into `trpnf`/`trpnb`/`trpsc`/`trexec`; new baselines from bpsi `trx`.
4. Port `trcytran` (CYTRAN) using bundled `cytran/`.
5. Port `trtglf` (TGLF) — gated on TGLF lib availability.
6. Adopt `USE plcomm` for `tr` (the folded P2-tr step).
7. Archive `trx`/`trm`; update top-level `Makefile` clean targets; refresh `tr_mcp`/`python/trlib`
   parameter registry for any new namelist keys.

---

## P2 — Parameter de-duplication into `pl/plcomm`

**Goal:** Eliminate local re-declaration of shared physics scalars in the transport/wave modules;
route them through `pl/plcomm.f90 (plcomm_parm)`. Verified 1e-10.

- Canonical home: `pl/plcomm.f90` — `RR,RA,RB,RKAP,RDLT,BB,Q0,QA,RIP,PROFJ` (l.50), species arrays
  `PA,PZ,PN,PNS,PTPR,PTPP,PTS,PU,PUS,PROFN1-3,PROFT1-3,…` `DIMENSION(NSM)` (l.63-68), `NSMAX,MODELG`.
- Template already in-repo and compiling: `trx`'s `USE plcomm`.
- **Order:** `tr` (done in P1) → **`w1`** (cleanest overlap: drop `BB,RR,RA,RB`, the `(NSM)`
  species arrays, `model_prof` from `w1comm.f90`) → **`tx`/`txnew`** (partial: only
  `PROFJ,PROFN1/2,PROFT1/2` overlap cleanly; `tx`'s `PA,PZ` are *scalars* and its profiles use a
  different parameterization — keep `tx` mostly out of the array part). `txnew` (`txcomm.f90:80`)
  carries the same debt and is the canonical successor to `tx`.
- Fukuyama's companion ask: split `trcomm` into **7 role sub-modules** (input / profile / source /
  metric / integral-quantity / **graphics** / auxiliary). The fork's existing split
  (`const/param/ctrl/mtx/profile/globals`) maps onto this; the **graphics** sub-module is where the
  `G`-prefixed single-precision vars concentrate. Also de-dup Fukuyama's flagged `PZ`/`PA` between
  `trcomm` and `plcomm`.
- Risk: init order (`pl_init` → modules) and BPSD-linkage overwrite paths — enumerate the call
  sites where pl scalars are written after module init before each swap; catch with 1e-10.

---

## P3 — eq↔pl decoupling + F90 completion

**Goal:** Break the eq↔pl build cycle by moving equilibrium-data reading + quantity calc out of
`eq` into `pl` (Fukuyama's special-case instruction); complete the F77→F90 conversion of the
named targets; standardize precision.

### eq↔pl move
- The cycle is real & bidirectional: `eq/eqcom*.inc` `USE plcomm` (compile-time eq→pl);
  `pl/plprof.f90` CALLs `eq`'s `GETRZ`/`GET_RZ`/`GET_BMINMAX`/`GET_DVDRHO` (link-time pl→eq).
  `pl/Makefile` already has the 3-stage build (`SRCS_NOEQ`→`libpl.a`, build `eq/libeq.a`,
  `SRCS_EQ`→rebuild `libpl.a`); `eq/Makefile` merges `libpl.a` into `libeq.a`.
- **Move into pl:** readers `eqfile.f`(EQ_READ/EQRTSK)/`eq-eqdsk.f`/`eq-qst.f`/`equread.f90`;
  quantity-calc `eqcalq.f`/`eqcalv.f`; **and the accessor layer `eqintf.f` (`GETRZ`/`GET_*`)** —
  moving the accessors is what actually breaks the link cycle. **Keep in eq:** the pure GS solve
  (`eqcalc.f`/`eqsub.f`/`eqfunc.f`/`eqsplf.f`/`newton.f`/`invematrix.f`).
- **Fukuyama must confirm the exact routine boundary** (esp. whether the `eqcom1/2/3` data the
  quantity routines read must migrate to pl too — a larger data-model move than just RR/RA/BB).
- The `pl/noeqlib.f`/`noequlib.f` stubs (empty `eq_*`/`equ_*`) become the seam: after the move,
  pl owns the readers/accessors and eq reduces to the solver; the stub interface flips to real
  implementations in pl.

### F90 completion (scope from the live inventory)
- **Arrives via merge (clean):** bpsi's **`equ/` F90** (24 `.f90`) — kyoshimi never touched `equ/`,
  so it merges without collision. kyoshimi's **`eq/` F90** stays. (bpsi's 12 small `eq` physics
  patches — e.g. `eqcalq` `NMAX 200→400`, QUEST `eq-eqdsk` — re-apply onto the kyoshimi `eq/*.f90`.)
- **Auto-convert (email-named, easy):** `lib/mdsplus.f` (674 L, 6 COMMON), `tools/guiread.f`
  (707 L, 18 COMMON), `tools/ufread.f` (321 L, 3 COMMON).
- **Hard but COMMON-centralized:** `wm` (119 blocks in `wmcom1.inc`+`vmcomm.inc`),
  `wmf` (106 blocks, same include design — future `w2d`), `eq` (finish `eqcom1-5.inc`→MODULE,
  build on the existing `equcom.f90 (module equ_params)` pattern). Use the
  `2026-04-18-eq-f90-modernization.md` plan as the template (LOW/MED/HIGH tiers, 1e-13 RMS).
- **`trlib` (third-party models): LICENSE CHECK FIRST.** `glf/`(GLF23, General Atomics),
  `nclass/`(NCLASS, Houlberg/ORNL), `mmm95`+`libmmm7_1`(MMM, Lehigh), `itg`(IFS-PPPL),
  `cytran`(Tamor/SAIC) — NTCC academic redistributions with author-contact/citation but **no
  in-tree OSI license**. Clear attribution/permission before f90-ifying or public redistribution.
- `equ/` legacy uses **lowercase `common`** — any COMMON-detection tooling must be case-insensitive.

### Precision standardization
- Add `-fdefault-real-8` to `make.header` `OFLAGS`/`DFLAGS` (currently absent; precision today
  rests on `IMPLICIT COMPLEX*16(C),REAL*8(A-B,D-F,H,O-Z)` in 25 fixed-form files).
- Preserve **`G`-prefixed graphics vars as single precision** (verified via the `GUCLIP` pattern in
  `lib/libgrf/grd2d.f90`, `eq/eqgout.f`, and graphics COMMONs `/GSCTR4/`,`/GSGFXY/` in fp/fpx).
  The per-module `*_graphics_stubs.f90` pattern already isolates graphics from the `.so` builds.

---

## P4 — Directory reorg + CMake

**Goal:** Execute the directory consolidation and replace the relative-path Makefile web with
CMake. Structure/build only; no result change.

### Canonical-directory verdicts (reconcile dir-list vs email)
`TASK-directory-lists.pdf` legend `*` = keep. Apply: keep the successor, retire the predecessor,
strip the trailing `x` on rename.

| Action | Dirs | Source / note |
|---|---|---|
| keep (canonical) | `tr`, `eq`, `equ`, `fpx`, `wrx`, `txnew`, `tf2d`, `ti`, `tot`, `pl`, `lib`, `mtxp`, `dp`, `ob`, `trlib`, `trmodels` | dir-list `*` |
| replace → successor | `fp`→`fpx`, `wr`→`wrx`, `tx`→`txnew`, `t2`→`tf2d` | dir-list |
| archive (this work, P1) | `trx`, `trm` | dir-list + P1 |
| archive | `trn`, `dpseki`, `fp.anzai`, `fp.nuga`, `fp.ota`, `plx`, `sak`, `wf2`, `wf2dt`, `wf3`, `wiq`, `wmfn`, `wmseki`, **`wmx`?**, **`wf2dx`?** | dir-list (⚠ email kept `wmx`/`wf2dx`; **Fukuyama to reconcile**) |
| **open** | `w1`,`wi`,`wim` (email: merge → `w1d`; dir-list: keep separate) | **Fukuyama to reconcile** |
| cross-cutting move | `adpost` → into `trlib` | dir-list (interacts with trlib license) |

### Dead-reference cleanup (surfaced by analysis, pre-existing)
- `wmseki/Makefile` → `../mtx/`,`../mpi/` (modules deleted); stale `rm ../mtx/*.o` in `wmf`/`wmfn`.
- top `Makefile` `veryclean` → nonexistent `plx`/`t2x`/`w1n`; `t2` → `t2x`.
- phantom `-I../equ/$(MOD)` in `trx`/`trm` (no build edge) — moot after archiving them.

### CMake introduction
- 76 Makefiles, 70 using `../<mod>/` relative paths; top `Makefile` is not a real driver (the build
  graph lives in per-module `../` edges). CMake links by target name
  (`target_link_libraries(eq PRIVATE pl lib mtxp)`), per-module `CMakeLists.txt` + top
  `add_subdirectory()`; encodes MODULE compile-order as target deps (replacing hand-written
  prerequisite lists + `(cd ../x; make)` chains).
- Stage module-by-module, coexisting with Makefiles (foothold `python/trlib/CMakeLists.txt`).
- Parameterize the absolute paths in `make.header`/`mtxp/make.mtxp` (PETSc/gsaf/gfortran) into a
  CMake toolchain covering both macOS (this Mac) and the Linux lab server.

---

## 3. Verification spine (cross-cutting)

- **Gate:** every PR in P0–P4 must pass `test_run/` `_equivalence` @1e-10 (+ `_c_abi`/`_ffi`/
  `_wrapper`/`_sweep` where the touched module has them).
- **New baselines only where physics legitimately changes** — exclusively the ported TRX paths in
  P1, baselined against the **bpsi `trx`** executable and documented as such.
- **C-ABI stability:** `tr_api.h`/`eq_api.h` etc. ABI versions must not regress; any new namelist
  key flows through `<m>_param_registry` and the ctypes wrapper / MCP `describe_parameters`.
- **Cross-platform:** run equivalence on both macOS (dev) and the Linux lab server (`ci/build-so-
  and-run-equivalence` on `myfork`); never let the macOS `libpl.a` hack reach the Linux build.

---

## 4. Open decisions for Fukuyama (do not block P0/P1)

1. **eq↔pl boundary (P3):** exact routine set to move into pl — readers + `eqcalq/eqcalv` only,
   or also the `eqintf` accessors and the `eqcom1/2/3` data they read?
2. **Dir-list vs email discrepancies (P4):** archive `wmx`/`wf2dx` (dir-list) or keep (email)?
   Merge `w1/wi/wim` → `w1d` (email) or keep separate (dir-list)?
3. **trlib LICENSE (P3):** attribution/permission for the NTCC third-party models before
   f90-ification / any public redistribution; does GLF23 (GA) allow public-repo redistribution?
4. **6 draft PRs #5–#10** (14 critical + 25 important review findings): agreed Fortran-modification
   policy before landing.
5. **P0b delivery path:** confirm the merge lands via a `myfork` PR for Fukuyama to pull (the user
   does not push to `ats-fukuyama/task`).

---

## 5. Out of scope

- Modules outside Phase L (`pl`/`dp`/`ob`/`wm`-family/`wf`-family/personal mirrors) get F90/merge
  treatment but **no library-ization** (Fukuyama: Phase-L scope = `tr,ti,fp,wr,wrx,eq,tot`).
- The CSD (Core-SOL-Divertor) coupling code is a *consumer* of `trx`/`tr` flux output
  (`cdbm_flux_for_csd`); if it ships in any merged tree, P1 must preserve the
  `cdbm_flux`/`cdbm_flux_interval` NAMELIST keys and the unit-273 text-file format — but CSD itself
  is not in this plan's conversion surface.
- External-library substitution (GSL/LAPACK/FFTW/PETSc/Matplotlib) from the April
  `refactoring_proposal.pdf` is a separate, later initiative.

---

## 6. Next step

After user review of this design, run `superpowers:writing-plans` to expand **P1 (TRX/tr
consolidation)** into a task-by-task implementation plan under
`task-kyoshimi/docs/superpowers/plans/2026-06-15-trx-tr-consolidation-*.md`, then execute with
`superpowers:subagent-driven-development`.
