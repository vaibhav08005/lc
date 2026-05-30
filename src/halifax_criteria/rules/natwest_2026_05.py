from __future__ import annotations

from ..models import MortgageCase, RuleResult
from . import natwest_applicant, natwest_credit, natwest_documentation, natwest_income, natwest_lending, natwest_property, natwest_schemes
from .natwest_catalogue import DEFAULT_CATALOGUE, SOURCE_URL, catalogue_results
from .natwest_common import CRITERIA_VERSION, rental_shortfalls, scheme_classification

RULE_GROUPS = {
    "applicant": [
        natwest_applicant.applicant_count,
        natwest_applicant.minimum_age,
        natwest_applicant.age_at_term_end,
        natwest_applicant.residency,
    ],
    "lending": [
        natwest_lending.loan_size,
        natwest_lending.term,
        natwest_lending.ltv,
        natwest_lending.loan_to_income,
        natwest_lending.interest_only,
        natwest_lending.additional_borrowing,
        natwest_lending.debt_consolidation,
    ],
    "income": [
        natwest_income.affordability,
        natwest_income.income_packaging,
        natwest_income.employment,
        natwest_income.variable_income,
        natwest_income.unacceptable_income,
    ],
    "credit": [
        natwest_credit.adverse_credit,
        natwest_credit.credit_scoring,
        natwest_credit.commitments,
        natwest_credit.background_btl,
    ],
    "property": [
        natwest_property.deposit,
        natwest_property.property_details,
        natwest_property.acreage_agricultural,
        natwest_property.cladding,
        natwest_property.valuation,
    ],
    "schemes": [
        natwest_schemes.special_schemes,
        natwest_schemes.porting_product_transfer,
        natwest_schemes.second_residential_property,
    ],
    "documentation": [
        natwest_documentation.bank_statements,
        natwest_documentation.certification,
        natwest_documentation.proof_of_address_id,
        natwest_documentation.offer_validity,
    ],
}

AUTOMATED_RULES = [rule for rules in RULE_GROUPS.values() for rule in rules]


def extra_derived(case: MortgageCase) -> dict:
    cap, reason = natwest_lending.natwest_ltv_cap(case)
    return {
        "natwest_selected_ltv_cap": cap,
        "natwest_ltv_cap_reason": reason,
        "natwest_interest_only_flag": natwest_lending.is_interest_only(case),
        "natwest_btl_rental_shortfalls": rental_shortfalls(case),
        "natwest_scheme_classification": scheme_classification(case),
    }


def evaluate_rules(case: MortgageCase, include_snapshot: bool = True) -> list[RuleResult]:
    results = [rule(case) for rule in AUTOMATED_RULES]
    if include_snapshot:
        results.extend(catalogue_results(DEFAULT_CATALOGUE))
    return results
