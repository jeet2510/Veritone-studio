# VeriTone Studio

**VeriTone Studio** is a full-stack web application for **AI-pattern detection**, **prose humanization**, **edit/change reporting**, and **persistent SQLite storage**, built with a separated **Backend API (`Flask` + `SQLite`)** and **Frontend Dashboard (`HTML/CSS/JS`)** and packaged for **Docker** and **Docker Compose**.

---

## Key Features

* **Unlimited File & Text Ingestion:** Upload `.txt`, `.md`, `.tex`, or `.pdf` files with no upload size cap (`MAX_CONTENT_LENGTH = None`), streamed to temporary storage so large files do not exhaust memory.
* **LaTeX Prose Extraction:** Strip LaTeX preambles, environments (`lstlisting`, `tabular`, `equation`, etc.), comments, and math markup when analyzing academic or research drafts.
* **AI-Pattern Detection:** Computes a `0–100` AI-likeness score using sentence-length burstiness/standard deviation, lexical diversity, formulaic AI transition/cliché phrase matching, and flagged sentence inspection.
* **Rule-Based Prose Humanizer:** Removes stiff lead-in transitions, swaps wordy/AI-heavy phrases for plain equivalents, splits overlong `which`-clauses where appropriate, and preserves technical terminology.
* **Full Change & Percentage Report:** Tracks total edits made, estimated percentage of words affected, modified vs. total sentence counts, and an edit-by-edit audit log (`before` -> `after`).
* **Server-Side Persistence & Exports:** Stores every run in SQLite (`data/veritone.db`) and lets you inspect history, delete runs, or download humanized `.txt` and full `.json` reports.

---

## Project Structure

```text
veritone_studio/
├── .dockerignore
├── .gitignore
├── Dockerfile
├── compose.yaml
├── requirements.txt
├── README.md
├── backend/
│   ├── __init__.py
│   ├── config.py          # App config, DB path, unlimited upload setting
│   ├── database.py        # SQLite schema and CRUD helpers
│   ├── detector.py        # Burstiness, lexical diversity & AI cliché detector
│   ├── humanizer.py       # Humanizer engine, change tracker & % calculator
│   ├── extractor.py       # Plain text, PDF (pypdf) & LaTeX (.tex) extractor
│   └── routes.py          # REST API endpoints (/api/*) & file downloads
└── frontend/
    ├── index.html         # Multi-tab web dashboard
    ├── css/
    │   └── styles.css     # Dashboard layout and styling
    └── js/
        ├── api.js         # Backend API client
        └── app.js         # UI state, tables, metrics & history management