from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable

from ..models import AutomationLevel, MortgageCase, RuleResult, RuleStatus
from .snapshot_catalogue import SOURCE_URL, snapshot_results

CRITERIA_VERSION = "2026-05-30"
SNAPSHOT_PATH = Path(__file__).resolve().parents[3] / "data" / "sources" / "halifax_intermediaries_criteria_2026-05-30.html"


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


def _max_ltv_for_loan(loan_amount: float) -> float | None:
    if loan_amount <= 570_000:
        return 95.0
    if loan_amount <= 750_000:
        return 90.0
    if loan_amount <= 2_000_000:
        return 85.0
    if loan_amount <= 5_000_000:
        return 75.0
    return None


def _is_yes(value: object) -> bool:
    return str(value).strip().lower() in {"yes", "true", "1", "y"}


def applicant_count(case: MortgageCase) -> RuleResult:
    if not case.no_of_applicants:
        return _missing("halifax.applicants.count", "applicant", "Number of applicants is required.", ["var_no_of_applicants"])
    if case.no_of_applicants > 4:
        return _result("halifax.applicants.count", "applicant", RuleStatus.FAIL, "Halifax permits a maximum of 4 applicants.")
    if case.no_of_applicants > 2:
        return _result(
            "halifax.applicants.count",
            "applicant",
            RuleStatus.REFER,
            "Applicant count is allowed, but only two incomes should be used for affordability.",
            {"applicant_count": case.no_of_applicants},
        )
    return _result("halifax.applicants.count", "applicant", RuleStatus.PASS, "Applicant count is within Halifax limits.")


def standard_ltv(case: MortgageCase) -> RuleResult:
    if case.loan_amount is None or case.ltv_percent is None:
        return _missing("halifax.ltv.standard_limits", "loan_to_value", "Property value and deposit are required to calculate LTV.", ["var_property_value", "var_deposit"])
    max_ltv = _max_ltv_for_loan(case.loan_amount)
    if max_ltv is None:
        return _result("halifax.ltv.standard_limits", "loan_to_value", RuleStatus.FAIL, "Loan amount exceeds the published Halifax residential lending table.", {"loan_amount": case.loan_amount})
    if case.ltv_percent > max_ltv:
        return _result(
            "halifax.ltv.standard_limits",
            "loan_to_value",
            RuleStatus.FAIL,
            f"LTV {case.ltv_percent:.2f}% exceeds Halifax maximum {max_ltv:.2f}% for this loan size.",
            {"loan_amount": case.loan_amount, "ltv_percent": round(case.ltv_percent, 2), "max_ltv": max_ltv},
        )
    return _result(
        "halifax.ltv.standard_limits",
        "loan_to_value",
        RuleStatus.PASS,
        f"LTV {case.ltv_percent:.2f}% is within Halifax standard limits.",
        {"loan_amount": case.loan_amount, "ltv_percent": round(case.ltv_percent, 2), "max_ltv": max_ltv},
    )


def high_ltv_purchase(case: MortgageCase) -> RuleResult:
    if case.ltv_percent is None or case.loan_amount is None or case.property_value is None:
        return _missing("halifax.ltv.90_to_95_purchase", "loan_to_value", "LTV inputs are required for 90-95% LTV checks.", ["var_property_value", "var_deposit"])
    if case.ltv_percent <= 90:
        return _result("halifax.ltv.90_to_95_purchase", "loan_to_value", RuleStatus.PASS, "90-95% LTV restrictions do not apply.")
    problems: list[str] = []
    if case.mortgage_type not in {"moving_home", "first_time_buyer", "purchase"}:
        problems.append("application is not clearly a purchase/homemover/FTB case")
    if case.property_value > 600_000:
        problems.append("purchase price exceeds GBP 600,000")
    if case.loan_amount > 570_000:
        problems.append("loan exceeds GBP 570,000")
    if case.repayment_type != "principal_over_mortgage_term":
        problems.append("borrowing above 90% LTV must be on repayment")
    if case.other_properties:
        problems.append("customer appears to have an interest in other properties")
    if problems:
        return _result("halifax.ltv.90_to_95_purchase", "loan_to_value", RuleStatus.FAIL, "90-95% LTV restrictions are breached: " + "; ".join(problems), {"problems": problems})
    return _result("halifax.ltv.90_to_95_purchase", "loan_to_value", RuleStatus.REFER, "90-95% LTV appears possible, subject to enhanced credit score and affordability.")


def term_limit(case: MortgageCase) -> RuleResult:
    if case.mortgage_term_months is None:
        return _missing("halifax.term.maximum", "term", "Mortgage term is required.", ["var_mortgage_term"])
    if case.mortgage_term_months > 480:
        return _result("halifax.term.maximum", "term", RuleStatus.FAIL, "Mortgage term exceeds Halifax maximum term of 40 years.", {"term_months": case.mortgage_term_months})
    return _result("halifax.term.maximum", "term", RuleStatus.PASS, "Mortgage term is within Halifax maximum term of 40 years.", {"term_months": case.mortgage_term_months})


