"""autopilot: a code orchestrator that runs Claude Code headlessly against a locked plan contract.

The model drafts the plan and implements one item per fresh session. Everything that
decides (lint, lock, judge, loop control, report) is code. See plans/ for the design.
"""

__version__ = "0.1.0"
