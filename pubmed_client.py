"""
pubmed_client.py
----------------
PubMed search client backed by Biopython's Entrez API.

Only returns high-quality evidence: randomized controlled trials (RCTs) and
meta-analyses, enforced via PubMed publication-type filters.

Environment variables (loaded from .env via python-dotenv):
    ENTREZ_EMAIL   – required by NCBI; identifies your application.
    ENTREZ_API_KEY – optional but raises the rate-limit from 3 to 10 req/s.
"""

import os
import time
from typing import Optional

from Bio import Entrez
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv()  # reads .env in the current working directory (or parents)

_email = os.getenv("ENTREZ_EMAIL")
if not _email:
    raise EnvironmentError(
        "ENTREZ_EMAIL is not set. "
        "Add it to your .env file: ENTREZ_EMAIL=you@example.com"
    )

Entrez.email = _email

_api_key = os.getenv("ENTREZ_API_KEY")
if _api_key:
    Entrez.api_key = _api_key

# NCBI allows 3 requests/second without a key, 10 with one.
_REQUEST_DELAY = 0.11 if _api_key else 0.34

PUBMED_BASE_URL = "https://pubmed.ncbi.nlm.nih.gov/"

# Tier 1: highest-quality evidence.
_HIGH_EVIDENCE_FILTER = (
    "(randomized controlled trial[Filter] OR meta-analysis[Filter] "
    "OR systematic review[Filter] OR practice guideline[Filter])"
)