def age_at_end(case: MortgageCase) -> RuleResult:
    if case.mortgage_term_years is None:
        return _missing("halifax.age.maximum_at_term_end", "age", "Mortgage term is required for age-at-end checks.", ["var_mortgage_term"])
    missing = [f"var_appl{app.index}_date_of_birth" for app in case.applicants if app.date_of_birth is None]
    if missing:
        return _missing("halifax.age.maximum_at_term_end", "age", "Applicant date of birth is required to check maximum age at end of term.", missing)
    max_age = 70 if case.interest_only_amount > 0 or case.repayment_type == "interest_only" else 80
    today = date.today()
    too_old: list[int] = []
    ages: dict[str, float] = {}
    for app in case.applicants:
        assert app.date_of_birth is not None
        current_age = (today - app.date_of_birth).days / 365.25
        end_age = current_age + case.mortgage_term_years
        ages[f"applicant_{app.index}"] = round(end_age, 2)
        if end_age > max_age:
            too_old.append(app.index)
    if too_old:
        return _result("halifax.age.maximum_at_term_end", "age", RuleStatus.FAIL, f"Applicant age at term end exceeds Halifax maximum age {max_age}.", {"end_ages": ages})
    return _result("halifax.age.maximum_at_term_end", "age", RuleStatus.PASS, f"Applicant age at term end is within Halifax maximum age {max_age}.", {"end_ages": ages})


def repayment_type(case: MortgageCase) -> RuleResult:
    if not case.repayment_type:
        return _missing("halifax.repayment.type", "repayment", "Repayment type is required.", ["var_repayment_type"])
    if case.interest_only_amount > 0 or "interest_only" in case.repayment_type:
        if case.ltv_percent and case.ltv_percent > 85:
            return _result("halifax.repayment.interest_only_ltv", "repayment", RuleStatus.FAIL, "Part interest-only lending cannot exceed 85% total LTV.")
        return _result("halifax.repayment.interest_only_ltv", "repayment", RuleStatus.REFER, "Interest-only repayment plan requires evidence and manual Halifax criteria checks.")
    return _result("halifax.repayment.type", "repayment", RuleStatus.PASS, "Repayment type is capital and interest.")


def lti_matrix(case: MortgageCase) -> RuleResult:
    if case.loan_amount is None or case.lti_multiple is None or case.ltv_percent is None:
        return _missing("halifax.lti.published_matrix", "lti", "Loan amount, income, and LTV are required for LTI checks.", ["var_property_value", "var_deposit", "var_appl*_gross_annual_salary"])
    income = case.gross_annual_income
    if case.ltv_percent > 90:
        max_lti = 4.49
    elif income < 40_000:
        max_lti = 4.49
    elif income >= 125_000 and case.ltv_percent <= 85:
        max_lti = 5.5
    elif income >= 75_000 and case.ltv_percent <= 85:
        max_lti = 5.0
    elif income >= 50_000 and case.ltv_percent <= 85:
        max_lti = 5.0
    else:
        max_lti = 4.49
    if case.lti_multiple > max_lti:
        return _result("halifax.lti.published_matrix", "lti", RuleStatus.FAIL, f"LTI {case.lti_multiple:.2f}x exceeds indicative Halifax cap {max_lti:.2f}x.", {"lti": round(case.lti_multiple, 2), "max_lti": max_lti})
    return _result("halifax.lti.published_matrix", "lti", RuleStatus.PASS, f"LTI {case.lti_multiple:.2f}x is within the indicative Halifax cap {max_lti:.2f}x.", {"lti": round(case.lti_multiple, 2), "max_lti": max_lti})


def residency(case: MortgageCase) -> RuleResult:
    missing: list[str] = []
    referrals: list[str] = []
    for app in case.applicants:
        if not app.nationality:
            missing.append(f"var_appl{app.index}_nationality")
            continue
        if app.nationality in {"british", "uk", "united kingdom"}:
            continue
        if app.residency_status in {"indefinite_leave_to_remain", "settled_status", "permanent_residence"}:
            continue
        referrals.append(f"applicant {app.index} is non-UK without permanent right to reside captured")
    if missing:
        return _missing("halifax.residency.non_uk_nationals", "residency", "Nationality/residency fields are required.", missing)
    if referrals:
        return _result("halifax.residency.non_uk_nationals", "residency", RuleStatus.REFER, "Non-UK national criteria require manual Halifax checks: " + "; ".join(referrals), {"referrals": referrals})
    return _result("halifax.residency.non_uk_nationals", "residency", RuleStatus.PASS, "Applicant nationality/residency meets the basic published screen.")


