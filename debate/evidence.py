"""Evidence layer for the debate engine (SPEC section 4).

Research and demonstration software. Not a medical device. Synthetic cases only.

Order: local knowledge base first, PubMed only if it has no hit for the topic.
PubMed is optional: if Biopython or the network is missing, records say "PubMed unavailable".
The local knowledge base is read-only here. Code never invents a citation: no hit = "NO EVIDENCE FOUND".
"""
import os
import re
import sys
from pathlib import Path

NO_EVIDENCE = "NO EVIDENCE FOUND"
BANNER_NONE = "No evidence retrieved. Treat all output as unsupported."
BANNER_NO_PUBMED = "PubMed not searched"
PUBMED_UNAVAILABLE = "PubMed unavailable"

# Level of evidence: 1 is best. Unknown ranks last.
LEVEL_NAMES = {
    1: "meta-analysis / systematic review",
    2: "randomised controlled trial",
    3: "practice guideline",
    4: "cohort / case-control",
    5: "case series / case report",
    6: "expert opinion / textbook",
}
UNKNOWN = "unknown"

# Publication-type tag (lower case, PubMed style) -> level. Best level wins.
PUBTYPE_LEVEL = {
    "meta-analysis": 1, "systematic review": 1,
    "randomized controlled trial": 2, "randomised controlled trial": 2,
    "practice guideline": 3, "guideline": 3,
    "cohort study": 4, "case-control study": 4, "observational study": 4,
    "clinical trial": 4, "controlled clinical trial": 4,
    "case series": 5, "case reports": 5, "case report": 5,
    "expert opinion": 6, "textbook": 6, "review": 6, "editorial": 6, "comment": 6,
}
_PREPRINT_WORDS = ("preprint", "arxiv", "medrxiv", "biorxiv")


def level_from_types(pub_types):
    """Best (lowest) level over publication-type tags. UNKNOWN if none match."""
    levels = [PUBTYPE_LEVEL[t.strip().lower()] for t in (pub_types or [])
              if isinstance(t, str) and t.strip().lower() in PUBTYPE_LEVEL]
    return min(levels) if levels else UNKNOWN


def is_preprint(*texts, pub_types=None):
    blob = " ".join(str(t) for t in texts if t).lower()
    if any(w in blob for w in _PREPRINT_WORDS):
        return True
    return any(isinstance(t, str) and "preprint" in t.lower() for t in (pub_types or []))


def rank_key(record):
    """Sort key: level first (unknown last), then newer year first."""
    lvl = record["level"] if isinstance(record["level"], int) else 99
    return (lvl, -(record.get("year") or 0))


# ---- real searchers (lazy; both can fail cleanly) ----

def brain_search(query, limit=5):
    """Search the local knowledge base, read-only. Returns list of dicts.

    The folder that holds query_brain.py comes from the environment variable DEBATE_KB_DIR.
    If it is unset or empty there is no local knowledge base: return no hits (PubMed is next).
    """
    kb_dir = os.environ.get("DEBATE_KB_DIR", "").strip()
    if not kb_dir:
        return []
    root = Path(kb_dir)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    sys.dont_write_bytecode = True  # leave the knowledge base folder untouched
    import query_brain  # local import, no MCP
    words = re.findall(r"[A-Za-z0-9]+", query)
    if not words:
        return []
    hits = query_brain.search(" OR ".join(words), limit)
    return [{"book": h.book, "file_path": h.file_path, "heading": h.heading,
             "snippet": h.snippet} for h in hits]


def pubmed_search(query, limit=5):
    """Call pubmed_client.search_clinical_evidence. Raises if Biopython/env/network is missing."""
    import pubmed_client  # needs Biopython and ENTREZ_EMAIL
    return pubmed_client.search_clinical_evidence(query, max_results=limit)


def _get(h, name, default=""):
    if isinstance(h, dict):
        return h.get(name, default)
    return getattr(h, name, default)


