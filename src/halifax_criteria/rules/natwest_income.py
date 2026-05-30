from __future__ import annotations

from ..models import AutomationLevel, MortgageCase, RuleStatus
from .natwest_common import has_any, result


def affordability(case: MortgageCase):
    return result("natwest.affordability.proprietary", "affordability", RuleStatus.REFER, "NatWest affordability calculators and final credit-bureau verified affordability cannot be reproduced from the input YAML.", {"lti_multiple": round(case.lti_multiple, 2) if case.lti_multiple is not None else None}, automation_level=AutomationLevel.OUT_OF_SCOPE_PROPRIETARY, section="Affordability Calculators", criteria_type="proprietary_rule", implemented_by="natwest.affordability")


def income_packaging(case: MortgageCase):
    return result("natwest.income.packaging", "income", RuleStatus.REFER, "Income and packaging rules require evidence review against NatWest acceptable income criteria.", section="Income and packaging", criteria_type="evidence_rule", implemented_by="natwest.income_packaging")


def employment(case: MortgageCase):
    non_standard = [app.index for app in case.applicants if app.employment_type and app.employment_type not in {"employed"}]
    if non_standard:
        return result("natwest.employment.type", "employment", RuleStatus.REFER, "Self-employed, contractor or non-standard employment requires NatWest income evidence review.", {"applicants": non_standard}, section="Employment Length", criteria_type="evidence_rule", implemented_by="natwest.employment")
    return result("natwest.employment.type", "employment", RuleStatus.PASS, "Supplied employment types do not trigger specialist NatWest income rules.", section="Employment Length", criteria_type="evidence_rule", implemented_by="natwest.employment")


def variable_income(case: MortgageCase):
    applicants = [app.index for app in case.applicants if app.bonus or app.commission or has_any(case, "bonus", "commission", "overtime")]
    if applicants:
        return result("natwest.income.variable", "income", RuleStatus.REFER, "Bonus, commission or additional income requires NatWest sustainability/evidence treatment.", {"applicants": applicants}, section="Additional Income", criteria_type="evidence_rule", implemented_by="natwest.income_packaging")
    return result("natwest.income.variable", "income", RuleStatus.PASS, "No variable income is supplied.", section="Additional Income", criteria_type="evidence_rule", implemented_by="natwest.income_packaging")


def unacceptable_income(case: MortgageCase):
    if has_any(case, "unacceptable income"):
        return result("natwest.income.unacceptable", "income", RuleStatus.FAIL, "Input indicates an unacceptable income type for NatWest criteria.", section="Unacceptable Income Types", criteria_type="hard_rule", implemented_by="natwest.income_packaging")
    return result("natwest.income.unacceptable", "income", RuleStatus.PASS, "No explicitly unacceptable income type is indicated.", section="Unacceptable Income Types", criteria_type="hard_rule", implemented_by="natwest.income_packaging")
