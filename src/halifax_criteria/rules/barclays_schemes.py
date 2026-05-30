from __future__ import annotations

from ..models import MortgageCase, RuleStatus
from .barclays_common import has_any, missing, result


def scheme_classification(case: MortgageCase) -> str | None:
    if has_any(case, "family springboard"):
        return "family_springboard"
    if has_any(case, "mortgage boost", "joint borrower"):
        return "mortgage_boost"
    if has_any(case, "right to buy"):
        return "right_to_buy"
    if has_any(case, "shared ownership"):
        return "shared_ownership"
    if has_any(case, "shared equity"):
        return "shared_equity"
    if has_any(case, "help to buy"):
        return "help_to_buy"
    if has_any(case, "discounted market"):
        return "discounted_market_sale"
    if has_any(case, "rent to own"):
        return "rent_to_own"
    if has_any(case, "green home"):
        return "green_home"
    if has_any(case, "forces help"):
        return "forces_help_to_buy"
    return None


def special_schemes(case: MortgageCase):
    scheme = scheme_classification(case)
    if not scheme:
        return result("barclays.schemes.classification", "schemes", RuleStatus.PASS, "No Barclays special scheme is indicated by supplied fields.", section="Family Springboard", criteria_type="manual_rule", implemented_by="barclays.special_schemes")
    if case.ltv_percent is None:
        return missing("barclays.schemes.classification", "schemes", "LTV inputs are required for scheme-specific Barclays checks.", ["var_property_value", "var_deposit"], section="Family Springboard", criteria_type="hard_rule", implemented_by="barclays.special_schemes")
    caps = {
        "shared_ownership": 90.0,
        "shared_equity": 85.0,
        "right_to_buy": 85.0,
        "help_to_buy": 75.0,
        "discounted_market_sale": 85.0,
    }
    cap = caps.get(scheme)
    if cap is not None and case.ltv_percent > cap:
        return result("barclays.schemes.classification", "schemes", RuleStatus.FAIL, f"Barclays {scheme} headline LTV cap is {cap:.0f}%.", {"scheme": scheme, "ltv_percent": round(case.ltv_percent, 2), "max_ltv": cap}, section="Family Springboard", criteria_type="hard_rule", implemented_by="barclays.special_schemes")
    return result("barclays.schemes.classification", "schemes", RuleStatus.REFER, "Barclays special scheme criteria require scheme evidence/manual review.", {"scheme": scheme, "ltv_percent": round(case.ltv_percent, 2)}, section="Family Springboard", criteria_type="manual_rule", implemented_by="barclays.special_schemes")


def loan_purpose(case: MortgageCase):
    if not case.mortgage_type:
        return missing("barclays.loan.purpose", "loan_purpose", "Mortgage type or loan purpose is required.", ["var_mortgage_type"], section="Loan purpose", criteria_type="hard_rule", implemented_by="barclays.loan_purpose")
    return result("barclays.loan.purpose", "loan_purpose", RuleStatus.REFER, "Loan purpose is supplied but Barclays purpose-specific criteria may require manual review.", {"mortgage_type": case.mortgage_type}, section="Loan purpose", criteria_type="manual_rule", implemented_by="barclays.loan_purpose")


def porting_permission_to_let(case: MortgageCase):
    if has_any(case, "port", "permission to let"):
        return result("barclays.porting_permission_to_let", "porting", RuleStatus.REFER, "Porting or permission-to-let criteria require Barclays product/account-specific checks.", section="Porting - Residential", criteria_type="manual_rule", implemented_by="barclays.porting_permission_to_let")
    return result("barclays.porting_permission_to_let", "porting", RuleStatus.PASS, "Porting and permission-to-let criteria do not appear to apply.", section="Porting - Residential", criteria_type="manual_rule", implemented_by="barclays.porting_permission_to_let")


def short_term_letting(case: MortgageCase):
    if has_any(case, "short term let", "airbnb", "holiday let"):
        return result("barclays.short_term_letting", "property_usage", RuleStatus.REFER, "Short-term letting criteria require Barclays property usage review.", section="Short-term letting", criteria_type="manual_rule", implemented_by="barclays.short_term_letting")
    return result("barclays.short_term_letting", "property_usage", RuleStatus.PASS, "Short-term letting is not indicated by supplied fields.", section="Short-term letting", criteria_type="manual_rule", implemented_by="barclays.short_term_letting")
