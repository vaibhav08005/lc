from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..models import MortgageCase, RuleResult
from . import barclays_applicant, barclays_credit, barclays_documentation, barclays_income, barclays_lending, barclays_portfolio, barclays_property, barclays_schemes
from .barclays_catalogue import DEFAULT_CATALOGUE, DEFAULT_SNAPSHOT, SOURCE_URL, catalogue_results
from .barclays_common import CRITERIA_VERSION, retained_property_count, unsecured_debt_total

SNAPSHOT_PATH = DEFAULT_SNAPSHOT
CATALOGUE_PATH = DEFAULT_CATALOGUE


RULE_GROUPS: dict[str, list[Callable[[MortgageCase], RuleResult]]] = {
    "applicant": [
        barclays_applicant.applicant_count,
        barclays_applicant.residency,
    ],
    "lending": [
        barclays_lending.loan_size,
        barclays_lending.term_limit,
        barclays_lending.age_at_end,
        barclays_lending.ltv,
        barclays_lending.additional_borrowing,
    ],
    "income_affordability": [
        barclays_income.minimum_income,
        barclays_income.income_multiples,
        barclays_income.affordability,
        barclays_income.employment,
        barclays_income.variable_income,
        barclays_income.reduced_income,
    ],
    "credit": [
        barclays_credit.unsecured_debt,
        barclays_credit.adverse_credit,
        barclays_credit.credit_reference_searches,
    ],
    "property": [
        barclays_property.deposit,
        barclays_property.new_build_incentives,
        barclays_property.property_details,
        barclays_property.leasehold,
        barclays_property.cladding,
        barclays_property.valuations,
    ],
    "schemes": [
        barclays_schemes.special_schemes,
        barclays_schemes.loan_purpose,
        barclays_schemes.porting_permission_to_let,
        barclays_schemes.short_term_letting,
    ],
    "documentation": [
        barclays_documentation.id_address_verification,
        barclays_documentation.supporting_documentation,
        barclays_documentation.internet_bank_statements,
        barclays_documentation.offer_validity,
    ],
    "portfolio": [
        barclays_portfolio.background_properties,
        barclays_portfolio.second_charges,
    ],
}

AUTOMATED_RULES: list[Callable[[MortgageCase], RuleResult]] = [rule for rules in RULE_GROUPS.values() for rule in rules]


def automated_rule_ids() -> set[str]:
    return {f"barclays.{group}.{rule.__name__}" for group, rules in RULE_GROUPS.items() for rule in rules}


def extra_derived(case: MortgageCase) -> dict:
    cap, reason = barclays_lending.barclays_ltv_cap(case)
    is_interest_only = case.interest_only_amount > 0 or case.repayment_type == "interest_only"
    return {
        "barclays_selected_ltv_cap": cap,
        "barclays_ltv_cap_reason": reason,
        "barclays_high_ltv_loan_size_flag": bool(case.ltv_percent and case.ltv_percent > 90 and case.loan_amount and case.loan_amount > 570_000),
        "barclays_interest_only_flag": is_interest_only,
        "barclays_retained_property_count": retained_property_count(case),
        "barclays_unsecured_debt_total": unsecured_debt_total(case),
        "barclays_scheme_classification": barclays_schemes.scheme_classification(case),
    }


def evaluate_rules(case: MortgageCase, include_snapshot: bool = True) -> list[RuleResult]:
    results = [rule(case) for rule in AUTOMATED_RULES]
    if include_snapshot and Path(CATALOGUE_PATH).exists():
        results.extend(catalogue_results(CATALOGUE_PATH))
    return results
