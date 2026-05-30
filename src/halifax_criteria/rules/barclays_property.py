from __future__ import annotations

from ..models import MortgageCase, RuleStatus
from .barclays_common import case_text, missing, result


def deposit(case: MortgageCase):
    if case.deposit is None:
        return missing("barclays.deposit.source", "deposit", "Deposit amount is required.", ["var_deposit"], section="Deposit", criteria_type="evidence_rule", implemented_by="barclays.deposit")
    if not case.deposit_sources:
        return missing("barclays.deposit.source", "deposit", "Deposit source details are required.", ["var_deposit_source_details"], section="Deposit", criteria_type="evidence_rule", implemented_by="barclays.deposit")
    manual = []
    for source in case.deposit_sources:
        source_type = str(source.get("source", "")).lower()
        if any(token in source_type for token in ["crypto", "loan", "incentive", "gift"]):
            manual.append(source_type)
    if manual:
        return result("barclays.deposit.source", "deposit", RuleStatus.REFER, "Deposit source requires Barclays evidence/manual criteria checks.", {"sources": sorted(set(manual))}, section="Deposit", criteria_type="evidence_rule", implemented_by="barclays.deposit")
    return result("barclays.deposit.source", "deposit", RuleStatus.PASS, "Deposit source does not show an obvious Barclays pre-screen issue.", section="Deposit", criteria_type="evidence_rule", implemented_by="barclays.deposit")


def new_build_incentives(case: MortgageCase):
    incentive = sum(float(item.get("amount") or 0) for item in case.deposit_sources if str(item.get("source", "")).lower() in {"incentive_builder", "builder_incentive"})
    text = case_text(case)
    if incentive <= 0:
        return result("barclays.new_build.incentives", "property", RuleStatus.PASS, "No builder incentive is supplied.", section="New build properties - Residential", criteria_type="hard_rule", implemented_by="barclays.new_build")
    if case.property_value is None:
        return missing("barclays.new_build.incentives", "property", "Property value is required for Barclays new-build incentive treatment.", ["var_property_value"], section="New build properties - Residential", criteria_type="hard_rule", implemented_by="barclays.new_build")
    incentive_percent = (incentive / case.property_value) * 100
    if "new" not in text and "build" not in text:
        return result("barclays.new_build.incentives", "property", RuleStatus.REFER, "Builder incentive is supplied but property is not clearly marked as new build.", {"incentive_percent": round(incentive_percent, 2)}, section="New build properties - Residential", criteria_type="hard_rule", implemented_by="barclays.new_build")
    if incentive_percent > 5:
        return result("barclays.new_build.incentives", "property", RuleStatus.REFER, "Barclays deducts financial incentives above 5% from value for maximum loan calculations.", {"incentive_percent": round(incentive_percent, 2)}, section="New build properties - Residential", criteria_type="hard_rule", implemented_by="barclays.new_build")
    return result("barclays.new_build.incentives", "property", RuleStatus.PASS, "New-build financial incentive is within the 5% threshold.", {"incentive_percent": round(incentive_percent, 2)}, section="New build properties - Residential", criteria_type="hard_rule", implemented_by="barclays.new_build")


def property_details(case: MortgageCase):
    missing_fields = [
        field
        for field, value in {
            "var_property_details_property_type": case.property_type,
            "var_property_details_description": case.property_description,
            "var_property_details_tenure": case.property_tenure,
            "var_property_details_construction_material": case.construction_material,
        }.items()
        if not value
    ]
    if missing_fields:
        return missing("barclays.property.acceptability", "property", "Property details are required for Barclays property acceptability checks.", missing_fields, section="Property types - Residential", criteria_type="hard_rule", implemented_by="barclays.property_details")
    text = case_text(case)
    if "mixed" in text and case.ltv_percent and case.ltv_percent > 80:
        return result("barclays.property.acceptability", "property", RuleStatus.FAIL, "Mixed-use properties are limited to 80% LTV by Barclays.", {"ltv_percent": round(case.ltv_percent, 2)}, section="Mixed-use properties - Residential", criteria_type="hard_rule", implemented_by="barclays.property_details")
    return result("barclays.property.acceptability", "property", RuleStatus.REFER, "Property details are supplied but Barclays valuation/security acceptability remains a manual check.", section="Property types - Residential", criteria_type="manual_rule", implemented_by="barclays.property_details")


def leasehold(case: MortgageCase):
    if case.property_tenure != "leasehold":
        return result("barclays.property.leasehold", "property", RuleStatus.PASS, "Leasehold criteria do not appear to apply.", section="Leasehold", criteria_type="hard_rule", implemented_by="barclays.leasehold")
    if not case.leasehold_term:
        return missing("barclays.property.leasehold", "property", "Leasehold term is required for Barclays leasehold checks.", ["var_property_details_leasehold_term"], section="Leasehold", criteria_type="hard_rule", implemented_by="barclays.leasehold")
    return result("barclays.property.leasehold", "property", RuleStatus.REFER, "Leasehold term is supplied but Barclays leasehold acceptability needs detailed criteria/manual review.", {"leasehold_term": case.leasehold_term}, section="Leasehold", criteria_type="hard_rule", implemented_by="barclays.leasehold")


def cladding(case: MortgageCase):
    if "ews" in case.raw or "cladding" in case_text(case):
        return result("barclays.property.cladding", "property", RuleStatus.REFER, "Cladding/Building Safety Act criteria require documentation and property review.", section="Cladding/The Building Safety Act 2022", criteria_type="evidence_rule", implemented_by="barclays.cladding")
    return result("barclays.property.cladding", "property", RuleStatus.PASS, "No cladding flag is supplied.", section="Cladding/The Building Safety Act 2022", criteria_type="evidence_rule", implemented_by="barclays.cladding")


def valuations(case: MortgageCase):
    return result("barclays.property.valuations", "valuation", RuleStatus.REFER, "Valuation outcome, appeals, Scottish valuations and property security are manual/proprietary Barclays processes.", section="Valuations - Residential", criteria_type="proprietary_rule", implemented_by="barclays.valuations")
