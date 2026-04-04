# 🔬 PharmaGuard — Multilingual Packaging & Labeling Compliance Agent

> **Hackathon Project** | Agentic AI Track | Built with Claude claude-sonnet-4-20250514

A multimodal AI agent that acts as a global pharmaceutical packaging auditor — comparing the "Source of Truth" English label against regional packaging artwork in any language.

![PharmaGuard Dashboard](./docs/screenshot.png)

---

## 🎯 The Problem

When a new safety warning or dosage update is mandated for a widely-used generic drug (like Viatris's Ibuprofen portfolio), the company must update packaging and inserts across **dozens of countries**. This involves:

- Translating medical text into 20+ languages
- Verifying that local marketing teams haven't accidentally altered the **core medical meaning**
- Reviewing PDF artwork for font size, warning placement, and regulatory symbols
- A tedious, error-prone **manual review process** taking weeks per cycle

**PharmaGuard automates this entire pipeline with two specialized AI agents.**

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        PHARMA GUARD                             │
│                   Compliance Orchestrator                        │
└────────────────────┬───────────────────┬────────────────────────┘
                     │                   │
          ┌──────────▼──────┐   ┌────────▼──────────┐
          │  Translation &   │   │   Vision Agent     │
          │  Semantic Agent  │   │  (Multimodal LLM)  │
          └──────────┬──────┘   └────────┬───────────┘
                     │                   │
          ┌──────────▼──────┐   ┌────────▼──────────┐
          │ Back-translate   │   │ PDF/Image OCR      │
          │ foreign text     │   │ + Text Extraction  │
          │                  │   │                    │
          │ Semantic compare │   │ Layout compliance  │
          │ vs. English      │   │ Font size checks   │
          │ master           │   │ Warning placement  │
          └──────────┬──────┘   └────────┬───────────┘
                     │                   │
          ┌──────────▼───────────────────▼───────────┐
          │          Compliance Report                 │
          │  • Score (0–100)                          │
          │  • Section-by-section breakdown            │
          │  • Annotated PDF with bounding boxes       │
          │  • Agent activity log                      │
          └──────────────────────────────────────────-┘
```

### Agent 1: Translation & Semantic Agent

- **Input**: Foreign-language text extracted from packaging + Master English label
- **Process**: Back-translates foreign text → English, then performs **semantic medical intent comparison** (not 1:1 word match)
- **Output**: Discrepancies, omissions, severity ratings per section
- **Key insight**: Catches subtle medical meaning drift that word-diff tools miss

### Agent 2: Vision Agent

- **Input**: Actual PDF/image of the carton artwork
- **Process**: Uses multimodal Claude to OCR the packaging AND analyze layout compliance
- **Output**: Annotated bounding boxes on the image — green (compliant) or red (flagged)
- **Checks**: Warning box placement, font hierarchy, required regulatory symbols, missing elements

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Anthropic API Key

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

uvicorn main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:3000
```

---

## 📦 Project Structure

```
pharma-guard/
├── backend/
│   ├── main.py                    # FastAPI orchestrator
│   ├── requirements.txt
│   ├── .env.example
│   └── agents/
│       ├── __init__.py
│       ├── translation_agent.py   # Back-translation + semantic comparison
│       └── vision_agent.py        # Multimodal layout + OCR analysis
│
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── main.jsx
│       ├── App.jsx                # Main dashboard shell
│       ├── styles.css             # Full dark-clinical theme
│       └── components/
│           ├── ComplianceReport.jsx  # Discrepancy cards + section chips
│           ├── PDFViewer.jsx         # Annotated packaging artwork
│           ├── AgentLog.jsx          # Real-time agent activity
│           └── UploadZone.jsx        # Drag-and-drop file upload
│
├── demo/
│   └── sample_labels/
│       └── french_label_with_issue.txt  # Sample demo data
│
└── README.md
```

---

## 🎬 Demo Flow (Hackathon Pitch)

1. **Paste** the approved master English Ibuprofen label (pre-loaded)
2. **Select** target language: French
3. **Upload** `demo/sample_labels/french_label_with_issue.txt` (or any packaging image)
4. **Click** "Run Compliance Check"
5. Watch both agents run sequentially in the **Agent Log** tab
6. See the **annotated artwork** with green/red bounding boxes
7. Review the **Compliance Report** showing the omitted renal impairment warning as CRITICAL

---

## 🌍 Supported Languages & Regulatory Contexts

| Language    | Regulatory Context                         |
|-------------|-------------------------------------------|
| French      | EU/EMA + Braille requirement              |
| German      | EU/EMA + German Drug Act (AMG)            |
| Japanese    | PMDA + JMHLW regulations                  |
| Spanish     | EU/EMA or LATAM (ANMAT/COFEPRIS)          |
| Portuguese  | Brazil ANVISA RDC 71/2009                 |
| Arabic      | Gulf Health Council (GCC)                  |
| Chinese     | NMPA guidelines                            |
| Russian     | Roszdravnadzor                             |

---

## 🔌 API Reference

### `POST /api/analyze`

**Form Data:**
| Field          | Type   | Description                          |
|----------------|--------|--------------------------------------|
| master_label   | string | Approved English label text          |
| target_language| string | e.g., "French", "Japanese"           |
| packaging_pdf  | file   | PNG, JPG, or PDF of packaging art    |

**Response:**
```json
{
  "overall_status": "needs_review",
  "compliance_score": 78.5,
  "translation_analysis": {
    "semantic_score": 82.0,
    "discrepancies": [
      {
        "severity": "critical",
        "section": "Dosage Warning",
        "explanation": "Renal impairment warning (CrCl <30 mL/min) is missing",
        "recommendation": "Add renal dosage adjustment warning"
      }
    ]
  },
  "vision_analysis": {
    "layout_score": 91.0,
    "issues": [...],
    "compliant_elements": [...]
  },
  "agent_log": [...],
  "summary": "Packaging review complete. Score: 78.5%."
}
```

---

## 💡 Extension Ideas (Post-Hackathon)

- **PDF.js integration** for true multi-page PDF rendering with overlays
- **Regulatory rule engine** — load country-specific rule JSON files
- **Batch processing** — analyze all 50 country variants in one run
- **Audit trail** — Supabase-backed history of all compliance reviews
- **Change-diff view** — highlight exactly which words changed meaning
- **Microsoft Teams / Slack alerts** for critical failures

---

## 🛠️ Built With

- **Claude claude-sonnet-4-20250514** — Translation, semantic analysis, vision/OCR
- **FastAPI** — Python backend orchestrator
- **React + Vite** — Frontend dashboard
- **Framer Motion** — Animations
- **React Dropzone** — File upload

---

## 👤 Author

Built for **Viatris Global Packaging Hackathon** by the GenAI team.

> *"The difference between a compliant label and a non-compliant one can mean patient safety. We built PharmaGuard to make that review instantaneous."*

---

## 📄 License

MIT
