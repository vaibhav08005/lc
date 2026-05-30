# Mortgage Criteria Evaluator

An indicative UK mortgage lending criteria evaluator for broker-style YAML case inputs. It currently supports Halifax and Barclays residential criteria packs.

The tool reads a YAML application, normalizes the `var_...` fields into a mortgage case, runs versioned lender criteria checks, and returns a structured decision report. It is designed for pre-screening and case triage, not for guaranteeing a lender mortgage approval.

## Important Disclaimer

This project does not reproduce a lender's final underwriting decision. Internal credit scoring, full affordability models, valuation outcomes, and underwriter discretion are not public. Where published criteria cannot be evaluated deterministically, the tool returns `REFER`, `INSUFFICIENT_DATA`, or a manual-review catalogue item.

Primary source snapshots:

`data/sources/halifax_intermediaries_criteria_2026-05-30.html`

`data/sources/barclays_intermediaries_residential_criteria_2026-05-31.html`

Source URLs:

https://www.halifax-intermediaries.co.uk/criteria.html

https://intermediaries.uk.barclays/home/lending-criteria/residential/

## What It Does

- Loads broker-style YAML input such as `input.yaml`.
- Normalizes applicant, income, mortgage, deposit, property, commitment, and background-property fields.
- Calculates derived values such as loan amount, LTV, base LTI, core LTI, total LTI, term years, and applicant count.
- Runs deterministic lender pre-screen rules where published criteria and input data are available.
- Represents visible lender criteria snapshots as auditable catalogue entries so criteria topics are not silently dropped.
- Builds a structured Barclays residential A-Z catalogue from accordion sections, paragraphs, list items, and table rows.
- Produces JSON by default, with an optional readable terminal table.

## Result Model

The overall result uses worst-rule-wins:

1. `FAIL` if any hard automated rule fails.
2. `INSUFFICIENT_DATA` if no hard fail exists but required facts are missing.
3. `REFER` if no hard fail/missing-data blocker exists but manual or proprietary checks remain.
4. `PASS` only when all evaluated checks pass and no manual/missing-data item remains.

Rule statuses:

- `PASS`: the supplied case passes that rule.
- `FAIL`: the supplied case breaches a hard rule.
- `REFER`: the case may be acceptable but needs broker/manual/Halifax review.
- `INSUFFICIENT_DATA`: required facts are missing from the input.

Automation levels:

- `AUTOMATED`: deterministic rule implemented in code.
- `MANUAL_REFER`: criteria exists but needs human review.
- `INSUFFICIENT_DATA`: criteria cannot be evaluated because input fields are missing.
- `OUT_OF_SCOPE_PROPRIETARY`: criteria depends on unavailable Halifax systems or judgement.

## Setup

Requirements:

- Python 3.10
- `uv`

Install dependencies:

```powershell
uv sync
```

Check Python version used by the project:

```powershell
uv run python --version
```

Expected major/minor version:

```text
Python 3.10.x
```

## Run

Evaluate the default sample file:

```powershell
uv run python -m halifax_criteria evaluate input.yaml
```

Evaluate with an explicit lender:

```powershell
uv run python -m halifax_criteria evaluate input.yaml --lender halifax
uv run python -m halifax_criteria evaluate input.yaml --lender barclays
```

Evaluate a different YAML case:

```powershell
uv run python -m halifax_criteria evaluate test-cases/additional-raw-case-45-joint-home-mover-high-variable-income-btl-surplus.yaml
```

Print a readable terminal report:

```powershell
uv run python -m halifax_criteria evaluate input.yaml --text
```

Run only deterministic automated rules, excluding snapshot catalogue items:

```powershell
uv run python -m halifax_criteria evaluate input.yaml --no-snapshot
```

Include every rule result in JSON output:

```powershell
uv run python -m halifax_criteria evaluate input.yaml --show-all-rules
```

By default, JSON output includes `issues` only, meaning failed and refer rules. Use `--show-all-rules` when debugging pass rules or catalogue coverage.

For Barclays, full output includes both automated rules and the structured A-Z catalogue stored at:

`data/catalogues/barclays_residential_criteria_2026-05-31.json`

## Example Output Shape

```json
{
  "lender": "Barclays",
  "criteria_version": "2026-05-31",
  "source_url": "https://intermediaries.uk.barclays/home/lending-criteria/residential/",
  "overall_result": "INSUFFICIENT_DATA",
  "derived": {
    "loan_amount": 200000.0,
    "ltv_percent": 66.67,
    "base_lti_multiple": 1.54,
    "lti_multiple": 1.38,
    "mortgage_term_months": 240,
    "applicant_count": 2,
    "barclays_selected_ltv_cap": 90.0,
    "barclays_ltv_cap_reason": "customer retaining more than one mortgaged residential property cap"
  },
  "rule_summary": {
    "total": 880,
    "pass": 17,
    "fail": 0,
    "refer": 727,
    "insufficient_data": 136
  },
  "missing_fields": [
    "var_appl1_date_of_birth",
    "var_appl2_date_of_birth"
  ],
  "issues": []
}
```

## Test

Run the full test suite:

```powershell
uv run pytest
```

The tests cover sample-case derivations, hard-rule failures, missing-data behavior, BTL shortfall logic, credit-card commitment treatment, and snapshot catalogue integrity.

## Project Documentation

- [Architecture](docs/architecture.md)
- [Input Format](docs/input-format.md)
- [Rules and Criteria Catalogue](docs/rules-and-catalogue.md)
- [Development Guide](docs/development.md)

## Repository Layout

```text
.
|-- data/sources/
|   |-- halifax_intermediaries_criteria_2026-05-30.html
|   `-- barclays_intermediaries_residential_criteria_2026-05-31.html
|-- data/catalogues/
|   `-- barclays_residential_criteria_2026-05-31.json
|-- docs/
|-- src/halifax_criteria/
|   |-- cli.py
|   |-- evaluator.py
|   |-- input_loader.py
|   |-- models.py
|   |-- normalizer.py
|   `-- rules/
|       |-- barclays_2026_05.py
|       |-- barclays_catalogue.py
|       |-- halifax_2026_05.py
|       `-- snapshot_catalogue.py
|-- test-cases/
|-- tests/
|-- input.yaml
|-- pyproject.toml
`-- uv.lock
```

## Maintenance Notes

When lender criteria changes, create a new dated snapshot and a new versioned rule module rather than editing historical criteria in place. This keeps old decisions explainable and allows future comparisons between criteria versions.
