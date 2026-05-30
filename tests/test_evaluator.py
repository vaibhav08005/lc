from __future__ import annotations

from pathlib import Path

from halifax_criteria.evaluator import evaluate_file, overall_result
from halifax_criteria.models import AutomationLevel, RuleResult, RuleStatus
from halifax_criteria.normalizer import normalize
from halifax_criteria.rules import barclays_2026_05
from halifax_criteria.rules.barclays_catalogue import build_catalogue, extract_sections, section_titles
from halifax_criteria.rules.halifax_2026_05 import evaluate_rules
from halifax_criteria.rules.snapshot_catalogue import extract_snapshot_items


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "input.yaml"
SNAPSHOT = ROOT / "data" / "sources" / "halifax_intermediaries_criteria_2026-05-30.html"
BARCLAYS_SNAPSHOT = ROOT / "data" / "sources" / "barclays_intermediaries_residential_criteria_2026-05-31.html"


def sample_case():
    import yaml

    return normalize(yaml.safe_load(SAMPLE.read_text(encoding="utf-8")))


def by_id(results: list[dict], rule_id: str) -> dict:
    return next(rule for rule in results if rule["rule_id"] == rule_id)


def test_sample_case_derivations_and_result():
    report = evaluate_file(SAMPLE)
    assert report["derived"]["loan_amount"] == 200000
    assert report["derived"]["ltv_percent"] == 66.67
    assert report["derived"]["base_gross_annual_income"] == 130000
    assert report["derived"]["base_lti_multiple"] == 1.54
    assert report["derived"]["lti_multiple"] == 1.38
    assert report["overall_result"] in {"INSUFFICIENT_DATA", "REFER"}
    assert "rule_results" not in report
    assert all(rule["status"] in {"FAIL", "REFER"} for rule in report["issues"])
    debug_report = evaluate_file(SAMPLE, include_all_rules=True)
    assert by_id(debug_report["rule_results"], "halifax.ltv.standard_limits")["status"] == "PASS"
    assert by_id(debug_report["rule_results"], "halifax.lti.published_matrix")["status"] == "PASS"
    assert by_id(debug_report["rule_results"], "halifax.term.maximum")["status"] == "PASS"


def test_high_ltv_above_cap_fails():
    case = sample_case()
    raw = dict(case.raw)
    raw["var_property_value"] = 700000
    raw["var_deposit"] = 20000
    results = evaluate_rules(normalize(raw), include_snapshot=False)
    assert next(result for result in results if result.rule_id == "halifax.ltv.standard_limits").status == RuleStatus.FAIL


def test_term_over_40_years_fails():
    case = sample_case()
    raw = dict(case.raw)
    raw["var_mortgage_term"] = 481
    results = evaluate_rules(normalize(raw), include_snapshot=False)
    assert next(result for result in results if result.rule_id == "halifax.term.maximum").status == RuleStatus.FAIL


def test_missing_dob_is_insufficient_data():
    results = evaluate_rules(sample_case(), include_snapshot=False)
    assert next(result for result in results if result.rule_id == "halifax.age.maximum_at_term_end").status == RuleStatus.INSUFFICIENT_DATA


def test_more_than_four_applicants_fails():
    case = sample_case()
    raw = dict(case.raw)
    raw["var_no_of_applicants"] = 5
    results = evaluate_rules(normalize(raw), include_snapshot=False)
    assert next(result for result in results if result.rule_id == "halifax.applicants.count").status == RuleStatus.FAIL


def test_non_uk_without_permanent_residency_refers():
    case = sample_case()
    raw = dict(case.raw)
    raw["var_appl2_residency_status"] = ""
    results = evaluate_rules(normalize(raw), include_snapshot=False)
    assert next(result for result in results if result.rule_id == "halifax.residency.non_uk_nationals").status == RuleStatus.REFER


def test_new_build_flat_cap_fails_above_85_ltv():
    case = sample_case()
    raw = dict(case.raw)
    raw["var_property_value"] = 300000
    raw["var_deposit"] = 30000
    raw["var_property_details_property_type"] = "flat"
    raw["var_property_details_description"] = "new build flat"
    results = evaluate_rules(normalize(raw), include_snapshot=False)
    assert next(result for result in results if result.rule_id == "halifax.property.new_build_caps").status == RuleStatus.FAIL


def test_builder_incentive_cap_fails_when_combined_ltv_too_high():
    case = sample_case()
    raw = dict(case.raw)
    raw["var_deposit"] = 20000
    raw["var_deposit_source_details"] = [{"source": "incentive_builder", "amount": 20000}]
    results = evaluate_rules(normalize(raw), include_snapshot=False)
    assert next(result for result in results if result.rule_id == "halifax.deposit.builder_incentive").status == RuleStatus.FAIL


