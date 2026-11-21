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

# VeriTone Studio

VeriTone Studio is a private writing-analysis workspace with a Flask API, a responsive HTML/CSS/JavaScript client, and SQLite persistence. It combines local linguistic heuristics with optional Google Gemini scoring and prose revision.

## Capabilities

- Account registration and session-based sign-in with Werkzeug password hashing, HttpOnly cookies, `user`/`admin` roles, and an environment-seeded administrator.
- Owner-scoped analysis history, deletion, and downloads. Requests for another account's existing analysis return `403`; missing records return `404`. Administrators can inspect platform audit records and manage account roles/status.
- Heuristic scoring for sentence-length variation, lexical diversity, formulaic phrases, and flagged sentences. When configured, Gemini adds contextual scoring and prose revision. Heuristic-only mode is available per run and the app works without an API key.
- TXT, Markdown, TeX, and PDF ingestion. Upload streams are copied in chunks to temporary disk files; Flask's `MAX_CONTENT_LENGTH` is unset. LaTeX extraction removes the preamble, comments, and common code, list, table, and math environments.
- Side-by-side source/output, linguistic metrics, sentence-level edit audit, estimated word impact, SQLite history, `.txt` output, and `.json` report exports.

Scores are heuristic estimates of writing patterns, not evidence that a person or model authored a text. When Gemini is enabled, submitted draft text is sent to Google's Gemini API; use heuristic-only mode for local processing.

## Run With Docker Compose

1. For local use, Compose seeds `admin@gmail.com` with the configured default password. For any shared or public deployment, copy `.env.example` to `.env` and replace both `VERITONE_SECRET_KEY` and `VERITONE_ADMIN_PASS` with private values before starting. Set `GEMINI_API_KEY` if Gemini is desired. Keep `.env` private; it is ignored by Git and excluded from the Docker build context.
2. From this directory, build and start the app:

   ```sh
   docker compose up --build
   ```

3. Open <http://localhost:5000>. The SQLite database is persisted at `./data/veritone.db` through the Compose volume.
4. To stop the service, run `docker compose down`. The `data/` directory remains on the host.

For HTTPS deployments, set `VERITONE_COOKIE_SECURE=true` and terminate TLS at a trusted reverse proxy. Configure a strong secret key and administrator password before exposing the service publicly.

## Run Locally

Requires Python 3.11 or newer.

```sh
cp .env.example .env
# Edit .env: set VERITONE_SECRET_KEY and VERITONE_ADMIN_PASS; GEMINI_API_KEY is optional.
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
set -a
source .env
set +a
flask --app 'backend:create_app()' run --debug --host 127.0.0.1
```

Open <http://127.0.0.1:5000>. Local data is stored in `data/veritone.db`. Without a Gemini key, scoring and humanization use the offline heuristic implementation; the workbench also offers a per-run heuristic-only toggle.

## Configuration

| Variable | Purpose |
| --- | --- |
| `VERITONE_SECRET_KEY` | Flask session signing key. Set a long, unique value. |
| `VERITONE_ADMIN_USER` | Username to create as the initial administrator (Compose default: `admin@gmail.com`). |
| `VERITONE_ADMIN_PASS` | Initial administrator password (Compose local default is configured in `compose.yaml`). Admin creation is skipped if empty. |
| `GEMINI_API_KEY` | Optional Google Gemini API key. |
| `GEMINI_MODEL` | Gemini model name (default: `gemini-2.0-flash`). |
| `VERITONE_DB_DIR` | SQLite data directory (default: project `data/`; Compose uses `/app/data`). |
| `VERITONE_COOKIE_SECURE` | Set to `true` when serving over HTTPS. |

## Project Layout

```text
backend/       Flask app factory, auth, SQLite, detector, humanizer, extraction, API routes
frontend/      Landing/auth flow and responsive user/admin studio
data/          SQLite database (created at runtime; not tracked)
Dockerfile     Python/Gunicorn image
compose.yaml   App service, configuration, and persistent database volume
```