# Tier 2: intermediate evidence (used when tier 1 returns < RARE_THRESHOLD results).
_MID_EVIDENCE_FILTER = (
    "(clinical trial[Filter] OR observational study[Filter])"
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_url(pmid: str) -> str:
    """Return the canonical PubMed URL for *pmid*."""
    return f"{PUBMED_BASE_URL}{pmid}/"


def _throttle() -> None:
    """Polite delay to stay within NCBI rate limits."""
    time.sleep(_REQUEST_DELAY)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search_clinical_evidence(
    query: str,
    max_results: int = 20,
    sort: str = "relevance",
) -> list[dict]:
    """
    Search PubMed for high-quality clinical evidence matching *query*.

    The search is automatically restricted to:
        randomized controlled trial[Filter] OR meta-analysis[Filter]
        OR systematic review[Filter] OR practice guideline[Filter]

    Parameters
    ----------
    query : str
        Free-text or structured PubMed query (MeSH terms are accepted).
    max_results : int
        Maximum number of records to return (default 20, max 10 000).
    sort : str
        PubMed sort order – ``"relevance"`` (default) or ``"pub_date"``.

    Returns
    -------
    list[dict]
        Each element contains:
        ``pmid``   – PubMed identifier (str)
        ``url``    – Direct link to the article on PubMed
        ``title``  – Article title
        ``authors``– Comma-separated author list
        ``journal``– Journal name (ISO abbreviation)
        ``year``   – Publication year
        ``abstract``– Abstract text (may be empty for older articles)

    Raises
    ------
    RuntimeError
        If the Entrez search or fetch step fails.
    ValueError
        If *query* is empty.
    """
    if not query or not query.strip():
        raise ValueError("query must not be empty")

    full_query = f"({query.strip()}) AND {_HIGH_EVIDENCE_FILTER}"

    # -- Step 1: esearch -------------------------------------------------------
    try:
        _throttle()
        search_handle = Entrez.esearch(
            db="pubmed",
            term=full_query,
            retmax=max_results,
            sort=sort,
            usehistory="y",
        )
        search_results = Entrez.read(search_handle)
        search_handle.close()
    except Exception as exc:
        raise RuntimeError(f"PubMed esearch failed: {exc}") from exc

    pmids: list[str] = search_results.get("IdList", [])
    if not pmids:
        return []

    # -- Step 2: efetch --------------------------------------------------------
    try:
        _throttle()
        fetch_handle = Entrez.efetch(
            db="pubmed",
            id=",".join(pmids),
            rettype="xml",
            retmode="xml",
        )
        records = Entrez.read(fetch_handle)
        fetch_handle.close()
    except Exception as exc:
        raise RuntimeError(f"PubMed efetch failed: {exc}") from exc

    # -- Step 3: parse ---------------------------------------------------------
    results: list[dict] = []
    articles = records.get("PubmedArticle", [])

    for article in articles:
        try:
            medline = article["MedlineCitation"]
            pmid = str(medline["PMID"])
            art = medline["Article"]

            title = str(art.get("ArticleTitle", ""))

            # Authors
            author_list = art.get("AuthorList", [])
            authors = ", ".join(
                f"{a.get('LastName', '')} {a.get('Initials', '')}".strip()
                for a in author_list
                if "LastName" in a
            )

            # Journal + year
            journal_info = art.get("Journal", {})
            journal = str(journal_info.get("ISOAbbreviation", ""))
            pub_date = (
                journal_info
                .get("JournalIssue", {})
                .get("PubDate", {})
            )
            year = str(
                pub_date.get("Year", pub_date.get("MedlineDate", ""))
            )

            # Abstract
            abstract_obj = art.get("Abstract", {})
            abstract_texts = abstract_obj.get("AbstractText", [])
            if isinstance(abstract_texts, list):
                abstract = " ".join(str(t) for t in abstract_texts)
            else:
                abstract = str(abstract_texts)

            results.append(
                {
                    "pmid": pmid,
                    "url": _build_url(pmid),
                    "title": title,
                    "authors": authors,
                    "journal": journal,
                    "year": year,
                    "abstract": abstract,
                }
            )
        except (KeyError, TypeError):
            # Skip malformed records rather than crashing the whole batch.
            continue

    return results


def search_mid_tier_evidence(
    query: str,
    max_results: int = 10,
    sort: str = "relevance",
) -> list[dict]:
    """
    Search PubMed for intermediate-tier clinical evidence matching *query*.

    Used as a secondary fallback (Tier 2) when ``search_clinical_evidence``
    returns fewer than ``RARE_THRESHOLD`` results.  Filters to:
        clinical trial[Filter] OR observational study[Filter]

    Returns the same dict structure as :func:`search_clinical_evidence`.
    """
    if not query or not query.strip():
        raise ValueError("query must not be empty")

    full_query = f"({query.strip()}) AND {_MID_EVIDENCE_FILTER}"

    try:
        _throttle()
        search_handle = Entrez.esearch(
            db="pubmed",
            term=full_query,
            retmax=max_results,
            sort=sort,
            usehistory="y",
        )
        search_results = Entrez.read(search_handle)
        search_handle.close()
    except Exception as exc:
        raise RuntimeError(f"PubMed esearch (mid-tier) failed: {exc}") from exc

    pmids: list[str] = search_results.get("IdList", [])
    if not pmids:
        return []

    try:
        _throttle()
        fetch_handle = Entrez.efetch(
            db="pubmed",
            id=",".join(pmids),
            rettype="xml",
            retmode="xml",
        )
        records = Entrez.read(fetch_handle)
        fetch_handle.close()
    except Exception as exc:
        raise RuntimeError(f"PubMed efetch (mid-tier) failed: {exc}") from exc

    results: list[dict] = []
    for article in records.get("PubmedArticle", []):
        try:
            medline = article["MedlineCitation"]
            pmid = str(medline["PMID"])
            art = medline["Article"]
            title = str(art.get("ArticleTitle", ""))
            author_list = art.get("AuthorList", [])
            authors = ", ".join(
                f"{a.get('LastName', '')} {a.get('Initials', '')}".strip()
                for a in author_list
                if "LastName" in a
            )
            journal_info = art.get("Journal", {})
            journal = str(journal_info.get("ISOAbbreviation", ""))
            pub_date = journal_info.get("JournalIssue", {}).get("PubDate", {})
            year = str(pub_date.get("Year", pub_date.get("MedlineDate", "")))
            abstract_obj = art.get("Abstract", {})
            abstract_texts = abstract_obj.get("AbstractText", [])
            if isinstance(abstract_texts, list):
                abstract = " ".join(str(t) for t in abstract_texts)
            else:
                abstract = str(abstract_texts)
            results.append({
                "pmid": pmid,
                "url": _build_url(pmid),
                "title": title,
                "authors": authors,
                "journal": journal,
                "year": year,
                "abstract": abstract,
            })
        except (KeyError, TypeError):
            continue

    return results


def search_case_studies(
    query: str,
    max_results: int = 10,
    sort: str = "relevance",
) -> list[dict]:
    """
    Search PubMed for case reports matching *query*.

    Used as a fallback when ``search_clinical_evidence`` returns fewer than
    ``RARE_THRESHOLD`` results (i.e., rare or emerging conditions with limited
    RCT/meta-analysis coverage).

    Returns the same dict structure as :func:`search_clinical_evidence`.
    """
    if not query or not query.strip():
        raise ValueError("query must not be empty")

    case_filter = "(case reports[pt] OR case series[pt])"
    full_query = f"({query.strip()}) AND {case_filter}"

    try:
        _throttle()
        search_handle = Entrez.esearch(
            db="pubmed",
            term=full_query,
            retmax=max_results,
            sort=sort,
            usehistory="y",
        )
        search_results = Entrez.read(search_handle)
        search_handle.close()
    except Exception as exc:
        raise RuntimeError(f"PubMed esearch (case studies) failed: {exc}") from exc

    pmids: list[str] = search_results.get("IdList", [])
    if not pmids:
        return []

    try:
        _throttle()
        fetch_handle = Entrez.efetch(
            db="pubmed",
            id=",".join(pmids),
            rettype="xml",
            retmode="xml",
        )
        records = Entrez.read(fetch_handle)
        fetch_handle.close()
    except Exception as exc:
        raise RuntimeError(f"PubMed efetch (case studies) failed: {exc}") from exc

    results: list[dict] = []
    for article in records.get("PubmedArticle", []):
        try:
            medline = article["MedlineCitation"]
            pmid = str(medline["PMID"])
            art = medline["Article"]
            title = str(art.get("ArticleTitle", ""))
            author_list = art.get("AuthorList", [])
            authors = ", ".join(
                f"{a.get('LastName', '')} {a.get('Initials', '')}".strip()
                for a in author_list
                if "LastName" in a
            )
            journal_info = art.get("Journal", {})
            journal = str(journal_info.get("ISOAbbreviation", ""))
            pub_date = (
                journal_info.get("JournalIssue", {}).get("PubDate", {})
            )
            year = str(pub_date.get("Year", pub_date.get("MedlineDate", "")))
            abstract_obj = art.get("Abstract", {})
            abstract_texts = abstract_obj.get("AbstractText", [])
            if isinstance(abstract_texts, list):
                abstract = " ".join(str(t) for t in abstract_texts)
            else:
                abstract = str(abstract_texts)
            results.append({
                "pmid": pmid,
                "url": _build_url(pmid),
                "title": title,
                "authors": authors,
                "journal": journal,
                "year": year,
                "abstract": abstract,
            })
        except (KeyError, TypeError):
            continue

    return results


def fetch_article(pmid: str) -> Optional[dict]:
    """
    Fetch a single PubMed article by PMID.

    Returns the same dict structure as each element of
    :func:`search_clinical_evidence`, or ``None`` if the PMID is not found.
    """
    results = search_clinical_evidence(f"{pmid}[uid]", max_results=1)
    return results[0] if results else None
