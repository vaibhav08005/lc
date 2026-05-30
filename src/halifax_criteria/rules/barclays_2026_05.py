from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable

from ..models import AutomationLevel, MortgageCase, RuleResult, RuleStatus
from .snapshot_catalogue import snapshot_results

CRITERIA_VERSION = "2026-05-31"
SOURCE_URL = "https://intermediaries.uk.barclays/home/lending-criteria/residential/"
SNAPSHOT_PATH = Path(__file__).resolve().parents[3] / "data" / "sources" / "barclays_intermediaries_residential_criteria_2026-05-31.html"


def _result(
    rule_id: str,
    category: str,
    status: RuleStatus,
    message: str,
    data: dict | None = None,
    source_ref: str | None = None,
    automation_level: AutomationLevel = AutomationLevel.AUTOMATED,
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
    )


def _missing(rule_id: str, category: str, message: str, fields: list[str]) -> RuleResult:
    return _result(
        rule_id,
        category,
        RuleStatus.INSUFFICIENT_DATA,
        message,
        {"missing_fields": fields},
        automation_level=AutomationLevel.INSUFFICIENT_DATA,
    )


def _is_yes(value: object) -> bool:
    return str(value).strip().lower() in {"yes", "true", "1", "y"}


def _case_text(case: MortgageCase) -> str:
    values = [
        case.mortgage_type,
        case.repayment_type,
        case.property_type,
        case.property_description,
        str(case.intend_to_purchase_flat or ""),
        str(case.raw.get("var_remo_options") or ""),
        str(case.raw.get("var_equity_release_amount") or ""),
        str(case.raw.get("var_add_borrow_details") or ""),
    ]
    return " ".join(value or "" for value in values).lower()


def applicant_count(case: MortgageCase) -> RuleResult:
    if not case.no_of_applicants:
        return _missing("barclays.applicants.count", "applicant", "Number of applicants is required.", ["var_no_of_applicants"])
    if case.no_of_applicants > 4:
        return _result("barclays.applicants.count", "applicant", RuleStatus.FAIL, "Barclays permits a maximum of 4 applicants.")
    if case.no_of_applicants > 2:
        return _result(
            "barclays.applicants.count",
            "applicant",
            RuleStatus.REFER,
            "Applicant count is allowed, but Barclays only considers a maximum of two applicant incomes.",
            {"applicant_count": case.no_of_applicants},
        )
    return _result("barclays.applicants.count", "applicant", RuleStatus.PASS, "Applicant count is within Barclays limits.")


def loan_size(case: MortgageCase) -> RuleResult:
    if case.loan_amount is None:
        return _missing("barclays.loan.size", "loan", "Loan amount requires property value and deposit.", ["var_property_value", "var_deposit"])
    if case.loan_amount < 5_000:
        return _result("barclays.loan.size", "loan", RuleStatus.FAIL, "Loan amount is below Barclays minimum loan size of GBP 5,000.", {"loan_amount": case.loan_amount})
    if case.loan_amount > 5_000_000:
        return _result("barclays.loan.size", "loan", RuleStatus.REFER, "Loan amount is above GBP 5m and may be subject to bespoke pricing/underwriter discretion.", {"loan_amount": case.loan_amount})
    return _result("barclays.loan.size", "loan", RuleStatus.PASS, "Loan amount is within standard Barclays size limits.", {"loan_amount": case.loan_amount})


def term_limit(case: MortgageCase) -> RuleResult:
    if case.mortgage_term_months is None:
        return _missing("barclays.term.maximum", "term", "Mortgage term is required.", ["var_mortgage_term"])
    if case.mortgage_term_months < 60:
        return _result("barclays.term.maximum", "term", RuleStatus.FAIL, "Mortgage term is below Barclays minimum term of 5 years.")
    is_interest_only = case.interest_only_amount > 0 or case.repayment_type == "interest_only"
    max_months = 300 if is_interest_only else 480
    if case.mortgage_term_months > max_months:
        max_years = max_months // 12
        return _result("barclays.term.maximum", "term", RuleStatus.FAIL, f"Mortgage term exceeds Barclays maximum term of {max_years} years for this repayment type.", {"term_months": case.mortgage_term_months})
    return _result("barclays.term.maximum", "term", RuleStatus.PASS, "Mortgage term is within Barclays published limits.", {"term_months": case.mortgage_term_months})


