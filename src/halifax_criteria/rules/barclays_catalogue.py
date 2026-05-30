from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from ..models import AutomationLevel, RuleResult, RuleStatus

SOURCE_URL = "https://intermediaries.uk.barclays/home/lending-criteria/residential/"
CRITERIA_VERSION = "2026-05-31"
DEFAULT_SNAPSHOT = Path(__file__).resolve().parents[3] / "data" / "sources" / "barclays_intermediaries_residential_criteria_2026-05-31.html"
DEFAULT_CATALOGUE = Path(__file__).resolve().parents[3] / "data" / "catalogues" / "barclays_residential_criteria_2026-05-31.json"


@dataclass(frozen=True)
class CriteriaStatement:
    section: str
    kind: str
    text: str


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.entries: list[tuple[str, str]] = []
        self.rows: list[str] = []
        self._active_tag: str | None = None
        self._buffer: list[str] = []
        self._in_row = False
        self._cell_buffer: list[str] = []
        self._row_cells: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "svg", "noscript"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "tr":
            self._flush()
            self._in_row = True
            self._row_cells = []
        elif tag in {"td", "th"} and self._in_row:
            self._cell_buffer = []
        elif tag in {"p", "li", "h1", "h2", "h3", "h4"}:
            self._flush()
            self._active_tag = tag

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "svg", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in {"p", "li", "h1", "h2", "h3", "h4"}:
            self._flush()
            self._active_tag = None
        elif tag in {"td", "th"} and self._in_row:
            cell = _clean(" ".join(self._cell_buffer))
            if cell:
                self._row_cells.append(cell)
            self._cell_buffer = []
        elif tag == "tr" and self._in_row:
            row = _clean(" | ".join(self._row_cells))
            if row and len(row) > 8:
                self.rows.append(row)
            self._in_row = False
            self._row_cells = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_row:
            self._cell_buffer.append(data)
        elif self._active_tag:
            self._buffer.append(data)

    def _flush(self) -> None:
        if not self._active_tag or not self._buffer:
            self._buffer = []
            return
        text = _clean(" ".join(self._buffer))
        if len(text) > 8:
            self.entries.append((self._active_tag, text))
        self._buffer = []


def _clean(text: str) -> str:
    text = unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text).strip()


def _slug(text: str, max_len: int = 80) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:max_len].strip("_") or "criteria"


def section_titles(html: str) -> list[str]:
    titles = re.findall(
        r'<span class="m-accordion-item__title aem-accordion-item__long-title">(.*?)</span>',
        html,
        flags=re.S,
    )
    result: list[str] = []
    for title in titles:
        clean = _clean(title)
        if clean and clean not in result:
            result.append(clean)
    return result


def extract_sections(snapshot_path: Path = DEFAULT_SNAPSHOT) -> dict[str, list[CriteriaStatement]]:
    html = snapshot_path.read_text(encoding="utf-8", errors="ignore")
    matches = list(
        re.finditer(
            r'<span class="m-accordion-item__title aem-accordion-item__long-title">(.*?)</span>',
            html,
            flags=re.S,
        )
    )
    sections: dict[str, list[CriteriaStatement]] = {}
    for index, match in enumerate(matches):
        title = _clean(match.group(1))
        if not title:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(html)
        segment = html[match.end() : end]
        parser = _VisibleTextParser()
        parser.feed(segment)
        statements: list[CriteriaStatement] = []
        seen: set[tuple[str, str]] = set()
        for kind, text in parser.entries:
            key = (kind, text)
            if key not in seen and text != title:
                statements.append(CriteriaStatement(title, kind, text))
                seen.add(key)
        for row in parser.rows:
            key = ("table_row", row)
            if key not in seen:
                statements.append(CriteriaStatement(title, "table_row", row))
                seen.add(key)
        sections[title] = statements
    return sections


IMPLEMENTED_BY_SECTION = {
    "Additional borrowing": "barclays.additional_borrowing",
    "Adverse credit history – Residential": "barclays.adverse_credit",
    "Affordability – Residential": "barclays.affordability",
    "Age/Term": "barclays.age_at_end",
    "Commitments – Residential": "barclays.commitments",
    "Deposit": "barclays.deposit",
    "Income multiples": "barclays.income_multiples",
    "Interest-only mortgages - Residential": "barclays.interest_only",
    "Loan to Value (LTV) - Residential": "barclays.ltv",
    "Mixed-use properties - Residential": "barclays.mixed_use",
    "New build properties - Residential": "barclays.new_build",
    "Number of applicants": "barclays.applicant_count",
    "Property types - Residential": "barclays.property_details",
    "Residency - Residential": "barclays.residency",
    "Term of mortgage - Residential": "barclays.term_limit",
}


