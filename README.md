# IPL Match Agent

`ipl-match-agent` is a full-stack IPL pre-match analysis app. It combines a FastAPI backend, a Streamlit frontend, live web lookups, curated venue data, and Supabase storage to generate match previews, first-innings score predictions, and supporting analysis.

## What It Does

- Accepts a match setup: batting team, bowling team, venue, toss winner, toss decision, and match date
- Runs an analysis agent that gathers playing XI or squad data, venue and pitch context, recent team form, head-to-head context, and key player or matchup signals
- Produces a structured prediction including a predicted first-innings score, confidence range, win probability, players to watch, match narrative, and analyst verdict
- Stores completed reports in Supabase
- Lets users submit actual results later to track prediction accuracy

## Project Structure

```text
ipl-match-agent/
├── agent/
│   ├── main.py              # FastAPI backend
│   ├── ipl_agent.py         # Gemini-based analysis workflow
│   ├── llm_client.py        # Free LLM client with Groq/Gemini fallback helpers
│   ├── tools.py             # Scraping + database-backed helper tools
│   ├── requirements.txt
│   └── __init__.py
├── frontend/
│   ├── app.py               # Streamlit frontend
│   └── requirements.txt
├── database/
│   └── schema.sql           # match_reports table
├── .github/workflows/
│   └── deploy.yml           # Render deploy hook trigger
├── Dockerfile               # Backend container image
├── render.yaml              # Render service config
└── README.md
```

## Architecture

### Backend

The backend lives in [agent/main.py](/C:/Users/saich/OneDrive/Documents/New%20folder/ipl-match-agent/agent/main.py) and exposes a FastAPI API for:

- starting an async analysis job
- fetching an analysis result by report id
- running a synchronous analysis
- saving user feedback
- viewing report history

The analysis engine in [agent/ipl_agent.py](/C:/Users/saich/OneDrive/Documents/New%20folder/ipl-match-agent/agent/ipl_agent.py) uses Google Gemini function calling with helper tools to collect match context and generate a structured JSON report.

### Frontend

The Streamlit UI in [frontend/app.py](/C:/Users/saich/OneDrive/Documents/New%20folder/ipl-match-agent/frontend/app.py) lets users:

- configure a match
- run the analysis
- watch tool progress
- review predictions and insights
- submit actual score feedback
- browse historical reports

### Data Layer

Supabase is used for:

- storing completed reports in `match_reports`
- reading squad data and historical data when available

The included SQL schema for report storage is in [database/schema.sql](/C:/Users/saich/OneDrive/Documents/New%20folder/ipl-match-agent/database/schema.sql).

## Requirements

- Python 3.11+
- A Supabase project
- A Gemini API key

Optional:

- A Groq API key if you want to use the helper client in `agent/llm_client.py`

## Environment Variables

Create environment variables for the backend:

```env
GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key_optional
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_service_or_api_key
```

For the frontend:

```env
API_URL=http://localhost:8000
```

You can also place `API_URL` in Streamlit secrets.

## Local Setup

### 1. Clone and enter the project

```powershell
git clone <your-repo-url>
cd "C:\Users\saich\OneDrive\Documents\New folder\ipl-match-agent"
```

### 2. Create a backend virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r agent\requirements.txt
```

### 3. Run the FastAPI backend

```powershell
$env:GEMINI_API_KEY="your_key"
$env:SUPABASE_URL="your_url"
$env:SUPABASE_KEY="your_key"
uvicorn agent.main:app --host 0.0.0.0 --port 8000
```

Backend will be available at [http://localhost:8000](http://localhost:8000).

### 4. Run the Streamlit frontend

Open a second terminal:

```powershell
.venv\Scripts\Activate.ps1
pip install -r frontend\requirements.txt
$env:API_URL="http://localhost:8000"
streamlit run frontend\app.py
```

Frontend will open in your browser, usually at [http://localhost:8501](http://localhost:8501).

## Database Setup

Run the schema in your Supabase SQL editor:

```sql
CREATE TABLE IF NOT EXISTS match_reports (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at       TIMESTAMPTZ DEFAULT now(),
    batting_team     TEXT,
    bowling_team     TEXT,
    venue            TEXT,
    toss_winner      TEXT,
    toss_decision    TEXT,
    match_date       DATE,
    predicted_score  INT,
    win_probability  JSONB,
    full_report      TEXT,
    actual_score     INT,
    actual_winner    TEXT
);

CREATE INDEX IF NOT EXISTS idx_match_reports_date ON match_reports(created_at DESC);
```

If you want full squad and historical-data features, you will also need compatible `players` and `match_data` tables, because some tool functions query them directly.

## API Endpoints

### `GET /`

Basic service message.

### `GET /health`

Health check endpoint used by Render.

### `POST /analyse`

Starts an asynchronous analysis job.

Example body:

```json
{
  "batting_team": "Mumbai Indians",
  "bowling_team": "Chennai Super Kings",
  "venue": "Wankhede Stadium",
  "toss_winner": "Mumbai Indians",
  "toss_decision": "Bat",
  "match_date": "2026-04-01"
}
```

### `GET /analyse/{report_id}`

Returns the status or final report for a background job.

### `POST /analyse/sync`

Runs the analysis synchronously and returns the full result immediately.

### `POST /feedback`

Stores actual match outcome fields for later evaluation.

### `GET /history`

Returns recent saved reports and average error for labeled predictions.

## Deployment

### Render

This repo includes:

- [Dockerfile](/C:/Users/saich/OneDrive/Documents/New%20folder/ipl-match-agent/Dockerfile) for the backend container
- [render.yaml](/C:/Users/saich/OneDrive/Documents/New%20folder/ipl-match-agent/render.yaml) for Render configuration

Set these Render environment variables:

- `GROQ_API_KEY`
- `GEMINI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_KEY`

### GitHub Actions

The workflow in [deploy.yml](/C:/Users/saich/OneDrive/Documents/New%20folder/ipl-match-agent/.github/workflows/deploy.yml) triggers a Render deploy hook on pushes to `main` when backend files or the Dockerfile change.

## Notes

- The backend currently depends on `GEMINI_API_KEY` in the main analysis path.
- Some helper modules support Groq, but the FastAPI app uses the Gemini-based agent directly.
- Some advanced tool paths expect Supabase tables beyond `match_reports`, especially `players` and `match_data`.
- The frontend and backend currently expect slightly different response shapes in a few places, so you may want to align those if you continue development.

## Roadmap Ideas

- Add `.env.example`
- Add automated tests for API routes and agent output parsing
- Align backend response schema with the Streamlit UI
- Add seed SQL for `players` and `match_data`
- Add Docker support for the frontend

## License

Add a license file if you plan to open-source or share the project publicly.
