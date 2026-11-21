"""Ground-truth documents: reference Markdown, typed elements, tags and checks.

A ground-truth folder holds, per document id, ``<id>.md`` and/or ``<id>.json``:

* ``<id>.md``   – reference Markdown (used by the original metrics as is).
* ``<id>.json`` – any of::

      {
        "type": "scan",                    # optional, added to tags
        "tags": ["german", "invoice"],     # optional
        "elements": [                      # optional, typed reference content
          {"category": "header", "text": "ACME Corp"},
          {"category": "heading1", "text": "Results"},
          {"category": "paragraph", "text": "..."},
          {"category": "table", "html": "<table>...</table>"}
        ],
        "checks": [ ... ]                  # optional, see evaluator_checks.py
      }

  Elements in DP-Bench's format (``{"category", "content": {"text", "html"}}``)
  are accepted too. Without ``<id>.md`` the reference Markdown is rendered from
  the elements with the same rules opendataloader-bench used for DP-Bench.
  With both, ``<id>.md`` stays the reference text and the elements only say
  which parts of it belong to which category.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from bs4 import BeautifulSoup

from .normalize import Phrase, clean, html_tables, tokens

DEFAULT_OPTIONAL = frozenset({"header", "footer", "figure", "chart"})

_ALIASES = {
    "page_header": "header",
    "page_footer": "footer",
    "page_number": "footer",
    "picture": "figure",
    "image": "figure",
}
_HEADING_CATEGORY = re.compile(r"^(?:heading(\d)?|title)$")


def normalize_category(category: str) -> str:
    key = re.sub(r"[\s\-]+", "_", (category or "").strip().lower())
    return _ALIASES.get(key, key)


@dataclass
class Element:
    category: str
    text: str = ""
    html: str = ""

    @property
    def heading_level(self) -> Optional[int]:
        match = _HEADING_CATEGORY.match(self.category)
        if not match:
            return None
        return int(match.group(1) or 1)


@dataclass
class GroundTruth:
    doc_id: str
    markdown: Optional[str] = None
    elements: Optional[List[Element]] = None
    tags: List[str] = field(default_factory=list)
    checks: List[dict] = field(default_factory=list)

    def optional_phrases(self, optional: Iterable[str]) -> List[Phrase]:
        """Normalized lines of text from elements in ``optional`` categories."""

        if self.elements is None:
            return []
        skip = {normalize_category(c) for c in optional}
        phrases = []
        for element in self.elements:
            if element.category in skip:
                for line in element.text.splitlines():
                    phrase = " ".join(tokens(clean(line)))
                    if phrase:
                        phrases.append(Phrase(phrase, from_end=element.category == "footer"))
        return phrases


def _render_element(element: Element) -> str:
    if element.category == "table":
        if not element.html:
            return ""
        html = element.html.strip()
        if not html.lower().startswith("<table"):
            html = f"<table>{html}</table>"
        return BeautifulSoup(html, "html.parser").prettify()
    text = element.text.strip()
    if not text:
        return ""
    level = element.heading_level
    if level is not None:
        return f"{'#' * level} {text}"
    if element.category == "list":
        return f"- {text}"
    return element.text


def render_markdown(elements: Sequence[Element]) -> str:
    return "\n\n".join(part for part in map(_render_element, elements) if part)


def _parse_element(raw: dict) -> Element:
    content = raw.get("content") if isinstance(raw.get("content"), dict) else raw
    return Element(
        category=normalize_category(raw.get("category", "")),
        text=content.get("text") or "",
        html=content.get("html") or "",
    )


def auto_tags(markdown: Optional[str], elements: Optional[List[Element]]) -> List[str]:
    """Content tags derived from the ground truth, prefixed with ``has:``."""

    found = set()
    if elements is not None:
        categories = {element.category for element in elements}
        if "table" in categories:
            found.add("has:tables")
        if "equation" in categories:
            found.add("has:equations")
        if categories & {"figure", "chart"}:
            found.add("has:figures")
        if categories & {"header", "footer"}:
            found.add("has:headers_footers")
        if any(element.heading_level for element in elements):
            found.add("has:headings")
    elif markdown:
        if html_tables(markdown):
            found.add("has:tables")
        if re.search(r"^#{1,6}\s", markdown, re.MULTILINE):
            found.add("has:headings")
    return sorted(found)


def load_document(doc_id: str, md_path: Optional[Path], json_path: Optional[Path]) -> GroundTruth:
    markdown = md_path.read_text(encoding="utf-8") if md_path else None
    data = json.loads(json_path.read_text(encoding="utf-8")) if json_path else {}

    elements = None
    if "elements" in data:
        elements = [_parse_element(raw) for raw in data["elements"]]
        if markdown is None:
            markdown = render_markdown(elements)

    tags = list(data.get("tags", []))
    if data.get("type"):
        tags.insert(0, str(data["type"]))
    tags += [tag for tag in auto_tags(markdown, elements) if tag not in tags]

    return GroundTruth(
        doc_id=doc_id,
        markdown=markdown,
        elements=elements,
        tags=tags,
        checks=list(data.get("checks", [])),
    )


def load_ground_truth(gt_dir: Path) -> List[GroundTruth]:
    """Load every document in ``gt_dir`` (``<id>.md`` and/or ``<id>.json``)."""

    ids = sorted(
        {path.stem for path in gt_dir.glob("*.md")}
        | {path.stem for path in gt_dir.glob("*.json")}
    )
    documents = []
    for doc_id in ids:
        md_path = gt_dir / f"{doc_id}.md"
        json_path = gt_dir / f"{doc_id}.json"
        documents.append(
            load_document(
                doc_id,
                md_path if md_path.is_file() else None,
                json_path if json_path.is_file() else None,
            )
        )
    return documents


def split_reference_json(reference_path: Path, out_dir: Path) -> int:
    """Split a DP-Bench style ``reference.json`` into one ``<id>.json`` per document."""

    data = json.loads(reference_path.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in data.items():
        elements = [
            {
                "category": raw.get("category", ""),
                "text": raw.get("content", {}).get("text") or "",
                "html": raw.get("content", {}).get("html") or "",
            }
            for raw in content.get("elements", [])
        ]
        payload = {"elements": [{k: v for k, v in e.items() if v} for e in elements]}
        (out_dir / f"{Path(filename).stem}.json").write_text(
            json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8"
        )
    return len(data)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        sys.exit("usage: python -m pdf_eval.ground_truth REFERENCE_JSON OUT_DIR")
    count = split_reference_json(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"wrote {count} documents to {sys.argv[2]}")