REQUIRED_FIELDS_BY_SECTION = {
    "Additional borrowing": ["var_mortgage_type", "var_equity_release_amount", "var_repayment_type"],
    "Adverse credit history – Residential": ["ccj/default/bankruptcy/dro/iva/arrears/missed-payment fields"],
    "Affordability – Residential": ["var_property_value", "var_deposit", "var_appl*_gross_annual_salary", "commitment fields"],
    "Age/Term": ["var_appl*_date_of_birth", "var_mortgage_term", "var_repayment_type"],
    "Commitments – Residential": ["var_appl*_credit_commitments", "var_other_properties"],
    "Deposit": ["var_deposit", "var_deposit_source_details"],
    "Income multiples": ["var_property_value", "var_deposit", "var_appl*_gross_annual_salary"],
    "Interest-only mortgages - Residential": ["var_repayment_type", "var_interest_only_amount", "var_property_value", "var_deposit"],
    "Loan to Value (LTV) - Residential": ["var_property_value", "var_deposit", "var_mortgage_type", "property/scheme flags"],
    "Mixed-use properties - Residential": ["var_property_details_property_type", "var_property_details_description", "var_property_value", "var_deposit"],
    "New build properties - Residential": ["var_property_details_description", "var_property_details_property_type", "var_deposit_source_details"],
    "Number of applicants": ["var_no_of_applicants"],
    "Property types - Residential": ["var_property_details_property_type", "var_property_details_description", "var_property_details_tenure"],
    "Residency - Residential": ["var_appl*_nationality", "var_appl*_residency_status"],
    "Term of mortgage - Residential": ["var_mortgage_term", "var_repayment_type"],
}


def _criteria_type(section: str, text: str) -> str:
    lower = f"{section} {text}".lower()
    if any(term in lower for term in ["calculator", "credit score", "underwriter", "disposable income", "valuation", "valuer", "survey"]):
        return "proprietary_rule"
    if any(term in lower for term in ["document", "evidence", "proof", "statement", "certified", "packaging", "verification", "id and address"]):
        return "evidence_rule"
    if any(term in lower for term in ["must", "cannot", "not acceptable", "maximum", "minimum", "limited to", "will be declined", "not allowed"]):
        return "hard_rule"
    if any(term in lower for term in ["may", "can consider", "contact", "refer", "review"]):
        return "soft_rule"
    return "manual_rule"


def _automation_level(criteria_type: str, implemented_by: str | None) -> str:
    if criteria_type == "proprietary_rule":
        return AutomationLevel.OUT_OF_SCOPE_PROPRIETARY.value
    if implemented_by and criteria_type == "hard_rule":
        return AutomationLevel.AUTOMATED.value
    if criteria_type == "evidence_rule":
        return AutomationLevel.INSUFFICIENT_DATA.value
    return AutomationLevel.MANUAL_REFER.value


def build_catalogue(snapshot_path: Path = DEFAULT_SNAPSHOT) -> list[dict[str, Any]]:
    catalogue: list[dict[str, Any]] = []
    sections = extract_sections(snapshot_path)
    for section, statements in sections.items():
        section_slug = _slug(section, 52)
        implemented_by = IMPLEMENTED_BY_SECTION.get(section)
        required_fields = REQUIRED_FIELDS_BY_SECTION.get(section, [])
        for index, statement in enumerate(statements, start=1):
            criteria_type = _criteria_type(section, statement.text)
            catalogue.append(
                {
                    "rule_id": f"barclays.catalogue.{section_slug}.{index:04d}",
                    "lender": "Barclays",
                    "criteria_version": CRITERIA_VERSION,
                    "section": section,
                    "source_url": SOURCE_URL,
                    "source_ref": f"{section} item {index}",
                    "source_text": statement.text,
                    "statement_kind": statement.kind,
                    "criteria_type": criteria_type,
                    "automation_level": _automation_level(criteria_type, implemented_by),
                    "required_fields": required_fields,
                    "implemented_by": implemented_by,
                }
            )
    return catalogue


def write_catalogue(
    snapshot_path: Path = DEFAULT_SNAPSHOT,
    output_path: Path = DEFAULT_CATALOGUE,
) -> list[dict[str, Any]]:
    catalogue = build_catalogue(snapshot_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(catalogue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return catalogue


def load_catalogue(path: Path = DEFAULT_CATALOGUE) -> list[dict[str, Any]]:
    if not path.exists():
        return build_catalogue()
    return json.loads(path.read_text(encoding="utf-8"))


def catalogue_results(path: Path = DEFAULT_CATALOGUE) -> list[RuleResult]:
    results: list[RuleResult] = []
    for item in load_catalogue(path):
        automation = AutomationLevel(item["automation_level"])
        if automation == AutomationLevel.OUT_OF_SCOPE_PROPRIETARY:
            status = RuleStatus.REFER
        elif automation == AutomationLevel.INSUFFICIENT_DATA:
            status = RuleStatus.INSUFFICIENT_DATA
        else:
            status = RuleStatus.REFER
        results.append(
            RuleResult(
                rule_id=item["rule_id"],
                category=_slug(item["section"], 40),
                status=status,
                automation_level=automation,
                severity="manual",
                message=f"Barclays criteria catalogue item requires review: {item['source_text']}",
                source_url=item["source_url"],
                source_ref=item["source_ref"],
                data={"statement_kind": item["statement_kind"]},
                section=item["section"],
                source_text=item["source_text"],
                criteria_type=item["criteria_type"],
                required_fields=item["required_fields"],
                implemented_by=item["implemented_by"],
            )
        )
    return results


if __name__ == "__main__":
    written = write_catalogue()
    print(f"Wrote {len(written)} Barclays criteria catalogue items to {DEFAULT_CATALOGUE}")