def employment(case: MortgageCase) -> RuleResult:
    missing: list[str] = []
    referrals: list[str] = []
    for app in case.applicants:
        if not app.employment_type:
            missing.append(f"var_appl{app.index}_employment_details_employment_type")
            continue
        if app.employment_type == "employed" and app.employed_type == "permanent":
            continue
        referrals.append(f"applicant {app.index} employment type '{app.employment_type}' requires evidence/manual criteria")
    if missing:
        return _missing("halifax.employment.minimum_time_and_evidence", "employment", "Employment type is required.", missing)
    if referrals:
        return _result("halifax.employment.minimum_time_and_evidence", "employment", RuleStatus.REFER, "; ".join(referrals), {"referrals": referrals})
    return _result("halifax.employment.minimum_time_and_evidence", "employment", RuleStatus.PASS, "Applicants are permanent employed in the supplied data.")


def deposit_sources(case: MortgageCase) -> RuleResult:
    if case.deposit is None:
        return _missing("halifax.deposit.source_acceptance", "deposit", "Deposit amount is required.", ["var_deposit"])
    if not case.deposit_sources:
        return _missing("halifax.deposit.source_acceptance", "deposit", "Deposit source details are required.", ["var_deposit_source_details"])
    unacceptable = []
    manual = []
    for source in case.deposit_sources:
        source_type = str(source.get("source", "")).lower()
        if "loan" in source_type:
            unacceptable.append(source_type)
        elif source_type in {"gifted", "gifted_deposit", "incentive_builder", "builder_incentive", "concessionary"}:
            manual.append(source_type)
    if unacceptable:
        return _result("halifax.deposit.source_acceptance", "deposit", RuleStatus.FAIL, "Personal loan deposit sources are not acceptable.", {"unacceptable_sources": unacceptable})
    if manual:
        return _result("halifax.deposit.source_acceptance", "deposit", RuleStatus.REFER, "Some deposit sources require Halifax evidence/manual checks.", {"manual_sources": manual})
    return _result("halifax.deposit.source_acceptance", "deposit", RuleStatus.PASS, "Deposit sources do not show an obvious unacceptable source.")


def builder_incentives(case: MortgageCase) -> RuleResult:
    incentive = sum(float(item.get("amount") or 0) for item in case.deposit_sources if str(item.get("source", "")).lower() in {"incentive_builder", "builder_incentive"})
    if incentive <= 0:
        return _result("halifax.deposit.builder_incentive", "deposit", RuleStatus.PASS, "No builder incentive is supplied.")
    if case.property_value is None or case.loan_amount is None:
        return _missing("halifax.deposit.builder_incentive", "deposit", "Property value and loan amount are required to assess builder incentives.", ["var_property_value", "var_deposit"])
    combined_ltv = ((case.loan_amount + incentive) / case.property_value) * 100
    max_ltv = _max_ltv_for_loan(case.loan_amount) or 0
    if combined_ltv > max_ltv:
        return _result("halifax.deposit.builder_incentive", "deposit", RuleStatus.FAIL, "Loan plus builder incentive exceeds relevant LTV cap.", {"combined_ltv": round(combined_ltv, 2), "max_ltv": max_ltv})
    return _result("halifax.deposit.builder_incentive", "deposit", RuleStatus.PASS, "Loan plus builder incentive is within the standard LTV cap.", {"combined_ltv": round(combined_ltv, 2), "max_ltv": max_ltv})


def property_details(case: MortgageCase) -> RuleResult:
    missing = []
    for field, value in {
        "var_property_details_property_type": case.property_type,
        "var_property_details_description": case.property_description,
        "var_property_details_tenure": case.property_tenure,
        "var_property_details_construction_material": case.construction_material,
    }.items():
        if not value:
            missing.append(field)
    if missing:
        return _missing("halifax.property.acceptability", "property", "Property type, tenure, description, and construction are needed for Halifax property acceptability checks.", missing)
    description = " ".join([case.property_type or "", case.property_description or ""])
    if "mobile" in description or "houseboat" in description or "timeshare" in description:
        return _result("halifax.property.acceptability", "property", RuleStatus.FAIL, "Property type is specifically excluded by Halifax property criteria.")
    return _result("halifax.property.acceptability", "property", RuleStatus.REFER, "Property details are supplied but valuation/surveyor acceptability remains a manual Halifax check.")


