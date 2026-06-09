# TASK Repository Folder Inventory & Reorganization Slides — Design (2026-06-09)

## 1. Purpose & Scope

The TASK repository has accumulated ~60 top-level directories mixing several
"worlds": the active Python-ization / refactoring project, inherited upstream
Fortran modules, personal/experimental mirror folders, and documentation that
has grown organically into multiple parallel systems.

This deliverable is a **stocktake (棚卸し) first** — classify the current state,
**no physical moves yet**. The output is a **slide deck** (not a README section)
that presents the folder taxonomy and surfaces reorganization candidates for
later discussion.

**Hard constraint (carried from project memory):** physical moves/deletes of
upstream Fortran module trees (eq/tr/fp/wr/wm/wf… bodies) require
ats-fukuyama sign-off. C-ABI / wrappers / registry / tests / docs are out of
that constraint. This spec therefore **only inventories**; it proposes no
Fortran-tree moves.

**Out of scope (this iteration):** physical `git mv`/deletion of any folder;
per-folder classification of the "personal variant" group (group C) — those
rows are intentionally left as **TBC (要確認) placeholders** for the user to
fill in.

## 2. Deliverable

- **Format:** PowerPoint (`.pptx`), language **English**.
- **Tooling:** follow the existing project convention — a python-pptx build
  script under `docs/slides/`, mirroring `build_status_2026-05-25.py`
  (16:9 = 13.333"×7.5", established color palette, textbox/title helpers).
- **Build script:** `docs/slides/build_folder_inventory_2026-06-09.py`
- **Output deck:** `docs/slides/2026-06-09-task-folder-inventory.pptx`
- Reuse color/layout helpers from the existing build scripts; do not introduce
  a new slide toolchain (no Marp, no separate designer system).

## 3. Classification Taxonomy

Four categories, color-coded on the slides:

- **A — Project-owned, active (Phase L refactoring).** Folders this project
  actively edits: the Phase L Fortran modules plus their Python wrappers,
  MCP servers, and project docs/scripts.
- **B — Upstream "current" modules (inherited).** Modules documented in the
  root `README` as present modules. Moving these needs ats-fukuyama sign-off.
- **C — Personal variants / experimental mirrors (TBC).** Person-suffixed or
  derivative folders that are archive candidates. **Each row left as
  "TBC — user to classify."**
- **D — Documentation redundancy / cleanup targets.** Overlapping doc roots,
  build-artifact contamination, thin folders, stray files.

## 4. Folder Inventory (source content for the deck)

Signals captured: last git-commit date (note: most read 2026-04-17/18 = bulk
import; later dates indicate folders this project actually touched), and
whether the folder is a buildable module (has a `Makefile`).

### A — Project-owned, active (Phase L)

| Folder | Role | Last touch |
|---|---|---|
| `eq` | 2D equilibrium (Phase L body) | 2026-05-13 |
| `tr` | 1D transport (Phase L body) | 2026-05-13 |
| `fp` | Fokker–Planck (Phase L body) | 2026-04-26 |
| `wr` | ray tracing (Phase L body) | 2026-04-26 |
| `wrx` | ray tracing variant (Phase L body) | 2026-04-26 |
| `ti` | transport/impurity (Phase L body) | 2026-04-26 |
| `tot` | all-in-one aggregate (Phase L body) | 2026-05-25 |
| `python/{eqlib,fplib,tilib,totlib,trlib,wrlib,wrxlib}` | Python wrappers | 2026-06-08 |
| `python/mcp-servers` | per-module MCP servers | 2026-06-08 |
| `docs/` | project documentation root (sphinx, manual, design, slides) | 2026-06-08 |
| `scripts/` | project scripts (pre-push, etc.) | 2026-05-11 |
| `test_run/` | test run fixtures/outputs | 2026-06-02 |

### B — Upstream "current" modules (inherited; sign-off to move)

| Group | Folders |
|---|---|
| Interface / equilibrium | `pl` (old per README), `equ` |
| Transport | `trn`, `tx`, `txnew` |
| Waves | `dp`, `w1`, `wm`, `wmf`, `wf2`, `wf3`, `wf2d`, `wf3d` |
| Other physics | `fit3d`, `ob`, `pic`, `pt` |
| Libraries | `lib`, `mtxp`, `gsaf` (graphics), `trmodels`, `trlib` (legacy C-ABI, 2024-05) |
| Tools / IO | `tools`, `bin`, `adpost`, `template`, `imas`, `imas-ids`, `open-adas` |

(`eq`/`tr`/`fp`/`wr`/`wrx`/`ti`/`tot` are upstream modules too, but listed in
A because they are the Phase L bodies under active edit.)

### C — Personal variants / experimental mirrors (TBC — user to classify)

| Lineage | Folders | Disposition |
|---|---|---|
| fp | `fp.anzai`, `fp.nuga`, `fp.ota`, `fpx` | TBC |
| wm | `wmseki`, `wmfn`, `wmx` | TBC |
| dp | `dpseki` | TBC |
| w-impurity | `wi`, `wim`, `wiq`, `wq` | TBC |
| tr | `trm`, `trx` | TBC |
| wf | `wf2dt`, `wf2dx` | TBC |
| other | `t2`, `tf2d`, `sak`, `demo-ec`, `sample` | TBC |

> Group C disposition is intentionally blank. The deck renders each row with a
> "TBC" badge; the user fills the actual classification (keep / archive /
> upstream-only) afterward.

### D — Documentation redundancy / cleanup targets

| Item | Finding |
|---|---|
| `doc/` vs `docs/` | `doc/` (2025) = legacy LaTeX manual sources; `docs/` (2026) = new project docs. Two parallel doc roots. |
| `docs/doc-design/` | LaTeX design-doc sources **with build artifacts committed/present** (`.aux/.dvi/.log/.out/.toc`); `.sty` files duplicate `doc/`. |
| `docs/*-library/` ×7 | `eq/fp/ti/tot/tr/wr/wrx-library` each hold a single `architecture.md` — very thin folders. |
| Stray / generated | `make.header.bak`, `tr/libtrapi.so`, scattered `.DS_Store`. Note: `fort.*`, `*.mod`, `*.so`, `RLAMDAG.dat` are already gitignored (not tracked). |

## 5. Slide Outline (8–10 slides, English)

1. **Title** — TASK Repository: Folder Inventory & Reorg Plan (2026-06-09)
2. **Purpose & scope** — stocktake first, no physical moves; Fortran-tree moves
   need ats-fukuyama sign-off.
3. **Big picture** — ~60 folders → 4 categories (A–D) with color legend.
4. **A — Project-owned active (Phase L)** — table from §4.A.
5. **B — Upstream current modules** — grouped table from §4.B.
6. **C — Personal variants / mirrors** — table from §4.C, every row badged
   **TBC** for the user to fill.
7. **D — Documentation cleanup targets** — table from §4.D.
8. **Next-phase options (undecided)** — e.g. consolidate `doc/`→`docs/`, strip
   LaTeX build artifacts from `docs/doc-design/`, decide fate of group C;
   any Fortran-tree move goes via `git mv` + sign-off.
9. *(optional)* **Held / excluded** — group C per-folder judgement deferred to
   user; no moves executed this iteration.

## 6. Self-review notes

- No "TODO"/placeholders other than the **intentional** group-C "TBC" rows
  (documented as a deliberate hand-off, §3/§4.C).
- Internally consistent: §4 tables are the literal source for §5 slides.
- Scope: single deliverable (one build script → one deck); no decomposition
  needed.
- Disambiguated: "inventory only, no moves" stated in §1, §2 out-of-scope, and
  the §5 closing slide.
