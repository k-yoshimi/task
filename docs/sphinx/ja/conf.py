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
