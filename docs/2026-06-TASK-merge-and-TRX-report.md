# TASK — bpsi→kyoshimi merge & TRX→tr consolidation

*Engineering report and lessons learned — P0 merge (delivered) + P1 TRX physics port (in progress).*
Last updated 2026‑06‑30. Delivered tip `d1f7f9e7`; CI green (736 passed).

---

## 1. Background

**TASK** is a Fortran tokamak plasma‑simulation stack (modules `pl` shared interface,
`eq` equilibrium, `tr`/`trx` transport, `fp`/`fpx` Fokker–Planck, `wr`/`wrx` ray tracing,
`wm` waves, `ti` impurity/ADAS, `tot` orchestrator). Three independent git lines had drifted apart:

| Line | Repo | Role |
|---|---|---|
| **bpsi** | `bpsi.nucleng.kyoto-u.ac.jp/pub/git/task` | Kyoto main dev — latest physics/bug‑fixes |
| **kyoshimi‑develop** | fork of bpsi @ `8eed6fc2` | **Phase‑L modernization**: F90‑ification, per‑module C‑ABI + `libXapi.so` + Python wrappers + MCP servers, `trcomm` split into 6 sub‑modules |
| **ats‑fukuyama** | `github.com/ats-fukuyama/task` | Stale 2023 backup (read‑only) |

**Goal.** Bring the latest upstream base onto the modernized fork *without regression*, then make
`tr` the single canonical transport module by hand‑porting `trx`'s newer fusion physics.

---

## 2. P0 — the merge

### 2.1 Strategy

An audit established **`bpsi/develop` is the latest base**, not a 3‑way upstream merge:
`ats-fukuyama/develop` is 119 commits behind bpsi and its "unique" commits are superseded backup
snapshots. So the merge is **bpsi base → the Phase‑L fork**, keeping every kyoshimi modernization and
grafting bpsi's intent (mostly bug‑fixes + the `eq`/`tr` q‑solver refinement).

```
8eed6fc2  fork point (2025‑12‑16)
   ├─ bpsi/develop      +23 commits → fa9dd493   (latest base)
   └─ kyoshimi‑develop  +Phase‑L    → 58f1fe2e   (C‑ABI/.so/MCP/6‑module split)
        0254aa91 = merge(1st parent = kyoshimi Phase‑L, 2nd = bpsi base)  ⇒ bpsi merged INTO the fork
        + build‑integration + baseline fixes → d1f7f9e7  (CI green, delivered)
```

### 2.2 Conflict resolutions (10 files)

Each conflict = *keep kyoshimi modernization, graft bpsi intent*:

| File | Resolution |
|---|---|
| `eq/eqinit.f90` | graft bpsi values into free‑form: `NTVMAX` 200→400, `NLPMAX` 20→100 |
| `eq/eqcalc.f90` | graft bpsi `EQLOOP` adaptive under‑relaxation |
| `eq/eqcalq.f90` | graft `NPRINT` print + `NMAX` 200→400 |
| `eq/eqsub.f90` | fixed‑form continuations → free‑form; richer diagnostic |
| `pl/Makefile` | keep `noeqlib` recipes + take bpsi `SRCS_NOEQ` + `plview.f90` |
| `tr/trcomm.f90` | take‑ours (6‑module split) + idempotent `DEALLOCATE_TRCOMM` |
| `tr/trcomm_param.f90` | species param list 8 → 15 (add `PNM/PTM/PTPR/PTPP/PUM/PUPR/PUPP`) |
| `tr/trmain.f90` | take‑theirs (drop double‑free) |
| `txnew/txcalv.f90` | take‑theirs (SAVE‑workspace allocation) |
| `wrx/wrcalpwr.f90` | genuine 3‑way blend: keep headless/OOB clamp + graft bpsi `dx` |

---

## 3. Validation — the CI‑greening journey

The merge’s CI had **never been green** on the sandbox (even the pure base `develop` failed — the build
never reached pytest). Getting to green surfaced issues *class by class*:

