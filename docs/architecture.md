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

5. `halifax_criteria.rules.halifax_2026_05`
   - Holds deterministic rules for the dated Halifax criteria version.
   - Exposes `evaluate_rules`.
   - Adds snapshot catalogue results when enabled.

6. `halifax_criteria.rules.snapshot_catalogue`
   - Parses the saved Halifax HTML snapshot.
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

## Snapshot Catalogue Design

The Halifax source page contains many criteria statements that cannot all become deterministic code immediately. Instead of ignoring them, the project stores a dated HTML snapshot and parses visible text into catalogue entries.

Catalogue entries:

- have stable generated `rule_id` values
- point to the Halifax source URL
- use `MANUAL_REFER`
- show as `REFER` results

This gives broad criteria coverage while keeping automated rules honest.

## Why Versioned Rules

Lender criteria changes over time. A dated rule module such as `halifax_2026_05.py` makes it clear which published criteria version was used for a result. Future updates should add a new module and snapshot, not silently rewrite history.
