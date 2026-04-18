"""Parse consumer genotyping file formats.

Supports:
- 23andMe v3, v4, v5 raw data (``*.txt`` tab-separated)
- AncestryDNA raw data (``*.txt`` tab-separated, different header)

Output is a flat ``{rsid: RawGenotype}`` mapping independent of source format.
The logic is pure-function dict manipulation so it ports cleanly to TS/WASM.
"""

from __future__ import annotations

import gzip
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional


@dataclass(frozen=True)
class RawGenotype:
    """One genotype call from a consumer DNA file.

    ``genotype`` is the two-character allele string on autosomes
    ("AG", "CC"), a single char on male sex chromosomes ("A"), or
    the special tokens ``"--"`` (no-call), ``"II"`` / ``"DD"`` / ``"DI"``
    for insertions/deletions. X-linked loci in males are returned as the
    single haploid allele.
    """

    rsid: str
    chromosome: str
    position: int
    genotype: str

    @property
    def is_no_call(self) -> bool:
        return self.genotype in ("--", "", "00")

    @property
    def is_indel(self) -> bool:
        # 23andMe reports insertions/deletions as I/D instead of A/C/G/T.
        return any(ch in ("I", "D") for ch in self.genotype)


def _open_maybe_gz(path: Path) -> io.TextIOBase:
    """Open plain text or gzipped text uniformly."""
    if path.suffix in (".gz", ".gzip"):
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8")
    return open(path, "r", encoding="utf-8")


def _iter_nonblank(fh: io.TextIOBase) -> Iterable[str]:
    for line in fh:
        line = line.rstrip("\n\r")
        if line and not line.startswith("#"):
            yield line


def parse_23andme(path: str | Path) -> Dict[str, RawGenotype]:
    """Parse a 23andMe raw-data ``.txt`` (optionally gzipped).

    23andMe format:

        # rsid	chromosome	position	genotype
        rs4477212	1	82154	AA
        rs3094315	1	752566	AG
        ...

    Returns a dict keyed by rsID. Rows with unknown rsIDs (``i`` prefix for
    23andMe internal probes) are preserved so PGx lookups that need them
    can still match.
    """
    p = Path(path)
    out: Dict[str, RawGenotype] = {}
    with _open_maybe_gz(p) as fh:
        for line in _iter_nonblank(fh):
            parts = line.split("\t")
            if len(parts) != 4:
                continue
            rsid, chrom, pos, gt = parts
            try:
                position = int(pos)
            except ValueError:
                continue
            out[rsid] = RawGenotype(
                rsid=rsid,
                chromosome=chrom,
                position=position,
                genotype=gt.strip().upper(),
            )
    return out


def parse_ancestry(path: str | Path) -> Dict[str, RawGenotype]:
    """Parse an AncestryDNA raw-data ``.txt`` (optionally gzipped).

    AncestryDNA format:

        #AncestryDNA raw data download
        rsid	chromosome	position	allele1	allele2
        rs4477212	1	82154	A	A
        ...

    Returns the same ``{rsid: RawGenotype}`` shape as ``parse_23andme``,
    with the two alleles concatenated into the ``genotype`` field.
    """
    p = Path(path)
    out: Dict[str, RawGenotype] = {}
    with _open_maybe_gz(p) as fh:
        for line in _iter_nonblank(fh):
            parts = line.split("\t")
            if len(parts) < 5:
                continue
            if parts[0].lower() == "rsid":
                continue  # header
            rsid, chrom, pos, a1, a2 = parts[:5]
            try:
                position = int(pos)
            except ValueError:
                continue
            a1 = (a1 or "").strip().upper() or "-"
            a2 = (a2 or "").strip().upper() or "-"
            out[rsid] = RawGenotype(
                rsid=rsid,
                chromosome=chrom,
                position=position,
                genotype=(a1 + a2).replace("00", "--"),
            )
    return out


def detect_and_parse(path: str | Path) -> Dict[str, RawGenotype]:
    """Best-effort format detection — header sniff then fallback to 23andMe."""
    p = Path(path)
    with _open_maybe_gz(p) as fh:
        head = fh.read(2048)
    if "AncestryDNA" in head or "allele1\tallele2" in head.lower():
        return parse_ancestry(p)
    return parse_23andme(p)


def genotype_at(calls: Dict[str, RawGenotype], rsid: str) -> Optional[str]:
    """Shortcut — return the sorted-allele genotype string or None.

    Sorting the alleles makes equality checks independent of phase
    (``"AG"`` and ``"GA"`` both normalize to ``"AG"``).
    """
    g = calls.get(rsid)
    if g is None or g.is_no_call:
        return None
    if len(g.genotype) == 2:
        return "".join(sorted(g.genotype))
    return g.genotype
