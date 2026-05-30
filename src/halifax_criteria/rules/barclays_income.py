from __future__ import annotations

from ..models import AutomationLevel, MortgageCase, RuleStatus
from .barclays_common import missing, result


def minimum_income(case: MortgageCase):
    if case.loan_amount is None:
        return missing("barclays.income.minimum", "income", "Loan amount is required for Barclays minimum income checks.", ["var_property_value", "var_deposit"], section="Income multiples", criteria_type="hard_rule", implemented_by="barclays.minimum_income")
    incomes = [app.gross_annual_salary for app in case.applicants[:2]]
    if not incomes or sum(incomes) <= 0:
        return missing("barclays.income.minimum", "income", "Applicant income is required.", ["var_appl*_gross_annual_salary"], section="Income multiples", criteria_type="hard_rule", implemented_by="barclays.minimum_income")
    if 35_000 <= case.loan_amount <= 1_000_000 and max(incomes) < 25_000:
        return result("barclays.income.minimum", "income", RuleStatus.FAIL, "For loans from GBP 35k to GBP 1m, at least one applicant must earn GBP 25k.", {"incomes": incomes}, section="Income multiples", criteria_type="hard_rule", implemented_by="barclays.minimum_income")
    if case.loan_amount > 1_000_000 and max(incomes) < 75_000 and sum(incomes) < 100_000:
        return result("barclays.income.minimum", "income", RuleStatus.FAIL, "For loans above GBP 1m, Barclays minimum income threshold is not met.", {"incomes": incomes}, section="Income multiples", criteria_type="hard_rule", implemented_by="barclays.minimum_income")
    return result("barclays.income.minimum", "income", RuleStatus.PASS, "Applicant income meets Barclays public minimum income screen.", {"incomes": incomes}, section="Income multiples", criteria_type="hard_rule", implemented_by="barclays.minimum_income")


def income_multiples(case: MortgageCase):
    if case.lti_multiple is None:
        return missing("barclays.income.multiples", "income", "Income and loan amount are required for income multiple checks.", ["var_property_value", "var_deposit", "var_appl*_gross_annual_salary"], section="Income multiples", criteria_type="hard_rule", implemented_by="barclays.income_multiples")
    return result("barclays.income.multiples", "income", RuleStatus.REFER, "Barclays income multiple limits depend on case type, affordability and product criteria; use Barclays calculator for maximum borrowing.", {"lti_multiple": round(case.lti_multiple, 2)}, section="Income multiples", criteria_type="soft_rule", implemented_by="barclays.income_multiples")


def affordability(case: MortgageCase):
    if case.lti_multiple is None:
        return missing("barclays.affordability.proprietary", "affordability", "Income and loan amount are required before Barclays affordability can be approximated.", ["var_property_value", "var_deposit", "var_appl*_gross_annual_salary"], section="Affordability – Residential", criteria_type="proprietary_rule", implemented_by="barclays.affordability")
    return result(
        "barclays.affordability.proprietary",
        "affordability",
        RuleStatus.REFER,
        "Barclays affordability uses its own calculator and disposable-income requirements; income multiples alone are not sufficient.",
        {"lti_multiple": round(case.lti_multiple, 2)},
        automation_level=AutomationLevel.OUT_OF_SCOPE_PROPRIETARY,
        section="Affordability – Residential",
        criteria_type="proprietary_rule",
        implemented_by="barclays.affordability",
    )


def employment(case: MortgageCase):
    missing_fields: list[str] = []
    referrals: list[str] = []
    for app in case.applicants:
        if not app.employment_type:
            missing_fields.append(f"var_appl{app.index}_employment_details_employment_type")
        elif app.employment_type == "employed" and app.employed_type == "permanent":
            continue
        else:
            referrals.append(f"applicant {app.index} employment type '{app.employment_type}' requires Barclays evidence/manual criteria")
    if missing_fields:
        return missing("barclays.employment.evidence", "employment", "Employment type is required.", missing_fields, section="Employed Applicants", criteria_type="evidence_rule", implemented_by="barclays.employment")
    if referrals:
        return result("barclays.employment.evidence", "employment", RuleStatus.REFER, "; ".join(referrals), {"referrals": referrals}, section="Employed Applicants", criteria_type="evidence_rule", implemented_by="barclays.employment")
    return result("barclays.employment.evidence", "employment", RuleStatus.PASS, "Applicants are permanent employed in the supplied data.", section="Employed Applicants", criteria_type="evidence_rule", implemented_by="barclays.employment")


def variable_income(case: MortgageCase):
    users_with_variable = [app.index for app in case.applicants if app.bonus or app.commission]
    if not users_with_variable:
        return result("barclays.income.variable", "income", RuleStatus.PASS, "No bonus, overtime or commission income is supplied.", section="Bonus, overtime or commission", criteria_type="evidence_rule", implemented_by="barclays.variable_income")
    return result("barclays.income.variable", "income", RuleStatus.REFER, "Bonus, overtime or commission income is present and requires Barclays evidence/sustainability treatment.", {"applicants": users_with_variable}, section="Bonus, overtime or commission", criteria_type="evidence_rule", implemented_by="barclays.variable_income")


def reduced_income(case: MortgageCase):
    if any(str(case.raw.get(key, "")).lower() == "yes" for key in case.raw if "maternity" in key or "income_reduced" in key):
        return result("barclays.income.reduced_period", "income", RuleStatus.REFER, "Reduced income for a defined period requires Barclays manual/evidence review.", section="Reduced income for defined period of time", criteria_type="evidence_rule", implemented_by="barclays.reduced_income")
    return result("barclays.income.reduced_period", "income", RuleStatus.PASS, "No reduced-income period is indicated by supplied fields.", section="Reduced income for defined period of time", criteria_type="evidence_rule", implemented_by="barclays.reduced_income")
