"""Shared agent scaffolding.

Convention (mirrors the analyst-edition plan): every agent is a self-contained
folder under `agents/<name>/` holding:
  - `agent.py`   — the agent's logic (its skill)
  - `prompt.py`  — its system prompt / instructions
  - `MEMORY.md`  — its curated, committed domain heuristics (loaded into the
                   prompt at run time; the last-known-good "memory")

`load_memory(__file__)` reads the sibling MEMORY.md so an agent's learned
heuristics travel with the code and can be reviewed/edited like any source.
"""

from __future__ import annotations

from pathlib import Path


def load_memory(agent_file: str) -> str:
    """Return the text of the MEMORY.md next to the calling agent module."""
    p = Path(agent_file).resolve().parent / "MEMORY.md"
    return p.read_text(encoding="utf-8").strip() if p.exists() else ""


def with_memory(system_prompt: str, agent_file: str) -> str:
    """Append the agent's curated memory to its system prompt, if any."""
    mem = load_memory(agent_file)
    if not mem:
        return system_prompt
    return f"{system_prompt}\n\n# Learned heuristics (agent memory)\n{mem}"