def test_credit_card_commitment_uses_five_percent_balance():
    results = evaluate_rules(sample_case(), include_snapshot=False)
    rule = next(result for result in results if result.rule_id == "halifax.commitments.credit_cards")
    assert rule.data["adjustments"][0]["used"] == 500


def test_btl_shortfall_creates_refer():
    results = evaluate_rules(sample_case(), include_snapshot=False)
    rule = next(result for result in results if result.rule_id == "halifax.background_mortgages")
    assert rule.status == RuleStatus.REFER
    assert rule.data["monthly_cost"] > 0


def test_worst_rule_wins_ordering():
    results = [
        RuleResult("a", "x", RuleStatus.PASS, AutomationLevel.AUTOMATED, "standard", "ok", "source"),
        RuleResult("b", "x", RuleStatus.REFER, AutomationLevel.MANUAL_REFER, "manual", "manual", "source"),
    ]
    assert overall_result(results) == RuleStatus.REFER
    results.append(RuleResult("c", "x", RuleStatus.INSUFFICIENT_DATA, AutomationLevel.INSUFFICIENT_DATA, "standard", "missing", "source"))
    assert overall_result(results) == RuleStatus.INSUFFICIENT_DATA
    results.append(RuleResult("d", "x", RuleStatus.FAIL, AutomationLevel.AUTOMATED, "hard", "fail", "source"))
    assert overall_result(results) == RuleStatus.FAIL


def test_snapshot_catalogue_integrity():
    items = extract_snapshot_items(SNAPSHOT)
    assert len(items) > 100
    assert len({item.rule_id for item in items}) == len(items)
    assert all(item.category for item in items)
    assert all(item.source_ref for item in items)


def test_barclays_sample_case_runs_with_expected_result_shape():
    report = evaluate_file(SAMPLE, lender="barclays")
    assert report["lender"] == "Barclays"
    assert report["criteria_version"] == "2026-05-31"
    assert report["derived"]["loan_amount"] == 200000
    assert report["derived"]["ltv_percent"] == 66.67
    assert report["derived"]["barclays_selected_ltv_cap"] == 90.0
    assert report["derived"]["barclays_retained_property_count"] == 2
    assert report["overall_result"] in {"INSUFFICIENT_DATA", "REFER"}
    assert report["rule_summary"]["total"] > 100


def test_barclays_high_ltv_loan_size_fails_above_570k():
    case = sample_case()
    raw = dict(case.raw)
    raw["var_property_value"] = 650000
    raw["var_deposit"] = 50000
    raw["var_other_properties"] = []
    results = barclays_2026_05.evaluate_rules(normalize(raw), include_snapshot=False)
    assert next(result for result in results if result.rule_id == "barclays.ltv.high_ltv_loan_size").status == RuleStatus.FAIL


def test_barclays_interest_only_over_75_ltv_fails():
    case = sample_case()
    raw = dict(case.raw)
    raw["var_property_value"] = 300000
    raw["var_deposit"] = 60000
    raw["var_repayment_type"] = "interest_only"
    raw["var_interest_only_amount"] = 240000
    results = barclays_2026_05.evaluate_rules(normalize(raw), include_snapshot=False)
    assert next(result for result in results if result.rule_id == "barclays.ltv.residential_limits").status == RuleStatus.FAIL


def test_barclays_term_under_5_years_fails():
    case = sample_case()
    raw = dict(case.raw)
    raw["var_mortgage_term"] = 48
    results = barclays_2026_05.evaluate_rules(normalize(raw), include_snapshot=False)
    assert next(result for result in results if result.rule_id == "barclays.term.maximum").status == RuleStatus.FAIL


def test_barclays_minimum_income_fails_when_no_applicant_has_25k():
    case = sample_case()
    raw = dict(case.raw)
    raw["var_appl1_gross_annual_salary"] = 20000
    raw["var_appl2_gross_annual_salary"] = 20000
    results = barclays_2026_05.evaluate_rules(normalize(raw), include_snapshot=False)
    assert next(result for result in results if result.rule_id == "barclays.income.minimum").status == RuleStatus.FAIL


def test_barclays_new_build_incentive_above_5_percent_refers():
    case = sample_case()
    raw = dict(case.raw)
    raw["var_property_details_property_type"] = "house"
    raw["var_property_details_description"] = "new build house"
    raw["var_deposit_source_details"] = [{"source": "incentive_builder", "amount": 20000}]
    results = barclays_2026_05.evaluate_rules(normalize(raw), include_snapshot=False)
    assert next(result for result in results if result.rule_id == "barclays.new_build.incentives").status == RuleStatus.REFER


def test_barclays_snapshot_catalogue_integrity():
    html = BARCLAYS_SNAPSHOT.read_text(encoding="utf-8", errors="ignore")
    titles = section_titles(html)
    sections = extract_sections(BARCLAYS_SNAPSHOT)
    assert len(titles) == 60
    assert set(titles) == set(sections)
    assert all(sections[title] for title in titles)


