from __future__ import annotations

from datetime import date

from ..models import AutomationLevel, MortgageCase, RuleResult, RuleStatus

CRITERIA_VERSION = "2026-05-31"
SOURCE_URL = "https://intermediaries.uk.barclays/home/lending-criteria/residential/"


def result(
    rule_id: str,
    category: str,
    status: RuleStatus,
    message: str,
    data: dict | None = None,
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


def missing(rule_id: str, category: str, message: str, fields: list[str], **kwargs) -> RuleResult:
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


def case_text(case: MortgageCase) -> str:
    values = [
        case.case_type,
        case.journey,
        case.mortgage_type,
        case.repayment_type,
        case.property_type,
        case.property_description,
        case.property_tenure,
        str(case.intend_to_purchase_flat or ""),
        str(case.raw.get("var_remo_options") or ""),
        str(case.raw.get("var_equity_release_amount") or ""),
        str(case.raw.get("var_add_borrow_details") or ""),
        str(case.raw.get("var_property_details_special_condition") or ""),
    ]
    return " ".join(value or "" for value in values).lower()


def has_any(case: MortgageCase, *terms: str) -> bool:
    text = case_text(case)
    return any(term.lower() in text for term in terms)


def applicant_end_ages(case: MortgageCase) -> tuple[dict[str, float], list[int], list[str]]:
    if case.mortgage_term_years is None:
        return {}, [], ["var_mortgage_term"]
    today = date.today()
    ages: dict[str, float] = {}
    missing_fields: list[str] = []
    for app in case.applicants:
        if app.date_of_birth is None:
            missing_fields.append(f"var_appl{app.index}_date_of_birth")
            continue
        end_age = ((today - app.date_of_birth).days / 365.25) + case.mortgage_term_years
        ages[f"applicant_{app.index}"] = round(end_age, 2)
    return ages, [], missing_fields


def unsecured_debt_total(case: MortgageCase) -> float:
    total = 0.0
    for app in case.applicants:
        for commitment in app.credit_commitments:
            ctype = str(commitment.get("type", "")).lower()
            if ctype in {"cards", "credit_card", "card", "loan", "overdraft"}:
                total += float(commitment.get("current_balance") or 0)
    return total


def retained_property_count(case: MortgageCase) -> int:
    return len([prop for prop in case.other_properties if str(prop.get("mortgage_status", "")).lower() == "yes" or prop.get("monthly_repayment")])
