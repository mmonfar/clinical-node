"""
clinical_engine.py
------------------
Virtual 360-Degree MDT Committee.

Models
------
Researcher       gpt-4o-mini  temp=0.0   PubMed query extraction + synthesis.
MDT Roundtable   gpt-4o       temp=0.25  Transcript-style HOD debate + gap-finder.
Auditor          gpt-4o-mini  temp=0.0   Formal minutes with MDT & gap sections.
"""

import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from openai import OpenAI

import pubmed_client
import state_manager

load_dotenv()

_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

RARE_THRESHOLD = 3
PUBMED_MAX_RESULTS = 5
MULTI_PILLAR_THRESHOLD = 2   # trigger pillar decomposition when initial query < this


# ---------------------------------------------------------------------------
# Specialty Library — single source of truth for all MDT selection
# ---------------------------------------------------------------------------

MDT_SPECIALTIES: dict[str, list[str]] = {
    "Surgical": [
        "Orthopedic Surgery",
        "Cardiothoracic Surgery",
        "Vascular Surgery",
        "Neurosurgery",
        "General / Trauma Surgery",
        "Pediatric Surgery",
        "Plastic & Reconstructive Surgery",
        "Urology",
        "OB-GYN",
        "ENT",
        "Maxillofacial Surgery",
        "Surgical Oncology",
    ],
    "Medical": [
        "Cardiology",
        "Nephrology / Renal Transplant",
        "Gastroenterology",
        "Pulmonology",
        "Endocrinology",
        "Hematology",
        "Infectious Disease",
        "Neurology",
        "Rheumatology",
        "Medical Oncology",
        "Radiation Oncology",
        "Geriatrics",
        "Palliative Care",
    ],
    "Support / Critical Care": [
        "ICU / Intensivist",
        "Emergency Medicine",
        "Anesthesia",
        "Radiology / Interventional Radiology",
        "Pathology",
        "Clinical Pharmacy",
    ],
}

# Flat list for sidebar multiselect
ALL_SPECIALTIES: list[str] = [
    spec for group in MDT_SPECIALTIES.values() for spec in group
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _format_abstracts(articles: list) -> str:
    blocks = []
    for i, a in enumerate(articles, 1):
        preview = (a.get("abstract") or "")[:400]
        if len(a.get("abstract", "")) > 400:
            preview += "..."
        blocks.append(
            f"[{i}] {a.get('title', '')} ({a.get('year', '')}, {a.get('journal', '')})\n"
            f"Abstract: {preview}"
        )
    return "\n\n".join(blocks)


def _build_ref_list(articles: list) -> str:
    """Build numbered reference string with real PubMed URLs."""
    if not articles:
        return "No articles retrieved."
    return "\n".join(
        f"[{i}] {a.get('title', 'Untitled')} "
        f"({a.get('year', '')}, {a.get('journal', '')}) — {a.get('url', '')}"
        for i, a in enumerate(articles, 1)
    )


def _dedup_articles(lists: list[list]) -> list:
    """Merge multiple article lists, deduplicating by PMID. Preserves order."""
    seen: set[str] = set()
    merged: list[dict] = []
    for lst in lists:
        for a in lst:
            pmid = a.get("pmid", "")
            if pmid and pmid not in seen:
                seen.add(pmid)
                merged.append(a)
    return merged


def _extract_keywords(sbar: dict) -> list:
    text = " ".join([
        sbar.get("situation", ""),
        sbar.get("background", ""),
        sbar.get("assessment", ""),
    ])
    words = [w.strip(".,;:()[]\"'") for w in text.split() if len(w) > 4]
    return list(dict.fromkeys(words))[:10]


# ---------------------------------------------------------------------------
# Public: SBAR parser
# ---------------------------------------------------------------------------

def parse_sbar_from_text(text: str) -> dict:
    """
    Extract SBAR fields from free-text clinical input using gpt-4o-mini.

    Returns dict: situation, background, assessment, recommendation.
    """
    response = _client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Extract SBAR components from a clinical case description. "
                    "Return JSON with keys: situation (str), background (str), "
                    "assessment (str), recommendation (str). "
                    "Infer missing fields from context. Never leave all fields empty."
                ),
            },
            {"role": "user", "content": text},
        ],
    )
    return json.loads(response.choices[0].message.content)


