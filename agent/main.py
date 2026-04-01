"""
agent/main.py - FastAPI backend for the IPL Match Analysis Agent
"""
import os, uuid, logging, datetime, json
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

try:
    # Local package layout: uvicorn agent.main:app
    from agent.ipl_agent import analyze_match
except ModuleNotFoundError:
    # Docker image layout: agent/ contents copied directly into /app
    from ipl_agent import analyze_match

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="IPL Match Analysis Agent", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_reports: dict = {}

class MatchRequest(BaseModel):
    batting_team: str
    bowling_team: str
    venue: str
    toss_winner: str
    toss_decision: str
    match_date: Optional[str] = None

@app.get("/")
def root(): return {"message": "IPL Match Analysis Agent v2 🏏"}

@app.get("/health")
def health(): return {"status": "ok"}

@app.post("/analyse")
async def analyse(req: MatchRequest, background_tasks: BackgroundTasks):
    rid = str(uuid.uuid4())
    _reports[rid] = {"status": "running", "tools_called": []}
    background_tasks.add_task(_run, rid, req)
    return {"report_id": rid, "status": "running"}

@app.get("/analyse/{report_id}")
def get_report(report_id: str):
    r = _reports.get(report_id)
    if not r: raise HTTPException(404, "Report not found")
    return {"report_id": report_id, **r}

@app.post("/analyse/sync")
async def analyse_sync(req: MatchRequest):
    rid = str(uuid.uuid4())
    def on_tool(name, args):
        pass
    try:
        result = analyze_match(
            req.batting_team, req.bowling_team, req.venue,
            req.toss_winner, req.toss_decision, req.match_date or "", on_tool
        )
        result["status"] = "done"
        _reports[rid] = result
        _save(rid, req, result)
        return {"report_id": rid, **result}
    except Exception as e:
        logger.exception(e)
        raise HTTPException(500, str(e))

def _run(rid: str, req: MatchRequest):
    try:
        def on_tool(name, args):
            _reports[rid].setdefault("tools_called", []).append({"tool": name, "args": args})
        result = analyze_match(
            req.batting_team, req.bowling_team, req.venue,
            req.toss_winner, req.toss_decision, req.match_date or "", on_tool
        )
        result["status"] = "done"
        _reports[rid] = result
        _save(rid, req, result)
    except Exception as e:
        logger.exception(e)
        _reports[rid] = {"status": "error", "error": str(e)}

def _save(rid: str, req: MatchRequest, result: dict):
    try:
        from supabase import create_client
        db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
        pred = result.get("prediction", {})
        db.table("match_reports").insert({
            "id": rid,
            "created_at": datetime.datetime.utcnow().isoformat(),
            "batting_team": req.batting_team,
            "bowling_team": req.bowling_team,
            "venue": req.venue,
            "toss_winner": req.toss_winner,
            "toss_decision": req.toss_decision,
            "match_date": req.match_date,
            "predicted_score": pred.get("predicted_score"),
            "win_probability": pred.get("win_probability"),
            "full_report": json.dumps(result, default=str),
        }).execute()
    except Exception as e:
        logger.warning(f"Save failed: {e}")

@app.post("/feedback")
async def feedback(report_id: str, actual_score: int, winner: str = ""):
    try:
        from supabase import create_client
        db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
        db.table("match_reports").update({
            "actual_score": actual_score, "actual_winner": winner
        }).eq("id", report_id).execute()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/history")
async def history(limit: int = 20):
    try:
        from supabase import create_client
        db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
        r = db.table("match_reports").select("*").order("created_at", desc=True).limit(limit).execute()
        labeled = [x for x in r.data if x.get("actual_score")]
        errors = [abs(x["predicted_score"] - x["actual_score"]) for x in labeled if x.get("predicted_score")]
        return {
            "records": r.data, "total": len(r.data),
            "labeled": len(labeled),
            "avg_error": round(sum(errors)/len(errors), 1) if errors else None
        }
    except Exception as e:
        raise HTTPException(500, str(e))
