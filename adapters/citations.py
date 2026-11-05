"""
adapters/citations.py
---------------------
Citation checks for committee output (see docs/GOVERNANCE.md).

A format-level check only: it confirms that every reference carries a
well-formed PMID with a matching PubMed URL, and that every [N] the model
cites points to a reference that exists. It does NOT call PubMed, so it
cannot tell whether a PMID is real or whether the article supports the
claim. Those checks are on the plan, not in place.

Pure functions, no I/O. Wired into the debate output (debate/output.py) through
check_evidence_refs() and pubmed_url(). Not yet wired into the UI or the minutes.
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


_EREF_RE = re.compile(r"^E([1-9]\d*)$")


def pubmed_url(pmid: object) -> str:
    """PubMed link for a valid PMID, else an empty string (never a made-up link)."""
    return f"{PUBMED_URL_PREFIX}{str(pmid).strip()}/" if is_valid_pmid(pmid) else ""


def check_evidence_refs(refs: list[str], records: list[dict]) -> list[dict]:
    """Check debate evidence refs ("E3" or "NONE") against the evidence list.

    Flags a ref that is malformed, points outside the list, or is a PubMed
    record without a valid PMID. Format only: it cannot tell if the source supports the claim.
    """
    flags: list[dict] = []
    ids = {r.get("id"): r for r in records}
    for ref in refs:
        if ref == "NONE":
            continue
        m = _EREF_RE.match(str(ref))
        if not m:
            flags.append({"ref": ref, "problem": "malformed evidence ref"})
        elif check_citation_numbers([int(m.group(1))], len(records)) or ref not in ids:
            flags.append({"ref": ref, "problem": "not in the evidence list"})
        elif ids[ref].get("source") == "pubmed" and not is_valid_pmid(
                str(ids[ref].get("ref", "")).replace("PMID", "").strip()):
            flags.append({"ref": ref, "problem": "missing or malformed PMID"})
    return flags


# ---------------------------------------------------------------------------
# Scrub: code removes any citation that has no retrieved article behind it.
# Code never invents a citation. A bad number is removed or marked.
# ---------------------------------------------------------------------------

NO_EVIDENCE = "NO EVIDENCE FOUND"
_GROUP_RE = re.compile(r"\[(\s*\d+(?:\s*[,;–-]\s*\d+)*\s*)\]")


def _scrub_group(match: re.Match, n_refs: int) -> str:
    nums = [int(x) for x in re.findall(r"\d+", match.group(1))]
    good = [n for n in nums if 1 <= n <= n_refs]
    if len(good) == len(nums):
        return match.group(0)
    kept = "".join(f"[{n}]" for n in good)
    return kept + f"[{NO_EVIDENCE}]"


def scrub_text(text: str, n_refs: int) -> tuple[str, int]:
    """Mark every [N] that points to no retrieved article.

    Returns (clean text, number of bad numbers found). Valid [N] stay.
    """
    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        nums = [int(x) for x in re.findall(r"\d+", m.group(1))]
        count += sum(1 for n in nums if not 1 <= n <= n_refs)
        return _scrub_group(m, n_refs)

    return _GROUP_RE.sub(repl, text or ""), count


def scrub_structure(value, n_refs: int):
    """Scrub every string in a nested dict/list and every ``citations`` list.

    Returns (clean copy, number of bad citations removed or marked).
    """
    if isinstance(value, str):
        return scrub_text(value, n_refs)
    if isinstance(value, list):
        out, total = [], 0
        for v in value:
            c, n = scrub_structure(v, n_refs)
            out.append(c)
            total += n
        return out, total
    if isinstance(value, dict):
        out, total = {}, 0
        for k, v in value.items():
            if k == "citations" and isinstance(v, list):
                good = [n for n in v if isinstance(n, int) and not isinstance(n, bool)
                        and 1 <= n <= n_refs]
                total += len(v) - len(good)
                out[k] = good
                continue
            c, n = scrub_structure(v, n_refs)
            out[k] = c
            total += n
        return out, total
    return value, 0


def count_refs(ref_list: str) -> int:
    """Number of numbered references in a prompt reference list."""
    return len(re.findall(r"(?m)^\[\d+\]", ref_list or ""))
