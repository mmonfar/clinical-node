"""
adapters/citations.py
---------------------
Citation checks for committee output (see docs/GOVERNANCE.md).

A format-level check only: it confirms that every reference carries a
well-formed PMID with a matching PubMed URL, and that every [N] the model
cites points to a reference that exists. It does NOT call PubMed, so it
cannot tell whether a PMID is real or whether the article supports the
claim. Those checks are on the plan, not in place.

Pure functions, no I/O. Not yet wired into the UI or the minutes.
"""

from __future__ import annotations

import re

PUBMED_URL_PREFIX = "https://pubmed.ncbi.nlm.nih.gov/"

# PMIDs are positive integers; today they have up to 8 digits.
_PMID_RE = re.compile(r"^[1-9]\d{0,8}$")
_BRACKET_RE = re.compile(r"\[(\d+)\]")


def is_valid_pmid(value: object) -> bool:
    """True if ``value`` is a well-formed PMID (format only, not existence)."""
    return bool(_PMID_RE.match(str(value or "").strip()))


def check_references(articles: list[dict]) -> list[dict]:
    """Flag reference-list entries with no valid PMID or a mismatched URL.

    Returns one ``{"ref": N, "problem": str}`` per problem, where N is the
    1-based number the prompts use for that article.
    """
    flags: list[dict] = []
    for n, a in enumerate(articles, 1):
        pmid = str(a.get("pmid") or "").strip()
        if not is_valid_pmid(pmid):
            flags.append({"ref": n, "problem": "missing or malformed PMID"})
            continue
        if a.get("url") != f"{PUBMED_URL_PREFIX}{pmid}/":
            flags.append({"ref": n, "problem": "URL does not match PMID"})
    return flags


def cited_numbers(text: str) -> list[int]:
    """All [N] citation numbers in free text, in order of appearance."""
    return [int(m) for m in _BRACKET_RE.findall(text or "")]


def check_citation_numbers(numbers: list[int], n_refs: int) -> list[int]:
    """Citation numbers that point outside the 1..n_refs reference list."""
    return [n for n in numbers if not 1 <= int(n) <= n_refs]


def check_roundtable(roundtable: list[dict], n_refs: int) -> list[dict]:
    """Flag roundtable statements that cite nothing or cite a missing reference.

    The roundtable prompt requires every clinical claim to cite [N]; this
    shows where the model did not comply.
    """
    flags: list[dict] = []
    for entry in roundtable:
        who = entry.get("specialist", "Unknown")
        cites = list(entry.get("citations") or [])
        if not cites:
            flags.append({"specialist": who, "problem": "no citation"})
            continue
        bad = check_citation_numbers(cites, n_refs)
        if bad:
            flags.append({"specialist": who, "problem": f"cites missing reference(s) {bad}"})
    return flags
