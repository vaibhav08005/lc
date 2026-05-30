# Rules and Criteria Catalogue

The project has two coverage layers:

1. Automated rules for criteria that can be evaluated from public lender criteria and available input fields.
2. Snapshot catalogue entries for visible lender criteria text that still requires manual review or future automation.

## Automated Rules

Automated rules live in:

`src/halifax_criteria/rules/halifax_2026_05.py`

Current Halifax automated rule groups:

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

Current Barclays automated rule groups:

| Rule ID | Category | Purpose |
| --- | --- | --- |
| `barclays.applicants.count` | applicant | Checks applicant count and flags more than 4 applicants. |
| `barclays.loan.size` | loan | Checks minimum loan size and refers loans above GBP 5m. |
| `barclays.term.maximum` | term | Checks 5-year minimum, 40-year repayment max, and 25-year interest-only max. |
| `barclays.age.maximum_at_term_end` | age | Checks age at term end, including interest-only age caps. |
| `barclays.ltv.residential_limits` | loan_to_value | Applies Barclays residential LTV caps by scenario. |
| `barclays.ltv.high_ltv_loan_size` | loan_to_value | Fails loans above GBP 570k where LTV is above 90%. |
| `barclays.income.minimum` | income | Applies public Barclays minimum income thresholds. |
| `barclays.affordability.proprietary` | affordability | Refers Barclays calculator/disposable-income assessment. |
| `barclays.residency.non_uk` | residency | Screens nationality and residency status. |
| `barclays.employment.evidence` | employment | Screens permanent employed cases and refers others. |
| `barclays.credit.unsecured_debt_vs_income` | credit | Fails where supplied unsecured debt is at least income. |
| `barclays.credit.adverse_history` | credit | Requires adverse-credit fields or refers declared adverse credit. |
| `barclays.deposit.source` | deposit | Screens deposit source evidence/manual criteria. |
| `barclays.new_build.incentives` | property | Applies Barclays new-build incentive referral logic. |
| `barclays.property.acceptability` | property | Screens property facts and mixed-use LTV cap. |
| `barclays.background_properties` | background_properties | Refers background property commitments for affordability treatment. |

Additional Barclays rule groups now cover:

- additional borrowing and debt-consolidation LTV caps
- variable/reduced income review
- credit reference searches
- leasehold, cladding, and valuation review
- special schemes such as shared ownership, shared equity, Right to Buy, Help to Buy, discounted market sale and Mortgage Boost
- ID/address, supporting documentation, internet bank statements and offer validity
- porting, permission to let, short-term letting and second/subsequent charges

Current NatWest automated rule groups cover:

- applicant count, minimum age, age at term end, and foreign-national residency screens
- loan amount, term, LTV caps, loan-to-income referral, interest-only, additional borrowing and debt consolidation
- affordability calculator, income packaging, employment, variable income, and unacceptable income treatment
- adverse credit declarations, credit scoring, financial commitments, and background BTL shortfalls
- deposit source, property facts, agricultural restriction LTV, cladding, and valuation
- shared/special schemes, porting/product transfer, second residential property, and core documentation checks

## Snapshot Catalogue

Snapshot catalogue entries are generated from:

`data/sources/halifax_intermediaries_criteria_2026-05-30.html`

Barclays snapshot:

`data/sources/barclays_intermediaries_residential_criteria_2026-05-31.html`

Barclays structured catalogue:

`data/catalogues/barclays_residential_criteria_2026-05-31.json`

NatWest main snapshot:

`data/sources/natwest_intermediary_lending_criteria_2026-05-31.html`

NatWest structured catalogue:

`data/catalogues/natwest_lending_criteria_2026-05-31.json`

The Barclays catalogue captures all 60 visible A-Z sections and stores one auditable entry per extracted paragraph, list item, or table row. Each entry includes source text, section name, criteria type, automation level, required fields, and implemented rule reference where one exists.

The NatWest catalogue captures all 118 visible A-Z sections plus linked same-domain criteria/hub snapshots. It currently stores 2,354 auditable source-backed entries across 29 NatWest source URLs.

The parsers read visible headings, paragraphs, list items, and table cells. Halifax snapshot entries remain manual-review catalogue items. Barclays and NatWest entries are classified as automated, manual, insufficient-data, or proprietary based on source text and linked implemented rule coverage.

This is why full runs can show hundreds or thousands of catalogue rules. The design is conservative: it is better to surface a visible criteria item for review than to silently ignore it.

## Running With or Without Snapshot Coverage

Full criteria coverage:

```powershell
uv run python -m halifax_criteria evaluate input.yaml
```

Explicit Barclays run:

```powershell
uv run python -m halifax_criteria evaluate input.yaml --lender barclays
```

Show all Barclays automated and catalogue rules:

```powershell
uv run python -m halifax_criteria evaluate input.yaml --lender barclays --show-all-rules
```

Explicit NatWest run:

```powershell
uv run python -m halifax_criteria evaluate input.yaml --lender natwest
```

Show all NatWest automated and catalogue rules:

```powershell
uv run python -m halifax_criteria evaluate input.yaml --lender natwest --show-all-rules
```

Automated-only mode:

```powershell
uv run python -m halifax_criteria evaluate input.yaml --no-snapshot
```

Use automated-only mode when developing deterministic rules or debugging calculations. Use full mode when producing a broad criteria review.

## Adding a New Automated Rule

1. Add a function to the appropriate lender rule module.
2. Return a `RuleResult` using `_result` or `_missing`.
3. Add the function to the lender rule orchestrator.
4. Add tests for pass, fail, and missing/refer behavior where relevant.
5. If the rule replaces a known snapshot item, make sure its rule ID and message are clear enough for audit.

Rule functions should:

- accept a `MortgageCase`
- return exactly one `RuleResult`
- avoid mutating the case
- include source-aware messages
- be conservative when lender criteria depends on internal systems

## Updating Lender Criteria

When the source criteria changes:

1. Save a new dated HTML snapshot under `data/sources/`.
2. Add a new versioned rules file, for example `halifax_2026_06.py`, `barclays_2026_06.py`, or `natwest_2026_06.py`.
3. Update `CRITERIA_VERSION`.
4. Keep the old snapshot and old rules file for historical explainability.
5. Add tests that show any changed behavior.

Do not silently rewrite old criteria versions unless you are fixing a bug in how that version was encoded.
