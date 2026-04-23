"""Sphinx configuration for the Japanese build of the TASK library manual."""
from __future__ import annotations

import os
import sys

# Import shared config.
sys.path.insert(0, os.path.abspath(".."))
from conf_common import *  # noqa: E402,F401,F403

language = "ja"
project = "TASK プラズマライブラリ マニュアル"
html_title = "TASK プラズマライブラリ — ユーザマニュアル"
html_short_title = "TASK マニュアル (JA)"

# PDF: override the shared English title + load xeCJK. The xeCJK / Noto
# Serif CJK JP dependency is isolated here, so `make pdf-en` builds
# without any CJK fonts installed. `author`, `latex_elements`, and
# `latex_documents` are imported from conf_common via `from … import *`.
_ja_preamble = r"""
\usepackage{xeCJK}
\setCJKmainfont{Noto Serif CJK JP}
\setCJKsansfont{Noto Sans CJK JP}
\setCJKmonofont{Noto Sans Mono CJK JP}
"""
latex_elements = {**latex_elements, "preamble": latex_elements.get("preamble", "") + _ja_preamble}  # noqa: F405,F821
latex_documents = [("index", "task_manual.tex", project, author, "manual")]  # noqa: F405
