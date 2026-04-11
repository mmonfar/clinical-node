CLAUDE.md | Clinical Intelligence Node Manifest

1\. Context \& Objectives

Build a Multi-Agent M\&M Committee. Analyze clinical cases against tiered medical evidence. Ensure auditability for governance.



Root: C:\\Users\\marti\\Python\_Projects\\clinical-node



Existing: state\_manager.py, pubmed\_client.py, .env, /minutes/.



Target: clinical\_engine.py, app.py, cron\_refine.py.



2\. Multi-Agent Logic (clinical\_engine.py)

Implement a virtual HOD committee (ICU, ED, Surgery, Medicine).



The Researcher (Temp 0.0): Tiered search logic. Prioritize RCT/Meta-analysis. If rare, descend to case studies. Perform "deep-dive" synthesis of abstracts and available full-text metadata.



The Risk Manager (Temp 0.2): Collaborative HOD persona. Identify loopholes. Cross-reference surgical/medical subspecialties. Highlight caveats and limitations.



The Auditor (Temp 0.0): Minutes lead. Map discussions to cases.json. Record rationale, conclusions, and recommendations.



3\. Frontend Architecture (app.py)

Aesthetic: Premium Medical (Cleveland Clinic/Mayo style).



Style: High-contrast blue/gray palette. Clean sans-serif. Professional whitespace.



Features:



Sidebar: Case Registry. Status: Active/Needs Review.



Main: SBAR Input Area.



Tabs: \[Executive Summary], \[Committee Discussion], \[Tiered Evidence], \[Audit Trail].



QA: Delete dead code. Verify relative paths. Use Custom CSS for the medical look.



4\. 72-Hour Refinement Logic (cron\_refine.py)

Cycle: Every 72 hours.



Task: Scan Active cases. Re-query PubMed for higher-impact articles.



Logic: Compare new evidence to existing minutes. If contradiction exists, flag as NEEDS REVIEW. Append "Dissenting Opinion" to Markdown.



Task Instructions for Claude Code

Phase 1: Audit



Read state\_manager.py and pubmed\_client.py.



Do not rewrite them. Extend functionality only.



Phase 2: Backend Development



Create clinical\_engine.py.



Use GPT-4o for the HOD committee loop.



Ensure JSON output includes: rationale, caveats, limitations, recommendations.



Phase 3: Frontend Development



Create app.py.



Implement custom Streamlit CSS for the "Mayo Clinic" aesthetic.



Ensure the Auditor agent pushes to /minutes and updates the JSON registry.



Phase 4: Refinement Logic



Create cron\_refine.py.



Implement the 72-hour lookback logic.



Use state\_manager to handle the file updates.



Phase 5: Production Cleanup



Run linting.



Remove unused variables.



Verify all links are clickable.



Formatting Constraints

Short sentences only.



No preamble.



Result first.



No em-dashes.



Standard grammar only.



Think before acting.

