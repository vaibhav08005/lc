from __future__ import annotations

from ..models import MortgageCase, RuleStatus
from .barclays_common import is_yes, missing, result, unsecured_debt_total


def unsecured_debt(case: MortgageCase):
    total_balance = unsecured_debt_total(case)
    if total_balance >= case.gross_annual_income and case.gross_annual_income > 0:
        return result("barclays.credit.unsecured_debt_vs_income", "credit", RuleStatus.FAIL, "Total unsecured bureau debt is greater than or equal to income used in affordability.", {"unsecured_debt": total_balance, "income": case.gross_annual_income}, section="Adverse credit history – Residential", criteria_type="hard_rule", implemented_by="barclays.unsecured_debt")
    return result("barclays.credit.unsecured_debt_vs_income", "credit", RuleStatus.PASS, "Unsecured debt does not exceed income used in affordability from supplied commitments.", {"unsecured_debt": total_balance, "income": case.gross_annual_income}, section="Adverse credit history – Residential", criteria_type="hard_rule", implemented_by="barclays.unsecured_debt")


def adverse_credit(case: MortgageCase):
    keys = [key for key in case.raw if any(term in key.lower() for term in ["ccj", "default", "bankrupt", "dro", "iva", "arrear", "judgement", "missed", "debt_management"])]
    if not keys:
        return missing("barclays.credit.adverse_history", "credit", "Adverse-credit declaration fields are not present in the input.", ["ccj/default/bankruptcy/dro/iva/arrears/missed-payment fields"], section="Adverse credit history – Residential", criteria_type="hard_rule", implemented_by="barclays.adverse_credit")
    positives = [key for key in keys if is_yes(case.raw.get(key))]
    if positives:
        return result("barclays.credit.adverse_history", "credit", RuleStatus.REFER, "Adverse credit is declared and must be assessed against Barclays adverse-credit criteria.", {"fields": positives}, section="Adverse credit history – Residential", criteria_type="hard_rule", implemented_by="barclays.adverse_credit")
    return result("barclays.credit.adverse_history", "credit", RuleStatus.PASS, "No adverse credit is declared in supplied fields.", section="Adverse credit history – Residential", criteria_type="hard_rule", implemented_by="barclays.adverse_credit")


def credit_reference_searches(case: MortgageCase):
    return result("barclays.credit.reference_searches", "credit", RuleStatus.REFER, "Credit reference search and credit score outcomes are Barclays-controlled and cannot be reproduced from input YAML.", section="Credit reference searches", criteria_type="proprietary_rule", implemented_by="barclays.credit_reference_searches")
