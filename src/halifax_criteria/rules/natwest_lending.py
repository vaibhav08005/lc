from __future__ import annotations

from ..models import MortgageCase, RuleStatus
from .natwest_common import case_text, has_any, is_interest_only, missing, result


def loan_size(case: MortgageCase):
    if case.loan_amount is None:
        return missing("natwest.loan.size", "loan", "Loan amount requires property value and deposit.", ["var_property_value", "var_deposit"], section="Lending Limits - Loan amounts and LTVs", criteria_type="hard_rule", implemented_by="natwest.ltv")
    if case.loan_amount <= 0:
        return result("natwest.loan.size", "loan", RuleStatus.FAIL, "Loan amount must be greater than zero.", {"loan_amount": case.loan_amount}, section="Lending Limits - Loan amounts and LTVs", criteria_type="hard_rule", implemented_by="natwest.ltv")
    return result("natwest.loan.size", "loan", RuleStatus.PASS, "Loan amount can be assessed against NatWest LTV and affordability criteria.", {"loan_amount": case.loan_amount}, section="Lending Limits - Loan amounts and LTVs", criteria_type="hard_rule", implemented_by="natwest.ltv")


def term(case: MortgageCase):
    if case.mortgage_term_months is None:
        return missing("natwest.term", "term", "Mortgage term is required.", ["var_mortgage_term"], section="Term", criteria_type="hard_rule", implemented_by="natwest.term")
    if case.mortgage_term_months <= 0:
        return result("natwest.term", "term", RuleStatus.FAIL, "Mortgage term must be greater than zero.", {"term_months": case.mortgage_term_months}, section="Term", criteria_type="hard_rule", implemented_by="natwest.term")
    if case.mortgage_term_months > 480:
        return result("natwest.term", "term", RuleStatus.FAIL, "Mortgage term exceeds the 40-year ceiling used by this pre-screen.", {"term_months": case.mortgage_term_months}, section="Term", criteria_type="hard_rule", implemented_by="natwest.term")
    return result("natwest.term", "term", RuleStatus.PASS, "Mortgage term is present and within pre-screen limits.", {"term_months": case.mortgage_term_months}, section="Term", criteria_type="hard_rule", implemented_by="natwest.term")


def natwest_ltv_cap(case: MortgageCase) -> tuple[float, str]:
    text = case_text(case)
    if "agricultural" in text or "acreage" in text:
        return 50.0, "agricultural restriction cap"
    for app in case.applicants:
        if app.nationality and app.nationality not in {"british", "uk", "united kingdom"} and app.residency_status and "permanent" not in app.residency_status:
            return 75.0, "foreign national without permanent right to reside cap"
    if is_interest_only(case):
        return 75.0, "interest-only indicative cap"
    if "new build" in text:
        return 90.0, "new-build indicative cap"
    return 95.0, "standard residential indicative cap"


def ltv(case: MortgageCase):
    if case.ltv_percent is None:
        return missing("natwest.ltv.maximum", "loan_to_value", "Property value and deposit are required to calculate LTV.", ["var_property_value", "var_deposit"], section="Maximum LTV", criteria_type="hard_rule", implemented_by="natwest.ltv")
    cap, reason = natwest_ltv_cap(case)
    if case.ltv_percent > cap:
        return result("natwest.ltv.maximum", "loan_to_value", RuleStatus.FAIL, f"LTV {case.ltv_percent:.2f}% exceeds NatWest {reason} of {cap:.2f}%.", {"ltv_percent": round(case.ltv_percent, 2), "max_ltv": cap, "reason": reason}, section="Maximum LTV", criteria_type="hard_rule", implemented_by="natwest.ltv")
    return result("natwest.ltv.maximum", "loan_to_value", RuleStatus.PASS, f"LTV {case.ltv_percent:.2f}% is within NatWest {reason} of {cap:.2f}%.", {"ltv_percent": round(case.ltv_percent, 2), "max_ltv": cap, "reason": reason}, section="Maximum LTV", criteria_type="hard_rule", implemented_by="natwest.ltv")


