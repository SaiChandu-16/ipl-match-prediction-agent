"""
agent/ipl_agent.py
-------------------
Full IPL Match Analysis Agent using Google Gemini 1.5 Flash (FREE).

Free tier limits:
  - 15 requests/minute
  - 1 million tokens/day
  - No credit card required

Produces:
  - Playing XI for both teams (auto-scraped)
  - Venue + pitch analysis
  - Batting lineup strength assessment
  - Bowling attack analysis
  - Key player matchups (batter vs bowler)
  - Recent form for both teams
  - Head-to-head at venue
  - Full innings prediction with reasoning
  - Win probability
  - Players to watch
"""

import os, json, re, logging, datetime, time
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool

logger = logging.getLogger(__name__)

# ── Gemini setup (FREE) ───────────────────────────────────────────────────────
def _configure_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    genai.configure(api_key=api_key)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "Chrome/122.0 Safari/537.36"
    )
}

# ── Venue historical averages (from Cricsheet data) ───────────────────────────
VENUE_STATS = {
    "Wankhede Stadium": {
        "avg_1st_innings": 175, "avg_2nd_innings": 168,
        "pace_wickets_pct": 62, "spin_wickets_pct": 38,
        "powerplay_avg": 54, "middle_avg": 62, "death_avg": 59,
        "chasing_wins_pct": 48, "dew_factor": "High",
        "pitch_type": "Flat, true bounce",
        "notes": "Scores 170+ common. Dew heavily favours chasing team in evening games."
    },
    "M Chinnaswamy Stadium": {
        "avg_1st_innings": 185, "avg_2nd_innings": 178,
        "pace_wickets_pct": 55, "spin_wickets_pct": 45,
        "powerplay_avg": 58, "middle_avg": 66, "death_avg": 61,
        "chasing_wins_pct": 45, "dew_factor": "Moderate",
        "pitch_type": "Batting paradise, short boundaries",
        "notes": "Highest scoring ground in IPL. Small boundaries, fast outfield."
    },
    "MA Chidambaram Stadium": {
        "avg_1st_innings": 158, "avg_2nd_innings": 152,
        "pace_wickets_pct": 35, "spin_wickets_pct": 65,
        "powerplay_avg": 48, "middle_avg": 55, "death_avg": 55,
        "chasing_wins_pct": 52, "dew_factor": "Low",
        "pitch_type": "Spin-friendly, slow and low",
        "notes": "Spinners dominate. Teams with 2+ quality spinners have big advantage."
    },
    "Eden Gardens": {
        "avg_1st_innings": 163, "avg_2nd_innings": 157,
        "pace_wickets_pct": 58, "spin_wickets_pct": 42,
        "powerplay_avg": 51, "middle_avg": 57, "death_avg": 55,
        "chasing_wins_pct": 50, "dew_factor": "Moderate",
        "pitch_type": "Balanced, good for all-round cricket",
        "notes": "Historically balanced. Slightly favours first-innings batting."
    },
    "Arun Jaitley Stadium": {
        "avg_1st_innings": 168, "avg_2nd_innings": 162,
        "pace_wickets_pct": 50, "spin_wickets_pct": 50,
        "powerplay_avg": 53, "middle_avg": 59, "death_avg": 56,
        "chasing_wins_pct": 49, "dew_factor": "Moderate",
        "pitch_type": "Good batting surface, even contest",
        "notes": "Even contest between bat and ball. Night dew can affect grip."
    },
    "Rajiv Gandhi International Stadium": {
        "avg_1st_innings": 172, "avg_2nd_innings": 165,
        "pace_wickets_pct": 60, "spin_wickets_pct": 40,
        "powerplay_avg": 54, "middle_avg": 60, "death_avg": 58,
        "chasing_wins_pct": 47, "dew_factor": "High",
        "pitch_type": "Good batting surface, some pace assistance",
        "notes": "Significant dew in evening games. Pace bowlers effective early."
    },
    "Narendra Modi Stadium": {
        "avg_1st_innings": 178, "avg_2nd_innings": 171,
        "pace_wickets_pct": 52, "spin_wickets_pct": 48,
        "powerplay_avg": 56, "middle_avg": 63, "death_avg": 59,
        "chasing_wins_pct": 46, "dew_factor": "Low",
        "pitch_type": "Large ground, batting-friendly",
        "notes": "Largest cricket stadium. Bigger boundaries than most IPL venues."
    },
    "Sawai Mansingh Stadium": {
        "avg_1st_innings": 163, "avg_2nd_innings": 157,
        "pace_wickets_pct": 42, "spin_wickets_pct": 58,
        "powerplay_avg": 50, "middle_avg": 57, "death_avg": 56,
        "chasing_wins_pct": 51, "dew_factor": "Low",
        "pitch_type": "Spin-friendly, dry conditions",
        "notes": "Dry Rajasthan climate. Surface deteriorates, benefiting spinners."
    },
    "Punjab Cricket Association Stadium": {
        "avg_1st_innings": 172, "avg_2nd_innings": 165,
        "pace_wickets_pct": 57, "spin_wickets_pct": 43,
        "powerplay_avg": 54, "middle_avg": 61, "death_avg": 57,
        "chasing_wins_pct": 48, "dew_factor": "Moderate",
        "pitch_type": "Good batting surface",
        "notes": "Good wicket for batting. Pace bowlers get some assistance early."
    },
    "BRSABV Ekana Cricket Stadium": {
        "avg_1st_innings": 168, "avg_2nd_innings": 161,
        "pace_wickets_pct": 55, "spin_wickets_pct": 45,
        "powerplay_avg": 52, "middle_avg": 58, "death_avg": 58,
        "chasing_wins_pct": 50, "dew_factor": "Moderate",
        "pitch_type": "Good batting surface, improving with each season",
        "notes": "Still developing as an IPL venue. Balanced conditions."
    },
}