def age_at_end(case: MortgageCase) -> RuleResult:
    if case.mortgage_term_years is None:
        return _missing("barclays.age.maximum_at_term_end", "age", "Mortgage term is required for age-at-end checks.", ["var_mortgage_term"])
    missing = [f"var_appl{app.index}_date_of_birth" for app in case.applicants if app.date_of_birth is None]
    if missing:
        return _missing("barclays.age.maximum_at_term_end", "age", "Applicant date of birth is required to check Barclays maximum age at end of term.", missing)
    is_interest_only = case.interest_only_amount > 0 or case.repayment_type == "interest_only"
    max_age = 70 if is_interest_only and (case.ltv_percent or 0) > 50 else (75 if is_interest_only else 80)
    today = date.today()
    too_old: list[int] = []
    ages: dict[str, float] = {}
    for app in case.applicants:
        assert app.date_of_birth is not None
        end_age = ((today - app.date_of_birth).days / 365.25) + case.mortgage_term_years
        ages[f"applicant_{app.index}"] = round(end_age, 2)
        if end_age > max_age:
            too_old.append(app.index)
    if too_old:
        return _result("barclays.age.maximum_at_term_end", "age", RuleStatus.FAIL, f"Applicant age at term end exceeds Barclays maximum age {max_age}.", {"end_ages": ages})
    return _result("barclays.age.maximum_at_term_end", "age", RuleStatus.PASS, f"Applicant age at term end is within Barclays maximum age {max_age}.", {"end_ages": ages})


def _barclays_ltv_cap(case: MortgageCase) -> tuple[float, str]:
    text = _case_text(case)
    is_interest_only = case.interest_only_amount > 0 or case.repayment_type == "interest_only"
    is_part_and_part = case.interest_only_amount > 0 and case.loan_amount is not None and case.interest_only_amount < case.loan_amount
    if is_part_and_part:
        return 85.0, "part-and-part maximum LTV"
    if is_interest_only:
        return 75.0, "interest-only maximum LTV"
    if "debt" in text and ("remo" in text or "remortgage" in text or "additional" in text):
        return 80.0, "debt-consolidation remortgage/additional borrowing cap"
    if "additional" in text or "further" in text or "capital" in text or case.raw.get("var_equity_release_amount"):
        return 85.0, "capital-raising/additional borrowing cap"
    if "new" in text and "build" in text and ("flat" in text or "apartment" in text or "maisonette" in text or _is_yes(case.intend_to_purchase_flat)):
        return 85.0, "new-build flat/apartment cap"
    if case.other_properties:
        return 90.0, "customer retaining more than one mortgaged residential property cap"
    if case.mortgage_type in {"remortgage", "remo"}:
        return 90.0, "like-for-like remortgage cap"
    return 95.0, "standard purchase cap"


def ltv(case: MortgageCase) -> RuleResult:
    if case.loan_amount is None or case.ltv_percent is None:
        return _missing("barclays.ltv.residential_limits", "loan_to_value", "Property value and deposit are required to calculate LTV.", ["var_property_value", "var_deposit"])
    cap, reason = _barclays_ltv_cap(case)
    if case.ltv_percent > cap:
        return _result(
            "barclays.ltv.residential_limits",
            "loan_to_value",
            RuleStatus.FAIL,
            f"LTV {case.ltv_percent:.2f}% exceeds Barclays {reason} of {cap:.2f}%.",
            {"ltv_percent": round(case.ltv_percent, 2), "max_ltv": cap, "reason": reason},
        )
    if case.ltv_percent > 90 and case.loan_amount > 570_000:
        return _result("barclays.ltv.high_ltv_loan_size", "loan_to_value", RuleStatus.FAIL, "Where Barclays LTV is above 90%, maximum loan size is GBP 570k.", {"loan_amount": case.loan_amount, "ltv_percent": round(case.ltv_percent, 2)})
    return _result("barclays.ltv.residential_limits", "loan_to_value", RuleStatus.PASS, f"LTV {case.ltv_percent:.2f}% is within Barclays {reason} of {cap:.2f}%.", {"ltv_percent": round(case.ltv_percent, 2), "max_ltv": cap, "reason": reason})


def minimum_income(case: MortgageCase) -> RuleResult:
    if case.loan_amount is None:
        return _missing("barclays.income.minimum", "income", "Loan amount is required for Barclays minimum income checks.", ["var_property_value", "var_deposit"])
    incomes = [app.gross_annual_salary for app in case.applicants[:2]]
    if not incomes or sum(incomes) <= 0:
        return _missing("barclays.income.minimum", "income", "Applicant income is required.", ["var_appl*_gross_annual_salary"])
    if 35_000 <= case.loan_amount <= 1_000_000 and max(incomes) < 25_000:
        return _result("barclays.income.minimum", "income", RuleStatus.FAIL, "For loans from GBP 35k to GBP 1m, at least one applicant must earn GBP 25k.", {"incomes": incomes})
    if case.loan_amount > 1_000_000 and max(incomes) < 75_000 and sum(incomes) < 100_000:
        return _result("barclays.income.minimum", "income", RuleStatus.FAIL, "For loans above GBP 1m, Barclays minimum income threshold is not met.", {"incomes": incomes})
    return _result("barclays.income.minimum", "income", RuleStatus.PASS, "Applicant income meets Barclays public minimum income screen.", {"incomes": incomes})