| Fix (commit) | Problem exposed | Root cause |
|---|---|---|
| `35c4bb5f` / `4bceac38` | eq fixed‑form leak; lost wrx OOB clamp | auto‑merge artifacts |
| `4df6e541` | wrx `dx` ÷0; `trmain` dropped `USE`; non‑idempotent dealloc | pre‑push review findings |
| `d4afbaca` | `../task/make.header: No such file` | repo not named `task` |
| `17f21f2c` / `9242c127` | `PT` clash (ti/wm); `pl_view` moved plparm→plview | bpsi added a bare `PT` to `plcomm_parm`; `pl_view` module move (fp broke at **link** time) |
| `bacf3f19` | numpy missing; mcp‑servers not importable | pre‑existing test‑env gaps, latent until the build first reached pytest |
| capture + `d1f7f9e7` | 3 equivalence baselines fail on gf13.2 | see §4 |

**Result: 736 passed, 6 skipped, 1 xfail (pre‑existing), 1 xpass — CI green on Python 3.11 + 3.13.**
Delivered by fast‑forwarding `myfork/kyoshimi-develop` to `d1f7f9e7`; sandbox PR #1 merged.

### 3.1 The equivalence baselines (1e‑10 regression gate)

Three baselines drifted on the CI compiler (gfortran‑13.2); two distinct causes:

- **`wrx_demo` / `wrx_iter01`** — *compiler‑version* FP reordering (gf8.5 baseline ≠ gf13.2 CI ≠ Mac
  gf15, all within ~1e‑9). Lesson: 1e‑10 binary equivalence is too tight for FP‑heavy modules (ray
  tracing, Fokker–Planck) *across compiler versions*, not just architectures — baselines must be
  captured on the exact CI compiler.
- **`tot_ht6m_short`** — a real ~1e‑4 *physics* shift (see §4).

Because the CI env couldn’t regenerate these two classes directly, we added an **env‑gated capture**:
the equivalence tests dump each case’s freshly computed `actual` metrics under `REGEN_OUTPUT_DIR`,
uploaded as a CI artifact; those gf13.2 values were then committed as the new baselines.

---

## 4. Case study — the `tot_ht6m` q‑solver refinement

The `tot_ht6m_short` integrated (eq→tr coupled) run shifted by **~1e‑4**. Root cause: bpsi’s merged
**EQ‑solver refinements** — finer flux‑surface grid (`NMAX` 200→400) + `EQLOOP` under‑relaxation — used
by the `modelg=3` `eq_load` path. Signature (all 50 radial rows):

- **current profile redistributes** (`j` up in the core, down in the mid‑radius to −7.9e‑4 @ ρ=0.74, up
  at the edge; `q` is its integral: down core, up outer);
- **total current conserved** (`AJT` Δ 3.9e‑5 ≪ local Δ 7.9e‑4);
- **density frozen** (0/50 rows); smooth, no NaN.

Reviewed and **owner‑approved** as an intended higher‑accuracy solve; the baseline was regenerated on
gf13.2 accordingly.

> **Process lesson (a genuine save).** An early analysis mis‑characterized the shift as *core‑localized
> (ρ≤0.20)* — an artifact of a **truncated CI log** (the comparator prints only ~52 of 210 mismatches,
> which happen to be the core rows). Two independent pre‑push reviewers caught the contradiction against
> the full committed baseline; the characterization was corrected to *global redistribution* and
> re‑approved. **Truncated tool output misleads — verify conclusions against the complete data.**

---

## 5. P1 — TRX → tr consolidation (physics update)

**Goal:** make `tr` the single canonical transport module by porting `trx`’s newer fusion physics, then
archiving `trx`/`trm`.

### 5.1 Old vs new fusion physics

| | kyoshimi `tr` (old) | bpsi `trx` (new) |
|---|---|---|
| Selector | scalar `MDLNF` | `model_pnf` |
| Reactions | hardcoded D+T only (`TRNFDT`) | multi‑reaction: DT / DD / DHe3 / TT / THe3 (`libnf`) |
| Source array | 1‑D `SNF(NR)` | species‑resolved `SNF_NSNNFNR(NS,NNF,NR)` |
| Reactivity ⟨σv⟩ | analytic fit `SIGMAM(T)` | spline over a tabulated `svnf_*` |

