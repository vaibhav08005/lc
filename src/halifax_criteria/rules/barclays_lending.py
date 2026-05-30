from __future__ import annotations

from ..models import MortgageCase, RuleStatus
from .barclays_common import case_text, has_any, is_yes, missing, retained_property_count, result


def loan_size(case: MortgageCase):
    if case.loan_amount is None:
        return missing("barclays.loan.size", "loan", "Loan amount requires property value and deposit.", ["var_property_value", "var_deposit"], section="Loan to Value (LTV) - Residential", criteria_type="hard_rule", implemented_by="barclays.loan_size")
    if case.loan_amount < 5_000:
        return result("barclays.loan.size", "loan", RuleStatus.FAIL, "Loan amount is below Barclays minimum loan size of GBP 5,000.", {"loan_amount": case.loan_amount}, section="Loan to Value (LTV) - Residential", criteria_type="hard_rule", implemented_by="barclays.loan_size")
    if case.loan_amount > 5_000_000:
        return result("barclays.loan.size", "loan", RuleStatus.REFER, "Loan amount is above GBP 5m and may be subject to bespoke pricing/underwriter discretion.", {"loan_amount": case.loan_amount}, section="Loan to Value (LTV) - Residential", criteria_type="soft_rule", implemented_by="barclays.loan_size")
    return result("barclays.loan.size", "loan", RuleStatus.PASS, "Loan amount is within standard Barclays size limits.", {"loan_amount": case.loan_amount}, section="Loan to Value (LTV) - Residential", criteria_type="hard_rule", implemented_by="barclays.loan_size")


def term_limit(case: MortgageCase):
    if case.mortgage_term_months is None:
        return missing("barclays.term.maximum", "term", "Mortgage term is required.", ["var_mortgage_term"], section="Term of mortgage - Residential", criteria_type="hard_rule", implemented_by="barclays.term_limit")
    if case.mortgage_term_months < 60:
        return result("barclays.term.maximum", "term", RuleStatus.FAIL, "Mortgage term is below Barclays minimum term of 5 years.", section="Term of mortgage - Residential", criteria_type="hard_rule", implemented_by="barclays.term_limit")
    is_interest_only = case.interest_only_amount > 0 or case.repayment_type == "interest_only"
    max_months = 300 if is_interest_only else 480
    if case.mortgage_term_months > max_months:
        max_years = max_months // 12
        return result("barclays.term.maximum", "term", RuleStatus.FAIL, f"Mortgage term exceeds Barclays maximum term of {max_years} years for this repayment type.", {"term_months": case.mortgage_term_months}, section="Term of mortgage - Residential", criteria_type="hard_rule", implemented_by="barclays.term_limit")
    return result("barclays.term.maximum", "term", RuleStatus.PASS, "Mortgage term is within Barclays published limits.", {"term_months": case.mortgage_term_months}, section="Term of mortgage - Residential", criteria_type="hard_rule", implemented_by="barclays.term_limit")


def age_at_end(case: MortgageCase):
    if case.mortgage_term_years is None:
        return missing("barclays.age.maximum_at_term_end", "age", "Mortgage term is required for age-at-end checks.", ["var_mortgage_term"], section="Age/Term", criteria_type="hard_rule", implemented_by="barclays.age_at_end")
    missing_fields = [f"var_appl{app.index}_date_of_birth" for app in case.applicants if app.date_of_birth is None]
    if missing_fields:
        return missing("barclays.age.maximum_at_term_end", "age", "Applicant date of birth is required to check Barclays maximum age at end of term.", missing_fields, section="Age/Term", criteria_type="hard_rule", implemented_by="barclays.age_at_end")
    is_interest_only = case.interest_only_amount > 0 or case.repayment_type == "interest_only"
    max_age = 70 if is_interest_only and (case.ltv_percent or 0) > 50 else (75 if is_interest_only else 80)
    from datetime import date

    today = date.today()
    ages: dict[str, float] = {}
    too_old: list[int] = []
    for app in case.applicants:
        assert app.date_of_birth is not None
        end_age = ((today - app.date_of_birth).days / 365.25) + case.mortgage_term_years
        ages[f"applicant_{app.index}"] = round(end_age, 2)
        if end_age > max_age:
            too_old.append(app.index)
    if too_old:
        return result("barclays.age.maximum_at_term_end", "age", RuleStatus.FAIL, f"Applicant age at term end exceeds Barclays maximum age {max_age}.", {"end_ages": ages}, section="Age/Term", criteria_type="hard_rule", implemented_by="barclays.age_at_end")
    return result("barclays.age.maximum_at_term_end", "age", RuleStatus.PASS, f"Applicant age at term end is within Barclays maximum age {max_age}.", {"end_ages": ages}, section="Age/Term", criteria_type="hard_rule", implemented_by="barclays.age_at_end")


