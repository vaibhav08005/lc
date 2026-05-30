from __future__ import annotations

from pathlib import Path
from typing import Any

from .input_loader import load_yaml
from .models import MortgageCase, RuleResult, RuleStatus
from .normalizer import normalize


def _rule_pack(lender: str):
    normalized = lender.strip().lower()
    if normalized == "halifax":
        from .rules import halifax_2026_05 as pack

        return {
            "lender": "Halifax",
            "criteria_version": pack.CRITERIA_VERSION,
            "source_url": "https://www.halifax-intermediaries.co.uk/criteria.html",
            "evaluate_rules": pack.evaluate_rules,
            "extra_derived": lambda case: {},
        }
    if normalized == "barclays":
        from .rules import barclays_2026_05 as pack

        return {
            "lender": "Barclays",
            "criteria_version": pack.CRITERIA_VERSION,
            "source_url": pack.SOURCE_URL,
            "evaluate_rules": pack.evaluate_rules,
            "extra_derived": pack.extra_derived,
        }
    raise ValueError(f"Unsupported lender '{lender}'. Supported lenders: halifax, barclays")


def overall_result(results: list[RuleResult]) -> RuleStatus:
    statuses = [result.status for result in results]
    if RuleStatus.FAIL in statuses:
        return RuleStatus.FAIL
    if RuleStatus.INSUFFICIENT_DATA in statuses:
        return RuleStatus.INSUFFICIENT_DATA
    if RuleStatus.REFER in statuses:
        return RuleStatus.REFER
    return RuleStatus.PASS


def derived(case: MortgageCase) -> dict[str, Any]:
    base_lti = case.loan_amount / case.base_gross_annual_income if case.loan_amount is not None and case.base_gross_annual_income else None
    core_lti = case.loan_amount / case.core_annual_income if case.loan_amount is not None and case.core_annual_income else None
    return {
        "loan_amount": case.loan_amount,
        "property_value": case.property_value,
        "deposit": case.deposit,
        "ltv_percent": round(case.ltv_percent, 2) if case.ltv_percent is not None else None,
        "gross_annual_income": case.gross_annual_income,
        "base_gross_annual_income": case.base_gross_annual_income,
        "core_annual_income": case.core_annual_income,
        "base_lti_multiple": round(base_lti, 2) if base_lti is not None else None,
        "core_lti_multiple": round(core_lti, 2) if core_lti is not None else None,
        "lti_multiple": round(case.lti_multiple, 2) if case.lti_multiple is not None else None,
        "mortgage_term_months": case.mortgage_term_months,
        "mortgage_term_years": case.mortgage_term_years,
        "applicant_count": case.no_of_applicants,
    }


def _collect_missing(results: list[RuleResult]) -> list[str]:
    missing: list[str] = []
    for result in results:
        for field in result.data.get("missing_fields", []):
            if field not in missing:
                missing.append(field)
    return missing


def _issue_results(results: list[RuleResult]) -> list[dict[str, Any]]:
    return [
        result.to_dict()
        for result in results
        if result.status in {RuleStatus.FAIL, RuleStatus.REFER}
    ]


def evaluate_file(
    path: str | Path,
    include_snapshot: bool = True,
    include_all_rules: bool = False,
    lender: str = "halifax",
) -> dict[str, Any]:
    raw = load_yaml(path)
    case = normalize(raw)
    pack = _rule_pack(lender)
    results = pack["evaluate_rules"](case, include_snapshot=include_snapshot)
    overall = overall_result(results)
    report = {
        "lender": pack["lender"],
        "criteria_version": pack["criteria_version"],
        "source_url": pack["source_url"],
        "overall_result": overall.value,
        "derived": {**derived(case), **pack["extra_derived"](case)},
        "rule_summary": {
            "total": len(results),
            "pass": sum(result.status == RuleStatus.PASS for result in results),
            "fail": sum(result.status == RuleStatus.FAIL for result in results),
            "refer": sum(result.status == RuleStatus.REFER for result in results),
            "insufficient_data": sum(result.status == RuleStatus.INSUFFICIENT_DATA for result in results),
        },
        "missing_fields": _collect_missing(results),
        "issues": _issue_results(results),
    }
    if include_all_rules:
        report["rule_results"] = [result.to_dict() for result in results]
    return report
