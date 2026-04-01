import streamlit as st, requests, time, os
from datetime import date

try:    API_URL = st.secrets["API_URL"]
except: API_URL = os.getenv("API_URL","https://your-agent.onrender.com")

st.set_page_config(page_title="IPL Match Analyst",page_icon="🏏",layout="wide")
IPL_TEAMS=["Mumbai Indians","Chennai Super Kings","Royal Challengers Bengaluru","Kolkata Knight Riders","Delhi Capitals","Rajasthan Royals","Sunrisers Hyderabad","Punjab Kings","Lucknow Super Giants","Gujarat Titans"]
VENUES=["Wankhede Stadium","M Chinnaswamy Stadium","Eden Gardens","MA Chidambaram Stadium","Arun Jaitley Stadium","Rajiv Gandhi International Stadium","Punjab Cricket Association Stadium","Sawai Mansingh Stadium","Narendra Modi Stadium","BRSABV Ekana Cricket Stadium"]
TOOL_ICONS={"get_playing_xi":"🧑 Fetching playing XI","get_venue_stats":"🏟️ Analysing venue","get_team_recent_form":"📊 Checking form","get_player_stats":"🏏 Player stats","get_matchup_analysis":"⚔️  Matchup analysis","get_pitch_and_conditions":"🌿 Pitch report","get_head_to_head":"📜 Head-to-head","search_news":"🔍 Searching news"}

st.title("🏏 IPL Match Analyst")
st.caption("Free AI agent: live squads · pitch · matchups · full match prediction")
st.divider()
tab1,tab2,tab3=st.tabs(["🎯 Analyse","📋 History","ℹ️ About"])