# ---------------------------------------------------------------------------
# Public: PubMed query builder
# ---------------------------------------------------------------------------

def build_pubmed_query(sbar: dict) -> str:
    """
    Extract focused MeSH-compatible clinical search terms from SBAR using gpt-4o-mini.

    Returns a concise Boolean PubMed query string (5-8 terms max).
    """
    combined = " | ".join(filter(None, [
        sbar.get("situation", ""),
        sbar.get("background", ""),
        sbar.get("assessment", ""),
    ]))

    response = _client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.0,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a PubMed search specialist. "
                    "Extract 5-8 focused MeSH-compatible clinical search terms from a case description. "
                    "Return ONLY the search string, no explanation. "
                    "Use AND/OR operators where helpful. "
                    "Example: 'femoral neck fracture AND hemiarthroplasty AND anticoagulation'"
                ),
            },
            {"role": "user", "content": combined},
        ],
    )
    return response.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Public: Pillar query decomposition
# ---------------------------------------------------------------------------

def build_pillar_queries(sbar: dict, initial_query: str) -> dict:
    """
    Decompose a complex case into three focused PubMed evidence pillars.

    Pillar A — The Conflict:   intersection of the two main complications.
    Pillar B — The Guidelines: primary life-threat guideline search.
    Pillar C — The Procedure:  interventional / procedural approach evidence.

    Returns dict with keys pillar_a, pillar_b, pillar_c, each containing
    ``label`` (str) and ``query`` (str).
    """
    combined = " | ".join(filter(None, [
        sbar.get("situation", ""),
        sbar.get("assessment", ""),
    ]))
    response = _client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a clinical librarian. Decompose a complex clinical case "
                    "into three PubMed evidence pillars.\n"
                    "Pillar A — The Conflict: intersection of the two main competing "
                    "complications or drug-disease conflicts (e.g., 'mesenteric ischemia AND DAPT').\n"
                    "Pillar B — The Guidelines: primary life-threat focused guideline query "
                    "(e.g., 'acute mesenteric ischemia management guidelines').\n"
                    "Pillar C — The Procedure / Middle Path: evidence for the key procedural "
                    "or interventional approach (e.g., 'interventional radiology mesenteric ischemia').\n"
                    "Each query must be concise, MeSH-compatible, and Boolean where helpful.\n"
                    "Return JSON: {\"pillar_a\": {\"label\": str, \"query\": str}, "
                    "\"pillar_b\": {\"label\": str, \"query\": str}, "
                    "\"pillar_c\": {\"label\": str, \"query\": str}}"
                ),
            },
            {
                "role": "user",
                "content": f"Initial query: {initial_query}\nCase: {combined}",
            },
        ],
    )
    return json.loads(response.choices[0].message.content)


# ---------------------------------------------------------------------------
# Internal: multi-pillar search engine
# ---------------------------------------------------------------------------

_PILLAR_META = {
    "A": {"display": "🥇 Gold — Conflict Intersection",    "tier_label": "Conflict"},
    "B": {"display": "🧭 Compass — Primary Guidelines",    "tier_label": "Guidelines"},
    "C": {"display": "📋 Context — Procedural Evidence",   "tier_label": "Procedure"},
}


def _search_pillar(pquery: str, pid: str) -> tuple[list, str]:
    """
    Search one pillar. Returns (articles, tier_label).
    Tries Tier 1, then mid-tier, then case reports.
    """
    arts = pubmed_client.search_clinical_evidence(pquery, max_results=PUBMED_MAX_RESULTS)
    if arts:
        return arts, "RCT / Meta-analysis / Systematic Review"

    # Pillar B — also try explicit practice guideline filter
    if pid == "B":
        guideline_q = f"({pquery}) AND (Practice Guideline[pt] OR guideline[ti])"
        arts = pubmed_client.search_clinical_evidence(guideline_q, max_results=PUBMED_MAX_RESULTS)
        if arts:
            return arts, "Practice Guidelines"

    arts = pubmed_client.search_mid_tier_evidence(pquery, max_results=PUBMED_MAX_RESULTS)
    if arts:
        return arts, "Clinical Trial / Observational Study"

    arts = pubmed_client.search_case_studies(pquery, max_results=3)
    return arts, "Case Reports"


