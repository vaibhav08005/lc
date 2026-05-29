from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from re import sub
from typing import Iterable

from ..models import AutomationLevel, RuleResult, RuleStatus


SOURCE_URL = "https://www.halifax-intermediaries.co.uk/criteria.html"


@dataclass(frozen=True)
class SnapshotItem:
    rule_id: str
    category: str
    text: str
    source_ref: str


class _CriteriaTextParser(HTMLParser):
    visible_tags = {"h1", "h2", "h3", "h4", "p", "li", "td", "th"}
    skip_tags = {"script", "style", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__()
        self._tag_stack: list[str] = []
        self._buffer: list[str] = []
        self._active_tag: str | None = None
        self.entries: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._tag_stack.append(tag)
        if tag in self.visible_tags:
            self._flush()
            self._active_tag = tag

    def handle_endtag(self, tag: str) -> None:
        if tag in self.visible_tags:
            self._flush()
            self._active_tag = None
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()

    def handle_data(self, data: str) -> None:
        if any(tag in self.skip_tags for tag in self._tag_stack):
            return
        if self._active_tag:
            self._buffer.append(data)

    def _flush(self) -> None:
        if not self._active_tag or not self._buffer:
            self._buffer.clear()
            return
        text = sub(r"\s+", " ", " ".join(self._buffer)).strip()
        self._buffer.clear()
        if len(text) >= 8 and not text.startswith("."):
            self.entries.append((self._active_tag, text))


def _slug(text: str, max_len: int = 52) -> str:
    slug = sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:max_len].strip("_") or "criteria_item"


def extract_snapshot_items(snapshot_path: Path) -> list[SnapshotItem]:
    html = snapshot_path.read_text(encoding="utf-8", errors="ignore")
    parser = _CriteriaTextParser()
    parser.feed(html)
    items: list[SnapshotItem] = []
    current_category = "general"
    started = False
    for tag, text in parser.entries:
        lower = text.lower()
        if lower == "mortgage lending criteria":
            started = True
        if not started:
            continue
        if lower.startswith(("contact us", "sign in", "register")):
            continue
        if tag in {"h2", "h3", "h4"}:
            current_category = _slug(text, 40)
        index = len(items) + 1
        items.append(
            SnapshotItem(
                rule_id=f"halifax.snapshot.{index:04d}.{_slug(text)}",
                category=current_category,
                text=text,
                source_ref=f"snapshot item {index}",
            )
        )
    return items


def snapshot_results(snapshot_path: Path, automated_rule_ids: Iterable[str]) -> list[RuleResult]:
    automated = set(automated_rule_ids)
    results: list[RuleResult] = []
    for item in extract_snapshot_items(snapshot_path):
        if item.rule_id in automated:
            continue
        results.append(
            RuleResult(
                rule_id=item.rule_id,
                category=item.category,
                status=RuleStatus.REFER,
                automation_level=AutomationLevel.MANUAL_REFER,
                severity="manual",
                message=f"Halifax criteria catalogue item requires manual consideration: {item.text}",
                source_url=SOURCE_URL,
                source_ref=item.source_ref,
            )
        )
    return results