# ── Player role database (roles inform matchup analysis) ──────────────────────
PLAYER_ROLES = {
    # Batters
    "Rohit Sharma": {"type": "Batter", "style": "Aggressive opener", "strength": "pace"},
    "Virat Kohli": {"type": "Batter", "style": "Anchor/aggressor", "strength": "pace"},
    "Suryakumar Yadav": {"type": "Batter", "style": "360 degree", "strength": "both"},
    "Yashasvi Jaiswal": {"type": "Batter", "style": "Aggressive opener", "strength": "spin"},
    "Travis Head": {"type": "Batter", "style": "Aggressive opener", "strength": "pace"},
    "Heinrich Klaasen": {"type": "WK-Batter", "style": "Power hitter", "strength": "both"},
    "Tilak Varma": {"type": "Batter", "style": "Anchor", "strength": "spin"},
    "Riyan Parag": {"type": "All-rounder", "style": "Finisher", "strength": "spin"},
    # Bowlers
    "Jasprit Bumrah": {"type": "Bowler", "style": "Pace", "wicket_zone": "early/death"},
    "Mohammed Shami": {"type": "Bowler", "style": "Pace", "wicket_zone": "early/middle"},
    "Rashid Khan": {"type": "Bowler", "style": "Leg-spin", "wicket_zone": "middle"},
    "Yuzvendra Chahal": {"type": "Bowler", "style": "Leg-spin", "wicket_zone": "middle"},
    "Kagiso Rabada": {"type": "Bowler", "style": "Pace", "wicket_zone": "early/death"},
    "Arshdeep Singh": {"type": "Bowler", "style": "Pace swing", "wicket_zone": "powerplay/death"},
    "Pat Cummins": {"type": "All-rounder", "style": "Pace", "wicket_zone": "all"},
    "Varun Chakravarthy": {"type": "Bowler", "style": "Mystery spin", "wicket_zone": "middle"},
    "Ravindra Jadeja": {"type": "All-rounder", "style": "Left-arm spin", "wicket_zone": "middle"},
}


# ── Tool implementations ──────────────────────────────────────────────────────