def loan_to_income(case: MortgageCase):
    if case.lti_multiple is None:
        return missing("natwest.loan_to_income", "income", "Loan, income and property fields are required to calculate LTI.", ["var_property_value", "var_deposit", "var_appl*_gross_annual_salary"], section="Loan to Income (residential new business only)", criteria_type="hard_rule", implemented_by="natwest.loan_to_income")
    return result("natwest.loan_to_income", "income", RuleStatus.REFER, "NatWest LTI is case and affordability dependent; use NatWest affordability outputs for final maximum borrowing.", {"lti_multiple": round(case.lti_multiple, 2)}, section="Loan to Income (residential new business only)", criteria_type="soft_rule", implemented_by="natwest.loan_to_income")


def interest_only(case: MortgageCase):
    if not is_interest_only(case):
        return result("natwest.interest_only", "repayment", RuleStatus.PASS, "Interest-only criteria do not appear to apply.", section="Interest only", criteria_type="hard_rule", implemented_by="natwest.interest_only")
    if case.ltv_percent is None:
        return missing("natwest.interest_only", "repayment", "LTV is required for NatWest interest-only checks.", ["var_property_value", "var_deposit"], section="Interest only", criteria_type="hard_rule", implemented_by="natwest.interest_only")
    if case.ltv_percent > 75:
        return result("natwest.interest_only", "repayment", RuleStatus.FAIL, "Interest-only borrowing exceeds the NatWest pre-screen LTV cap.", {"ltv_percent": round(case.ltv_percent, 2), "max_ltv": 75.0}, section="Interest only", criteria_type="hard_rule", implemented_by="natwest.interest_only")
    return result("natwest.interest_only", "repayment", RuleStatus.REFER, "Interest-only appears within headline LTV cap but requires repayment strategy and income eligibility review.", {"ltv_percent": round(case.ltv_percent, 2)}, section="Interest only", criteria_type="evidence_rule", implemented_by="natwest.interest_only")


def additional_borrowing(case: MortgageCase):
    text = case_text(case)
    applies = "additional" in text or "further" in text or bool(case.raw.get("var_equity_release_amount"))
    if not applies:
        return result("natwest.additional_borrowing", "additional_borrowing", RuleStatus.PASS, "Additional borrowing criteria do not appear to apply.", section="Additional Borrowing Purposes", criteria_type="hard_rule", implemented_by="natwest.additional_borrowing")
    if any(term in text for term in ["business", "start up", "startup"]):
        return result("natwest.additional_borrowing", "additional_borrowing", RuleStatus.FAIL, "NatWest does not allow additional borrowing for business purposes.", {"purpose_text": case.raw.get("var_add_borrow_details")}, section="Additional Borrowing Purposes", criteria_type="hard_rule", implemented_by="natwest.additional_borrowing")
    if any(term in text for term in ["buy to let", "consent to let", "btl"]) and any(term in text for term in ["gambling", "business", "unsecured debt consolidation"]):
        return result("natwest.additional_borrowing", "additional_borrowing", RuleStatus.FAIL, "NatWest cannot consider BTL/consent-to-let additional borrowing for gambling, business purpose, or unsecured debt consolidation.", {"purpose_text": case.raw.get("var_add_borrow_details")}, section="Additional Borrowing Purposes", criteria_type="hard_rule", implemented_by="natwest.additional_borrowing")
    return result("natwest.additional_borrowing", "additional_borrowing", RuleStatus.REFER, "Additional borrowing purpose requires NatWest purpose, valuation and packaging review.", {"purpose_text": case.raw.get("var_add_borrow_details")}, section="Additional Borrowing Purposes", criteria_type="manual_rule", implemented_by="natwest.additional_borrowing")


def debt_consolidation(case: MortgageCase):
    if "debt" not in case_text(case):
        return result("natwest.debt_consolidation", "loan_purpose", RuleStatus.PASS, "Debt consolidation is not indicated.", section="Debt Consolidation", criteria_type="manual_rule", implemented_by="natwest.additional_borrowing")
    return result("natwest.debt_consolidation", "loan_purpose", RuleStatus.REFER, "Debt consolidation requires NatWest purpose and affordability review.", section="Debt Consolidation", criteria_type="manual_rule", implemented_by="natwest.additional_borrowing")
