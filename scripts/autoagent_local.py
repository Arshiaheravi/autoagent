#!/usr/bin/env python3
"""Autoagent CLI wrapper that bypasses the editable install pointing at
~/Documents/autoagent (TCC-blocked from Claude Code's bash sandbox) and
resolves engine/skills/templates from ~/.autoagent/ instead.

Use this instead of the global `autoagent` shim when running from a
TCC-restricted parent process.

Usage:
    python3 ~/.autoagent/scripts/autoagent_local.py <args>
"""
from __future__ import annotations

import os
import sys

LOCAL_ROOT = os.environ.get("AUTOAGENT_HOME", os.path.expanduser("~/.autoagent"))

# Drop the editable finder that hardcodes ~/Documents/autoagent paths.
sys.meta_path[:] = [
    f for f in sys.meta_path
    if "autoagent_agency" not in type(f).__module__
    and "autoagent_agency" not in getattr(f, "__module__", "")
]

# Put the local engine on sys.path BEFORE anything else so the regular
# import machinery resolves engine/skills/templates from here.
sys.path.insert(0, LOCAL_ROOT)

# Some submodules read project paths relative to engine.__file__ — set this
# env so dependent modules don't fall back to Documents either.
os.environ.setdefault("AUTOAGENT_ROOT", LOCAL_ROOT)

from engine.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