def _multi_pillar_search(initial_query: str, sbar: dict) -> dict:
    """
    Decompose case into 3 evidence pillars (A/B/C), search each independently,
    de-duplicate by PMID, and return a structured multi-pillar result.
    """
    pillar_queries = build_pillar_queries(sbar, initial_query)

    pillar_configs = [
        ("A", pillar_queries.get("pillar_a", {})),
        ("B", pillar_queries.get("pillar_b", {})),
        ("C", pillar_queries.get("pillar_c", {})),
    ]

    seen_pmids: set[str] = set()
    all_articles: list[dict] = []
    pillars: list[dict] = []

    for pid, pconf in pillar_configs:
        meta    = _PILLAR_META[pid]
        pquery  = pconf.get("query", "").strip()
        plabel  = pconf.get("label", meta["display"])

        if not pquery:
            pillars.append({
                "id": pid, "display": meta["display"], "label": plabel,
                "query": "", "tier": "No query generated", "articles": [],
            })
            continue

        arts, p_tier = _search_pillar(pquery, pid)

        # Deduplicate — only add articles not seen in earlier pillars
        unique: list[dict] = []
        for a in arts:
            pmid = a.get("pmid", "")
            if pmid and pmid not in seen_pmids:
                seen_pmids.add(pmid)
                all_articles.append(a)
                unique.append(a)

        pillars.append({
            "id":       pid,
            "display":  meta["display"],
            "label":    plabel,
            "query":    pquery,
            "tier":     p_tier,
            "articles": unique,
        })

    return {
        "tier":           "Multi-Pillar Evidence Matrix",
        "articles":       all_articles,
        "query":          initial_query,
        "is_multi_pillar": True,
        "pillars":        pillars,
    }


# ---------------------------------------------------------------------------
# Public: Researcher step
# ---------------------------------------------------------------------------

def researcher_search(query: str, sbar: dict | None = None) -> dict:
    """
    Evidence search with automatic multi-pillar fallback.

    Standard path (returns >= MULTI_PILLAR_THRESHOLD results):
      Tier 1  — RCT / Meta-analysis / Systematic Review / Practice Guideline
      Tier 1b — Society Consensus (NCCN / AHA / ESC / ESMO / NICE / WHO)
      Tier 2  — Clinical Trial / Observational Study
      Tier 3  — Case Reports

    Multi-pillar path (initial query returns < MULTI_PILLAR_THRESHOLD):
      Decomposes case into Pillar A (Conflict), B (Guidelines), C (Procedure).
      Runs each independently and de-duplicates by PMID.

    All result dicts include: tier, articles, query, is_multi_pillar, pillars.
    """
    _single = lambda tier, arts, q: {
        "tier": tier, "articles": arts, "query": q,
        "is_multi_pillar": False, "pillars": [],
    }

    # Tier 1 — highest quality
    high = pubmed_client.search_clinical_evidence(query, max_results=PUBMED_MAX_RESULTS)
    if len(high) >= RARE_THRESHOLD:
        return _single("RCT / Meta-analysis / Systematic Review", high, query)

    # Trigger multi-pillar when initial query returns too few results
    if len(high) < MULTI_PILLAR_THRESHOLD and sbar is not None:
        return _multi_pillar_search(query, sbar)

    # Tier 1b — guideline anchor: pivot to society consensus when RCTs scarce
    society_terms = "(NCCN OR AHA OR ESC OR ESMO OR NICE OR WHO OR consensus)"
    anchored_query = f"({query}) AND {society_terms}"
    anchored = pubmed_client.search_clinical_evidence(
        anchored_query, max_results=PUBMED_MAX_RESULTS
    )
    if len(anchored) >= RARE_THRESHOLD:
        return _single("Practice Guidelines (Society Consensus)", anchored, anchored_query)

    # Tier 2 — intermediate evidence
    mid = pubmed_client.search_mid_tier_evidence(query, max_results=PUBMED_MAX_RESULTS)
    if len(mid) >= RARE_THRESHOLD:
        return _single("Clinical Trial / Observational Study", mid, query)

    # Tier 3 — case reports
    cases = pubmed_client.search_case_studies(query, max_results=PUBMED_MAX_RESULTS)
    return _single("Case Reports (rare condition)", cases, query)


