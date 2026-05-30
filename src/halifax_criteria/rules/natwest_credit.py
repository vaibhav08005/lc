from __future__ import annotations

from ..models import AutomationLevel, MortgageCase, RuleStatus
from .natwest_common import declared_adverse_fields, rental_shortfalls, result


def adverse_credit(case: MortgageCase):
    fields, positive = declared_adverse_fields(case)
    if not fields:
        from .natwest_common import missing

        return missing("natwest.credit.adverse_history", "credit", "Adverse-credit declaration fields are not present in the input.", ["ccj/bankruptcy/insolvency/iva/dro/debt-repayment-plan fields"], section="Adverse Credit", criteria_type="hard_rule", implemented_by="natwest.adverse_credit")
    if positive:
        return result("natwest.credit.adverse_history", "credit", RuleStatus.FAIL, "NatWest cannot accept declared insolvency, debt repayment plan, bankruptcy or CCJ answers within the published six-year declaration window.", {"fields": fields}, section="Adverse Credit", criteria_type="hard_rule", implemented_by="natwest.adverse_credit")
    return result("natwest.credit.adverse_history", "credit", RuleStatus.PASS, "No adverse-credit declaration is supplied in mapped fields.", {"fields": fields}, section="Adverse Credit", criteria_type="hard_rule", implemented_by="natwest.adverse_credit")


def credit_scoring(case: MortgageCase):
    return result("natwest.credit.scoring", "credit", RuleStatus.REFER, "NatWest credit scoring and bureau conduct assessment are proprietary lender processes.", automation_level=AutomationLevel.OUT_OF_SCOPE_PROPRIETARY, section="Credit scoring", criteria_type="proprietary_rule", implemented_by="natwest.credit_scoring")


def commitments(case: MortgageCase):
    commitments = sum(len(app.credit_commitments) for app in case.applicants)
    if commitments:
        return result("natwest.commitments", "commitments", RuleStatus.REFER, "Committed expenditure, loans and credit cards require NatWest affordability treatment.", {"commitment_count": commitments}, section="Financial Commitments", criteria_type="hard_rule", implemented_by="natwest.commitments")
    return result("natwest.commitments", "commitments", RuleStatus.PASS, "No applicant credit commitments are supplied.", section="Financial Commitments", criteria_type="hard_rule", implemented_by="natwest.commitments")


def background_btl(case: MortgageCase):
    shortfalls = rental_shortfalls(case)
    if shortfalls:
        return result("natwest.background_btl", "background_properties", RuleStatus.REFER, "Background BTL rental shortfalls must be keyed as other financial commitments.", {"shortfalls": shortfalls}, section="Background Buy to Lets", criteria_type="hard_rule", implemented_by="natwest.background_btl")
    if case.other_properties:
        return result("natwest.background_btl", "background_properties", RuleStatus.REFER, "Background properties are supplied and require NatWest affordability treatment.", {"property_count": len(case.other_properties)}, section="Background Buy to Lets", criteria_type="hard_rule", implemented_by="natwest.background_btl")
    return result("natwest.background_btl", "background_properties", RuleStatus.PASS, "No background properties are supplied.", section="Background Buy to Lets", criteria_type="hard_rule", implemented_by="natwest.background_btl")
