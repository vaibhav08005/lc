from __future__ import annotations

from ..models import MortgageCase, RuleStatus
from .barclays_common import missing, result


def applicant_count(case: MortgageCase):
    if not case.no_of_applicants:
        return missing("barclays.applicants.count", "applicant", "Number of applicants is required.", ["var_no_of_applicants"], section="Number of applicants", criteria_type="hard_rule", implemented_by="barclays.applicant_count")
    if case.no_of_applicants > 4:
        return result("barclays.applicants.count", "applicant", RuleStatus.FAIL, "Barclays permits a maximum of 4 applicants.", section="Number of applicants", criteria_type="hard_rule", implemented_by="barclays.applicant_count")
    if case.no_of_applicants > 2:
        return result("barclays.applicants.count", "applicant", RuleStatus.REFER, "Applicant count is allowed, but Barclays only considers a maximum of two applicant incomes.", {"applicant_count": case.no_of_applicants}, section="Number of applicants", criteria_type="hard_rule", implemented_by="barclays.applicant_count")
    return result("barclays.applicants.count", "applicant", RuleStatus.PASS, "Applicant count is within Barclays limits.", section="Number of applicants", criteria_type="hard_rule", implemented_by="barclays.applicant_count")


def residency(case: MortgageCase):
    missing_fields: list[str] = []
    referrals: list[str] = []
    for app in case.applicants:
        if not app.nationality:
            missing_fields.append(f"var_appl{app.index}_nationality")
        elif app.nationality in {"british", "uk", "united kingdom"}:
            continue
        elif app.residency_status in {"indefinite_leave_to_remain", "settled_status", "permanent_residence"}:
            continue
        else:
            referrals.append(f"applicant {app.index} is non-UK without permanent residence status captured")
    if missing_fields:
        return missing("barclays.residency.non_uk", "residency", "Nationality/residency fields are required.", missing_fields, section="Residency - Residential", criteria_type="hard_rule", implemented_by="barclays.residency")
    if referrals:
        return result("barclays.residency.non_uk", "residency", RuleStatus.REFER, "Non-UK national criteria require manual Barclays review: " + "; ".join(referrals), {"referrals": referrals}, section="Residency - Residential", criteria_type="hard_rule", implemented_by="barclays.residency")
    return result("barclays.residency.non_uk", "residency", RuleStatus.PASS, "Applicant nationality/residency meets the basic Barclays screen.", section="Residency - Residential", criteria_type="hard_rule", implemented_by="barclays.residency")
