"""Public copy attributes baseline mortality the way the runtime snapshot does.

The runtime life table's ``provenance.status`` records whether its values match
the CDC tables it names. Every public surface that ties Optiqal's baseline to
CDC life tables must agree with that record:

- while the status records a mismatch, each sentence that pairs CDC (or NVSR)
  with life tables must disclose it, and the About page and FAQ must carry that
  disclosure;
- once the snapshot is generated from NVSR 72-12, no surface may still disclose
  a mismatch, and the About page and FAQ must name the CDC source.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

from optiqal.snapshots import load_snapshot

REPO_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_SURFACES = (
    "src/app/about/page.tsx",
    "src/app/faq/page.tsx",
    "src/app/brand/writing/page.tsx",
    "docs/index.md",
    "docs/methodology.md",
)
REQUIRED_SURFACES = ("src/app/about/page.tsx", "src/app/faq/page.tsx")

_CDC = re.compile(r"\b(?:CDC|NVSR)\b")
_TABLES = re.compile(r"\btables?\b", re.IGNORECASE)
_DISCLOSURE = re.compile(r"\b(?:not|none|no)\b[^.;]*?\bmatch", re.IGNORECASE)


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
        sentences.extend(
            s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9'(\[])", block) if s
        )
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


def test_public_copy_agrees_with_the_life_table_provenance():
    mismatch = _snapshot_mismatch()
    found = {}
    for relative in PUBLIC_SURFACES:
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