def test_barclays_catalogue_has_required_audit_fields():
    catalogue = build_catalogue(BARCLAYS_SNAPSHOT)
    assert len(catalogue) > 800
    rule_ids = {item["rule_id"] for item in catalogue}
    assert len(rule_ids) == len(catalogue)
    for item in catalogue:
        assert item["lender"] == "Barclays"
        assert item["criteria_version"] == "2026-05-31"
        assert item["section"]
        assert item["source_url"].startswith("https://intermediaries.uk.barclays/")
        assert item["source_ref"]
        assert item["source_text"]
        assert item["criteria_type"] in {"hard_rule", "soft_rule", "evidence_rule", "manual_rule", "proprietary_rule"}
        assert item["automation_level"] in {"AUTOMATED", "MANUAL_REFER", "INSUFFICIENT_DATA", "OUT_OF_SCOPE_PROPRIETARY"}
        assert isinstance(item["required_fields"], list)


def test_barclays_show_all_rules_includes_catalogue_source_text():
    report = evaluate_file(SAMPLE, lender="barclays", include_all_rules=True)
    assert "rule_results" in report
    catalogue_rules = [rule for rule in report["rule_results"] if rule["rule_id"].startswith("barclays.catalogue.")]
    assert catalogue_rules
    assert all(rule["section"] for rule in catalogue_rules[:20])
    assert all(rule["source_text"] for rule in catalogue_rules[:20])


def test_barclays_purchase_standard_ltv_passes_ltv_rule():
    case = sample_case()
    raw = dict(case.raw)
    raw["var_other_properties"] = []
    results = barclays_2026_05.evaluate_rules(normalize(raw), include_snapshot=False)
    assert next(result for result in results if result.rule_id == "barclays.ltv.residential_limits").status == RuleStatus.PASS


def test_barclays_additional_borrowing_over_85_ltv_fails():
    case = sample_case()
    raw = dict(case.raw)
    raw["var_property_value"] = 300000
    raw["var_deposit"] = 30000
    raw["var_equity_release_amount"] = 10000
    raw["var_other_properties"] = []
    results = barclays_2026_05.evaluate_rules(normalize(raw), include_snapshot=False)
    assert next(result for result in results if result.rule_id == "barclays.additional_borrowing").status == RuleStatus.FAIL


def test_barclays_debt_consolidation_over_80_ltv_fails():
    case = sample_case()
    raw = dict(case.raw)
    raw["var_property_value"] = 300000
    raw["var_deposit"] = 45000
    raw["var_mortgage_type"] = "remortgage"
    raw["var_add_borrow_details"] = "debt consolidation"
    raw["var_other_properties"] = []
    results = barclays_2026_05.evaluate_rules(normalize(raw), include_snapshot=False)
    assert next(result for result in results if result.rule_id == "barclays.ltv.residential_limits").status == RuleStatus.FAIL


def test_barclays_applicant_over_max_age_fails():
    case = sample_case()
    raw = dict(case.raw)
    raw["var_appl1_date_of_birth"] = "1950-01-01"
    raw["var_appl2_date_of_birth"] = "1980-01-01"
    results = barclays_2026_05.evaluate_rules(normalize(raw), include_snapshot=False)
    assert next(result for result in results if result.rule_id == "barclays.age.maximum_at_term_end").status == RuleStatus.FAIL


def test_barclays_unsecured_debt_equal_to_income_fails():
    case = sample_case()
    raw = dict(case.raw)
    raw["var_appl1_credit_commitments"] = [{"type": "cards", "current_balance": 150000, "monthly_payment": 1000}]
    results = barclays_2026_05.evaluate_rules(normalize(raw), include_snapshot=False)
    assert next(result for result in results if result.rule_id == "barclays.credit.unsecured_debt_vs_income").status == RuleStatus.FAIL


def test_barclays_shared_ownership_cap_fails():
    case = sample_case()
    raw = dict(case.raw)
    raw["var_property_value"] = 300000
    raw["var_deposit"] = 15000
    raw["var_mortgage_type"] = "shared ownership purchase"
    raw["var_other_properties"] = []
    results = barclays_2026_05.evaluate_rules(normalize(raw), include_snapshot=False)
    assert next(result for result in results if result.rule_id == "barclays.schemes.classification").status == RuleStatus.FAIL


def test_barclays_affordability_is_marked_proprietary():
    results = barclays_2026_05.evaluate_rules(sample_case(), include_snapshot=False)
    rule = next(result for result in results if result.rule_id == "barclays.affordability.proprietary")
    assert rule.status == RuleStatus.REFER
    assert rule.automation_level == AutomationLevel.OUT_OF_SCOPE_PROPRIETARY