### 5.2 The Task‑1 decision (Option A)

Recon corrected a plan premise: `tr_m0904` / `tr_iter01` **run `MDLNF=1` (fusion ON)**, so naïvely
retiring `MDLNF` would change two core baselines. A direct comparison settled the strategy:

> **The new `libnf` DT table `svnf_dt` is the same analytic fit as the old `SIGMAM`, tabulated to 2
> significant figures** (`svnf_dt` is tabulated in cm³/s, `SIGMAM` returns m³/s; the agreement below is after the cm³/s→m³/s conversion). At the table temperatures they agree to 0.03–1.2 %. But `libnf`
> splines the **raw** ⟨σv⟩ against `log10(T)` (`SPL1D`), so at core/fusion temperatures T ≳ 5 keV the
> spline stays within ~1–2 % of `SIGMAM`, while between the widely-spaced low-T edge points (T ≲ 3 keV, where
> ⟨σv⟩ is negligible and no fusion occurs) the raw-value spline overshoots strongly — immaterial to the
> fusion power. So the DT **reactivity** is the same fit at the reference points; migrating existing DT
> cases to `model_pnf` gains **zero
> physics gain**; `model_pnf`’s real value is the **multi‑reaction** capability (DD/DHe3/TT/THe3) that
> `MDLNF` lacks — which is purely additive.

**Decision — Option A:** keep the exact old `MDLNF`/`SIGMAM` DT path (3 baselines bit‑for‑bit), add
`model_pnf` as an **additive** multi‑reaction path (default off ⇒ every regression gate trivially
holds), to be validated (Tasks 2, 7) against a bpsi‑`trx` reference at 1e‑10. `MDLNF` is **not** retired.

### 5.3 Remaining plan (Tasks 2–10)

Extract collision fns → `trcoll`/`trlib` (3) · fusion data model in the split `trcomm`, inert (4) ·
port `libnf` (5) · generic `tr_pnf` dispatch gated by `model_pnf>0` (6) · bpsi‑`trx` reference oracle +
validate `model_pnf=1..4` @1e‑10 (2, 7) · species‑resolved NBI/RF arrays (8) · expose via C‑ABI /
registry / MCP (9) · archive `trx`/`trm` (10). *Deferred:* TGLF (needs external GACODE lib).

---

## 6. Lessons learned

1. **`.so`‑only tests miss static‑binary issues.** Menu files and some modules are excluded from
   `libXapi.so`; only the full static build (`tot libs`) or standalone binaries exercise them
   (`trmain` USE‑drop; four `pl_view` menu breaks — one only at *link* time).
2. **Truncated tool output misleads.** The `tot_ht6m` "core‑localized" error came from a truncated CI
   log; independent reviewers caught it against the full data.
3. **1e‑10 binary equivalence is too tight for FP‑heavy modules across compiler versions** — capture
   baselines on the exact CI compiler, or use a per‑platform tolerance.
4. **An independent‑reviewer pre‑push gate earns its keep.** Two reviewers caught three real issues the
   author missed (the link‑time `_pl_view_`, a wrong root‑cause attribution, the localization error).
5. **Physics‑change baselines need explicit owner approval and rigorous characterization** — never
   silently overwrite a reference.
6. **Verify a new capability adds physics before migrating** — the `model_pnf` DT reactivity is the same
   fit as the legacy path (~1 % rounding), so DT was kept legacy and `model_pnf` reserved for its
   genuinely new multi‑reaction value.

---

## 7. Reproduce / verify

```bash
# build (Linux/CI compiler) + the 1e‑10 + C‑ABI gates
make -C tr tr2 libtrapi.so tr_api_check_all
make -C tot libs && make -C tot tot_api_check_all && make -C tot tot
PYTHONPATH=python:python/mcp-servers python -m pytest python/ \
    --forked --timeout=120 --timeout-method=signal    # 736 passed on gf13.2

# key commits
0254aa91  merge: reconcile bpsi/develop base (23 commits) into kyoshimi‑develop
d1f7f9e7  delivered tip (CI green); 11504a9d  P1 Task‑1 decisions
```
