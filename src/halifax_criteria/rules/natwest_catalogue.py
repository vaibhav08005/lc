from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from ..models import AutomationLevel, RuleResult, RuleStatus

SOURCE_URL = "https://www.intermediary.natwest.com/lending-criteria.html"
CRITERIA_VERSION = "2026-05-31"
SOURCE_DIR = Path(__file__).resolve().parents[3] / "data" / "sources"
DEFAULT_SNAPSHOT = SOURCE_DIR / "natwest_intermediary_lending_criteria_2026-05-31.html"
DEFAULT_CATALOGUE = Path(__file__).resolve().parents[3] / "data" / "catalogues" / "natwest_lending_criteria_2026-05-31.json"


@dataclass(frozen=True)
class CriteriaStatement:
    source_file: str
    source_url: str
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
        if tag in {"script", "style", "svg", "noscript", "header", "footer", "nav"}:
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
        if tag in {"script", "style", "svg", "noscript", "header", "footer", "nav"} and self._skip_depth:
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
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _slug(text: str, max_len: int = 80) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:max_len].strip("_") or "criteria"


def _source_url(path: Path) -> str:
    if path.name == DEFAULT_SNAPSHOT.name:
        return SOURCE_URL
    slug = path.name.removeprefix("natwest_").removesuffix("_2026-05-31.html")
    page = slug.replace("_html", ".html").replace("_", "-")
    if page.startswith("intermediary-solutions-"):
        page = page.replace("intermediary-solutions-", "intermediary-solutions/", 1)
    return f"https://www.intermediary.natwest.com/{page}"


def _heading_matches(html: str, tags: str = "h1|h2|h3") -> list[re.Match[str]]:
    return list(re.finditer(rf"<(?P<tag>{tags})\b[^>]*>(?P<text>.*?)</(?P=tag)>", html, flags=re.S | re.I))


def _heading_text(match: re.Match[str]) -> str:
    return _clean(match.group("text"))


def _is_navigation_heading(text: str) -> bool:
    if not text:
        return True
    lower = text.lower()
    if lower in {"only for use by mortgage intermediaries", "a -z lending criteria", "a-z lending criteria"}:
        return True
    if re.match(r"^lending criteria(?:\s*-?\s*[a-z](?:/[a-z])*(?: continued)?)?$", lower):
        return True
    if lower in {"products", "criteria", "calculators", "placing business", "help and contacts", "menu close"}:
        return True
    return False


def section_titles(html: str) -> list[str]:
    titles: list[str] = []
    for match in _heading_matches(html, "h3"):
        text = _heading_text(match)
        if not _is_navigation_heading(text) and text not in titles:
            titles.append(text)
    return titles


def _statements_from_segment(source_file: str, url: str, section: str, segment: str) -> list[CriteriaStatement]:
    parser = _VisibleTextParser()
    parser.feed(segment)
    statements: list[CriteriaStatement] = []
    seen: set[tuple[str, str]] = set()
    for kind, text in parser.entries:
        if text == section or _is_navigation_heading(text):
            continue
        key = (kind, text)
        if key not in seen:
            statements.append(CriteriaStatement(source_file, url, section, kind, text))
            seen.add(key)
    for row in parser.rows:
        key = ("table_row", row)
        if key not in seen:
            statements.append(CriteriaStatement(source_file, url, section, "table_row", row))
            seen.add(key)
    if not statements:
        statements.append(CriteriaStatement(source_file, url, section, "heading", section))
    return statements


def extract_main_sections(snapshot_path: Path = DEFAULT_SNAPSHOT) -> dict[str, list[CriteriaStatement]]:
    html = snapshot_path.read_text(encoding="utf-8", errors="ignore")
    matches = _heading_matches(html, "h3")
    sections: dict[str, list[CriteriaStatement]] = {}
    url = _source_url(snapshot_path)
    for index, match in enumerate(matches):
        title = _heading_text(match)
        if _is_navigation_heading(title):
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(html)
        segment = html[match.end() : end]
        sections[title] = _statements_from_segment(snapshot_path.name, url, title, segment)
    return sections


def extract_linked_sections(source_dir: Path = SOURCE_DIR) -> dict[str, list[CriteriaStatement]]:
    sections: dict[str, list[CriteriaStatement]] = {}
    for path in sorted(source_dir.glob("natwest_*_2026-05-31.html")):
        if path.name in {DEFAULT_SNAPSHOT.name, "natwest_intermediary_solutions_lending_criteria_html_2026-05-31.html"}:
            continue
        html = path.read_text(encoding="utf-8", errors="ignore")
        matches = _heading_matches(html, "h1|h2|h3")
        url = _source_url(path)
        for index, match in enumerate(matches):
            title = _heading_text(match)
            if _is_navigation_heading(title):
                continue
            end = matches[index + 1].start() if index + 1 < len(matches) else len(html)
            segment = html[match.end() : end]
            key = f"{title} [{path.stem}]"
            statements = _statements_from_segment(path.name, url, title, segment)
            if statements:
                sections[key] = statements
    return sections


