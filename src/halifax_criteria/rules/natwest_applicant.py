from __future__ import annotations

from ..models import MortgageCase, RuleStatus
from .natwest_common import applicant_current_ages, applicant_end_ages, is_interest_only, missing, result


def applicant_count(case: MortgageCase):
    if not case.no_of_applicants:
        return missing("natwest.applicants.count", "applicant", "Number of applicants is required.", ["var_no_of_applicants"], section="Applicants (number of)", criteria_type="hard_rule", implemented_by="natwest.applicant_count")
    if case.no_of_applicants > 2:
        return result("natwest.applicants.count", "applicant", RuleStatus.FAIL, "NatWest maximum number of applicants is two.", {"applicant_count": case.no_of_applicants}, section="Applicants (number of)", criteria_type="hard_rule", implemented_by="natwest.applicant_count")
    return result("natwest.applicants.count", "applicant", RuleStatus.PASS, "Applicant count is within NatWest limit.", {"applicant_count": case.no_of_applicants}, section="Applicants (number of)", criteria_type="hard_rule", implemented_by="natwest.applicant_count")


def minimum_age(case: MortgageCase):
    ages, missing_fields = applicant_current_ages(case)
    if missing_fields:
        return missing("natwest.age.minimum", "age", "Applicant date of birth is required for NatWest minimum-age checks.", missing_fields, section="Age Requirements", criteria_type="hard_rule", implemented_by="natwest.age")
    underage = [name for name, age in ages.items() if age < 18]
    if underage:
        return result("natwest.age.minimum", "age", RuleStatus.FAIL, "NatWest applicants must be at least 18 at application.", {"current_ages": ages}, section="Age Requirements", criteria_type="hard_rule", implemented_by="natwest.age")
    return result("natwest.age.minimum", "age", RuleStatus.PASS, "Applicants meet NatWest minimum age requirement.", {"current_ages": ages}, section="Age Requirements", criteria_type="hard_rule", implemented_by="natwest.age")


def age_at_term_end(case: MortgageCase):
    ages, missing_fields = applicant_end_ages(case)
    if missing_fields:
        return missing("natwest.age.maximum_at_term_end", "age", "Date of birth and mortgage term are required for NatWest age-at-term-end checks.", missing_fields, section="Age Requirements", criteria_type="hard_rule", implemented_by="natwest.age")
    max_age = 70 if is_interest_only(case) else 75
    too_old = [name for name, age in ages.items() if age > max_age]
    if too_old:
        return result("natwest.age.maximum_at_term_end", "age", RuleStatus.FAIL, f"Applicant age at term end exceeds NatWest residential maximum age {max_age}.", {"end_ages": ages, "max_age": max_age}, section="Age Requirements", criteria_type="hard_rule", implemented_by="natwest.age")
    return result("natwest.age.maximum_at_term_end", "age", RuleStatus.PASS, f"Applicant age at term end is within NatWest residential maximum age {max_age}.", {"end_ages": ages, "max_age": max_age}, section="Age Requirements", criteria_type="hard_rule", implemented_by="natwest.age")


def residency(case: MortgageCase):
    missing_fields = [f"var_appl{app.index}_nationality" for app in case.applicants if not app.nationality]
    if missing_fields:
        return missing("natwest.residency.foreign_nationals", "residency", "Nationality fields are required for NatWest residency checks.", missing_fields, section="Foreign nationals", criteria_type="hard_rule", implemented_by="natwest.residency")
    referrals: list[str] = []
    for app in case.applicants:
        nationality = app.nationality or ""
        status = app.residency_status or ""
        if nationality not in {"british", "uk", "united kingdom"}:
            referrals.append(f"applicant {app.index} nationality/residency requires foreign national review")
            if status and "permanent" not in status and case.ltv_percent and case.ltv_percent > 75:
                return result("natwest.residency.foreign_nationals", "residency", RuleStatus.FAIL, "NatWest caps customers without permanent right to reside at 75% LTV.", {"ltv_percent": round(case.ltv_percent, 2), "applicant": app.index}, section="Foreign nationals", criteria_type="hard_rule", implemented_by="natwest.residency")
            if status and "permanent" not in status and is_interest_only(case):
                return result("natwest.residency.foreign_nationals", "residency", RuleStatus.FAIL, "NatWest does not allow interest only for customers without permanent right to reside.", {"applicant": app.index}, section="Foreign nationals", criteria_type="hard_rule", implemented_by="natwest.residency")
    if referrals:
        return result("natwest.residency.foreign_nationals", "residency", RuleStatus.REFER, "Foreign national/residency criteria require manual NatWest review.", {"referrals": referrals}, section="Foreign nationals", criteria_type="hard_rule", implemented_by="natwest.residency")
    return result("natwest.residency.foreign_nationals", "residency", RuleStatus.PASS, "Supplied nationality fields do not trigger NatWest foreign-national restrictions.", section="Foreign nationals", criteria_type="hard_rule", implemented_by="natwest.residency")
