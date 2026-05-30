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
import re
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, Optional


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


@dataclass(frozen=True)
class GenotypeFileSummary:
    """Non-sensitive file metadata retained alongside derived genetics."""

    source_name: str
    format_name: str
    compression: str
    call_count: int = 0
    selected_member: Optional[str] = None
    chip_version: Optional[str] = None


def _ensure_readable_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.stat().st_size == 0:
        raise ValueError(f"Genotype file is empty: {path}")


def _zip_member_score(info: zipfile.ZipInfo) -> tuple[int, str]:
    name = info.filename.lower()
    if "statistical" in name:
        priority = 2
    elif "genome" in name:
        priority = 0
    else:
        priority = 1
    return priority, name


def _select_zip_member(path: Path) -> zipfile.ZipInfo:
    _ensure_readable_file(path)
    try:
        with zipfile.ZipFile(path) as zf:
            members = [
                info
                for info in zf.infolist()
                if not info.is_dir()
                and info.filename.lower().endswith((".txt", ".tsv"))
                and info.file_size > 0
            ]
            if not members:
                raise ValueError(f"No genotype text file found inside {path}")
            return sorted(members, key=_zip_member_score)[0]
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Invalid ZIP genotype file: {path}") from exc


@contextmanager
def _open_maybe_compressed(path: Path) -> Iterator[io.TextIOBase]:
    """Open plain, gzipped, or zipped genotype text uniformly."""
    _ensure_readable_file(path)
    suffix = path.suffix.lower()
    if suffix in (".gz", ".gzip"):
        with gzip.open(path, "rb") as raw:
            yield io.TextIOWrapper(raw, encoding="utf-8")
    elif suffix == ".zip":
        member = _select_zip_member(path)
        with zipfile.ZipFile(path) as zf, zf.open(member) as raw:
            yield io.TextIOWrapper(raw, encoding="utf-8")
    else:
        with open(path, "r", encoding="utf-8") as fh:
            yield fh


def _compression_label(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".zip":
        return "zip"
    if suffix in (".gz", ".gzip"):
        return "gzip"
    return "plain"


def _infer_chip_version(*values: Optional[str]) -> Optional[str]:
    for value in values:
        if not value:
            continue
        match = re.search(r"(?:^|[_\s.-])v([345])(?:[_\s.-]|$)", value.lower())
        if match:
            return f"v{match.group(1)}"
    return None


def summarize_genotype_file(
    path: str | Path,
    call_count: int = 0,
) -> GenotypeFileSummary:
    """Return non-sensitive metadata about a genotype file.

    This deliberately stores only file/container metadata and aggregate row
    count, never rsIDs or genotype calls.
    """
    p = Path(path)
    selected_member = None
    if p.suffix.lower() == ".zip":
        selected_member = _select_zip_member(p).filename
    with _open_maybe_compressed(p) as fh:
        head = fh.read(2048)
    format_name = "AncestryDNA" if "ancestrydna" in head.lower() else "23andMe"
    return GenotypeFileSummary(
        source_name=p.name,
        selected_member=selected_member,
        format_name=format_name,
        compression=_compression_label(p),
        call_count=call_count,
        chip_version=_infer_chip_version(p.name, selected_member, head),
    )


def _iter_nonblank(fh: io.TextIOBase) -> Iterable[str]:
    for line in fh:
        line = line.rstrip("\n\r")
        if line and not line.startswith("#"):
            yield line


def parse_23andme(path: str | Path) -> Dict[str, RawGenotype]:
    """Parse a 23andMe raw-data ``.txt`` (optionally gzipped).

    23andMe raw format:

        # rsid	chromosome	position	genotype
        rs4477212	1	82154	AA
        rs3094315	1	752566	AG
        ...

    23andMe phased genotype downloads use a five-column layout:

        rs4477212	1	82154	A	A
        rs3094315	1	752566	A	G

    Returns a dict keyed by rsID. Rows with unknown rsIDs (``i`` prefix for
    23andMe internal probes) are preserved so PGx lookups that need them
    can still match.
    """
    p = Path(path)
    out: Dict[str, RawGenotype] = {}
    with _open_maybe_compressed(p) as fh:
        for line in _iter_nonblank(fh):
            parts = line.split("\t")
            if parts[0].lower() == "rsid":
                continue
            if len(parts) == 4:
                rsid, chrom, pos, gt = parts
            elif len(parts) >= 5:
                rsid, chrom, pos, a1, a2 = parts[:5]
                a1 = (a1 or "").strip().upper() or "-"
                a2 = (a2 or "").strip().upper() or "-"
                gt = (a1 + a2).replace("00", "--")
            else:
                continue
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
    with _open_maybe_compressed(p) as fh:
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
    with _open_maybe_compressed(p) as fh:
        head = fh.read(2048)
    if "ancestrydna" in head.lower():
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
