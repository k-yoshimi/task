"""Sphinx configuration for the English build of the TASK library manual."""
from __future__ import annotations

import os
import sys

# Import shared config.
sys.path.insert(0, os.path.abspath(".."))
from conf_common import *  # noqa: E402,F401,F403

language = "en"
project = "TASK Plasma Library Manual"
html_title = "TASK Plasma Library — User Manual"
html_short_title = "TASK Manual (EN)"
