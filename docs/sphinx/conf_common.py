"""Shared Sphinx configuration for the TASK library manual.

Both ``docs/sphinx/en/conf.py`` and ``docs/sphinx/ja/conf.py`` import this
module via::

    import os, sys
    sys.path.insert(0, os.path.abspath(".."))
    from conf_common import *  # noqa: F401,F403

and then override the language-specific settings (``language``,
``project``, etc.).
"""
from __future__ import annotations

import os
import sys

# -- Make the in-repo Python wrapper packages importable for autodoc ---------
# Layout:  <repo>/python/{eqlib,trlib,...}
#          <repo>/docs/sphinx/{en,ja}/conf.py   (two dirs up)
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(_REPO_ROOT, "python"))

# -- Project metadata (common) -----------------------------------------------
author = "BPSI (Kyoto University) / TASK library team"
copyright = "2026, BPSI — Kyoto University"
version = "L-6"
release = "L-6"

# -- General configuration ---------------------------------------------------
extensions = [
    # myst_nb transitively registers myst_parser, so we only list myst_nb
    # here; listing both triggers a "setting already registered" crash.
    "myst_nb",               # Markdown (.md) + Jupyter notebook integration
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",   # Google / NumPy docstring styles
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.mathjax",
    "sphinx_copybutton",
    "sphinx_design",
]

# MyST options: enable a reasonable set of extensions.
myst_enable_extensions = [
    "colon_fence",      # ::: directives
    "deflist",
    "fieldlist",
    "tasklist",
    "attrs_inline",
    # "linkify" auto-link detection removed — requires linkify-it-py, not
    # worth adding an extra dep for minor convenience.
]
myst_heading_anchors = 3

# myst-nb: don't execute by default (we pre-run notebooks). Can be flipped to
# "auto" once notebooks are cached-friendly.
nb_execution_mode = "off"

# Files Sphinx should recognise as source.  When myst_nb is in extensions
# it auto-registers parsers for .md and .ipynb; we only need to enumerate
# .rst ourselves.
source_suffix = {
    ".rst": "restructuredtext",
}

# Paths Sphinx searches inside srcdir; overridden per-language if needed.
templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "**.ipynb_checkpoints"]

# Autodoc: class docstrings inherit __init__; type hints in description.
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}
autodoc_typehints = "description"
autoclass_content = "both"   # merge class + __init__ docstrings

# Napoleon: render "Attributes:" blocks as inline :ivar: fields instead of
# standalone `.. attribute::` directives. This avoids duplicate-object
# warnings when autodoc ALSO picks up dataclass fields (the Attributes
# block docs them, and autoclass ``:members:`` would register them again).
napoleon_use_ivar = True

# -- LaTeX / PDF output ------------------------------------------------------
# Run `make pdf-en` or `make pdf-ja` to build; see Makefile for the xelatex
# pipeline. Requires: xelatex + Noto Serif CJK JP fonts.
#   Apt:     texlive-xetex texlive-lang-japanese fonts-noto-cjk
#   TinyTeX: tlmgr install cmap fontspec polyglossia collection-latexrecommended \
#                         fncychap tabulary titlesec varwidth wrapfig \
#                         capt-of eqparbox needspace
#   (`fontspec` is not part of collection-latexrecommended; it is required
#   by the `fontpkg` block below.)
latex_engine = "xelatex"

# Sphinx picks `jsbook` as the document class when language='ja', which
# requires (u)pLaTeX and is incompatible with xelatex. Force the English
# `report` class so xelatex + xeCJK can render the Japanese build too.
latex_docclass = {
    "howto": "article",
    "manual": "report",
}

latex_elements = {
    "papersize": "a4paper",
    "pointsize": "11pt",
    # Override Sphinx's default font pins (which select FreeSerif etc. that
    # aren't on minimal TeX Live installs). `fontpkg` is injected BEFORE
    # Sphinx's own \setmainfont defaults, so we win.
    "fontpkg": r"""
\usepackage{fontspec}
\setmainfont{DejaVu Serif}
\setsansfont{DejaVu Sans}
\setmonofont{DejaVu Sans Mono}
""",
    # Force polyglossia to treat English as the main language regardless of
    # the Sphinx-level `language` setting. Otherwise the JA build asks
    # polyglossia for Japanese, which then insists on a CJK-capable main
    # roman font. Let a per-language preamble (in ja/conf.py) add xeCJK
    # when CJK rendering is actually required — that way `make pdf-en`
    # works without CJK fonts installed.
    "babel": r"""
\usepackage{polyglossia}
\setdefaultlanguage{english}
""",
    # `preamble` is appended per-language in en/conf.py and ja/conf.py.
    "preamble": "",
    # fncychap's Bjornstrup style requires pzc (Zapf Chancery) metrics that
    # aren't in minimal TeX installs; empty string lets Sphinx fall back to
    # its default chapter style.
    "fncychap": "",
    "figure_align": "H",
}

latex_documents = [
    ("index", "task_manual.tex", "TASK Plasma Library Manual",
     author, "manual"),
]

# Intersphinx: link out to Python + numpy.
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
}

# -- HTML output -------------------------------------------------------------
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_css_files: list[str] = []  # per-language confs may append

# Hide "View page source" if we're embedding release tags, etc.
html_theme_options = {
    "collapse_navigation": False,
    "navigation_depth": 4,
    "titles_only": False,
}

# -- Copybutton: skip the "$" and ">>>" prompts ------------------------------
copybutton_prompt_text = r">>> |\$ |# "
copybutton_prompt_is_regexp = True

# -- i18n reminder -----------------------------------------------------------
# We use the *parallel-tree* i18n strategy (`docs/sphinx/en/` and
# `docs/sphinx/ja/` are independent Sphinx projects).  Each PR that changes
# one tree should mention whether the other tree also needs an update.
# A future migration to gettext-based i18n would add `.po` files under
# `docs/sphinx/locales/`; `sphinx-intl` is already in requirements.txt for
# that eventuality.