def get_playing_xi(team_name: str) -> dict:
    """Fetch playing XI from ESPNcricinfo or Cricbuzz."""
    logger.info(f"Fetching XI: {team_name}")

    # Try Cricbuzz live scores
    try:
        resp = requests.get(
            "https://www.cricbuzz.com/cricket-match/live-scores",
            headers=HEADERS, timeout=10
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        # Find match links containing team name
        for link in soup.find_all("a", href=re.compile(r"/cricket-scores/")):
            text = link.get_text()
            short = team_name.split()[0]
            if short.lower() in text.lower():
                match_url = "https://www.cricbuzz.com" + link["href"]
                mr = requests.get(match_url, headers=HEADERS, timeout=10)
                ms = BeautifulSoup(mr.text, "html.parser")
                players = [
                    el.get_text(strip=True)
                    for el in ms.find_all(class_=re.compile(r"playing-xi|player-name"))
                    if len(el.get_text(strip=True)) > 3
                ][:11]
                if players:
                    return {
                        "team": team_name,
                        "players": players,
                        "confirmed": True,
                        "source": "Cricbuzz live"
                    }
    except Exception as e:
        logger.warning(f"Cricbuzz XI fetch failed: {e}")

    # Fallback: Supabase squad
    try:
        from supabase import create_client
        db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
        rows = db.table("players")\
            .select("name, role, country")\
            .eq("team_name", team_name)\
            .eq("is_active", True)\
            .execute().data
        # Build role-annotated player list
        players_with_roles = [
            {"name": p["name"], "role": p["role"], "country": p["country"]}
            for p in rows
        ]
        return {
            "team": team_name,
            "players": [p["name"] for p in players_with_roles],
            "players_detail": players_with_roles,
            "confirmed": False,
            "source": "Supabase squad (full squad, not confirmed XI)"
        }
    except Exception as e:
        return {"team": team_name, "players": [], "error": str(e)}


def get_venue_stats(venue: str) -> dict:
    """Return historical venue stats."""
    stats = VENUE_STATS.get(venue, {
        "avg_1st_innings": 165, "avg_2nd_innings": 158,
        "pace_wickets_pct": 55, "spin_wickets_pct": 45,
        "powerplay_avg": 52, "middle_avg": 57, "death_avg": 56,
        "chasing_wins_pct": 50, "dew_factor": "Unknown",
        "pitch_type": "Unknown", "notes": "Limited data for this venue"
    })
    return {"venue": venue, **stats}


def get_recent_form(team_name: str, matches: int = 5) -> dict:
    """Fetch recent match results and scores."""
    logger.info(f"Fetching form: {team_name}")

    try:
        query = f"{team_name} IPL 2026 recent matches results"
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=HEADERS, timeout=10
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        snippets = [
            el.get_text(strip=True)
            for el in soup.find_all("a", class_="result__snippet")[:5]
        ]
        return {
            "team": team_name,
            "snippets": snippets,
            "source": "DuckDuckGo web search"
        }
    except Exception as e:
        return {"team": team_name, "error": str(e), "snippets": []}


def get_player_stats(player_name: str) -> dict:
    """Fetch individual player stats from ESPNcricinfo."""
    logger.info(f"Fetching stats: {player_name}")

    # Check local role database first
    role_info = PLAYER_ROLES.get(player_name, {})

    try:
        query = f"{player_name} IPL 2026 batting bowling statistics"
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=HEADERS, timeout=8
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        snippets = [
            el.get_text(strip=True)
            for el in soup.find_all("a", class_="result__snippet")[:3]
        ]
        return {
            "player": player_name,
            "role_info": role_info,
            "snippets": snippets,
            "source": "Web search"
        }
    except Exception as e:
        return {"player": player_name, "role_info": role_info, "error": str(e)}


def get_head_to_head(team1: str, team2: str, venue: str = "") -> dict:
    """Fetch head-to-head record between two teams."""
    logger.info(f"H2H: {team1} vs {team2}")

    try:
        query = f"{team1} vs {team2} IPL head to head record {venue} 2024 2025 2026"
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=HEADERS, timeout=10
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        snippets = [
            el.get_text(strip=True)
            for el in soup.find_all("a", class_="result__snippet")[:4]
        ]
        return {
            "team1": team1,
            "team2": team2,
            "venue": venue,
            "snippets": snippets,
            "source": "Web search"
        }
    except Exception as e:
        return {"team1": team1, "team2": team2, "error": str(e)}


def search_web(query: str) -> dict:
    """Search DuckDuckGo (completely free, no API key)."""
    logger.info(f"Web search: {query}")
    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=HEADERS, timeout=10
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        results = [el.get_text(strip=True) for el in soup.find_all("a", class_="result__a")[:5]]
        snippets = [el.get_text(strip=True) for el in soup.find_all("a", class_="result__snippet")[:5]]
        return {"query": query, "results": results, "snippets": snippets}
    except Exception as e:
        return {"query": query, "error": str(e)}


def get_pitch_report(venue: str, match_date: str = "") -> dict:
    """Search for pre-match pitch report."""
    query = f"{venue} IPL 2026 pitch report {match_date} conditions"
    web = search_web(query)
    venue_stats = get_venue_stats(venue)
    return {
        "venue": venue,
        "venue_historical": venue_stats,
        "live_report_snippets": web.get("snippets", []),
        "source": "DuckDuckGo + historical data"
    }


def get_toss_stats(batting_team: str, venue: str) -> dict:
    """Historical toss advantage stats at venue."""
    venue_data = VENUE_STATS.get(venue, {})
    chasing_wins = venue_data.get("chasing_wins_pct", 50)
    batting_first_wins = 100 - chasing_wins
    return {
        "venue": venue,
        "batting_first_wins_pct": batting_first_wins,
        "chasing_wins_pct": chasing_wins,
        "recommendation": (
            "Bat first" if batting_first_wins > 53
            else "Chase" if chasing_wins > 53
            else "Either — balanced venue"
        ),
        "dew_factor": venue_data.get("dew_factor", "Unknown"),
        "notes": venue_data.get("notes", "")
    }


# ── Tool registry for Gemini ─────────────────────────────────────────────────

TOOL_FUNCTIONS = {
    "get_playing_xi":    get_playing_xi,
    "get_venue_stats":   get_venue_stats,
    "get_recent_form":   get_recent_form,
    "get_player_stats":  get_player_stats,
    "get_head_to_head":  get_head_to_head,
    "get_pitch_report":  get_pitch_report,
    "get_toss_stats":    get_toss_stats,
    "search_web":        search_web,
}

GEMINI_TOOLS = Tool(function_declarations=[
    FunctionDeclaration(
        name="get_playing_xi",
        description="Fetch the confirmed playing XI for an IPL team. Call for BOTH teams.",
        parameters={"type": "object", "properties": {
            "team_name": {"type": "string", "description": "Full IPL team name"}
        }, "required": ["team_name"]}
    ),
    FunctionDeclaration(
        name="get_venue_stats",
        description="Get historical batting/bowling stats, average scores, and pitch character for a venue.",
        parameters={"type": "object", "properties": {
            "venue": {"type": "string"}
        }, "required": ["venue"]}
    ),
    FunctionDeclaration(
        name="get_recent_form",
        description="Get recent match results and form for a team (last 5 matches).",
        parameters={"type": "object", "properties": {
            "team_name": {"type": "string"},
            "matches": {"type": "integer", "description": "Number of recent matches (default 5)"}
        }, "required": ["team_name"]}
    ),
    FunctionDeclaration(
        name="get_player_stats",
        description="Get individual player batting or bowling stats and recent performance.",
        parameters={"type": "object", "properties": {
            "player_name": {"type": "string"}
        }, "required": ["player_name"]}
    ),
    FunctionDeclaration(
        name="get_head_to_head",
        description="Get head-to-head record between two IPL teams, especially at the given venue.",
        parameters={"type": "object", "properties": {
            "team1": {"type": "string"},
            "team2": {"type": "string"},
            "venue": {"type": "string"}
        }, "required": ["team1", "team2"]}
    ),
    FunctionDeclaration(
        name="get_pitch_report",
        description="Fetch pitch report and conditions for a venue on match day.",
        parameters={"type": "object", "properties": {
            "venue": {"type": "string"},
            "match_date": {"type": "string"}
        }, "required": ["venue"]}
    ),
    FunctionDeclaration(
        name="get_toss_stats",
        description="Get historical toss advantage stats — whether batting or chasing is better at this venue.",
        parameters={"type": "object", "properties": {
            "batting_team": {"type": "string"},
            "venue": {"type": "string"}
        }, "required": ["batting_team", "venue"]}
    ),
    FunctionDeclaration(
        name="search_web",
        description="Search the web for any cricket info — injury news, weather, squad updates, match previews.",
        parameters={"type": "object", "properties": {
            "query": {"type": "string"}
        }, "required": ["query"]}
    ),
])

SYSTEM_PROMPT = """You are an expert IPL cricket analyst. Your job is to produce a complete, 
detailed pre-match prediction and analysis report.

For every match you must:
1. Call get_playing_xi for BOTH teams
2. Call get_venue_stats for the venue
3. Call get_pitch_report for the venue
4. Call get_toss_stats for the venue
5. Call get_recent_form for BOTH teams
6. Call get_head_to_head for the two teams
7. Call get_player_stats for 3–4 key players (top batter + key bowler for each team)
8. Call search_web for injury news and match preview

After gathering all data, produce your analysis as VALID JSON matching this exact schema:

{
  "match": {
    "batting_team": "...",
    "bowling_team": "...",
    "venue": "...",
    "date": "..."
  },
  "prediction": {
    "predicted_score": <int>,
    "confidence_range": {"low": <int>, "high": <int>},
    "phase_breakdown": {
      "powerplay_1_6": <int>,
      "middle_7_15": <int>,
      "death_16_20": <int>
    },
    "win_probability": {
      "batting_team_pct": <int>,
      "bowling_team_pct": <int>
    }
  },
  "lineup_analysis": {
    "batting_team": {
      "strengths": ["...", "..."],
      "weaknesses": ["...", "..."],
      "batting_order_assessment": "...",
      "power_hitters": ["player1", "player2"],
      "anchor_batters": ["player1"],
      "bowling_quality": "..."
    },
    "bowling_team": {
      "strengths": ["...", "..."],
      "weaknesses": ["...", "..."],
      "bowling_attack_assessment": "...",
      "key_bowlers": ["player1", "player2"],
      "batting_depth": "..."
    }
  },
  "key_matchups": [
    {
      "batter": "...",
      "bowler": "...",
      "advantage": "batter|bowler|even",
      "reason": "..."
    }
  ],
  "venue_analysis": {
    "avg_first_innings": <int>,
    "pitch_type": "...",
    "pace_vs_spin": "...",
    "toss_advantage": "...",
    "dew_factor": "...",
    "key_insight": "..."
  },
  "form_analysis": {
    "batting_team_form": "...",
    "bowling_team_form": "...",
    "momentum": "batting_team|bowling_team|neutral"
  },
  "head_to_head": {
    "summary": "...",
    "venue_record": "...",
    "recent_encounters": "..."
  },
  "players_to_watch": [
    {
      "name": "...",
      "team": "...",
      "reason": "...",
      "impact_potential": "high|medium"
    }
  ],
  "playing_xis": {
    "batting_team_xi": ["..."],
    "bowling_team_xi": ["..."]
  },
  "match_narrative": "A 3-4 sentence summary of the key story of this match.",
  "key_factors": ["...", "...", "..."],
  "analyst_verdict": "..."
}

Be analytical, specific, and use the real data you collected. Consider:
- How the batting lineup matches up against the specific bowling attack
- Which batters struggle vs pace vs spin given the venue character
- Power hitter count and death overs batting depth
- Bowling attack variety (pace/spin balance) vs the batting lineup
- Specific player matchups that could be decisive
- Impact of pitch, dew, and toss on the prediction
"""


def run_tool(name: str, args: dict) -> str:
    fn = TOOL_FUNCTIONS.get(name)
    if not fn:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        result = fn(**args)
        return json.dumps(result, default=str)
    except Exception as e:
        logger.error(f"Tool {name} failed: {e}")
        return json.dumps({"error": str(e)})


def analyze_match(
    batting_team: str,
    bowling_team: str,
    venue: str,
    toss_winner: str,
    toss_decision: str,
    match_date: str = None,
    on_tool_call=None,
) -> dict:
    """
    Run the full match analysis agent.
    Returns structured analysis + prediction JSON.
    on_tool_call(name, args): optional callback for live UI updates.
    """
    if not match_date:
        match_date = datetime.date.today().isoformat()

    _configure_gemini()

    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=SYSTEM_PROMPT,
        tools=[GEMINI_TOOLS],
    )

    user_prompt = (
        f"Produce a complete pre-match analysis and score prediction for:\n\n"
        f"Match: {batting_team} (batting) vs {bowling_team} (bowling)\n"
        f"Venue: {venue}\n"
        f"Toss: {toss_winner} won and chose to {toss_decision}\n"
        f"Date: {match_date}\n\n"
        f"Use all your tools to gather live data, then produce the full JSON analysis."
    )

    chat = model.start_chat()
    tool_calls_log = []
    response = chat.send_message(user_prompt)

    # ── Agentic loop ──────────────────────────────────────────────────────────
    for _ in range(15):  # max 15 rounds
        # Check for tool calls
        tool_calls = [
            p for p in response.parts
            if hasattr(p, "function_call") and p.function_call.name
        ]
        if not tool_calls:
            break

        # Execute all tool calls
        tool_responses = []
        for part in tool_calls:
            fc = part.function_call
            name = fc.name
            args = dict(fc.args) if fc.args else {}

            logger.info(f"Tool call: {name}({args})")
            tool_calls_log.append({"tool": name, "input": args})

            if on_tool_call:
                on_tool_call(name, args)

            result_str = run_tool(name, args)

            tool_responses.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=name,
                        response={"result": result_str}
                    )
                )
            )

            time.sleep(0.5)  # be polite to free APIs

        response = chat.send_message(tool_responses)

    # ── Parse final JSON ──────────────────────────────────────────────────────
    final_text = "".join(
        p.text for p in response.parts if hasattr(p, "text")
    )

    try:
        json_match = re.search(r"\{[\s\S]*\}", final_text)
        if json_match:
            result = json.loads(json_match.group())
        else:
            raise ValueError("No JSON found")
    except Exception as e:
        logger.error(f"JSON parse failed: {e}\nRaw: {final_text[:300]}")
        result = _fallback_prediction(batting_team, bowling_team, venue, final_text)

    result["tool_calls"] = tool_calls_log
    result["raw_response"] = final_text
    return result


def _fallback_prediction(batting_team, bowling_team, venue, raw_text):
    """Best-effort fallback if JSON parsing fails."""
    v = VENUE_STATS.get(venue, {})
    score = v.get("avg_1st_innings", 165)
    return {
        "match": {"batting_team": batting_team, "bowling_team": bowling_team, "venue": venue},
        "prediction": {
            "predicted_score": score,
            "confidence_range": {"low": score - 15, "high": score + 15},
            "phase_breakdown": {
                "powerplay_1_6": int(score * 0.30),
                "middle_7_15": int(score * 0.35),
                "death_16_20": score - int(score * 0.30) - int(score * 0.35),
            },
            "win_probability": {"batting_team_pct": 50, "bowling_team_pct": 50}
        },
        "match_narrative": raw_text[:500],
        "key_factors": ["See raw response for details"],
        "analyst_verdict": "Analysis incomplete — see raw response",
        "playing_xis": {"batting_team_xi": [], "bowling_team_xi": []},
        "key_matchups": [],
        "players_to_watch": [],
        "lineup_analysis": {},
        "venue_analysis": {},
        "form_analysis": {},
        "head_to_head": {},
    }
