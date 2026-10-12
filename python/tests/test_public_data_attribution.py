"""Public copy attributes baseline mortality the way the runtime snapshot does.

The runtime life table's ``provenance.status`` records whether its values match
the CDC tables it names. Public copy must agree with that record:

- while the status records a mismatch, each sentence that names CDC (or NCHS,
  or NVSR) together with tables must say the table does not match, and the
  About page and FAQ must carry that disclosure;
- once the snapshot is generated from NVSR 72-12, no such sentence may still
  disclose a mismatch, and the About page and FAQ must name the CDC source.

The check works one sentence at a time, over every page and component under
``src/`` and the published docs. It is a pattern match, so it has limits: it
does not catch an attribution that never uses the word "table", or one whose
source and table sit in separate sentences, and it accepts any "not match"
wording as a disclosure without reading what the sentence says does not match.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

from optiqal.snapshots import load_snapshot

REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_SURFACES = (
    "README.md",
    "docs/index.md",
    "docs/appendix.md",
    "docs/methodology.md",
)
REQUIRED_SURFACES = ("src/app/about/page.tsx", "src/app/faq/page.tsx")

_CDC = re.compile(
    r"\b(?:CDC|NCHS|NVSR)\b|Centers for Disease Control|National Vital Statistics"
    r"|National Center for Health Statistics",
    re.IGNORECASE,
)
_TABLES = re.compile(r"\btables?\b", re.IGNORECASE)
# The negated verb itself: "does not match", "not matching", "none of ... matches".
_DISCLOSURE = re.compile(
    r"\b(?:not|none of\b[^.;]*?)\s+match(?:es|ing)?\b", re.IGNORECASE
)
# Sentence end, except after "U.S.", which the copy writes before "life tables".
_SENTENCE_END = re.compile(r"(?<!\bU\.S\.)(?<=[.!?])\s+(?=[A-Z0-9'(\[])")


def public_surfaces() -> tuple[str, ...]:
    """Every page and component source, plus the published docs."""
    sources = sorted(
        path.relative_to(REPO_ROOT).as_posix()
        for folder in ("src/app", "src/components")
        for path in (REPO_ROOT / folder).rglob("*.tsx")
        if not path.name.endswith(".test.tsx")
    )
    return (*sources, *DOC_SURFACES)


def _sentences(source: str) -> list[str]:
    """Split TSX or Markdown into prose sentences.

    Tags, JSX spacers, and emphasis markup are dropped. String quotes, list
    items, headings, and blank lines end a block, and blocks split at sentence
    punctuation, so a disclosure only counts in the sentence that attributes.
    """
    text = re.sub(r"<[^>]*>", " ", source)
    text = html.unescape(text.replace('{" "}', " "))
    text = re.sub(r'\n\s*(?:[-*]|\d+\.)\s+|\n\s*#+\s|\n\s*\n|"', "\x00", text)
    text = re.sub(r"[*_`]", "", text)
    sentences = []
    for block in text.split("\x00"):
        block = re.sub(r"\s+", " ", block).strip()
        sentences.extend(s for s in _SENTENCE_END.split(block) if s)
    return sentences


def cdc_table_sentences(source: str) -> list[str]:
    return [s for s in _sentences(source) if _CDC.search(s) and _TABLES.search(s)]


def _snapshot_mismatch() -> bool:
    provenance = load_snapshot("cdc_life_table").provenance
    return "does not match" in provenance["status"]


def test_sentence_finder_sees_disclosed_and_bare_attributions():
    bare = "We use CDC life tables for baseline mortality. Other text."
    disclosed = (
        "<li>It is attributed to the CDC&apos;s 2021 life tables but does not "
        "match the published tables.</li>"
    )

    assert cdc_table_sentences(bare) == [
        "We use CDC life tables for baseline mortality."
    ]
    assert not _DISCLOSURE.search(cdc_table_sentences(bare)[0])
    [sentence] = cdc_table_sentences(disclosed)
    assert _DISCLOSURE.search(sentence)


def test_sentence_finder_is_not_fooled_by_spelling_or_abbreviations():
    for bare in (
        "Baseline mortality comes from the Centers for Disease Control life tables.",
        "Baseline mortality comes from cdc life tables.",
        "Mortality follows the NCHS life tables.",
        "We use the CDC's 2021 U.S. Life Tables.",
        "We use the National Vital Statistics life tables.",
    ):
        [sentence] = cdc_table_sentences(bare)
        assert sentence == bare
        assert not _DISCLOSURE.search(sentence)


def test_a_claimed_match_is_not_a_disclosure():
    claim = "No adjustment is needed because our rates match the CDC life tables."
    assert not _DISCLOSURE.search(claim)
    for disclosure in (
        "The rates do not match the CDC life tables.",
        "A legacy table, attributed to but not matching the CDC tables.",
        "None of the 44 anchors matches the CDC tables.",
    ):
        assert _DISCLOSURE.search(disclosure), disclosure


def test_public_copy_agrees_with_the_life_table_provenance():
    mismatch = _snapshot_mismatch()
    surfaces = public_surfaces()
    assert set(REQUIRED_SURFACES) <= set(surfaces)
    found = {}
    for relative in surfaces:
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        found[relative] = cdc_table_sentences(source)
        for sentence in found[relative]:
            disclosed = bool(_DISCLOSURE.search(sentence))
            if mismatch:
                assert disclosed, (
                    f"{relative} ties the baseline to CDC tables without disclosing "
                    f"that the runtime snapshot does not match them: {sentence!r}"
                )
            else:
                assert not disclosed, (
                    f"{relative} still discloses a mismatch the runtime snapshot no "
                    f"longer has: {sentence!r}"
                )
    for relative in REQUIRED_SURFACES:
        assert found[relative], f"{relative} no longer states the life-table source"


def test_a_matching_snapshot_names_nvsr_72_12():
    provenance = load_snapshot("cdc_life_table").provenance
    if _snapshot_mismatch():
        assert "commit 5e472e22" in provenance["source"]
    else:
        assert "72(12)" in provenance["source"]
        assert provenance["url"].endswith("nvsr72-12.pdf")
