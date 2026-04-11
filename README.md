# Clinical Intelligence Node

A multi-agent virtual M&M (Morbidity & Mortality) Committee platform.
Analyses clinical cases against tiered medical evidence. Produces structured MDT minutes with full audit trails.

---

## ⚠️ Disclaimer

**All clinical cases used in development, testing, and demonstration of this platform are entirely fictional.**
They were created solely to test software functionality and do not represent any real patient, clinical encounter, or medical record.
No real patient data has been used or stored at any point.

This tool is **not a substitute for clinical judgement**. It is a decision-support aid intended to augment, not replace, qualified medical professionals.
Always involve appropriate clinical specialists before acting on any output.

---

## Architecture

Three LLM agents collaborate on each case:

| Agent | Model | Temp | Role |
|---|---|---|---|
| Researcher | gpt-4o-mini | 0.0 | PubMed multi-pillar evidence search + synthesis |
| MDT Roundtable | gpt-4o | 0.25 | 360° specialist debate, gap-finding, risk heatmap |
| Auditor | gpt-4o-mini | 0.0 | Formal Markdown M&M minutes + audit trail |

### Evidence Ladder

1. RCT / Meta-analysis / Systematic Review
2. Practice Guidelines (NCCN / AHA / ESC / ESMO / NICE / WHO)
3. Clinical Trial / Observational Study
4. Case Reports *(rare/emerging conditions only)*

When an initial query returns fewer than 2 results the Researcher automatically triggers **Multi-Pillar decomposition**:

- **Pillar A — The Conflict:** intersection of the two main complications
- **Pillar B — The Guidelines:** primary life-threat guideline search
- **Pillar C — The Procedure:** interventional / procedural evidence

---

## Features

- Free-text or SBAR case input via chat interface
- Dynamic MDT panel selection from 25+ specialties
- Mandatory invitee list (force any specialist into the roundtable)
- Risk Heatmap (High / Medium / Low per clinical risk)
- Critical Information Gap banner
- Evidence Matrix tab with clickable PubMed links
- Formal M&M minutes with versioned audit trail
- 72-hour automated refinement cycle with contradiction detection
- EPR copy-paste buffer + Markdown download

---

## Setup

### 1. Clone

```bash
git clone https://github.com/your-username/clinical-node.git
cd clinical-node
```

### 2. Create virtual environment

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure credentials

```bash
cp .env.example .env
```

Edit `.env` and add your keys:

| Variable | Source |
|---|---|
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com/api-keys) |
| `ENTREZ_EMAIL` | Your email — required by NCBI |
| `ENTREZ_API_KEY` | [NCBI account](https://www.ncbi.nlm.nih.gov/account/) — optional, raises rate limit to 10 req/s |

### 5. Run

```bash
streamlit run app.py
```

---

## Project Structure

```
clinical-node/
├── app.py                  # Streamlit frontend
├── clinical_engine.py      # Multi-agent MDT pipeline
├── pubmed_client.py        # PubMed / Entrez search client
├── cron_refine.py          # 72-hour refinement cycle
├── state_manager.py        # cases.json CRUD + minutes persistence
├── .streamlit/
│   └── config.toml         # Theme (light, Mayo Clinic palette)
├── .env.example            # Credential template
├── requirements.txt
└── README.md
```

**Runtime directories (gitignored):**

```
minutes/        # Generated M&M minutes (Markdown, one file per case)
cases.json      # Case registry (created on first run)
.refine_state.json  # Refinement cycle timestamp
```

---

## 72-Hour Refinement

Run manually from the sidebar or on a schedule:

```bash
# Windows Task Scheduler / cron
python cron_refine.py
```

When new PubMed evidence contradicts recorded minutes, the case is flagged **Needs Review** and a Dissenting Opinion is appended to its minutes.

---

## Infosec Notes

- `.env` is gitignored. Never commit API keys.
- `cases.json` and `minutes/` are gitignored. No case data is tracked in version control.
- No data is sent anywhere other than the OpenAI API and NCBI Entrez API.
- No authentication layer is included. Do not expose this app on a public URL without adding one.

---

## License

MIT
