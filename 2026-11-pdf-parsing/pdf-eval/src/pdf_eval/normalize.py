"""Turn Markdown/HTML parser output into comparable plain text and tokens.

Both ground truth and prediction go through the same steps, so formatting
choices (bold, links, HTML vs Markdown tables, ligatures, words hyphenated
across line breaks) do not count as content errors.
"""

from __future__ import annotations

import re
import unicodedata
from html import unescape
from typing import List, NamedTuple, Optional, Sequence

from bs4 import BeautifulSoup

from .converter_markdown_table import convert_to_markdown_with_html_tables

_PUNCT_MAP = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u00ad": "",
    }
)

_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_HTML_TABLE = re.compile(r"<table[^>]*?>.*?</table>", re.IGNORECASE | re.DOTALL)
_HTML_TAG = re.compile(r"<[^>]+>")
_MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_HYPHEN_BREAK = re.compile(r"(\w)-[ \t]*\n[ \t]*(\w)")
_TOKEN = re.compile(r"[^\W_]+")
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def with_html_tables(markdown: str) -> str:
    """Return ``markdown`` with Markdown pipe tables rewritten as HTML tables."""

    return convert_to_markdown_with_html_tables(markdown or "") or ""


def html_tables(markdown: str) -> List[str]:
    """Return every table in ``markdown`` as an HTML string."""

    soup = BeautifulSoup(with_html_tables(markdown), "html.parser")
    return [str(table) for table in soup.find_all("table")]


def table_cells(table_html: str) -> List[str]:
    """Return the text of every cell in ``table_html``."""

    soup = BeautifulSoup(table_html, "html.parser")
    return [cell.get_text(" ") for cell in soup.find_all(["td", "th"])]


def clean(text: str) -> str:
    """Unescape entities, unify Unicode forms and rejoin hyphenated line breaks."""

    text = unescape(text)
    text = unicodedata.normalize("NFKC", text).translate(_PUNCT_MAP)
    return _HYPHEN_BREAK.sub(r"\1\2", text)


def _table_to_text(match: "re.Match[str]") -> str:
    return "\n" + "\n".join(table_cells(match.group(0))) + "\n"


def plain_text(markdown: str) -> str:
    """Strip Markdown and HTML markup from ``markdown``, keeping table cell text."""

    text = with_html_tables(markdown)
    text = _HTML_COMMENT.sub(" ", text)
    text = _HTML_TABLE.sub(_table_to_text, text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = _HTML_TAG.sub(" ", text)
    text = _MD_IMAGE.sub(" ", text)
    text = _MD_LINK.sub(r"\1", text)
    return clean(text)


def tokens(text: str) -> List[str]:
    """Split already-cleaned text into case-folded word tokens."""

    return [token.casefold() for token in _TOKEN.findall(text)]


def text_tokens(markdown: str) -> List[str]:
    """Word tokens of ``markdown`` after removing all markup."""

    return tokens(plain_text(markdown))


class Phrase(NamedTuple):
    """Normalized text (space-joined tokens) and where to look for it first."""

    text: str
    from_end: bool = False


def remove_phrases(words: List[str], phrases: Sequence[Phrase]) -> List[str]:
    """Remove one occurrence of each phrase from ``words``.

    Longer phrases go first. Phrases marked ``from_end`` (footers) remove
    their last occurrence, others their first.
    """

    if not phrases:
        return list(words)
    haystack = " " + " ".join(words) + " "
    for phrase in sorted(phrases, key=lambda p: len(p.text), reverse=True):
        needle = f" {phrase.text} "
        index = haystack.rfind(needle) if phrase.from_end else haystack.find(needle)
        if index >= 0:
            haystack = haystack[:index] + " " + haystack[index + len(needle):]
    return haystack.split()


def phrase_recall(phrases: List[str], markdown: str) -> Optional[float]:
    """Share of words in ``phrases`` found as whole phrases in ``markdown``.

    ``phrases`` must already be normalized (space-joined tokens). Each match
    is consumed, so a phrase that appears once in the prediction can only be
    credited once. Longer phrases are matched first.
    """

    total = sum(len(phrase.split()) for phrase in phrases)
    if not total:
        return None
    haystack = " " + " ".join(text_tokens(markdown)) + " "
    found = 0
    for phrase in sorted(phrases, key=len, reverse=True):
        needle = f" {phrase} "
        index = haystack.find(needle)
        if index < 0:
            continue
        found += len(phrase.split())
        haystack = haystack[:index] + " \x00 " + haystack[index + len(needle):]
    return found / total


def headings(markdown: str) -> List[tuple[int, str]]:
    """Return ``(level, normalized text)`` for every ATX heading in ``markdown``."""

    found = []
    for line in (markdown or "").splitlines():
        match = _HEADING.match(line)
        if match:
            text = " ".join(tokens(plain_text(match.group(2))))
            if text:
                found.append((len(match.group(1)), text))
    return found
