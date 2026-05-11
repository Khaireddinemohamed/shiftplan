import streamlit as st
import pandas as pd
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ShiftPlan — Team Holiday Manager",
    page_icon="🗓️",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_FILE = Path("shiftplan_data.json")

TEAMS       = ["Morning 🌅", "Afternoon ☀️", "Night 🌙"]
TEAM_SHORT  = {"Morning 🌅": "morning", "Afternoon ☀️": "afternoon", "Night 🌙": "night"}
SHIFTS      = ["Work", "Morning 🌅", "Afternoon ☀️", "Night 🌙", "Holiday 🏖️", "Off"]
SHIFT_COLOR = {
    "Work":          "#4af0b8",
    "Morning 🌅":    "#f5c842",
    "Afternoon ☀️":  "#4af0b8",
    "Night 🌙":      "#a78bfa",
    "Holiday 🏖️":   "#f07a4a",
    "Off":           "#555",
}
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ── Persistence ─────────────────────────────────────────────────────────────
def load_data() -> dict:
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text())
        except Exception:
            pass
    return {"members": [], "schedules": {}, "holiday_log": [], "next_id": 1}


def save_data(d: dict):
    DATA_FILE.write_text(json.dumps(d, indent=2, default=str))


def get_data() -> dict:
    if "data" not in st.session_state:
        st.session_state["data"] = load_data()
    return st.session_state["data"]


def persist():
    save_data(get_data())


# ── Helpers ──────────────────────────────────────────────────────────────────
def get_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def week_key(d: date) -> str:
    return get_monday(d).isoformat()


def fmt_date(s: str) -> str:
    if not s:
        return "—"
    try:
        return datetime.fromisoformat(s).strftime("%d %b %Y")
    except Exception:
        return s


def team_badge(team: str) -> str:
    colors = {"morning": "#f5c842", "afternoon": "#4af0b8", "night": "#a78bfa"}
    c = colors.get(team, "#888")
    return f'<span style="background:{c}22;color:{c};border:1px solid {c}55;padding:2px 10px;border-radius:20px;font-size:.75rem">{team.capitalize()}</span>'


# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'DM Mono', monospace; }
h1,h2,h3 { font-family: 'Syne', sans-serif !important; }

