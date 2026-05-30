from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any


class RuleStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    REFER = "REFER"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class AutomationLevel(str, Enum):
    AUTOMATED = "AUTOMATED"
    MANUAL_REFER = "MANUAL_REFER"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    OUT_OF_SCOPE_PROPRIETARY = "OUT_OF_SCOPE_PROPRIETARY"


@dataclass(frozen=True)
class Applicant:
    index: int
    date_of_birth: date | None
    nationality: str | None
    residency_status: str | None
    uk_residency_period: Any
    employment_type: str | None
    employed_type: str | None
    income_sterling: str | None
    gross_annual_salary: float
    bonus: float
    commission: float
    benefits_income: float
    credit_commitments: list[dict[str, Any]] = field(default_factory=list)

    @property
    def core_income(self) -> float:
        return self.gross_annual_salary + self.bonus + self.commission

    @property
    def total_income(self) -> float:
        return self.core_income + self.benefits_income


@dataclass(frozen=True)
class MortgageCase:
    raw: dict[str, Any]
    case_type: str | None
    journey: str | None
    mortgage_type: str | None
    no_of_applicants: int
    applicants: list[Applicant]
    property_value: float | None
    deposit: float | None
    deposit_sources: list[dict[str, Any]]
    repayment_type: str | None
    interest_only_amount: float
    mortgage_term_months: int | None
    property_type: str | None
    property_description: str | None
    property_tenure: str | None
    property_year_built: Any
    construction_material: str | None
    leasehold_term: Any
    intend_to_purchase_flat: Any
    other_properties: list[dict[str, Any]]

    @property
    def loan_amount(self) -> float | None:
        if self.property_value is None or self.deposit is None:
            return None
        return max(self.property_value - self.deposit, 0)

    @property
    def ltv_percent(self) -> float | None:
        if not self.property_value or self.loan_amount is None:
            return None
        return (self.loan_amount / self.property_value) * 100

    @property
    def gross_annual_income(self) -> float:
        return sum(app.total_income for app in self.applicants[:2])

    @property
    def base_gross_annual_income(self) -> float:
        return sum(app.gross_annual_salary for app in self.applicants[:2])

    @property
    def core_annual_income(self) -> float:
        return sum(app.core_income for app in self.applicants[:2])

    @property
    def lti_multiple(self) -> float | None:
        if not self.gross_annual_income or self.loan_amount is None:
            return None
        return self.loan_amount / self.gross_annual_income

    @property
    def mortgage_term_years(self) -> float | None:
        if self.mortgage_term_months is None:
            return None
        return self.mortgage_term_months / 12


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    category: str
    status: RuleStatus
    automation_level: AutomationLevel
    severity: str
    message: str
    source_url: str
    source_ref: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    section: str | None = None
    source_text: str | None = None
    criteria_type: str | None = None
    required_fields: list[str] = field(default_factory=list)
    implemented_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "category": self.category,
            "status": self.status.value,
            "automation_level": self.automation_level.value,
            "severity": self.severity,
            "message": self.message,
            "source_url": self.source_url,
            "source_ref": self.source_ref,
            "data": self.data,
            "section": self.section,
            "source_text": self.source_text,
            "criteria_type": self.criteria_type,
            "required_fields": self.required_fields,
            "implemented_by": self.implemented_by,
        }
