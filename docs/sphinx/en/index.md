# TASK Plasma Library Manual

Welcome to the user manual for the TASK family of plasma-physics modules,
re-packaged as in-process shared libraries (`lib{eq,tr,ti,fp,wr,wrx,tot}api.so`)
with thin `ctypes`-based Python wrappers (`python/{eq,tr,ti,fp,wr,wrx,tot}lib`).

The manual is published in two parallel language trees. This is the English
tree; the Japanese version lives under `../ja/`. Both trees stay in sync
through reviewer discipline — see `docs/sphinx/README.md` for the
contribution contract.

```{note}
This Sphinx manual supersedes the standalone LaTeX document at
`docs/manual/task-library-manual.tex`, which is now frozen at its 2026-04
snapshot. New changes land here.
```

## Audience

This manual is written for researchers and engineers who want to call the
TASK modules from Python (or directly through the C ABI). Readers are
assumed to be comfortable with Python and plasma-physics terminology, but
no prior exposure to the legacy `tr2` / interactive menu workflow is required.

## Contents

```{toctree}
:maxdepth: 2
:caption: Foundation

common/architecture
```

```{toctree}
:maxdepth: 2
:caption: Modules

tr/index
eq/index
ti/index
fp/index
wr/index
wrx/index
tot/index
```

## Status snapshot

| Chapter | State |
|---------|-------|
| Common architecture | full port from LaTeX Ch.2 |
| `tr` | full port + autodoc + quickstart notebook |
| `eq` / `ti` / `fp` / `wr` / `wrx` / `tot` | placeholder (to be fleshed out in follow-up PRs) |

## Indices

* {ref}`genindex`
* {ref}`modindex`
