from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from .models import Applicant, MortgageCase


def _blank_to_none(value: Any) -> Any:
    if value == "":
        return None
    return value


def _text(value: Any) -> str | None:
    value = _blank_to_none(value)
    if value is None:
        return None
    return str(value).strip().lower()


def _money(value: Any) -> float:
    value = _blank_to_none(value)
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _optional_money(value: Any) -> float | None:
    value = _blank_to_none(value)
    if value is None:
        return None
    return _money(value)


def _int(value: Any) -> int | None:
    value = _blank_to_none(value)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _date(value: Any) -> date | None:
    value = _blank_to_none(value)
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).date()
    if isinstance(value, str):
        value = value.strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                pass
    return None


def _frequency_annualized(amount: Any, frequency: Any) -> float:
    value = _money(amount)
    if value == 0:
        return 0.0
    freq = _text(frequency)
    multiplier = {
        "weekly": 52,
        "fortnightly": 26,
        "four_weekly": 13,
        "monthly": 12,
        "quarterly": 4,
        "half_yearly": 2,
        "annually": 1,
        "annual": 1,
        None: 1,
    }.get(freq, 1)
    return value * multiplier


def _applicant(raw: dict[str, Any], index: int) -> Applicant:
    prefix = f"var_appl{index}_"
    recent_bonus = _frequency_annualized(
        raw.get(prefix + "recent_nongtd_bonus"),
        raw.get(prefix + "recent_nongtd_bonus_frequency"),
    )
    previous_bonus = _frequency_annualized(
        raw.get(prefix + "prev_nongtd_bonus"),
        raw.get(prefix + "prev_nongtd_bonus_frequency"),
    )
    bonus_values = [value for value in (recent_bonus, previous_bonus) if value > 0]
    bonus = min(bonus_values) if len(bonus_values) == 2 else (bonus_values[0] if bonus_values else 0.0)
    benefits = sum(
        [
            _frequency_annualized(raw.get(prefix + "child_tax_credits"), raw.get(prefix + "child_tax_credits_frequency")),
            _frequency_annualized(
                raw.get(prefix + "employment_and_support_allowance"),
                raw.get(prefix + "employment_and_support_allowance_frequency"),
            ),
            _frequency_annualized(raw.get(prefix + "income_support"), raw.get(prefix + "income_support_frequency")),
        ]
    )
    commitments = raw.get(prefix + "credit_commitments") or []
    if not isinstance(commitments, list):
        commitments = []
    return Applicant(
        index=index,
        date_of_birth=_date(raw.get(prefix + "date_of_birth")),
        nationality=_text(raw.get(prefix + "nationality")),
        residency_status=_text(raw.get(prefix + "residency_status")),
        uk_residency_period=raw.get(prefix + "uk_residency_period"),
        employment_type=_text(raw.get(prefix + "employment_details_employment_type")),
        employed_type=_text(raw.get(prefix + "employment_details_employed_type")),
        income_sterling=_text(raw.get(prefix + "income_sterling")),
        gross_annual_salary=_money(raw.get(prefix + "gross_annual_salary")),
        bonus=bonus,
        commission=_frequency_annualized(raw.get(prefix + "recent_commission"), raw.get(prefix + "recent_commission_frequency")),
        benefits_income=benefits,
        credit_commitments=commitments,
    )


def normalize(raw: dict[str, Any]) -> MortgageCase:
    count = _int(raw.get("var_no_of_applicants")) or 0
    applicants = [_applicant(raw, index) for index in range(1, count + 1)]
    deposit_sources = raw.get("var_deposit_source_details") or []
    if not isinstance(deposit_sources, list):
        deposit_sources = []
    other_properties = raw.get("var_other_properties") or []
    if not isinstance(other_properties, list):
        other_properties = []
    return MortgageCase(
        raw=raw,
        case_type=_text(raw.get("var_case_type")),
        journey=_text(raw.get("var_journey")),
        mortgage_type=_text(raw.get("var_mortgage_type")),
        no_of_applicants=count,
        applicants=applicants,
        property_value=_optional_money(raw.get("var_property_value")),
        deposit=_optional_money(raw.get("var_deposit")),
        deposit_sources=deposit_sources,
        repayment_type=_text(raw.get("var_repayment_type")),
        interest_only_amount=_money(raw.get("var_interest_only_amount")),
        mortgage_term_months=_int(raw.get("var_mortgage_term")),
        property_type=_text(raw.get("var_property_details_property_type")),
        property_description=_text(raw.get("var_property_details_description")),
        property_tenure=_text(raw.get("var_property_details_tenure")),
        property_year_built=raw.get("var_property_details_year_built"),
        construction_material=_text(raw.get("var_property_details_construction_material")),
        leasehold_term=raw.get("var_property_details_leasehold_term"),
        intend_to_purchase_flat=raw.get("var_intend_to_purchase_flat"),
        other_properties=other_properties,
    )