def researcher_synthesize(sbar: dict, evidence: dict) -> str:
    """
    Synthesize PubMed abstracts into a structured evidence summary (gpt-4o-mini).

    For multi-pillar results, groups abstracts by pillar and mandates an explicit
    pillar gap statement in the synthesis.
    """
    tier        = evidence.get("tier", "")
    is_multi    = evidence.get("is_multi_pillar", False)
    pillars     = evidence.get("pillars", [])

    if is_multi and pillars:
        # Build abstract block grouped by pillar
        blocks: list[str] = []
        ref_num = 1
        pillar_summary: list[str] = []
        for p in pillars:
            p_arts  = p.get("articles", [])
            display = p.get("display", "")
            pquery  = p.get("query", "")
            blocks.append(f"\n=== {display} (Query: {pquery}) ===")
            if p_arts:
                for a in p_arts:
                    preview = (a.get("abstract") or "")[:350]
                    blocks.append(
                        f"[{ref_num}] {a.get('title','')} "
                        f"({a.get('year','')}, {a.get('journal','')})\n{preview}"
                    )
                    ref_num += 1
                pillar_summary.append(f"{display}: {len(p_arts)} article(s) — {p.get('tier','')}")
            else:
                blocks.append("⚠️ No articles retrieved for this pillar.")
                pillar_summary.append(f"{display}: EMPTY")

        abstract_block = "\n\n".join(blocks)

        # Identify strongest and gap pillars for the mandatory statement
        non_empty  = [p["display"] for p in pillars if p.get("articles")]
        empty      = [p["display"] for p in pillars if not p.get("articles")]
        strongest  = non_empty[0] if non_empty else "none"
        gap_names  = " and ".join(empty) if empty else "other pillars"
        gap_clause = (
            f"Evidence is strongest for {strongest} but remains a gap "
            f"for the intersection of {gap_names}."
        )
        pillar_instruction = (
            "\n\nCRITICAL — this is a multi-pillar evidence matrix. "
            "You MUST include this exact gap statement (adapted to the content): "
            f"'{gap_clause}'"
        )
    else:
        abstract_block   = _format_abstracts(evidence.get("articles", []))
        pillar_instruction = ""

    response = _client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.0,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are the Researcher on a virtual HOD M&M committee. "
                    "Synthesize clinical evidence concisely. "
                    "Sections: Key Findings | Level of Evidence | Relevance to Case | Evidence Gaps. "
                    "Cite articles by number in brackets [1][2]. No preamble."
                    + pillar_instruction
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Situation: {sbar.get('situation', '')}\n"
                    f"Assessment: {sbar.get('assessment', '')}\n\n"
                    f"Evidence Tier: {tier}\n\n"
                    f"Articles:\n{abstract_block}\n\n"
                    "Produce the evidence synthesis."
                ),
            },
        ],
    )
    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# Public: MDT Roundtable (replaces single Risk Manager)
# ---------------------------------------------------------------------------