def barclays_ltv_cap(case: MortgageCase) -> tuple[float, str]:
    text = case_text(case)
    is_interest_only = case.interest_only_amount > 0 or case.repayment_type == "interest_only"
    is_part_and_part = case.interest_only_amount > 0 and case.loan_amount is not None and case.interest_only_amount < case.loan_amount
    if has_any(case, "help to buy"):
        return 75.0, "Help to Buy equity loan scheme cap"
    if has_any(case, "discounted market", "section 106", "s.106", "s75", "s.75"):
        return 85.0, "discounted market sale or S.106/S.75 cap"
    if has_any(case, "shared ownership", "shared equity", "right to buy"):
        return 90.0, "special scheme cap"
    if is_part_and_part:
        return 85.0, "part-and-part maximum LTV"
    if is_interest_only:
        return 75.0, "interest-only maximum LTV"
    if "debt" in text and ("remo" in text or "remortgage" in text or "additional" in text):
        return 80.0, "debt-consolidation remortgage/additional borrowing cap"
    if "additional" in text or "further" in text or "capital" in text or case.raw.get("var_equity_release_amount"):
        return 85.0, "capital-raising/additional borrowing cap"
    if "new" in text and "build" in text and ("flat" in text or "apartment" in text or "maisonette" in text or is_yes(case.intend_to_purchase_flat)):
        return 85.0, "new-build flat/apartment cap"
    if retained_property_count(case) > 1:
        return 90.0, "customer retaining more than one mortgaged residential property cap"
    if case.mortgage_type in {"remortgage", "remo"}:
        return 90.0, "like-for-like remortgage cap"
    return 95.0, "standard purchase cap"


def ltv(case: MortgageCase):
    if case.loan_amount is None or case.ltv_percent is None:
        return missing("barclays.ltv.residential_limits", "loan_to_value", "Property value and deposit are required to calculate LTV.", ["var_property_value", "var_deposit"], section="Loan to Value (LTV) - Residential", criteria_type="hard_rule", implemented_by="barclays.ltv")
    cap, reason = barclays_ltv_cap(case)
    if case.ltv_percent > cap:
        return result("barclays.ltv.residential_limits", "loan_to_value", RuleStatus.FAIL, f"LTV {case.ltv_percent:.2f}% exceeds Barclays {reason} of {cap:.2f}%.", {"ltv_percent": round(case.ltv_percent, 2), "max_ltv": cap, "reason": reason}, section="Loan to Value (LTV) - Residential", criteria_type="hard_rule", implemented_by="barclays.ltv")
    if case.ltv_percent > 90 and case.loan_amount > 570_000:
        return result("barclays.ltv.high_ltv_loan_size", "loan_to_value", RuleStatus.FAIL, "Where Barclays LTV is above 90%, maximum loan size is GBP 570k.", {"loan_amount": case.loan_amount, "ltv_percent": round(case.ltv_percent, 2)}, section="Loan to Value (LTV) - Residential", criteria_type="hard_rule", implemented_by="barclays.ltv")
    return result("barclays.ltv.residential_limits", "loan_to_value", RuleStatus.PASS, f"LTV {case.ltv_percent:.2f}% is within Barclays {reason} of {cap:.2f}%.", {"ltv_percent": round(case.ltv_percent, 2), "max_ltv": cap, "reason": reason}, section="Loan to Value (LTV) - Residential", criteria_type="hard_rule", implemented_by="barclays.ltv")


def additional_borrowing(case: MortgageCase):
    if not has_any(case, "additional", "further") and not case.raw.get("var_equity_release_amount"):
        return result("barclays.additional_borrowing", "additional_borrowing", RuleStatus.PASS, "Additional borrowing criteria do not appear to apply.", section="Additional borrowing", criteria_type="hard_rule", implemented_by="barclays.additional_borrowing")
    if case.ltv_percent is None:
        return missing("barclays.additional_borrowing", "additional_borrowing", "LTV is required for additional borrowing checks.", ["var_property_value", "var_deposit"], section="Additional borrowing", criteria_type="hard_rule", implemented_by="barclays.additional_borrowing")
    cap = 80.0 if has_any(case, "debt") else 85.0
    if case.ltv_percent > cap:
        return result("barclays.additional_borrowing", "additional_borrowing", RuleStatus.FAIL, f"Additional borrowing exceeds Barclays cap of {cap:.0f}% LTV.", {"ltv_percent": round(case.ltv_percent, 2), "max_ltv": cap}, section="Additional borrowing", criteria_type="hard_rule", implemented_by="barclays.additional_borrowing")
    return result("barclays.additional_borrowing", "additional_borrowing", RuleStatus.REFER, "Additional borrowing appears within headline LTV cap but requires Barclays purpose/product/valuation checks.", {"ltv_percent": round(case.ltv_percent, 2), "max_ltv": cap}, section="Additional borrowing", criteria_type="soft_rule", implemented_by="barclays.additional_borrowing")