def new_build_caps(case: MortgageCase) -> RuleResult:
    description = " ".join([case.property_type or "", case.property_description or "", str(case.intend_to_purchase_flat or "")]).lower()
    if "new" not in description and "build" not in description:
        if not case.property_type and not case.property_description:
            return _missing("halifax.property.new_build_caps", "property", "Property description/type is needed to decide whether new-build caps apply.", ["var_property_details_property_type", "var_property_details_description"])
        return _result("halifax.property.new_build_caps", "property", RuleStatus.PASS, "New-build cap is not indicated by supplied property fields.")
    if case.ltv_percent is None:
        return _missing("halifax.property.new_build_caps", "property", "LTV is required for new-build caps.", ["var_property_value", "var_deposit"])
    cap = 85.0 if "flat" in description or _is_yes(case.intend_to_purchase_flat) else 95.0
    if "converted" in description or "refurbished" in description:
        cap = 80.0
    if case.ltv_percent > cap:
        return _result("halifax.property.new_build_caps", "property", RuleStatus.FAIL, f"Property appears subject to a {cap:.0f}% new-build/converted property cap.", {"ltv": round(case.ltv_percent, 2), "cap": cap})
    return _result("halifax.property.new_build_caps", "property", RuleStatus.PASS, f"Property LTV is within the indicated new-build/converted cap of {cap:.0f}%.")


def commitments(case: MortgageCase) -> RuleResult:
    monthly = 0.0
    adjustments = []
    for app in case.applicants:
        for commitment in app.credit_commitments:
            ctype = str(commitment.get("type", "")).lower()
            declared = float(commitment.get("monthly_payment") or 0)
            balance = float(commitment.get("current_balance") or 0)
            used = max(declared, balance * 0.05) if ctype in {"cards", "credit_card", "card"} else declared
            monthly += used
            if used != declared:
                adjustments.append({"applicant": app.index, "type": ctype, "declared": declared, "used": used})
    return _result("halifax.commitments.credit_cards", "commitments", RuleStatus.PASS, "Credit commitments were normalized for affordability pre-screening.", {"monthly_commitments": monthly, "adjustments": adjustments})


def background_properties(case: MortgageCase) -> RuleResult:
    if not case.other_properties:
        return _result("halifax.background_mortgages", "background_properties", RuleStatus.PASS, "No background properties are supplied.")
    warnings = []
    monthly_cost = 0.0
    for index, prop in enumerate(case.other_properties, start=1):
        payment = float(prop.get("monthly_repayment") or 0)
        rent = float(prop.get("monthly_rent") or 0)
        is_rental = str(prop.get("is_rental_property", "")).lower() == "yes"
        if is_rental:
            required_rent = payment * 1.25
            if rent < required_rent:
                shortfall = required_rent - rent
                monthly_cost += shortfall
                warnings.append(f"property {index} rent is below 125% mortgage payment by {shortfall:.2f}")
        elif payment:
            monthly_cost += payment
            warnings.append(f"property {index} mortgage payment should be treated as a commitment unless sold")
    if warnings:
        return _result("halifax.background_mortgages", "background_properties", RuleStatus.REFER, "Background property treatment requires affordability/manual review.", {"monthly_cost": monthly_cost, "warnings": warnings})
    return _result("halifax.background_mortgages", "background_properties", RuleStatus.PASS, "Background properties do not show an obvious pre-screen issue.", {"property_count": len(case.other_properties)})


def adverse_credit(case: MortgageCase) -> RuleResult:
    fields = [key for key in case.raw if any(term in key.lower() for term in ["ccj", "default", "bankrupt", "iva", "arrear", "debt_management", "repossession"])]
    if not fields:
        return _missing("halifax.credit.adverse_declaration", "credit", "Adverse credit declaration fields are not present in the input.", ["ccj/default/bankruptcy/iva/arrears fields"])
    positive = [field for field in fields if _is_yes(case.raw.get(field))]
    if positive:
        return _result("halifax.credit.adverse_declaration", "credit", RuleStatus.REFER, "Adverse credit is declared and must be considered by Halifax scoring/manual criteria.", {"fields": positive})
    return _result("halifax.credit.adverse_declaration", "credit", RuleStatus.PASS, "No adverse credit is declared in supplied fields.")


AUTOMATED_RULES: list[Callable[[MortgageCase], RuleResult]] = [
    applicant_count,
    standard_ltv,
    high_ltv_purchase,
    term_limit,
    age_at_end,
    repayment_type,
    lti_matrix,
    residency,
    employment,
    deposit_sources,
    builder_incentives,
    property_details,
    new_build_caps,
    commitments,
    background_properties,
    adverse_credit,
]


def evaluate_rules(case: MortgageCase, include_snapshot: bool = True) -> list[RuleResult]:
    results = [rule(case) for rule in AUTOMATED_RULES]
    if include_snapshot and SNAPSHOT_PATH.exists():
        results.extend(snapshot_results(SNAPSHOT_PATH, {result.rule_id for result in results}))
    return results