def mdt_roundtable_review(
    sbar: dict,
    synthesis: str,
    ref_list: str,
    invited_specialists: list[str] | None = None,
) -> dict:
    """
    360-degree MDT roundtable with transcript-style HOD friction protocol.

    Dynamically selects 4-5 relevant specialists plus any invited ones.
    Each HOD argues from their departmental priority.
    Conflicts are categorised as Systemic Gaps.

    Returns JSON with keys:
      selected_specialists, roundtable, conflicts, critical_info_missing,
      risk_heatmap, rationale, caveats, limitations, recommendations,
      subspecialty_flags, final_recommendation.
    """
    invited_clause = (
        f"\nMANDATORY INVITEES — include these regardless of case type: "
        f"{', '.join(invited_specialists)}"
        if invited_specialists
        else ""
    )

    specialty_catalogue = json.dumps(MDT_SPECIALTIES, indent=2)

    response = _client.chat.completions.create(
        model="gpt-4o",
        temperature=0.25,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are the MDT Coordinator for a 360-degree virtual M&M Roundtable.\n\n"
                    f"Available specialties:\n{specialty_catalogue}\n"
                    f"{invited_clause}\n\n"
                    "INSTRUCTIONS:\n"
                    "1. SELECT the 4-5 most clinically relevant specialists for this case "
                    "(plus any mandatory invitees).\n"
                    "2. Generate a TRANSCRIPT. Each specialist:\n"
                    "   - States their departmental PRIORITY (what they care about most).\n"
                    "   - Makes a clinical STATEMENT arguing from that priority.\n"
                    "   - Every clinical claim MUST cite [number] from the reference list.\n"
                    "   - States a clear POSITION on the management plan.\n"
                    "3. Identify CONFLICTS where specialist priorities clash. "
                    "Label each as a Systemic Gap with the parties and description.\n"
                    "4. List CRITICAL INFORMATION MISSING that would change management "
                    "(e.g., TNM staging, ECOG PS, weight for CrCl, specific imaging, "
                    "coagulation studies, genomic markers).\n"
                    "5. Build a RISK HEATMAP: identify 3-6 specific clinical risks and "
                    "rate each as High / Medium / Low based on the MDT discussion.\n"
                    "6. Apply MANDATORY CLINICAL CHECKS:\n"
                    "   - REVERSAL AGENTS: For bleeding/surgical urgency — "
                    "Warfarin→4F-PCC+VitK, Dabigatran→Idarucizumab, "
                    "FXa inhibitors→Andexanet alfa/4F-PCC, NMB→Sugammadex.\n"
                    "   - RENAL DOSING: eGFR insufficient. Require CrCl (Cockcroft-Gault). "
                    "Flag CrCl<30 as contraindication, 30-50 as dose-adjustment.\n"
                    "7. Provide a FINAL CONSOLIDATED RECOMMENDATION from the committee chair.\n\n"
                    "Return ONLY valid JSON with keys:\n"
                    "  selected_specialists (list[str]),\n"
                    "  roundtable (list[{specialist:str, priority:str, statement:str, "
                    "citations:list[int], position:str}]),\n"
                    "  conflicts (list[{parties:list[str], issue:str, description:str}]),\n"
                    "  critical_info_missing (list[str]),\n"
                    "  risk_heatmap (dict[str, 'High'|'Medium'|'Low']),\n"
                    "  rationale (str),\n"
                    "  caveats (list[str]),\n"
                    "  limitations (list[str]),\n"
                    "  recommendations (list[str]),\n"
                    "  subspecialty_flags (list[str]),\n"
                    "  final_recommendation (str)"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"SBAR:\n"
                    f"S: {sbar.get('situation', '')}\n"
                    f"B: {sbar.get('background', '')}\n"
                    f"A: {sbar.get('assessment', '')}\n"
                    f"R: {sbar.get('recommendation', '')}\n\n"
                    f"Evidence Synthesis:\n{synthesis}\n\n"
                    f"Reference List (cite by number):\n{ref_list}\n\n"
                    "Conduct the MDT roundtable."
                ),
            },
        ],
    )
    return json.loads(response.choices[0].message.content)