IMPLEMENTED_BY_KEYWORDS = {
    "additional borrowing": "natwest.additional_borrowing",
    "adverse credit": "natwest.adverse_credit",
    "affordability": "natwest.affordability",
    "age requirements": "natwest.age",
    "applicants": "natwest.applicant_count",
    "foreign nationals": "natwest.residency",
    "interest only": "natwest.interest_only",
    "loan to income": "natwest.loan_to_income",
    "lending limits": "natwest.ltv",
    "maximum ltv": "natwest.ltv",
    "term": "natwest.term",
    "background buy to lets": "natwest.background_btl",
    "financial commitments": "natwest.commitments",
    "acreage": "natwest.acreage",
    "agricultural": "natwest.acreage",
    "valuation": "natwest.valuation",
    "property": "natwest.property",
    "deposit": "natwest.deposit",
    "shared ownership": "natwest.schemes",
    "shared equity": "natwest.schemes",
    "right to buy": "natwest.schemes",
}


REQUIRED_FIELDS_BY_KEYWORD = {
    "additional borrowing": ["var_add_borrow_details", "var_equity_release_amount"],
    "adverse credit": ["adverse-credit declaration fields"],
    "age requirements": ["var_appl*_date_of_birth", "var_mortgage_term", "var_repayment_type"],
    "applicants": ["var_no_of_applicants"],
    "foreign nationals": ["var_appl*_nationality", "var_appl*_residency_status"],
    "interest only": ["var_repayment_type", "var_interest_only_amount", "var_property_value", "var_deposit"],
    "loan to income": ["var_property_value", "var_deposit", "var_appl*_gross_annual_salary"],
    "lending limits": ["var_property_value", "var_deposit"],
    "maximum ltv": ["var_property_value", "var_deposit"],
    "term": ["var_mortgage_term"],
    "background buy to lets": ["var_other_properties"],
    "financial commitments": ["commitment fields"],
    "deposit": ["var_deposit", "var_deposit_source_details"],
    "property": ["var_property_details_property_type", "var_property_details_description", "var_property_details_tenure"],
}


def _implemented_by(section: str) -> str | None:
    lower = section.lower()
    for keyword, rule in IMPLEMENTED_BY_KEYWORDS.items():
        if keyword in lower:
            return rule
    return None


def _required_fields(section: str) -> list[str]:
    lower = section.lower()
    fields: list[str] = []
    for keyword, values in REQUIRED_FIELDS_BY_KEYWORD.items():
        if keyword in lower:
            fields.extend(values)
    return sorted(set(fields))


def _criteria_type(section: str, text: str) -> str:
    lower = f"{section} {text}".lower()
    if any(term in lower for term in ["calculator", "credit score", "credit scoring", "valuer", "valuation", "underwriter", "underwriting", "professional opinion"]):
        return "proprietary_rule"
    if any(term in lower for term in ["document", "evidence", "proof", "statement", "certification", "packaging", "identification", "solicitor"]):
        return "evidence_rule"
    if any(term in lower for term in ["must", "can't", "cannot", "not allowed", "unable to accept", "maximum", "minimum", "restricted", "not acceptable", "will be declined"]):
        return "hard_rule"
    if any(term in lower for term in ["may", "can consider", "subject to", "refer", "review"]):
        return "soft_rule"
    return "manual_rule"


def _automation_level(criteria_type: str, implemented_by: str | None) -> str:
    if criteria_type == "proprietary_rule":
        return AutomationLevel.OUT_OF_SCOPE_PROPRIETARY.value
    if criteria_type == "evidence_rule":
        return AutomationLevel.INSUFFICIENT_DATA.value
    if implemented_by and criteria_type == "hard_rule":
        return AutomationLevel.AUTOMATED.value
    return AutomationLevel.MANUAL_REFER.value


def build_catalogue(snapshot_path: Path = DEFAULT_SNAPSHOT, source_dir: Path = SOURCE_DIR) -> list[dict[str, Any]]:
    grouped_sections = extract_main_sections(snapshot_path)
    grouped_sections.update(extract_linked_sections(source_dir))
    catalogue: list[dict[str, Any]] = []
    for section_key, statements in grouped_sections.items():
        for statement in statements:
            index = len(catalogue) + 1
            section = statement.section
            criteria_type = _criteria_type(section, statement.text)
            implemented_by = _implemented_by(section)
            catalogue.append(
                {
                    "rule_id": f"natwest.catalogue.{_slug(statement.source_file.removesuffix('.html'), 38)}.{_slug(section, 42)}.{index:04d}",
                    "lender": "NatWest",
                    "criteria_version": CRITERIA_VERSION,
                    "section": section,
                    "source_url": statement.source_url,
                    "source_ref": f"{section} item {index}",
                    "source_text": statement.text,
                    "statement_kind": statement.kind,
                    "criteria_type": criteria_type,
                    "automation_level": _automation_level(criteria_type, implemented_by),
                    "required_fields": _required_fields(section),
                    "implemented_by": implemented_by,
                }
            )
    return catalogue


def write_catalogue(snapshot_path: Path = DEFAULT_SNAPSHOT, output_path: Path = DEFAULT_CATALOGUE) -> list[dict[str, Any]]:
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
        status = RuleStatus.INSUFFICIENT_DATA if automation == AutomationLevel.INSUFFICIENT_DATA else RuleStatus.REFER
        results.append(
            RuleResult(
                rule_id=item["rule_id"],
                category=_slug(item["section"], 40),
                status=status,
                automation_level=automation,
                severity="manual",
                message=f"NatWest criteria catalogue item requires review: {item['source_text']}",
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
    main_sections = extract_main_sections()
    linked_sources = {item["source_url"] for item in written if item["source_url"] != SOURCE_URL}
    print(f"Wrote {len(written)} NatWest criteria catalogue items to {DEFAULT_CATALOGUE}")
    print(f"Main A-Z sections: {len(main_sections)}")
    print(f"Linked NatWest source pages: {len(linked_sources)}")