with tab1:
    c1,c2=st.columns(2)
    with c1:
        st.subheader("Match Setup")
        team1=st.selectbox("Batting Team",IPL_TEAMS,key="t1")
        team2=st.selectbox("Bowling Team",[t for t in IPL_TEAMS if t!=team1],key="t2")
        venue=st.selectbox("Venue",VENUES)
        mdate=st.date_input("Match Date",value=date.today())
    with c2:
        st.subheader("Toss")
        toss_w=st.selectbox("Toss Winner",[team1,team2])
        toss_d=st.radio("Elected to",["Bat","Field"],horizontal=True)
        st.info("Agent auto-fetches:\n- Playing XI from Cricbuzz\n- Pitch & weather\n- Last 5 matches form\n- Batter vs bowler matchups\n- Head-to-head stats")
    st.divider()
    go=st.button("🤖 Run Full Match Analysis",type="primary",use_container_width=True)

    if go:
        payload={"batting_team":team1,"bowling_team":team2,"venue":venue,"toss_winner":toss_w,"toss_decision":toss_d,"match_date":mdate.isoformat()}
        with st.spinner("Starting agent..."):
            try:
                r=requests.post(f"{API_URL}/analyse",json=payload,timeout=15)
                r.raise_for_status()
                rid=r.json()["report_id"]
            except Exception as e:
                st.error(f"API error: {e}"); st.stop()
        st.session_state["rid"]=rid
        sbox=st.empty(); prog=st.progress(0); tlog=st.empty()
        with st.spinner("Analysing..."):
            for i in range(90):
                time.sleep(2); prog.progress(min(i*2,90))
                try: poll=requests.get(f"{API_URL}/analyse/{rid}",timeout=10).json()
                except: continue
                tools=poll.get("tools_called",[])
                if tools:
                    lines=[f"✅ {TOOL_ICONS.get(t['tool'],t['tool'])}: **{list(t.get('args',{}).values())[0] if t.get('args') else ''}**" for t in tools]
                    tlog.markdown("\n\n".join(lines))
                if poll.get("status")=="done":
                    prog.progress(100); sbox.success("✅ Done!"); st.session_state["report"]=poll; break
                elif poll.get("status")=="error":
                    st.error(poll.get("error")); st.stop()
                else: sbox.info(f"🔄 {i*2}s | {len(tools)} tools called")
            else: sbox.warning("Timed out"); st.stop()

    rep=st.session_state.get("report",{})
    if rep and rep.get("status")=="done":
        st.divider()
        pred=rep.get("prediction",{})
        if pred.get("predicted_score"):
            st.subheader("🎯 Prediction")
            m1,m2,m3,m4=st.columns(4)
            m1.metric("Predicted Score",f"{pred['predicted_score']} runs")
            cr=pred.get("confidence_range",{})
            m2.metric("Low",f"{cr.get('low','—')} runs")
            m3.metric("High",f"{cr.get('high','—')} runs")
            wp=pred.get("win_probability",{})
            m4.metric("Win prob",wp.get(team1,"50%"))
            pb=pred.get("phase_breakdown",{})
            if pb:
                import pandas as pd
                df=pd.DataFrame({"Phase":["Powerplay (1-6)","Middle (7-15)","Death (16-20)"],"Runs":[pb.get("powerplay_1_6",0),pb.get("middle_overs_7_15",0),pb.get("death_overs_16_20",0)]})
                st.bar_chart(df.set_index("Phase"))
            if pred.get("match_narrative"):
                st.info(f"📖 {pred['match_narrative']}")

        mu=rep.get("matchup_analysis",{})
        if mu:
            st.divider(); st.subheader("⚔️ Lineup Matchup Analysis")
            ca,cb=st.columns(2)
            with ca:
                st.markdown(f"**{team1} advantages**")
                for a in mu.get("batting_advantages",[]): st.markdown(f"- {a}")
            with cb:
                st.markdown(f"**{team2} advantages**")
                for a in mu.get("bowling_advantages",[]): st.markdown(f"- {a}")
            st.markdown(f"**Overall advantage: `{mu.get('overall_lineup_advantage','Even')}`**")
            for b in mu.get("key_battles",[])[:4]:
                st.markdown(f"- 🏏 {b.get('batter','?')} vs 🎳 {b.get('bowler','?')} → {b.get('prediction','')}")

        st.divider()
        cb1,cb2=st.columns(2)
        ba=rep.get("batting_xi_analysis",{})
        with cb1:
            st.subheader(f"🏏 {team1}")
            for p in ba.get("key_players",[])[:5]:
                t=p.get("threat_level",""); ic="🔴" if t=="High" else "🟡" if t=="Med" else "🟢"
                st.markdown(f"{ic} **{p['name']}** — {p.get('current_form','')} ({p.get('role','')})")
            st.caption(f"Batting strength: **{ba.get('team_batting_strength','?')}**")

        boa=rep.get("bowling_xi_analysis",{})
        with cb2:
            st.subheader(f"🎳 {team2}")
            for b in boa.get("bowling_attack",[])[:5]:
                t=b.get("threat",""); ic="🔴" if t=="High" else "🟡" if t=="Med" else "🟢"
                st.markdown(f"{ic} **{b['name']}** ({b.get('type','')}) — Econ: {b.get('economy','?')}")
            st.caption(f"Pace/Spin: **{boa.get('pace_spin_balance','?')}**")

        vp=rep.get("venue_and_pitch",{})
        if vp:
            st.divider(); st.subheader("🌿 Venue & Pitch")
            vc1,vc2,vc3=st.columns(3)
            vc1.metric("Avg 1st innings",f"{vp.get('avg_1st_innings','?')} runs")
            vc2.metric("Pitch type",vp.get("pitch_type","?"))
            vc3.metric("Dew factor",vp.get("dew_factor","?"))
            if vp.get("key_insight"): st.info(f"💡 {vp['key_insight']}")

        rf=rep.get("recent_form",{})
        if rf:
            st.divider(); st.subheader("📊 Recent Form")
            f1,f2=st.columns(2)
            f1.markdown(f"**{team1}:** {rf.get('batting_team_form','?')}")
            f2.markdown(f"**{team2}:** {rf.get('bowling_team_form','?')}")

        verdict=rep.get("analyst_verdict")
        if verdict:
            st.divider(); st.subheader("🧠 Analyst Verdict"); st.markdown(verdict)

        with st.expander("🔍 Raw JSON + tools"):
            for t in rep.get("tool_calls_log",[]): st.markdown(f"- `{t['tool']}` ← `{t.get('args',{})}`")
            st.json({k:v for k,v in rep.items() if k not in ("raw_response","tool_calls_log")})

    if st.session_state.get("rid") and rep.get("status")=="done":
        st.divider(); st.subheader("✅ Submit Result")
        with st.form("fb"):
            actual=st.number_input("Actual 1st innings score",0,350,step=1)
            winner=st.selectbox("Winner",[team1,team2,"No result"])
            if st.form_submit_button("Submit"):
                requests.post(f"{API_URL}/feedback",params={"report_id":st.session_state["rid"],"actual_score":actual,"winner":winner},timeout=10)
                ps=rep.get("prediction",{}).get("predicted_score",0)
                st.success(f"Off by {abs(actual-ps)} runs!")

with tab2:
    if st.button("🔄 Refresh"): st.rerun()
    try:
        import pandas as pd
        h=requests.get(f"{API_URL}/history",timeout=10).json()
        c1,c2,c3=st.columns(3)
        c1.metric("Total",h["total"]); c2.metric("With actual",h["labeled"]); c3.metric("Avg error",h["avg_error"] or "—")
        if h["records"]:
            df=pd.DataFrame([{"Date":r["created_at"][:10],"Match":f"{r['batting_team']} vs {r['bowling_team']}","Venue":r["venue"][:20],"Predicted":r["predicted_score"],"Actual":r.get("actual_score") or "—"} for r in h["records"]])
            st.dataframe(df,use_container_width=True,hide_index=True)
    except Exception as e: st.warning(f"Could not load: {e}")

with tab3:
    st.markdown("""
### 100% Free Stack

| What | Service | Cost |
|---|---|---|
| Agent LLM | Groq (Llama 3.3 70B) | **Free** — 14,400 req/day |
| LLM Fallback | Google Gemini 2.0 Flash | **Free** — 1,500 req/day |
| Backend | Render free tier | **Free** |
| Frontend | Streamlit Cloud | **Free** forever |
| Database | Supabase | **Free** 500MB |
| Data | Cricbuzz/ESPNcricinfo scraping | **Free** |

### Setup (3 minutes)
1. Get **Groq API key** free → `console.groq.com` (no credit card)
2. Get **Gemini key** free → `aistudio.google.com` (backup)
3. Add to Render env vars: `GROQ_API_KEY`, `GEMINI_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`
4. Deploy → done!
""")