# Backward-compatible alias
def risk_manager_review(
    sbar: dict,
    synthesis: str,
    ref_list: str = "",
    invited_specialists: list[str] | None = None,
) -> dict:
    """Alias for mdt_roundtable_review. Maintained for backward compatibility."""
    return mdt_roundtable_review(sbar, synthesis, ref_list, invited_specialists)


# ---------------------------------------------------------------------------
# Public: Auditor step
# ---------------------------------------------------------------------------

def auditor_record(case_id: str, output: dict) -> str:
    """
    Write formal Markdown minutes and persist case to cases.json.

    Includes:
      - ## ⚠️ CRITICAL INFORMATION GAP banner (if applicable)
      - ## Multidisciplinary Discussion transcript
      - ## Systemic Gaps section
      - ## References with real PubMed URLs
    Returns the minutes text.
    """
    mdt = output.get("risk_analysis", {})
    sbar = output.get("sbar", {})
    tier = output.get("evidence", {}).get("tier", "")
    articles = output.get("evidence", {}).get("articles", [])

    ref_block = _build_ref_list(articles)

    # Roundtable transcript for the prompt
    roundtable = mdt.get("roundtable", [])
    roundtable_str = "\n\n".join(
        f"**{e.get('specialist', 'Unknown')}** "
        f"(Priority: {e.get('priority', '')})\n"
        f"{e.get('statement', '')}\n"
        f"Position: {e.get('position', '')} | "
        f"Cites: {e.get('citations', [])}"
        for e in roundtable
    ) or "No roundtable data."

    conflicts = mdt.get("conflicts", [])
    conflicts_str = "\n".join(
        f"- {' vs '.join(c.get('parties', []))}: {c.get('description', '')}"
        for c in conflicts
    ) or "No systemic gaps identified."

    critical_missing = mdt.get("critical_info_missing", [])
    gap_banner = (
        "⚠️ CRITICAL INFORMATION GAP: " + ", ".join(critical_missing)
        if critical_missing
        else ""
    )

    risk_heatmap = mdt.get("risk_heatmap", {})
    heatmap_str = "\n".join(
        f"- {k}: {v}" for k, v in risk_heatmap.items()
    ) or "Not assessed."

    gap_prefix = (
        "## ⚠️ CRITICAL INFORMATION GAP\n\n" + gap_banner + "\n\n"
        if gap_banner else ""
    )

    response = _client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.0,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are the Auditor on a virtual HOD M&M committee. "
                    "Produce formal structured Markdown minutes.\n\n"
                    "REQUIRED SECTIONS (in this order):\n"
                    "1. ## ⚠️ CRITICAL INFORMATION GAP — ONLY if gap_banner is non-empty; "
                    "place this at the very top before all other content.\n"
                    "2. ## Case ID & Date\n"
                    "3. ## Clinical Summary (SBAR)\n"
                    "4. ## Evidence Review (cite using [N] matching the reference list)\n"
                    "5. ## Multidisciplinary Discussion — full HOD transcript\n"
                    "6. ## Systemic Gaps — each HOD conflict explicitly listed\n"
                    "7. ## Risk Assessment — heatmap table\n"
                    "8. ## Conclusions\n"
                    "9. ## Final Recommendation\n"
                    "10. ## Action Items\n"
                    "11. ## References — every reference as: "
                    "[N] Title (Journal, Year) — URL\n\n"
                    "CRITICAL: Never use '[Article N]' or placeholder citations. "
                    "Only cite titles and URLs from the provided reference list. "
                    "Every clinical claim must map to a citation number."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"{gap_prefix}"
                    f"Case: {case_id} | Date: {output.get('timestamp', '')}\n\n"
                    f"SBAR:\n"
                    f"S: {sbar.get('situation', '')}\n"
                    f"B: {sbar.get('background', '')}\n"
                    f"A: {sbar.get('assessment', '')}\n"
                    f"R: {sbar.get('recommendation', '')}\n\n"
                    f"Evidence Tier: {tier}\n"
                    f"Evidence Synthesis:\n{output.get('researcher_synthesis', '')}\n\n"
                    f"MDT Roundtable Transcript:\n{roundtable_str}\n\n"
                    f"Systemic Gaps:\n{conflicts_str}\n\n"
                    f"Risk Heatmap:\n{heatmap_str}\n\n"
                    f"Rationale: {mdt.get('rationale', '')}\n"
                    f"Caveats: {json.dumps(mdt.get('caveats', []))}\n"
                    f"Limitations: {json.dumps(mdt.get('limitations', []))}\n"
                    f"Recommendations: {json.dumps(mdt.get('recommendations', []))}\n"
                    f"Final Recommendation: {mdt.get('final_recommendation', '')}\n\n"
                    f"Reference List (use exactly):\n{ref_block}\n\n"
                    "Produce the formal M&M minutes in Markdown."
                ),
            },
        ],
    )
    minutes_text = response.choices[0].message.content

    state_manager.append_minutes(
        case_id=case_id,
        content=minutes_text,
        author="Auditor (GPT-4o-mini)",
    )

    evidence_urls = [a["url"] for a in articles]

    existing = state_manager.get_case(case_id)
    if existing is None:
        state_manager.create_case(
            case_id=case_id,
            keywords=_extract_keywords(sbar),
            status="active",
            summary=sbar.get("situation", ""),
            evidence_links=evidence_urls,
        )
    else:
        state_manager.update_case_field(case_id, "status", "active")
        for url in evidence_urls:
            state_manager.append_evidence_link(case_id, url)

    case = state_manager.get_case(case_id)
    case["committee_output"] = output
    state_manager.save_case(case)

    return minutes_text