class EvidenceList:
    """Holds E1..En records, per-topic results and banners."""

    def __init__(self, brain=None, pubmed=None, limit=3, use_pubmed=True, pubtypes=None):
        self._brain = brain if brain is not None else brain_search
        self._pubmed = pubmed if pubmed is not None else pubmed_search
        # Publication-type lookup (esummary). Only the real PubMed path uses it by default,
        # so tests with a fake PubMed never touch the network.
        if pubtypes is None and pubmed is None:
            from debate.pubtypes import fetch_pubtypes
            pubtypes = fetch_pubtypes
        self._pubtypes = pubtypes
        self.limit = limit
        self.use_pubmed = use_pubmed
        self.records = []
        self.topics = {}
        self.notes = []
        self._by_ref = {}
        self.pubmed_status = "not needed"

    def _add(self, source, ref, level, year, snippet, preprint, pubmed_status):
        if ref in self._by_ref:
            return self._by_ref[ref]
        rec = {"id": f"E{len(self.records) + 1}", "source": source, "ref": ref,
               "level": level, "year": year, "snippet": snippet,
               "preprint": preprint, "pubmed_status": pubmed_status}
        self.records.append(rec)
        self._by_ref[ref] = rec
        return rec

    def _lookup_types(self, papers):
        """PMID -> publication types for papers that have none. Failure = level stays unknown."""
        need = [str(_get(p, "pmid")) for p in papers if not _get(p, "pub_types", None)]
        if not need or self._pubtypes is None:
            return {}
        try:
            return dict(self._pubtypes(need))
        except Exception as exc:  # network or JSON error: keep the run going
            self.notes.append(f"publication-type lookup failed: {type(exc).__name__}")
            return {}

    def search_topic(self, topic):
        """Search one topic. Returns the topic result dict."""
        ids = []
        try:
            hits = list(self._brain(topic, self.limit) or [])
        except Exception as exc:  # brain failure must not stop the run
            hits = []
            self.notes.append(f"brain search failed for {topic!r}: {type(exc).__name__}")
        for h in hits[: self.limit]:
            fp, head = _get(h, "file_path"), _get(h, "heading")
            pt = _get(h, "pub_types", None)
            level = level_from_types(pt) if pt else 6  # brain page without a primary study
            rec = self._add("brain", f"{fp} | {head}", level, _get(h, "year", 0) or 0,
                            _get(h, "snippet"), is_preprint(fp, head, pub_types=pt),
                            "not needed")
            ids.append(rec["id"])
        status = "not needed"
        if not ids:
            if not self.use_pubmed:
                status = BANNER_NO_PUBMED
            else:
                try:
                    papers = list(self._pubmed(topic, self.limit) or [])
                    status = "searched"
                    papers = papers[: self.limit]
                    looked_up = self._lookup_types(papers)
                    for p in papers:
                        pmid = str(_get(p, "pmid"))
                        if not re.fullmatch(r"[0-9]+", pmid):
                            continue  # no valid PMID = no citation
                        pt = _get(p, "pub_types", None) or looked_up.get(pmid)
                        m = re.search(r"\d{4}", str(_get(p, "year")))
                        year = int(m.group()) if m else 0
                        snip = (str(_get(p, "title")) + ". " + str(_get(p, "abstract")))[:300]
                        rec = self._add("pubmed", f"PMID {pmid}", level_from_types(pt), year,
                                        snip, is_preprint(_get(p, "journal"), pub_types=pt),
                                        "searched")
                        ids.append(rec["id"])
                except Exception as exc:  # ImportError (no Biopython), EnvironmentError, network
                    status = PUBMED_UNAVAILABLE
                    self.notes.append(f"{PUBMED_UNAVAILABLE} for {topic!r}: {type(exc).__name__}")
        if status != "not needed":
            if self.pubmed_status in ("not needed", status):
                self.pubmed_status = status
            else:
                self.pubmed_status = "mixed"
        ranked = sorted((r for r in self.records if r["id"] in ids), key=rank_key)
        result = {"topic": topic, "evidence_ids": [r["id"] for r in ranked],
                  "status": "found" if ids else NO_EVIDENCE, "pubmed_status": status}
        self.topics[topic] = result
        return result

    def gather(self, topics):
        for t in topics:
            self.search_topic(t)
        return self

    def best_ref(self, topic):
        """One citation per claim: best-ranked id for the topic, or 'NONE'. Never invented."""
        res = self.topics.get(topic)
        return res["evidence_ids"][0] if res and res["evidence_ids"] else "NONE"

    def ids(self):
        return {r["id"] for r in self.records}

    def label(self, ref):
        """Text shown next to a claim or objection."""
        return NO_EVIDENCE if ref == "NONE" else ref

    def banners(self):
        out = []
        if not self.records:
            out.append(BANNER_NONE)
        if self.pubmed_status in (PUBMED_UNAVAILABLE, "mixed"):
            out.append(PUBMED_UNAVAILABLE)
        if self.pubmed_status == BANNER_NO_PUBMED:
            out.append(BANNER_NO_PUBMED)
        return out

    def to_dict(self):
        return {"records": self.records, "topics": self.topics, "banners": self.banners(),
                "notes": self.notes}
