"""
cron_refine.py
--------------
72-hour refinement cycle for the Clinical Intelligence Node.

Run this script on a schedule (e.g., via cron or Task Scheduler every 72 h).

Logic
-----
1. Load all cases with status "active".
2. Re-query PubMed using each case's keywords.
3. Compare new article titles against existing minute content.
4. If contradicting new evidence is found:
   - Flag the case as "needs_review".
   - Append a "Dissenting Opinion" block to its minutes file.
"""

import json
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from openai import OpenAI
import os

import pubmed_client
import state_manager

load_dotenv()

_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

LOOKBACK_HOURS = 72
MIN_NEW_ARTICLES = 1  # minimum new articles needed to trigger GPT contradiction check

_REFINE_STATE_FILE = state_manager.BASE_DIR / ".refine_state.json"


def _record_run() -> None:
    """Persist the current UTC timestamp as the last refinement run time."""
    payload = {"last_run": datetime.now(timezone.utc).isoformat()}
    _REFINE_STATE_FILE.write_text(json.dumps(payload), encoding="utf-8")


def get_last_run() -> str | None:
    """Return the ISO timestamp of the last refinement run, or None."""
    if _REFINE_STATE_FILE.exists():
        try:
            return json.loads(_REFINE_STATE_FILE.read_text(encoding="utf-8")).get("last_run")
        except (json.JSONDecodeError, KeyError):
            return None
    return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_active_cases() -> dict:
    """Return cases whose status is 'active'."""
    return {
        cid: case
        for cid, case in state_manager.load_cases().items()
        if (case.get("status") or "").lower() == "active"
    }


def _load_minutes_text(case_id: str) -> str:
    """Return the text of an existing minutes file, or empty string."""
    minutes_path = state_manager.MINUTES_DIR / f"{case_id}.md"
    if minutes_path.exists():
        return minutes_path.read_text(encoding="utf-8")
    return ""


def _fetch_new_evidence(keywords: list) -> list:
    """Re-query PubMed using case keywords. Returns article list."""
    if not keywords:
        return []
    query = " ".join(keywords[:6])
    try:
        articles = pubmed_client.search_clinical_evidence(query, max_results=10)
        if not articles:
            articles = pubmed_client.search_case_studies(query, max_results=10)
        return articles
    except RuntimeError as exc:
        print(f"  PubMed query failed: {exc}", file=sys.stderr)
        return []


def _find_new_articles(case: dict, fresh_articles: list) -> list:
    """Return articles whose PubMed URL is not already in evidence_links."""
    existing_urls = set(case.get("evidence_links") or [])
    return [a for a in fresh_articles if a.get("url") not in existing_urls]


def _check_contradiction(minutes_text: str, new_articles: list) -> tuple[bool, str]:
    """
    Use GPT-4o to determine if new articles contradict the recorded minutes.

    Returns (is_contradiction: bool, dissent_text: str).
    """
    abstract_block = "\n\n".join(
        f"[{i+1}] {a['title']} ({a.get('year','')}, {a.get('journal','')})\n"
        f"Abstract: {(a.get('abstract') or '')[:400]}"
        for i, a in enumerate(new_articles[:6], 0)
    )

    system_prompt = (
        "You are a senior clinical evidence auditor. "
        "Your task is to compare new PubMed articles against recorded M&M minutes "
        "and determine if the new evidence contradicts or substantially updates "
        "the existing clinical conclusions. "
        "Return JSON with keys: "
        "contradiction (bool), "
        "dissenting_opinion (str — formal Markdown text, empty string if no contradiction)."
    )

    user_prompt = (
        f"Existing M&M Minutes (excerpt):\n"
        f"{minutes_text[-3000:]}\n\n"
        f"New PubMed Articles:\n{abstract_block}\n\n"
        "Does the new evidence contradict or substantially revise the existing conclusions? "
        "Return JSON."
    )

    try:
        response = _client.chat.completions.create(
            model="gpt-4o",
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        result = json.loads(response.choices[0].message.content)
        contradiction = bool(result.get("contradiction", False))
        dissent = str(result.get("dissenting_opinion", ""))
        return contradiction, dissent
    except Exception as exc:
        print(f"  GPT contradiction check failed: {exc}", file=sys.stderr)
        return False, ""


def _flag_needs_review(case_id: str, new_articles: list, dissent_text: str) -> None:
    """Update case status and append dissenting opinion to minutes."""
    state_manager.update_case_field(case_id, "status", "needs_review")

    for article in new_articles:
        url = article.get("url")
        if url:
            state_manager.append_evidence_link(case_id, url)

    timestamp = datetime.now(timezone.utc).isoformat()
    dissent_block = (
        f"## Dissenting Opinion — {timestamp}\n\n"
        f"> **AUTOMATED 72-HOUR REVIEW:** New evidence was found that may "
        f"contradict or substantially update prior conclusions.\n\n"
        f"{dissent_text}\n\n"
        f"**New Articles Flagged:**\n"
        + "\n".join(
            f"- [{a['title']}]({a.get('url', '')})"
            f" ({a.get('year','')}, {a.get('journal','')})"
            for a in new_articles
        )
    )

    state_manager.append_minutes(
        case_id=case_id,
        content=dissent_block,
        author="cron_refine.py (automated)",
    )

    print(f"  Flagged as NEEDS REVIEW. Dissenting opinion appended.")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def refine_all_cases() -> None:
    """
    Run the 72-hour refinement cycle across all active cases.

    Prints a summary of actions taken to stdout.
    """
    active_cases = _get_active_cases()
    timestamp = datetime.now(timezone.utc).isoformat()

    _record_run()
    print(f"\n=== cron_refine.py | {timestamp} ===")
    print(f"Active cases found: {len(active_cases)}\n")

    if not active_cases:
        print("Nothing to refine.")
        return

    flagged = 0
    skipped = 0

    for case_id, case in active_cases.items():
        print(f"Processing: {case_id}")
        keywords = case.get("keywords") or []

        if not keywords:
            summary = case.get("summary", "")
            keywords = [w for w in summary.split() if len(w) > 4][:6]

        if not keywords:
            print("  No keywords. Skipping.")
            skipped += 1
            continue

        fresh_articles = _fetch_new_evidence(keywords)
        if not fresh_articles:
            print("  No articles returned from PubMed. Skipping.")
            skipped += 1
            continue

        new_articles = _find_new_articles(case, fresh_articles)
        print(f"  New articles found: {len(new_articles)}")

        if len(new_articles) < MIN_NEW_ARTICLES:
            print("  No new evidence. No changes.")
            skipped += 1
            continue

        minutes_text = _load_minutes_text(case_id)
        if not minutes_text:
            print("  No existing minutes to compare against. Skipping contradiction check.")
            skipped += 1
            continue

        contradiction, dissent_text = _check_contradiction(minutes_text, new_articles)

        if contradiction:
            _flag_needs_review(case_id, new_articles, dissent_text)
            flagged += 1
        else:
            print("  No contradiction detected. Case remains Active.")
            skipped += 1

    print(f"\n--- Summary ---")
    print(f"Flagged NEEDS REVIEW : {flagged}")
    print(f"No change            : {skipped}")
    print(f"=================\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    refine_all_cases()
