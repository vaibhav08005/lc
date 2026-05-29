# Development Guide

## Local Environment

This project uses:

- Python 3.10
- `uv`
- `pytest`

Install or refresh dependencies:

```powershell
uv sync
```

Run the package:

```powershell
uv run python -m halifax_criteria evaluate input.yaml
```

Run tests:

```powershell
uv run pytest
```

## Common Commands

Show only deterministic automated rules:

```powershell
uv run python -m halifax_criteria evaluate input.yaml --no-snapshot
```

Show human-readable report:

```powershell
uv run python -m halifax_criteria evaluate input.yaml --text
```

Show every rule result in JSON:

```powershell
uv run python -m halifax_criteria evaluate input.yaml --show-all-rules
```

Evaluate an additional test case:

```powershell
uv run python -m halifax_criteria evaluate test-cases/additional-raw-case-48-joint-ftb-high-commitments-part-and-part.yaml --no-snapshot
```

## Test Coverage

Tests live in:

`tests/test_evaluator.py`

Current coverage includes:

- sample-case derivations
- LTV fail scenarios
- maximum-term fail scenarios
- missing DOB handling
- applicant count fail scenarios
- non-UK residency referral
- new-build flat cap
- builder incentive cap
- credit-card 5% balance treatment
- BTL shortfall referral
- worst-rule-wins result ordering
- snapshot catalogue integrity

## Coding Guidelines

- Keep rule logic deterministic and side-effect free.
- Prefer returning `REFER` over pretending to know Halifax internal decisions.
- Prefer returning `INSUFFICIENT_DATA` when an input field is needed for a real rule.
- Keep rule messages readable for a broker or reviewer.
- Keep historical criteria versions intact.
- Add tests with every new automated rule.

## Output Debugging

The default JSON intentionally omits passing rules to keep output manageable. It includes:

- `derived`
- `rule_summary`
- `missing_fields`
- `issues`

Use `--show-all-rules` when you need the full `rule_results` list.

## Git Hygiene

Ignored local files include:

- `.venv/`
- `.pytest_cache/`
- `__pycache__/`
- extracted Codex transcript files

Do not commit local runtime caches or generated virtual environments.
