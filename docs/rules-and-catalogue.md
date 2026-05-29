# Rules and Criteria Catalogue

The project has two coverage layers:

1. Automated rules for criteria that can be evaluated from public Halifax criteria and available input fields.
2. Snapshot catalogue entries for visible Halifax criteria text that still requires manual review or future automation.

## Automated Rules

Automated rules live in:

`src/halifax_criteria/rules/halifax_2026_05.py`

Current automated rule groups:

| Rule ID | Category | Purpose |
| --- | --- | --- |
| `halifax.applicants.count` | applicant | Checks applicant count and flags more than 4 applicants. |
| `halifax.ltv.standard_limits` | loan_to_value | Checks standard Halifax LTV/loan-size limits. |
| `halifax.ltv.90_to_95_purchase` | loan_to_value | Applies extra restrictions above 90% LTV. |
| `halifax.term.maximum` | term | Checks maximum 40-year term. |
| `halifax.age.maximum_at_term_end` | age | Checks maximum age at term end when DOBs are supplied. |
| `halifax.repayment.type` | repayment | Checks repayment type and interest-only referral/fail conditions. |
| `halifax.lti.published_matrix` | lti | Applies an indicative public LTI matrix. |
| `halifax.residency.non_uk_nationals` | residency | Screens nationality and residency status. |
| `halifax.employment.minimum_time_and_evidence` | employment | Screens basic permanent employed cases and refers others. |
| `halifax.deposit.source_acceptance` | deposit | Screens deposit source issues. |
| `halifax.deposit.builder_incentive` | deposit | Checks loan plus builder incentive against LTV cap. |
| `halifax.property.acceptability` | property | Requires property facts and flags obvious excluded types. |
| `halifax.property.new_build_caps` | property | Applies new-build/converted cap logic where indicated. |
| `halifax.commitments.credit_cards` | commitments | Uses 5% of card balance when higher than declared payment. |
| `halifax.background_mortgages` | background_properties | Applies BTL rent shortfall and retained mortgage review logic. |
| `halifax.credit.adverse_declaration` | credit | Requires adverse-credit declaration fields or refers declared adverse credit. |

## Snapshot Catalogue

Snapshot catalogue entries are generated from:

`data/sources/halifax_intermediaries_criteria_2026-05-30.html`

The parser reads visible headings, paragraphs, list items, and table cells. Each item becomes a `MANUAL_REFER` rule unless it is replaced by a specific automated rule.

This is why full runs can show thousands of catalogue rules. The design is conservative: it is better to surface a visible criteria item for review than to silently ignore it.

## Running With or Without Snapshot Coverage

Full criteria coverage:

```powershell
uv run python -m halifax_criteria evaluate input.yaml
```

Automated-only mode:

```powershell
uv run python -m halifax_criteria evaluate input.yaml --no-snapshot
```

Use automated-only mode when developing deterministic rules or debugging calculations. Use full mode when producing a broad criteria review.

## Adding a New Automated Rule

1. Add a function to `halifax_2026_05.py`.
2. Return a `RuleResult` using `_result` or `_missing`.
3. Add the function to `AUTOMATED_RULES`.
4. Add tests for pass, fail, and missing/refer behavior where relevant.
5. If the rule replaces a known snapshot item, make sure its rule ID and message are clear enough for audit.

Rule functions should:

- accept a `MortgageCase`
- return exactly one `RuleResult`
- avoid mutating the case
- include source-aware messages
- be conservative when Halifax criteria depends on internal systems

## Updating Halifax Criteria

When the source criteria changes:

1. Save a new dated HTML snapshot under `data/sources/`.
2. Add a new versioned rules file, for example `halifax_2026_06.py`.
3. Update `CRITERIA_VERSION`.
4. Keep the old snapshot and old rules file for historical explainability.
5. Add tests that show any changed behavior.

Do not silently rewrite old criteria versions unless you are fixing a bug in how that version was encoded.
