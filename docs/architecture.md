# Architecture

This project is a small Python package built around a clear pipeline:

```text
YAML input
  -> input loader
  -> normalizer
  -> canonical mortgage case
  -> versioned Halifax rules
  -> rule results
  -> overall decision report
```

## Runtime Flow

1. `halifax_criteria.cli`
   - Parses CLI arguments.
   - Calls `evaluate_file`.
   - Prints JSON by default or a Rich text table with `--text`.

2. `halifax_criteria.input_loader`
   - Reads YAML with `yaml.safe_load`.
   - Requires the root document to be a mapping.

3. `halifax_criteria.normalizer`
   - Converts broker-style `var_...` fields into a `MortgageCase`.
   - Converts blank strings to `None`.
   - Converts money-like values to `float`.
   - Annualizes simple frequency-based income fields.
   - Builds one `Applicant` object per applicant.

4. `halifax_criteria.models`
   - Defines the core dataclasses:
     - `Applicant`
     - `MortgageCase`
     - `RuleResult`
   - Defines enums:
     - `RuleStatus`
     - `AutomationLevel`

5. `halifax_criteria.rules.<lender>_<version>`
   - Holds deterministic rules for the dated lender criteria version.
   - Exposes `evaluate_rules`.
   - Adds snapshot catalogue results when enabled.

6. `halifax_criteria.rules.snapshot_catalogue`
   - Parses saved lender HTML snapshots.
   - Converts visible criteria text into manual-review catalogue entries.
   - Ensures visible criteria items are represented even when not automated.

7. `halifax_criteria.evaluator`
   - Calculates derived report values.
   - Applies worst-rule-wins decisioning.
   - Builds the final JSON-compatible report.

## Decision Flow

The evaluator deliberately separates rule-level outcomes from the final case outcome.

Rule-level outcome examples:

- LTV is within max cap: `PASS`
- Term exceeds 40 years: `FAIL`
- DOB is missing: `INSUFFICIENT_DATA`
- Property acceptability needs valuation/manual review: `REFER`

Overall outcome is then calculated with this precedence:

```text
FAIL > INSUFFICIENT_DATA > REFER > PASS
```

This makes the report conservative. A case with strong headline LTV/LTI may still be `INSUFFICIENT_DATA` if DOB, property, or adverse-credit facts are missing.

## Lender Rule Packs

Supported rule packs:

- `halifax_2026_05`
- `barclays_2026_05`

The CLI selects the rule pack with `--lender`. Halifax remains the default for backward compatibility.

The Barclays implementation is split by concern:

- `barclays_applicant`
- `barclays_lending`
- `barclays_income`
- `barclays_credit`
- `barclays_property`
- `barclays_schemes`
- `barclays_documentation`
- `barclays_portfolio`

`barclays_2026_05` is the orchestrator that combines these grouped rules with the structured Barclays catalogue.

## Snapshot Catalogue Design

Lender source pages contain many criteria statements that cannot all become deterministic code immediately. Instead of ignoring them, the project stores dated HTML snapshots and parses visible text into catalogue entries.

Barclays has a dedicated extractor in `barclays_catalogue.py`. It parses the residential A-Z accordion titles and content, then writes:

`data/catalogues/barclays_residential_criteria_2026-05-31.json`

The catalogue currently represents all 60 visible Barclays residential A-Z sections and 848 source-backed criteria statements.

Catalogue entries:

- have stable generated `rule_id` values
- point to the relevant lender source URL
- carry an automation classification such as `AUTOMATED`, `MANUAL_REFER`, `INSUFFICIENT_DATA`, or `OUT_OF_SCOPE_PROPRIETARY`
- show conservative review-oriented results unless a deterministic rule evaluates the case directly

This gives broad criteria coverage while keeping automated rules honest.

## Why Versioned Rules

Lender criteria changes over time. A dated rule module such as `halifax_2026_05.py` makes it clear which published criteria version was used for a result. Future updates should add a new module and snapshot, not silently rewrite history.
