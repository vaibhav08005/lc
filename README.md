# Halifax Criteria Evaluator

Indicative Halifax mortgage lending criteria evaluator for broker-style YAML inputs.

This tool is a pre-screen. It cannot predict Halifax's final decision because credit scoring, full affordability, valuation, and underwriting discretion are not public.

## Setup

The project is managed with `uv` and Python 3.10.

```powershell
uv sync
```

## Run

```powershell
uv run python -m halifax_criteria evaluate input.yaml
```

For a readable table:

```powershell
uv run python -m halifax_criteria evaluate input.yaml --text
```

To run only deterministic automated rules without the criteria snapshot catalogue:

```powershell
uv run python -m halifax_criteria evaluate input.yaml --no-snapshot
```

## Test

```powershell
uv run pytest
```

## Criteria Snapshot

The dated Halifax source snapshot is stored at:

`data/sources/halifax_intermediaries_criteria_2026-05-30.html`

Automated rules handle deterministic checks. The remaining visible criteria page content is represented as manual-review catalogue entries so criteria topics are not silently dropped.