def affordability(case: MortgageCase) -> RuleResult:
    if case.lti_multiple is None:
        return _missing("barclays.affordability.proprietary", "affordability", "Income and loan amount are required before Barclays affordability can be approximated.", ["var_property_value", "var_deposit", "var_appl*_gross_annual_salary"])
    return _result(
        "barclays.affordability.proprietary",
        "affordability",
        RuleStatus.REFER,
        "Barclays affordability uses its own calculator and disposable-income requirements; income multiples alone are not sufficient.",
        {"lti_multiple": round(case.lti_multiple, 2)},
        automation_level=AutomationLevel.OUT_OF_SCOPE_PROPRIETARY,
    )


def residency(case: MortgageCase) -> RuleResult:
    missing: list[str] = []
    referrals: list[str] = []
    for app in case.applicants:
        if not app.nationality:
            missing.append(f"var_appl{app.index}_nationality")
        elif app.nationality in {"british", "uk", "united kingdom"}:
            continue
        elif app.residency_status in {"indefinite_leave_to_remain", "settled_status", "permanent_residence"}:
            continue
        else:
            referrals.append(f"applicant {app.index} is non-UK without permanent residence status captured")
    if missing:
        return _missing("barclays.residency.non_uk", "residency", "Nationality/residency fields are required.", missing)
    if referrals:
        return _result("barclays.residency.non_uk", "residency", RuleStatus.REFER, "Non-UK national criteria require manual Barclays review: " + "; ".join(referrals), {"referrals": referrals})
    return _result("barclays.residency.non_uk", "residency", RuleStatus.PASS, "Applicant nationality/residency meets the basic Barclays screen.")


def employment(case: MortgageCase) -> RuleResult:
    missing: list[str] = []
    referrals: list[str] = []
    for app in case.applicants:
        if not app.employment_type:
            missing.append(f"var_appl{app.index}_employment_details_employment_type")
        elif app.employment_type == "employed" and app.employed_type == "permanent":
            continue
        else:
            referrals.append(f"applicant {app.index} employment type '{app.employment_type}' requires Barclays evidence/manual criteria")
    if missing:
        return _missing("barclays.employment.evidence", "employment", "Employment type is required.", missing)
    if referrals:
        return _result("barclays.employment.evidence", "employment", RuleStatus.REFER, "; ".join(referrals), {"referrals": referrals})
    return _result("barclays.employment.evidence", "employment", RuleStatus.PASS, "Applicants are permanent employed in the supplied data.")


def unsecured_debt(case: MortgageCase) -> RuleResult:
    total_balance = 0.0
    for app in case.applicants:
        for commitment in app.credit_commitments:
            ctype = str(commitment.get("type", "")).lower()
            if ctype in {"cards", "credit_card", "card", "loan", "overdraft"}:
                total_balance += float(commitment.get("current_balance") or 0)
    if total_balance >= case.gross_annual_income and case.gross_annual_income > 0:
        return _result("barclays.credit.unsecured_debt_vs_income", "credit", RuleStatus.FAIL, "Total unsecured bureau debt is greater than or equal to income used in affordability.", {"unsecured_debt": total_balance, "income": case.gross_annual_income})
    return _result("barclays.credit.unsecured_debt_vs_income", "credit", RuleStatus.PASS, "Unsecured debt does not exceed income used in affordability from supplied commitments.", {"unsecured_debt": total_balance, "income": case.gross_annual_income})


def adverse_credit(case: MortgageCase) -> RuleResult:
    keys = [key for key in case.raw if any(term in key.lower() for term in ["ccj", "default", "bankrupt", "dro", "iva", "arrear", "judgement", "missed", "debt_management"])]
    if not keys:
        return _missing("barclays.credit.adverse_history", "credit", "Adverse-credit declaration fields are not present in the input.", ["ccj/default/bankruptcy/dro/iva/arrears/missed-payment fields"])
    positives = [key for key in keys if _is_yes(case.raw.get(key))]
    if positives:
        return _result("barclays.credit.adverse_history", "credit", RuleStatus.REFER, "Adverse credit is declared and must be assessed against Barclays adverse-credit criteria.", {"fields": positives})
    return _result("barclays.credit.adverse_history", "credit", RuleStatus.PASS, "No adverse credit is declared in supplied fields.")