/* Sidebar */
section[data-testid="stSidebar"] { background: #16181f !important; }
section[data-testid="stSidebar"] * { color: #e8eaf0 !important; }

/* Main background */
.stApp { background: #0e0f13; color: #e8eaf0; }

/* Metric cards */
div[data-testid="metric-container"] {
    background: #16181f;
    border: 1px solid #2a2d38;
    border-radius: 10px;
    padding: 14px 18px;
}
div[data-testid="metric-container"] label { color: #7a7f94 !important; font-size:.7rem !important; }
div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
    font-family:'Syne',sans-serif !important; font-size:1.8rem !important; color:#f5c842 !important;
}

/* Buttons */
button[kind="primary"] { background: #f5c842 !important; color: #000 !important; border:none !important; }
button[kind="secondary"] { border: 1px solid #2a2d38 !important; color:#e8eaf0 !important; }

/* Dataframe */
.stDataFrame { border-radius:8px; overflow:hidden; }

/* Section headers */
.section-header {
    font-family:'Syne',sans-serif; font-weight:800; font-size:1.15rem;
    color:#f5c842; border-bottom:1px solid #2a2d38;
    padding-bottom:8px; margin-bottom:18px;
}
/* Holiday balance */
.bal-ok   { color:#4af0b8; font-weight:600; }
.bal-low  { color:#f07a4a; font-weight:600; }
/* Progress bar */
.prog-wrap { background:#0e0f13; border-radius:4px; height:8px; overflow:hidden; margin-top:4px; }
.prog-fill { height:100%; border-radius:4px; background:#4af0b8; }
/* Info box */
.info-box {
    background:#1e2029; border:1px solid #2a2d38; border-radius:8px;
    padding:14px 18px; margin-bottom:12px; font-size:.85rem;
}
/* Cell pill */
.shift-pill {
    display:inline-block; padding:3px 12px; border-radius:20px;
    font-size:.72rem; font-weight:500; letter-spacing:.4px;
}
</style>
""", unsafe_allow_html=True)


# ── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🗓️ ShiftPlan")
    st.caption("Team Holiday & Shift Manager")
    st.divider()
    page = st.radio(
        "Navigate",
        ["👥 Team Members", "📅 Weekly Planning", "🏖️ Holidays", "📊 Statistics"],
        label_visibility="collapsed",
    )
    st.divider()
    d = get_data()
    total_hdays = sum(m.get("hdays", 0) for m in d["members"])
    st.metric("Team Members", len(d["members"]))
    st.metric("Total Holiday Days", round(total_hdays, 1))
    eligible = [m for m in d["members"] if m.get("weeks", 0) >= 4]
    if eligible:
        st.warning(f"⚡ {len(eligible)} member(s) eligible for +2.5d holiday!")
    st.divider()
    st.caption("Data saved to `shiftplan_data.json`")


# ═══════════════════════════════════════════════════════════════════════════
# PAGE: TEAM MEMBERS
# ═══════════════════════════════════════════════════════════════════════════
if page == "👥 Team Members":
    d = get_data()
    st.markdown('<div class="section-header">👥 Team Members</div>', unsafe_allow_html=True)

    # ── Add / Edit form ──────────────────────────────────────────────────
    edit_id = st.session_state.get("edit_member_id")
    edit_m  = next((m for m in d["members"] if m["id"] == edit_id), None) if edit_id else None

    with st.expander("➕ Add / Edit Member", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            name = st.text_input("Full Name", value=edit_m["name"] if edit_m else "")
        with col2:
            team_opts = TEAMS
            team_def  = 0
            if edit_m:
                for i, t in enumerate(TEAMS):
                    if TEAM_SHORT[t] == edit_m.get("team"):
                        team_def = i
            team = st.selectbox("Shift Team", TEAMS, index=team_def)
        with col3:
            role = st.text_input("Role / Position", value=edit_m.get("role","") if edit_m else "")
        with col4:
            start_val = date.fromisoformat(edit_m["start"]) if edit_m and edit_m.get("start") else date.today()
            start = st.date_input("Start Date", value=start_val)

        col5, col6, col7 = st.columns(3)
        with col5:
            weeks = st.number_input("Weeks Worked (current 4-wk cycle)", 0, 4,
                                    value=int(edit_m.get("weeks", 0)) if edit_m else 0, step=1)
        with col6:
            hdays = st.number_input("Holiday Balance (days)", 0.0, 365.0,
                                    value=float(edit_m.get("hdays", 0)) if edit_m else 0.0, step=0.5)
        with col7:
            notes_mem = st.text_input("Internal Notes", value=edit_m.get("notes","") if edit_m else "")

        c1, c2, c3 = st.columns([1,1,5])
        with c1:
            save_btn = st.button("💾 Save Member", type="primary", use_container_width=True)
        with c2:
            if edit_m and st.button("✕ Cancel Edit", use_container_width=True):
                st.session_state.pop("edit_member_id", None)
                st.rerun()

        if save_btn:
            if not name.strip():
                st.error("Please enter a name.")
            else:
                team_key = TEAM_SHORT[team]
                if edit_m:
                    edit_m.update({
                        "name": name.strip(), "team": team_key,
                        "role": role.strip(), "start": start.isoformat(),
                        "weeks": weeks, "hdays": hdays, "notes": notes_mem.strip()
                    })
                    persist()
                    st.session_state.pop("edit_member_id", None)
                    st.success(f"✅ {name} updated!")
                else:
                    d["members"].append({
                        "id": d["next_id"], "name": name.strip(), "team": team_key,
                        "role": role.strip(), "start": start.isoformat(),
                        "weeks": weeks, "hdays": hdays, "notes": notes_mem.strip()
                    })
                    d["next_id"] += 1
                    persist()
                    st.success(f"✅ {name} added to {team}!")
                st.rerun()

    st.divider()

    # ── Member table ─────────────────────────────────────────────────────
    if not d["members"]:
        st.info("No team members yet. Add your first member above.")
    else:
        # Filter
        fil_col1, fil_col2 = st.columns([2,5])
        with fil_col1:
            fil_team = st.selectbox("Filter by team", ["All"] + [t for t in TEAMS])
        members_show = d["members"]
        if fil_team != "All":
            members_show = [m for m in d["members"] if m["team"] == TEAM_SHORT[fil_team]]

        for m in members_show:
            with st.container():
                c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([2,1.2,1.2,1.2,1,1.2,0.8,0.8])
                c1.markdown(f"**{m['name']}**")
                c2.markdown(team_badge(m.get("team","")), unsafe_allow_html=True)
                c3.write(m.get("role") or "—")
                c4.write(fmt_date(m.get("start","")))
                weeks = m.get("weeks", 0)
                c5.markdown(
                    f"<span style='color:#4af0b8'>{weeks}/4 ✓</span>" if weeks >= 4
                    else f"{weeks}/4",
                    unsafe_allow_html=True
                )
                hd = m.get("hdays", 0)
                c6.markdown(
                    f"<span class='bal-ok'>{hd}d</span>" if hd >= 1
                    else f"<span class='bal-low'>{hd}d</span>",
                    unsafe_allow_html=True
                )
                with c7:
                    if st.button("✏️", key=f"edit_{m['id']}", help="Edit"):
                        st.session_state["edit_member_id"] = m["id"]
                        st.rerun()
                with c8:
                    if st.button("🗑️", key=f"del_{m['id']}", help="Delete"):
                        d["members"] = [x for x in d["members"] if x["id"] != m["id"]]
                        persist()
                        st.rerun()
                st.divider()


# ═══════════════════════════════════════════════════════════════════════════
# PAGE: WEEKLY PLANNING
# ═══════════════════════════════════════════════════════════════════════════
elif page == "📅 Weekly Planning":
    d = get_data()
    st.markdown('<div class="section-header">📅 Weekly Shift Planning</div>', unsafe_allow_html=True)

    if not d["members"]:
        st.info("Add team members first to start planning.")
        st.stop()

    # Week navigation
    if "plan_week" not in st.session_state:
        st.session_state["plan_week"] = get_monday(date.today())

    col_prev, col_lbl, col_next, _, col_fil = st.columns([1,3,1,1,3])
    with col_prev:
        if st.button("← Prev Week"):
            st.session_state["plan_week"] -= timedelta(weeks=1)
            st.rerun()
    with col_lbl:
        wstart = st.session_state["plan_week"]
        wend   = wstart + timedelta(days=6)
        st.markdown(f"**{wstart.strftime('%d %b')} — {wend.strftime('%d %b %Y')}**")
    with col_next:
        if st.button("Next Week →"):
            st.session_state["plan_week"] += timedelta(weeks=1)
            st.rerun()
    with col_fil:
        filter_team = st.selectbox("Show team", ["All"] + list(TEAMS), key="plan_filter", label_visibility="collapsed")

    wk  = week_key(wstart)
    if wk not in d["schedules"]:
        d["schedules"][wk] = {}

    members_plan = d["members"]
    if filter_team != "All":
        members_plan = [m for m in d["members"] if m["team"] == TEAM_SHORT[filter_team]]

    week_dates = [wstart + timedelta(days=i) for i in range(7)]

    # Legend
    leg_html = " &nbsp;|&nbsp; ".join(
        f'<span class="shift-pill" style="background:{c}22;color:{c};border:1px solid {c}55">{s}</span>'
        for s, c in SHIFT_COLOR.items()
    )
    st.markdown(f'<div style="margin-bottom:14px;font-size:.78rem">{leg_html}</div>', unsafe_allow_html=True)

    # Grid — one expander row per member
    changed = False
    for m in members_plan:
        mid = str(m["id"])
        if mid not in d["schedules"][wk]:
            d["schedules"][wk][mid] = {}

        tc = {"morning":"#f5c842","afternoon":"#4af0b8","night":"#a78bfa"}.get(m.get("team",""),"#888")
        with st.expander(
            f"{'●'} {m['name']}  ({m.get('role','')})  — {m.get('team','').capitalize()} team",
            expanded=True
        ):
            cols = st.columns(7)
            for i, (col, day_date) in enumerate(zip(cols, week_dates)):
                with col:
                    current = d["schedules"][wk][mid].get(str(i), "Work")
                    st.caption(f"{DAYS[i][:3]} {day_date.day}/{day_date.month}")
                    new_val = st.selectbox(
                        "shift", SHIFTS,
                        index=SHIFTS.index(current) if current in SHIFTS else 0,
                        key=f"cell_{wk}_{mid}_{i}",
                        label_visibility="collapsed"
                    )
                    if new_val != current:
                        # Deduct holiday balance if holiday placed
                        if new_val == "Holiday 🏖️" and current != "Holiday 🏖️":
                            if m.get("hdays", 0) >= 1:
                                m["hdays"] = round(m["hdays"] - 1, 1)
                                d["holiday_log"].insert(0, {
                                    "id": int(datetime.now().timestamp()*1000),
                                    "memberId": m["id"],
                                    "memberName": m["name"],
                                    "date": day_date.isoformat(),
                                    "type": "use", "days": -1,
                                    "balanceAfter": m["hdays"],
                                    "notes": f"Planned (grid) — {DAYS[i]}",
                                    "label": "Used"
                                })
                            else:
                                st.warning(f"⚠️ {m['name']} has no holiday days left!")
                        # Restore if un-set
                        if current == "Holiday 🏖️" and new_val != "Holiday 🏖️":
                            m["hdays"] = round(m.get("hdays", 0) + 1, 1)
                        d["schedules"][wk][mid][str(i)] = new_val
                        changed = True

    if changed:
        persist()
        st.rerun()

    # Week summary
    st.divider()
    st.markdown("**Week Summary**")
    counts = {s: 0 for s in SHIFTS}
    for m in members_plan:
        mid = str(m["id"])
        for i in range(7):
            s = d["schedules"][wk].get(mid, {}).get(str(i), "Work")
            counts[s] = counts.get(s, 0) + 1

    sc1, sc2, sc3, sc4, sc5 = st.columns(5)
    sc1.metric("Morning 🌅",   counts.get("Morning 🌅", 0),   "shifts")
    sc2.metric("Afternoon ☀️", counts.get("Afternoon ☀️", 0), "shifts")
    sc3.metric("Night 🌙",     counts.get("Night 🌙", 0),     "shifts")
    sc4.metric("Holiday 🏖️",  counts.get("Holiday 🏖️", 0),  "days")
    sc5.metric("Off",          counts.get("Off", 0),           "days")

    # Export week to CSV
    st.divider()
    rows = []
    for m in members_plan:
        mid = str(m["id"])
        row = {"Name": m["name"], "Team": m.get("team","").capitalize()}
        for i, day_date in enumerate(week_dates):
            row[f"{DAYS[i][:3]} {day_date.day}/{day_date.month}"] = \
                d["schedules"][wk].get(mid, {}).get(str(i), "Work")
        rows.append(row)
    if rows:
        df_export = pd.DataFrame(rows)
        csv = df_export.to_csv(index=False).encode()
        st.download_button(
            "⬇️ Export Week as CSV", csv,
            file_name=f"schedule_{wk}.csv", mime="text/csv"
        )


# ═══════════════════════════════════════════════════════════════════════════
# PAGE: HOLIDAYS
# ═══════════════════════════════════════════════════════════════════════════
elif page == "🏖️ Holidays":
    d = get_data()
    st.markdown('<div class="section-header">🏖️ Holiday Management</div>', unsafe_allow_html=True)

    if not d["members"]:
        st.info("Add team members first.")
        st.stop()

    # ── Balance overview ─────────────────────────────────────────────────
    st.subheader("Holiday Balances")
    for m in d["members"]:
        weeks = m.get("weeks", 0)
        hdays = m.get("hdays", 0)
        pct   = min(int((weeks / 4) * 100), 100)
        tc    = {"morning": "#f5c842", "afternoon": "#4af0b8", "night": "#a78bfa"}.get(m.get("team",""), "#888")

        with st.container():
            c1, c2, c3, c4, c5, c6 = st.columns([2, 1.2, 2, 1.5, 1, 1])
            c1.markdown(f"**{m['name']}**")
            c2.markdown(team_badge(m.get("team","")), unsafe_allow_html=True)
            c3.markdown(
                f'<div style="font-size:.75rem;color:#7a7f94;margin-bottom:2px">{weeks}/4 weeks in cycle</div>'
                f'<div class="prog-wrap"><div class="prog-fill" style="width:{pct}%"></div></div>',
                unsafe_allow_html=True
            )
            bal_class = "bal-ok" if hdays >= 1 else "bal-low"
            c4.markdown(f"<span class='{bal_class}'>{hdays} day(s)</span>", unsafe_allow_html=True)
            with c5:
                if st.button("+1 Week", key=f"wk_{m['id']}", use_container_width=True):
                    m["weeks"] = min(4, m.get("weeks", 0) + 1)
                    if m["weeks"] >= 4:
                        st.toast(f"🎉 {m['name']} completed 4 weeks! Grant holiday below.", icon="🎉")
                    persist()
                    st.rerun()
            with c6:
                if weeks >= 4:
                    if st.button("+2.5d 🎉", key=f"cyc_{m['id']}", type="primary", use_container_width=True):
                        m["hdays"] = round(m.get("hdays", 0) + 2.5, 1)
                        m["weeks"] = 0
                        d["holiday_log"].insert(0, {
                            "id": int(datetime.now().timestamp()*1000),
                            "memberId": m["id"], "memberName": m["name"],
                            "date": date.today().isoformat(),
                            "type": "add", "days": 2.5,
                            "balanceAfter": m["hdays"],
                            "notes": "4-week cycle completed",
                            "label": "Cycle complete (+2.5d)"
                        })
                        persist()
                        st.rerun()
            st.divider()

    # ── Manual record ─────────────────────────────────────────────────────
    with st.expander("📝 Record Holiday / Adjust Balance"):
        col1, col2, col3, col4 = st.columns(4)
        member_names = [m["name"] for m in d["members"]]
        with col1:
            sel_name = st.selectbox("Member", member_names)
        with col2:
            h_type = st.selectbox("Type", [
                "Use holiday days",
                "Add days (manual)",
                "Complete 4-week cycle (+2.5d)",
            ])
        with col3:
            h_days = st.number_input("Days", 0.5, 365.0, value=1.0, step=0.5)
        with col4:
            h_date = st.date_input("Date", value=date.today())

        h_notes = st.text_input("Notes (optional)")

        if st.button("✅ Record Entry", type="primary"):
            sel_m = next((m for m in d["members"] if m["name"] == sel_name), None)
            if sel_m:
                delta = 0
                label = ""
                ok    = True
                if h_type == "Use holiday days":
                    if sel_m.get("hdays", 0) < h_days:
                        st.error("⚠️ Insufficient holiday balance!")
                        ok = False
                    else:
                        delta = -h_days
                        label = "Used"
                elif h_type == "Add days (manual)":
                    delta = h_days
                    label = "Added (manual)"
                else:
                    delta = 2.5
                    label = "Cycle complete (+2.5d)"
                    sel_m["weeks"] = 0

                if ok:
                    sel_m["hdays"] = round(sel_m.get("hdays", 0) + delta, 1)
                    d["holiday_log"].insert(0, {
                        "id": int(datetime.now().timestamp()*1000),
                        "memberId": sel_m["id"], "memberName": sel_m["name"],
                        "date": h_date.isoformat(), "type": h_type,
                        "days": delta, "balanceAfter": sel_m["hdays"],
                        "notes": h_notes, "label": label
                    })
                    persist()
                    st.success(f"✅ Recorded {delta:+g}d for {sel_m['name']}")
                    st.rerun()

    # ── Log ───────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Holiday Log")
    if not d["holiday_log"]:
        st.info("No records yet.")
    else:
        log_rows = []
        for l in d["holiday_log"][:100]:
            log_rows.append({
                "Date":          fmt_date(l.get("date","")),
                "Member":        l.get("memberName",""),
                "Type":          l.get("label") or l.get("type",""),
                "Days":          f"{l.get('days',0):+g}",
                "Balance After": f"{l.get('balanceAfter',0)}d",
                "Notes":         l.get("notes","") or "—",
            })
        df_log = pd.DataFrame(log_rows)
        st.dataframe(df_log, use_container_width=True, hide_index=True)

        if st.button("🗑️ Clear All Log Entries"):
            if st.session_state.get("confirm_clear"):
                d["holiday_log"] = []
                persist()
                st.session_state.pop("confirm_clear", None)
                st.rerun()
            else:
                st.session_state["confirm_clear"] = True
                st.warning("Click again to confirm clearing all log entries.")


# ═══════════════════════════════════════════════════════════════════════════
# PAGE: STATISTICS
# ═══════════════════════════════════════════════════════════════════════════
elif page == "📊 Statistics":
    d = get_data()
    st.markdown('<div class="section-header">📊 Statistics</div>', unsafe_allow_html=True)

    members = d["members"]
    if not members:
        st.info("No team members yet.")
        st.stop()

    # KPIs
    total_hdays = sum(m.get("hdays", 0) for m in members)
    eligible    = [m for m in members if m.get("weeks", 0) >= 4]
    m_morning   = [m for m in members if m.get("team") == "morning"]
    m_afternoon = [m for m in members if m.get("team") == "afternoon"]
    m_night     = [m for m in members if m.get("team") == "night"]

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Members",     len(members))
    c2.metric("Morning 🌅",        len(m_morning))
    c3.metric("Afternoon ☀️",      len(m_afternoon))
    c4.metric("Night 🌙",          len(m_night))
    c5.metric("Total Holiday Days", round(total_hdays, 1))
    c6.metric("Eligible (+2.5d)",   len(eligible))

    st.divider()

    # Per-team breakdown
    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("Team Breakdown")
        for team_key, team_label, color in [
            ("morning",   "Morning 🌅",   "#f5c842"),
            ("afternoon", "Afternoon ☀️", "#4af0b8"),
            ("night",     "Night 🌙",     "#a78bfa"),
        ]:
            ms = [m for m in members if m.get("team") == team_key]
            st.markdown(
                f'<div style="color:{color};font-weight:700;margin:12px 0 6px">{team_label} — {len(ms)} members</div>',
                unsafe_allow_html=True
            )
            if ms:
                rows = [{"Name": m["name"], "Role": m.get("role","—"),
                         "Weeks (cycle)": f"{m.get('weeks',0)}/4",
                         "Holiday Balance": f"{m.get('hdays',0)}d"} for m in ms]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.caption("No members in this team.")

    with col_r:
        st.subheader("Holiday Balance Chart")
        if members:
            chart_df = pd.DataFrame({
                "Name":    [m["name"] for m in members],
                "Balance": [m.get("hdays", 0) for m in members],
            }).set_index("Name")
            st.bar_chart(chart_df)

        st.subheader("Members Eligible for +2.5d Holiday")
        if eligible:
            for m in eligible:
                col1, col2 = st.columns([3, 1])
                col1.markdown(
                    f"**{m['name']}** — {team_badge(m.get('team',''))} — "
                    f"<span style='color:#4af0b8'>{m.get('weeks',0)}/4 wks complete</span>",
                    unsafe_allow_html=True
                )
                with col2:
                    if st.button(f"+2.5d", key=f"stat_cyc_{m['id']}", type="primary"):
                        m["hdays"] = round(m.get("hdays", 0) + 2.5, 1)
                        m["weeks"] = 0
                        d["holiday_log"].insert(0, {
                            "id": int(datetime.now().timestamp()*1000),
                            "memberId": m["id"], "memberName": m["name"],
                            "date": date.today().isoformat(),
                            "type": "add", "days": 2.5,
                            "balanceAfter": m["hdays"],
                            "notes": "4-week cycle completed (Stats page)",
                            "label": "Cycle complete (+2.5d)"
                        })
                        persist()
                        st.rerun()
        else:
            st.info("No members have completed 4 weeks yet.")

    st.divider()
    st.subheader("Export All Data")
    col_a, col_b = st.columns(2)
    with col_a:
        mem_rows = [{
            "ID": m["id"], "Name": m["name"], "Team": m.get("team","").capitalize(),
            "Role": m.get("role",""), "Start": m.get("start",""),
            "Weeks (cycle)": m.get("weeks",0), "Holiday Balance": m.get("hdays",0),
            "Notes": m.get("notes","")
        } for m in members]
        csv_mem = pd.DataFrame(mem_rows).to_csv(index=False).encode()
        st.download_button("⬇️ Export Members CSV", csv_mem, "shiftplan_members.csv", "text/csv")
    with col_b:
        if d["holiday_log"]:
            log_rows = [{
                "Date": l.get("date",""), "Member": l.get("memberName",""),
                "Type": l.get("label",""), "Days": l.get("days",0),
                "Balance After": l.get("balanceAfter",0), "Notes": l.get("notes","")
            } for l in d["holiday_log"]]
            csv_log = pd.DataFrame(log_rows).to_csv(index=False).encode()
            st.download_button("⬇️ Export Holiday Log CSV", csv_log, "shiftplan_log.csv", "text/csv")
