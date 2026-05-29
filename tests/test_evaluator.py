from __future__ import annotations

from pathlib import Path

from halifax_criteria.evaluator import evaluate_file, overall_result
from halifax_criteria.models import AutomationLevel, RuleResult, RuleStatus
from halifax_criteria.normalizer import normalize
from halifax_criteria.rules.halifax_2026_05 import evaluate_rules
from halifax_criteria.rules.snapshot_catalogue import extract_snapshot_items


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "input.yaml"
SNAPSHOT = ROOT / "data" / "sources" / "halifax_intermediaries_criteria_2026-05-30.html"


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
