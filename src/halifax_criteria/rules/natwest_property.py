from __future__ import annotations

from ..models import AutomationLevel, MortgageCase, RuleStatus
from .natwest_common import has_any, missing, result


def deposit(case: MortgageCase):
    if case.deposit is None:
        return missing("natwest.deposit.source", "deposit", "Deposit amount is required.", ["var_deposit"], section="Deposit", criteria_type="hard_rule", implemented_by="natwest.deposit")
    if not case.deposit_sources:
        return missing("natwest.deposit.source", "deposit", "Deposit source details are required.", ["var_deposit_source_details"], section="Deposit", criteria_type="evidence_rule", implemented_by="natwest.deposit")
    manual = [str(source.get("source") or "").lower() for source in case.deposit_sources if source.get("source")]
    if any(term in " ".join(manual) for term in ["gift", "builder", "equity", "incentive"]):
        return result("natwest.deposit.source", "deposit", RuleStatus.REFER, "Deposit source is supplied and requires NatWest evidence/manual criteria review.", {"sources": manual}, section="Deposit", criteria_type="evidence_rule", implemented_by="natwest.deposit")
    return result("natwest.deposit.source", "deposit", RuleStatus.PASS, "Deposit source does not show an obvious NatWest pre-screen issue.", {"sources": manual}, section="Deposit", criteria_type="evidence_rule", implemented_by="natwest.deposit")


def property_details(case: MortgageCase):
    missing_fields: list[str] = []
    if not case.property_type:
        missing_fields.append("var_property_details_property_type")
    if not case.property_description:
        missing_fields.append("var_property_details_description")
    if not case.property_tenure:
        missing_fields.append("var_property_details_tenure")
    if missing_fields:
        return missing("natwest.property.details", "property", "Property details are required for NatWest property acceptability checks.", missing_fields, section="Property Types", criteria_type="hard_rule", implemented_by="natwest.property")
    return result("natwest.property.details", "property", RuleStatus.REFER, "Property facts are supplied but NatWest valuation/security acceptability remains a manual check.", section="Property Types", criteria_type="manual_rule", implemented_by="natwest.property")


def acreage_agricultural(case: MortgageCase):
    if not has_any(case, "agricultural", "acreage"):
        return result("natwest.property.agricultural_restriction", "property", RuleStatus.PASS, "Acreage/agricultural restriction criteria do not appear to apply.", section="Acreage/Agricultural restriction", criteria_type="hard_rule", implemented_by="natwest.acreage")
    if case.ltv_percent is None:
        return missing("natwest.property.agricultural_restriction", "property", "LTV is required for agricultural restriction checks.", ["var_property_value", "var_deposit"], section="Acreage/Agricultural restriction", criteria_type="hard_rule", implemented_by="natwest.acreage")
    if case.ltv_percent > 50:
        return result("natwest.property.agricultural_restriction", "property", RuleStatus.FAIL, "NatWest agricultural restriction maximum LTV is 50%.", {"ltv_percent": round(case.ltv_percent, 2), "max_ltv": 50.0}, section="Acreage/Agricultural restriction", criteria_type="hard_rule", implemented_by="natwest.acreage")
    return result("natwest.property.agricultural_restriction", "property", RuleStatus.REFER, "Agricultural restriction is within headline LTV cap but requires employment, valuation and underwriting review.", {"ltv_percent": round(case.ltv_percent, 2)}, section="Acreage/Agricultural restriction", criteria_type="soft_rule", implemented_by="natwest.acreage")


def cladding(case: MortgageCase):
    if case.raw.get("var_property_details_has_ews1_cert") or has_any(case, "cladding", "ews1"):
        return result("natwest.property.cladding", "property", RuleStatus.REFER, "Cladding and EWS1/FRAEW requirements require NatWest valuer/document review.", section="Cladding", criteria_type="evidence_rule", implemented_by="natwest.property")
    return result("natwest.property.cladding", "property", RuleStatus.PASS, "No cladding flag is supplied.", section="Cladding", criteria_type="evidence_rule", implemented_by="natwest.property")


def valuation(case: MortgageCase):
    return result("natwest.property.valuation", "valuation", RuleStatus.REFER, "Valuation, Scottish home reports and property security are NatWest valuer/proprietary processes.", automation_level=AutomationLevel.OUT_OF_SCOPE_PROPRIETARY, section="Valuation", criteria_type="proprietary_rule", implemented_by="natwest.valuation")
