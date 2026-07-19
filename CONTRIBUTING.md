# Contributing to Conductor

Thanks for helping improve Conductor.

## Before opening a change

1. Search existing issues and discussions for related work.
2. Open an issue before proposing a large feature or architectural change.
3. Keep each pull request focused on one concern.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pre-commit install
make check
```

## Expectations

- Add tests for behavior changes.
- Preserve module boundaries and avoid hidden cross-module dependencies.
- Update documentation when contracts or decisions change.
- Use clear commit and pull-request descriptions that explain intent and trade-offs.
- Never commit models, generated datasets, credentials, or local environment files.

All participants must follow the [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).
