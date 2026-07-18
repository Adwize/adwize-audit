# Agents

Each agent is a self-contained folder (the convention the analyst edition
scales up):

```
agents/<name>/
  agent.py    # the agent's logic / skill
  prompt.py   # its system prompt (instructions)
  MEMORY.md   # curated, committed domain heuristics, loaded into the prompt
```

`agents/_base.py` provides `with_memory(system_prompt, __file__)`, which appends
the folder's `MEMORY.md` to the prompt so an agent's learnings travel with the
code and are reviewable like any source.

All LLM agents are **key-gated**: without `OPENAI_API_KEY` they no-op, and the
deterministic pipeline runs unaffected.

## Agents in this (OSS) edition

- **`analyst/`** — turns deterministic scan findings into an executive summary +
  prioritized recommendations. Runs during `audit scan` when a key is set.
- **`schema_maintainer/`** — owns the YAML knowledge in `core/schemas/`. Its
  skill: discover GTM tag functions seen in scans that the schema doesn't map,
  classify them (LLM), and write updates to `$ADWIZE_SCHEMA_DIR` (which the
  schema loader prefers over the committed fallback). Drive it with
  `adwize-audit schema discover` / `adwize-audit schema learn`.

The authenticated analyst edition adds the orchestrator + specialist auditors +
synthesizer + doc-writer under this same convention, in a separate private repo.
