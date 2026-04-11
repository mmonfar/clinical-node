"""
state_manager.py
----------------
Handles persistent state for clinical M&M cases:
  - Saving / loading case records to cases.json
  - Appending session minutes to Markdown files in /minutes
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent
CASES_FILE = BASE_DIR / "cases.json"
MINUTES_DIR = BASE_DIR / "minutes"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_raw() -> dict:
    """Return the full contents of cases.json, or an empty dict if absent."""
    if CASES_FILE.exists():
        with open(CASES_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def _save_raw(data: dict) -> None:
    """Persist *data* to cases.json with human-readable indentation."""
    with open(CASES_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def _now_iso() -> str:
    """Return the current UTC timestamp as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Case record schema
# ---------------------------------------------------------------------------

def _empty_case(case_id: str) -> dict:
    """Return a blank case record following the canonical schema."""
    return {
        "case_id": case_id,
        "keywords": [],
        "status": "open",
        "summary": "",
        "last_update": _now_iso(),
        "evidence_links": [],
    }


# ---------------------------------------------------------------------------
# Public API – case management
# ---------------------------------------------------------------------------

def load_cases() -> dict:
    """
    Load all cases from cases.json.

    Returns
    -------
    dict
        Mapping of case_id -> case record.  Empty dict if the file does not
        exist yet.
    """
    return _load_raw()


def get_case(case_id: str) -> Optional[dict]:
    """
    Retrieve a single case by ID.

    Returns ``None`` if the case does not exist.
    """
    return load_cases().get(case_id)


def save_case(case: dict) -> dict:
    """
    Upsert *case* into cases.json.

    The record must contain at least a ``case_id`` key.  ``last_update`` is
    refreshed automatically before writing.

    Returns
    -------
    dict
        The saved case record.
    """
    if "case_id" not in case:
        raise ValueError("case record must contain a 'case_id' key")

    data = _load_raw()
    case["last_update"] = _now_iso()
    data[case["case_id"]] = case
    _save_raw(data)
    return case


def create_case(
    case_id: str,
    keywords: Optional[list] = None,
    status: str = "open",
    summary: str = "",
    evidence_links: Optional[list] = None,
) -> dict:
    """
    Create a new case record and persist it.

    If a case with the same *case_id* already exists it is returned as-is
    without modification.

    Parameters
    ----------
    case_id : str
        Unique identifier for the case.
    keywords : list[str], optional
        Search keywords associated with the case.
    status : str
        Workflow status, e.g. ``"open"``, ``"in_review"``, ``"closed"``.
    summary : str
        Free-text clinical summary.
    evidence_links : list[str], optional
        PubMed (or other) URLs gathered for this case.

    Returns
    -------
    dict
        The newly created (or pre-existing) case record.
    """
    data = _load_raw()
    if case_id in data:
        return data[case_id]

    record = _empty_case(case_id)
    record["keywords"] = keywords or []
    record["status"] = status
    record["summary"] = summary
    record["evidence_links"] = evidence_links or []

    data[case_id] = record
    _save_raw(data)
    return record


def update_case_field(case_id: str, field: str, value) -> dict:
    """
    Update a single field on an existing case.

    Raises
    ------
    KeyError
        If *case_id* does not exist in cases.json.
    """
    data = _load_raw()
    if case_id not in data:
        raise KeyError(f"Case '{case_id}' not found in cases.json")

    data[case_id][field] = value
    data[case_id]["last_update"] = _now_iso()
    _save_raw(data)
    return data[case_id]


def append_evidence_link(case_id: str, url: str) -> dict:
    """
    Add *url* to the ``evidence_links`` list of a case (no duplicates).

    Raises
    ------
    KeyError
        If *case_id* does not exist.
    """
    data = _load_raw()
    if case_id not in data:
        raise KeyError(f"Case '{case_id}' not found in cases.json")

    links: list = data[case_id].setdefault("evidence_links", [])
    if url not in links:
        links.append(url)
        data[case_id]["last_update"] = _now_iso()
        _save_raw(data)

    return data[case_id]


def delete_case(case_id: str) -> bool:
    """
    Remove a case from cases.json.

    Returns ``True`` if the case was found and deleted, ``False`` otherwise.
    """
    data = _load_raw()
    if case_id not in data:
        return False
    del data[case_id]
    _save_raw(data)
    return True


# ---------------------------------------------------------------------------
# Public API – minutes
# ---------------------------------------------------------------------------

def append_minutes(case_id: str, content: str, author: str = "") -> Path:
    """
    Append *content* to the Markdown minutes file for *case_id*.

    The file is located at ``minutes/<case_id>.md`` (relative to this
    module).  It is created if it does not exist.  Each call appends a
    timestamped block so the file grows as a chronological log.

    Parameters
    ----------
    case_id : str
        Identifies which case the minutes belong to.
    content : str
        The minutes text to append (plain text or Markdown).
    author : str, optional
        Name or identifier of the person recording the minutes.

    Returns
    -------
    Path
        Absolute path to the updated minutes file.
    """
    MINUTES_DIR.mkdir(parents=True, exist_ok=True)
    minutes_file = MINUTES_DIR / f"{case_id}.md"

    timestamp = _now_iso()
    author_line = f"**Author:** {author}  \n" if author else ""

    block = (
        f"\n---\n\n"
        f"## Minutes – {timestamp}\n\n"
        f"{author_line}"
        f"{content.strip()}\n"
    )

    with open(minutes_file, "a", encoding="utf-8") as fh:
        fh.write(block)

    return minutes_file.resolve()
