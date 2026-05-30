from __future__ import annotations

from ..models import MortgageCase, RuleStatus
from .natwest_common import scheme_classification, result


def special_schemes(case: MortgageCase):
    scheme = scheme_classification(case)
    if not scheme:
        return result("natwest.schemes.classification", "schemes", RuleStatus.PASS, "No NatWest special scheme is indicated by supplied fields.", section="Shared Ownership", criteria_type="manual_rule", implemented_by="natwest.schemes")
    return result("natwest.schemes.classification", "schemes", RuleStatus.REFER, "NatWest special scheme criteria require scheme-specific evidence/manual review.", {"scheme": scheme, "ltv_percent": round(case.ltv_percent, 2) if case.ltv_percent is not None else None}, section="Shared Ownership", criteria_type="manual_rule", implemented_by="natwest.schemes")


def porting_product_transfer(case: MortgageCase):
    text = " ".join(str(case.raw.get(key) or "").lower() for key in ("var_mortgage_type", "var_remo_options", "var_journey"))
    if "port" in text or "product transfer" in text or "switch" in text:
        return result("natwest.porting_product_transfer", "porting", RuleStatus.REFER, "Porting, product transfers and Track and Switch require account/product-specific NatWest review.", section="Porting", criteria_type="manual_rule", implemented_by="natwest.porting")
    return result("natwest.porting_product_transfer", "porting", RuleStatus.PASS, "Porting/product-transfer criteria do not appear to apply.", section="Porting", criteria_type="manual_rule", implemented_by="natwest.porting")


def second_residential_property(case: MortgageCase):
    if case.other_properties:
        return result("natwest.second_residential_property", "property_usage", RuleStatus.REFER, "Second residential property and existing property ownership require NatWest affordability/manual review.", {"property_count": len(case.other_properties)}, section="Second Residential Property", criteria_type="manual_rule", implemented_by="natwest.second_residential_property")
    return result("natwest.second_residential_property", "property_usage", RuleStatus.PASS, "No second residential property is supplied.", section="Second Residential Property", criteria_type="manual_rule", implemented_by="natwest.second_residential_property")
