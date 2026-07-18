"""Per-agent model selection.

Each agent gets its own default model (matched to its job), overridable via env.
Precedence for `model_for(agent)`:
  1. ADWIZE_MODEL_<AGENT>   — explicit per-agent override
  2. ADWIZE_OPENAI_MODEL    — global override for all agents
  3. the per-agent default below
"""

from __future__ import annotations

import os

# analyst does the reasoning/synthesis → a stronger model; schema_maintainer
# just classifies short codes → a cheap, fast model.
DEFAULTS: dict[str, str] = {
    "analyst": "gpt-4o",
    "schema_maintainer": "gpt-4o-mini",
}
_FALLBACK = "gpt-4o-mini"


def model_for(agent: str) -> str:
    specific = os.getenv(f"ADWIZE_MODEL_{agent.upper()}")
    if specific:
        return specific
    glob = os.getenv("ADWIZE_OPENAI_MODEL")
    if glob:
        return glob
    return DEFAULTS.get(agent, _FALLBACK)
