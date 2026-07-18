# Contributing to adwize-audit

Thanks for your interest in improving adwize-audit! This document covers how to set up a development environment and submit changes.

## Development setup

```bash
git clone https://github.com/Adwize/adwize-audit.git
cd adwize-audit
uv venv
uv sync --extra dev
uv run playwright install chromium
```

Copy the environment template:

```bash
cp .env.sample .env
```

The LLM agents are optional — all deterministic checks and tests run without an API key.

## Running tests

```bash
uv run pytest
```

Most tests mock the Playwright browser and network calls so they run fast without a real browser session. Tests that require a live crawl are marked and skipped in CI.

## Code style

The project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
uv run ruff check .
uv run ruff format --check .
```

Configuration lives in `pyproject.toml` (line length 100, Python 3.12 target). CI enforces these checks on every PR.

## Submitting changes

1. Fork the repository and create a branch from `main`.
2. Make your changes — keep commits focused and atomic.
3. Add or update tests if you're changing behavior.
4. Run `ruff check .` and `ruff format .` before committing.
5. Open a pull request against `main` with a clear description of what and why.

## Adding a new check

Checks live in `core/checks/crawl_checks.py`. To add one:

1. Define a new checkpoint entry in `core/registry/crawl_checkpoints.yaml`.
2. Write a check function in `crawl_checks.py` that accepts the crawl snapshot and returns a `Finding`.
3. Register it in the check runner (the function is auto-discovered by checkpoint ID convention).
4. Add a test in `tests/test_scoring.py` or a dedicated test file.

## Adding a new schema

Knowledge schemas live in `core/schemas/` as YAML files. If you're adding detection for a new vendor, CMP, or PII pattern:

1. Add entries to the relevant YAML file (`vendors.yaml`, `cmp.yaml`, `pii.yaml`).
2. Update the corresponding loader if the schema shape changes.
3. Add test cases in `tests/test_schemas.py`.

## Questions?

Open an issue on GitHub — we're happy to help.
