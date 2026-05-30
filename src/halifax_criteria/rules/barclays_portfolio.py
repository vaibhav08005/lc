from __future__ import annotations

from ..models import MortgageCase, RuleStatus
from .barclays_common import result


def background_properties(case: MortgageCase):
    if not case.other_properties:
        return result("barclays.background_properties", "background_properties", RuleStatus.PASS, "No background properties are supplied.", section="Commitments – Residential", criteria_type="hard_rule", implemented_by="barclays.background_properties")
    warnings = []
    for index, prop in enumerate(case.other_properties, start=1):
        if float(prop.get("monthly_repayment") or 0) > 0:
            warnings.append(f"property {index} mortgage payment should be included in Barclays affordability")
    return result("barclays.background_properties", "background_properties", RuleStatus.REFER, "Background residential/BTL property commitments require Barclays affordability treatment.", {"warnings": warnings, "property_count": len(case.other_properties)}, section="Commitments – Residential", criteria_type="hard_rule", implemented_by="barclays.background_properties")


def second_charges(case: MortgageCase):
    if any("second" in str(value).lower() and "charge" in str(value).lower() for value in case.raw.values()):
        return result("barclays.second_charges", "charges", RuleStatus.REFER, "Second/subsequent charge criteria require manual Barclays review.", section="Second/subsequent charges", criteria_type="manual_rule", implemented_by="barclays.second_charges")
    return result("barclays.second_charges", "charges", RuleStatus.PASS, "Second/subsequent charge criteria do not appear to apply.", section="Second/subsequent charges", criteria_type="manual_rule", implemented_by="barclays.second_charges")
