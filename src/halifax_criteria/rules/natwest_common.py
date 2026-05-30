from __future__ import annotations

from datetime import date
from typing import Any

from ..models import AutomationLevel, MortgageCase, RuleResult, RuleStatus

CRITERIA_VERSION = "2026-05-31"
SOURCE_URL = "https://www.intermediary.natwest.com/lending-criteria.html"


def result(
    rule_id: str,
    category: str,
    status: RuleStatus,
    message: str,
    data: dict[str, Any] | None = None,
    source_ref: str | None = None,
    automation_level: AutomationLevel = AutomationLevel.AUTOMATED,
    section: str | None = None,
    source_text: str | None = None,
    criteria_type: str | None = None,
    required_fields: list[str] | None = None,
    implemented_by: str | None = None,
) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        category=category,
        status=status,
        automation_level=automation_level,
        severity="hard" if status == RuleStatus.FAIL else "standard",
        message=message,
        source_url=SOURCE_URL,
        source_ref=source_ref,
        data=data or {},
        section=section,
        source_text=source_text,
        criteria_type=criteria_type,
        required_fields=required_fields or [],
        implemented_by=implemented_by,
    )


def missing(rule_id: str, category: str, message: str, fields: list[str], **kwargs: Any) -> RuleResult:
    return result(
        rule_id,
        category,
        RuleStatus.INSUFFICIENT_DATA,
        message,
        {"missing_fields": fields},
        automation_level=AutomationLevel.INSUFFICIENT_DATA,
        required_fields=fields,
        **kwargs,
    )


def is_yes(value: object) -> bool:
    return str(value).strip().lower() in {"yes", "true", "1", "y"}


def money(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def raw_text(case: MortgageCase, *keys: str) -> str:
    return " ".join(str(case.raw.get(key) or "") for key in keys).lower()


def case_text(case: MortgageCase) -> str:
    values: list[str] = [
        str(case.case_type or ""),
        str(case.journey or ""),
        str(case.mortgage_type or ""),
        str(case.repayment_type or ""),
        str(case.property_type or ""),
        str(case.property_description or ""),
        str(case.property_tenure or ""),
        str(case.construction_material or ""),
        str(case.intend_to_purchase_flat or ""),
        str(case.raw.get("var_ownership_type") or ""),
        str(case.raw.get("var_ownership_type_ftb") or ""),
        str(case.raw.get("var_remo_options") or ""),
        str(case.raw.get("var_equity_release_amount") or ""),
        str(case.raw.get("var_add_borrow_details") or ""),
        str(case.raw.get("var_property_details_special_condition") or ""),
        str(case.raw.get("var_property_occupancy_usage") or ""),
    ]
    for source in case.deposit_sources:
        values.append(str(source.get("source") or ""))
    return " ".join(values).lower()


def has_any(case: MortgageCase, *terms: str) -> bool:
    text = case_text(case)
    return any(term.lower() in text for term in terms)


def is_interest_only(case: MortgageCase) -> bool:
    repayment = (case.repayment_type or "").lower()
    return case.interest_only_amount > 0 or "interest" in repayment or "part" in repayment or "mixed" in repayment


def applicant_end_ages(case: MortgageCase) -> tuple[dict[str, float], list[str]]:
    if case.mortgage_term_years is None:
        return {}, ["var_mortgage_term"]
    today = date.today()
    ages: dict[str, float] = {}
    missing_fields: list[str] = []
    for app in case.applicants:
        if app.date_of_birth is None:
            missing_fields.append(f"var_appl{app.index}_date_of_birth")
            continue
        age_now = (today - app.date_of_birth).days / 365.25
        ages[f"applicant_{app.index}"] = round(age_now + case.mortgage_term_years, 2)
    return ages, missing_fields


def applicant_current_ages(case: MortgageCase) -> tuple[dict[str, float], list[str]]:
    today = date.today()
    ages: dict[str, float] = {}
    missing_fields: list[str] = []
    for app in case.applicants:
        if app.date_of_birth is None:
            missing_fields.append(f"var_appl{app.index}_date_of_birth")
            continue
        ages[f"applicant_{app.index}"] = round((today - app.date_of_birth).days / 365.25, 2)
    return ages, missing_fields


def declared_adverse_fields(case: MortgageCase) -> tuple[list[str], bool]:
    terms = ("adverse", "ccj", "bankrupt", "bankruptcy", "insolven", "iva", "debt_repayment", "debt_relief", "arrears", "default")
    present: list[str] = []
    positive = False
    for key, value in case.raw.items():
        lower_key = key.lower()
        if any(term in lower_key for term in terms):
            present.append(key)
            if is_yes(value) or str(value).strip().lower() in {"declared", "present"}:
                positive = True
    if is_yes(case.raw.get("var_adverse_credit_declared")):
        present.append("var_adverse_credit_declared")
        positive = True
    return sorted(set(present)), positive


def rental_shortfalls(case: MortgageCase) -> list[dict[str, float]]:
    shortfalls: list[dict[str, float]] = []
    for index, prop in enumerate(case.other_properties, start=1):
        rent = money(prop.get("monthly_rent"))
        repayment = money(prop.get("monthly_repayment"))
        if repayment > rent and (rent > 0 or str(prop.get("is_rental_property", "")).lower() == "yes"):
            shortfalls.append({"property_index": index, "monthly_shortfall": round(repayment - rent, 2)})
    return shortfalls


def scheme_classification(case: MortgageCase) -> str | None:
    text = case_text(case)
    schemes = [
        ("shared ownership", "shared_ownership"),
        ("shared equity", "shared_equity"),
        ("right to buy", "right_to_buy"),
        ("lift", "lift"),
        ("family-backed", "family_backed_mortgage"),
        ("family backed", "family_backed_mortgage"),
        ("help to buy", "help_to_buy"),
        ("mortgage guarantee", "mortgage_guarantee"),
        ("concessionary", "concessionary_purchase"),
    ]
    for needle, label in schemes:
        if needle in text:
            return label
    return None