# ---------------------------------------------------------------------------
# Public: build output dict
# ---------------------------------------------------------------------------

def build_output(
    case_id: str,
    sbar: dict,
    evidence: dict,
    synthesis: str,
    mdt_result: dict,
    invited_specialists: list[str] | None = None,
) -> dict:
    """Assemble the full committee output dict."""
    return {
        "case_id": case_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sbar": sbar,
        "evidence": {
            "tier":            evidence.get("tier", ""),
            "article_count":   len(evidence.get("articles", [])),
            "articles":        evidence.get("articles", []),
            "query":           evidence.get("query", ""),
            "is_multi_pillar": evidence.get("is_multi_pillar", False),
            "pillars":         evidence.get("pillars", []),
        },
        "researcher_synthesis": synthesis,
        # ── Legacy flat fields (backward compat) ──
        "rationale": mdt_result.get("rationale", ""),
        "caveats": mdt_result.get("caveats", []),
        "limitations": mdt_result.get("limitations", []),
        "recommendations": mdt_result.get("recommendations", []),
        "subspecialty_flags": mdt_result.get("subspecialty_flags", []),
        # ── MDT fields ──
        "selected_specialists": mdt_result.get("selected_specialists", []),
        "invited_specialists": invited_specialists or [],
        "roundtable": mdt_result.get("roundtable", []),
        "conflicts": mdt_result.get("conflicts", []),
        "critical_info_missing": mdt_result.get("critical_info_missing", []),
        "risk_heatmap": mdt_result.get("risk_heatmap", {}),
        "final_recommendation": mdt_result.get("final_recommendation", ""),
        # ── Full result preserved for auditor ──
        "risk_analysis": mdt_result,
    }


# ---------------------------------------------------------------------------
# Convenience: full pipeline in one call
# ---------------------------------------------------------------------------

def run_committee(
    case_id: str,
    sbar: dict,
    invited_specialists: list[str] | None = None,
) -> dict:
    """
    Run the full MDT committee pipeline.

    For progressive UI with live status, call individual step functions directly.
    """
    query = build_pubmed_query(sbar)
    evidence = researcher_search(query, sbar=sbar)
    synthesis = researcher_synthesize(sbar, evidence)
    ref_list = _build_ref_list(evidence.get("articles", []))
    mdt_result = mdt_roundtable_review(sbar, synthesis, ref_list, invited_specialists)
    output = build_output(case_id, sbar, evidence, synthesis, mdt_result, invited_specialists)
    auditor_record(case_id, output)
    return output
