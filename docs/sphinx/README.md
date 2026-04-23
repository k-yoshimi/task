# TASK library manual — Sphinx sources

This directory hosts the Sphinx sources for the TASK library user manual.
It supersedes the standalone LaTeX document at
`docs/manual/task-library-manual.tex`, which is now frozen at its 2026-04
snapshot.

## Layout

```
docs/sphinx/
├── README.md                 (this file)
├── requirements.txt          pip install target
├── Makefile                  builds both language trees
├── conf_common.py            shared Sphinx config (extensions, autodoc, MyST)
├── en/                       English tree (independent Sphinx project)
│   ├── conf.py               imports conf_common, sets language='en'
│   ├── index.md
│   ├── common/architecture.md
│   ├── tr/index.md           (full chapter)
│   └── {eq,ti,fp,wr,wrx,tot}/index.md   (placeholders)
├── ja/                       Japanese tree (same shape as en/)
└── shared/notebooks/         executable notebooks included from both trees
```

## i18n strategy

We use the **parallel-tree** strategy: `en/` and `ja/` are two independent
Sphinx projects with their own `conf.py`. Source prose is edited in both
languages directly — no `.po` files involved. The trade-off is that we
rely on reviewer discipline to keep the trees in sync; PRs that modify
one tree should state whether the other tree needs a matching update.

`sphinx-intl` is present in `requirements.txt` so we can migrate to a
gettext-driven flow later without re-architecting the project.

## Building

```bash
pip install -r docs/sphinx/requirements.txt     # one-time
cd docs/sphinx
make              # builds both en and ja into _build/{en,ja}
make en           # only the English tree
make ja           # only the Japanese tree
make linkcheck-en
make clean
```

The default `SPHINXOPTS = -W --keep-going` treats warnings as errors
(CI-strict). Nitpicky mode (`-n`) is opt-in — many existing wrapper
docstrings use unqualified `:class:` refs that would otherwise warn,
so nitpicky is promoted to the default only after those docstrings are
hardened. Override for local dev:

```bash
make SPHINXOPTS="" en
```

## Notebooks

Jupyter notebooks live under `docs/sphinx/shared/notebooks/` and are
symlinked or copied into both language trees. They are included via
`myst-nb` with `nb_execution_mode = "off"` — we commit pre-executed
output cells for determinism. To re-execute before committing:

```bash
jupyter nbconvert --to notebook --execute --inplace <notebook>.ipynb
```

## Contribution contract

1. A code change that adds/removes a public Python-wrapper symbol
   should include a matching documentation update in at least `en/`
   (JA counterpart can trail by one PR if time-constrained, but must be
   linked via an issue).
2. A change to a Fortran API signature must update the relevant chapter
   in both trees (or leave a TODO pointing at the issue).
3. `make` must pass cleanly (`-W`) before merge. CI enforces this.
