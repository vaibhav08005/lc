# Input Format

The evaluator currently accepts broker-style YAML mappings using the `var_...` field naming convention shown in `input.yaml`.

## Minimal Required Shape

The root YAML value must be a mapping:

```yaml
var_no_of_applicants: 2
var_case_type: aip
var_mortgage_type: moving_home
var_property_value: 300000
var_deposit: 100000
var_mortgage_term: 240
var_repayment_type: principal_over_mortgage_term
var_appl1_gross_annual_salary: 70000
var_appl2_gross_annual_salary: 60000
```

Blank fields are allowed and are treated as missing data.

## Important Top-Level Fields

| Field | Purpose |
| --- | --- |
| `var_no_of_applicants` | Number of applicants. Halifax max applicant checks use this. |
| `var_case_type` | Case stage, for example `aip`. |
| `var_mortgage_type` | Purchase/remortgage/home-mover style classification. |
| `var_property_value` | Purchase/property value used for loan and LTV calculations. |
| `var_deposit` | Deposit amount used to derive loan amount. |
| `var_deposit_source_details` | List of deposit sources and amounts. |
| `var_repayment_type` | Repayment type, such as `principal_over_mortgage_term`. |
| `var_interest_only_amount` | Interest-only portion where present. |
| `var_mortgage_term` | Mortgage term in months. |
| `var_other_properties` | Background property and BTL data. |

## Applicant Fields

Applicant fields are numbered:

```text
var_appl1_...
var_appl2_...
```

The normalizer currently reads:

| Field suffix | Purpose |
| --- | --- |
| `date_of_birth` | Age at end of term checks. |
| `nationality` | Residency/nationality checks. |
| `residency_status` | Permanent right to reside checks. |
| `uk_residency_period` | Non-UK national manual criteria support. |
| `employment_details_employment_type` | Employment category. |
| `employment_details_employed_type` | Permanent/contract style classification. |
| `income_sterling` | Income currency indicator. |
| `gross_annual_salary` | Base salary. |
| `recent_nongtd_bonus` | Recent bonus. |
| `prev_nongtd_bonus` | Previous bonus. |
| `recent_commission` | Commission. |
| `child_tax_credits` | Benefit income. |
| `employment_and_support_allowance` | Benefit income. |
| `income_support` | Benefit income. |
| `credit_commitments` | Credit-card and commitment checks. |

## Income Handling

The report exposes three income/LTI views:

- `base_gross_annual_income`: salary only.
- `core_annual_income`: salary plus bonus and commission.
- `gross_annual_income`: core income plus benefit-style income currently read by the normalizer.

The derived fields include:

- `base_lti_multiple`
- `core_lti_multiple`
- `lti_multiple`

This is intentional because lender treatment of variable income and benefits can require manual review.

## Deposit Sources

Example:

```yaml
var_deposit_source_details:
  - source: savings
    amount: 50000
  - source: incentive_builder
    amount: 50000
```

The evaluator treats builder incentives as requiring additional checks and calculates combined LTV as:

```text
(loan_amount + builder_incentive) / property_value
```

## Background Properties

Example:

```yaml
var_other_properties:
  - is_rental_property: "yes"
    monthly_repayment: 900
    monthly_rent: 1000
    current_balance: 50000
```

BTL rent is checked against 125% of mortgage payment. A shortfall becomes a manual affordability review item.

## Missing Data

Missing or blank data does not crash the evaluator. It produces `INSUFFICIENT_DATA` where that field is needed for a rule.

Common missing fields in the sample:

- applicant DOBs
- property type
- property description
- tenure
- construction material
- adverse-credit declaration fields