def deposit(case: MortgageCase) -> RuleResult:
    if case.deposit is None:
        return _missing("barclays.deposit.source", "deposit", "Deposit amount is required.", ["var_deposit"])
    if not case.deposit_sources:
        return _missing("barclays.deposit.source", "deposit", "Deposit source details are required.", ["var_deposit_source_details"])
    manual = []
    fail = []
    for source in case.deposit_sources:
        source_type = str(source.get("source", "")).lower()
        if "crypto" in source_type:
            manual.append(source_type)
        if "loan" in source_type:
            manual.append(source_type)
        if source_type in {"incentive_builder", "builder_incentive", "gifted", "gifted_deposit"}:
            manual.append(source_type)
    if fail:
        return _result("barclays.deposit.source", "deposit", RuleStatus.FAIL, "Deposit source is unacceptable.", {"sources": fail})
    if manual:
        return _result("barclays.deposit.source", "deposit", RuleStatus.REFER, "Deposit source requires Barclays evidence/manual criteria checks.", {"sources": sorted(set(manual))})
    return _result("barclays.deposit.source", "deposit", RuleStatus.PASS, "Deposit source does not show an obvious Barclays pre-screen issue.")


def new_build_incentives(case: MortgageCase) -> RuleResult:
    incentive = sum(float(item.get("amount") or 0) for item in case.deposit_sources if str(item.get("source", "")).lower() in {"incentive_builder", "builder_incentive"})
    text = _case_text(case)
    if incentive <= 0:
        return _result("barclays.new_build.incentives", "property", RuleStatus.PASS, "No builder incentive is supplied.")
    if case.property_value is None:
        return _missing("barclays.new_build.incentives", "property", "Property value is required for Barclays new-build incentive treatment.", ["var_property_value"])
    incentive_percent = (incentive / case.property_value) * 100
    if "new" not in text and "build" not in text:
        return _result("barclays.new_build.incentives", "property", RuleStatus.REFER, "Builder incentive is supplied but property is not clearly marked as new build.", {"incentive_percent": round(incentive_percent, 2)})
    if incentive_percent > 5:
        return _result("barclays.new_build.incentives", "property", RuleStatus.REFER, "Barclays deducts financial incentives above 5% from value for maximum loan calculations.", {"incentive_percent": round(incentive_percent, 2)})
    return _result("barclays.new_build.incentives", "property", RuleStatus.PASS, "New-build financial incentive is within the 5% threshold.", {"incentive_percent": round(incentive_percent, 2)})


def property_details(case: MortgageCase) -> RuleResult:
    missing = [
        field
        for field, value in {
            "var_property_details_property_type": case.property_type,
            "var_property_details_description": case.property_description,
            "var_property_details_tenure": case.property_tenure,
            "var_property_details_construction_material": case.construction_material,
        }.items()
        if not value
    ]
    if missing:
        return _missing("barclays.property.acceptability", "property", "Property details are required for Barclays property acceptability checks.", missing)
    text = _case_text(case)
    if "mixed" in text and case.ltv_percent and case.ltv_percent > 80:
        return _result("barclays.property.acceptability", "property", RuleStatus.FAIL, "Mixed-use properties are limited to 80% LTV by Barclays.", {"ltv_percent": round(case.ltv_percent, 2)})
    return _result("barclays.property.acceptability", "property", RuleStatus.REFER, "Property details are supplied but Barclays valuation/security acceptability remains a manual check.")


def background_properties(case: MortgageCase) -> RuleResult:
    if not case.other_properties:
        return _result("barclays.background_properties", "background_properties", RuleStatus.PASS, "No background properties are supplied.")
    warnings = []
    for index, prop in enumerate(case.other_properties, start=1):
        if float(prop.get("monthly_repayment") or 0) > 0:
            warnings.append(f"property {index} mortgage payment should be included in Barclays affordability")
    return _result("barclays.background_properties", "background_properties", RuleStatus.REFER, "Background residential/BTL property commitments require Barclays affordability treatment.", {"warnings": warnings, "property_count": len(case.other_properties)})


AUTOMATED_RULES: list[Callable[[MortgageCase], RuleResult]] = [
    applicant_count,
    loan_size,
    term_limit,
    age_at_end,
    ltv,
    minimum_income,
    affordability,
    residency,
    employment,
    unsecured_debt,
    adverse_credit,
    deposit,
    new_build_incentives,
    property_details,
    background_properties,
]


def evaluate_rules(case: MortgageCase, include_snapshot: bool = True) -> list[RuleResult]:
    results = [rule(case) for rule in AUTOMATED_RULES]
    if include_snapshot and SNAPSHOT_PATH.exists():
        results.extend(
            snapshot_results(
                SNAPSHOT_PATH,
                {result.rule_id for result in results},
                source_url=SOURCE_URL,
                id_prefix="barclays.snapshot",
                lender_name="Barclays",
                start_markers=("residential lending criteria", "what are our lending criteria?"),
            )
        )
    return results
