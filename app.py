import streamlit as st
import pandas as pd
import json
from datetime import date, datetime, timedelta
from pathlib import Path

st.set_page_config(
    page_title="ShiftPlan — Team Holiday Manager",
    page_icon="🗓️",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_FILE = Path("shiftplan_data.json")
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ── Persistence ──────────────────────────────────────────────────────────────
def load_data():
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text())
        except:
            pass
    return {"members": [], "schedules": {}, "holiday_log": [], "next_id": 1}

def save_data(d):
    DATA_FILE.write_text(json.dumps(d, indent=2, default=str))

def get_data():
    if "data" not in st.session_state:
        st.session_state["data"] = load_data()
    return st.session_state["data"]

def persist():
    save_data(get_data())


# ── Holiday calculation ───────────────────────────────────────────────────────
def calc_normal_holidays(start_str):
    """Every 4 weeks from start date = 2.5 normal holiday days (auto)."""
    if not start_str:
        return 0.0
    try:
        start = date.fromisoformat(start_str)
        today = date.today()
        if today <= start:
            return 0.0
        weeks_worked = (today - start).days / 7
        cycles = int(weeks_worked // 4)
        return round(cycles * 2.5, 1)
    except:
        return 0.0

def calc_recup_days(member_id, schedules):
    """Count Sundays worked across all scheduled weeks = x2 recup days each."""
    total_sundays = 0
    for wk, week_data in schedules.items():
        mid = str(member_id)
        if mid in week_data:
            shift_sunday = week_data[mid].get("6", "Off")
            if shift_sunday == "Work":
                total_sundays += 1
    return total_sundays * 2


# ── Helpers ───────────────────────────────────────────────────────────────────
def get_monday(d):
    return d - timedelta(days=d.weekday())

def week_key(d):
    return get_monday(d).isoformat()

def fmt_date(s):
    if not s:
        return "—"
    try:
        return datetime.fromisoformat(s).strftime("%d %b %Y")
    except:
        return s


# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Mono:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'DM Mono', monospace; }
section[data-testid="stSidebar"] { background: #16181f !important; }
section[data-testid="stSidebar"] * { color: #e8eaf0 !important; }
.stApp { background: #0e0f13; color: #e8eaf0; }
.section-header {
    font-weight: 800; font-size: 1.15rem; color: #f5c842;
    border-bottom: 1px solid #2a2d38; padding-bottom: 8px; margin-bottom: 18px;
}
div[data-testid="metric-container"] {
    background: #16181f; border: 1px solid #2a2d38;
    border-radius: 10px; padding: 14px 18px;
}
div[data-testid="metric-container"] label { color: #7a7f94 !important; font-size:.7rem !important; }
div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
    font-size: 1.8rem !important; color: #f5c842 !important;
}
.bal-ok  { color: #4af0b8; font-weight: 600; }
.bal-low { color: #f07a4a; font-weight: 600; }
.tag-normal { background:#f5c84222; color:#f5c842; border:1px solid #f5c84255;
              padding:2px 10px; border-radius:20px; font-size:.75rem; }
.tag-recup  { background:#a78bfa22; color:#a78bfa; border:1px solid #a78bfa55;
              padding:2px 10px; border-radius:20px; font-size:.75rem; }
</style>
""", unsafe_allow_html=True)


# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🗓️ ShiftPlan")
    st.caption("Team Holiday & Shift Manager")
    st.divider()
    page = st.radio("Navigate", [
        "👥 Team Members",
        "📅 Weekly Planning",
        "🏖️ Holidays",
        "📊 Statistics"
    ], label_visibility="collapsed")
    st.divider()
    d = get_data()
    st.metric("Team Members", len(d["members"]))
    total_normal_left = sum(
        round(calc_normal_holidays(m.get("start","")) - m.get("used_normal", 0), 1)
        for m in d["members"]
    )
    total_recup_left = sum(
        round(calc_recup_days(m["id"], d["schedules"]) - m.get("used_recup", 0), 1)
        for m in d["members"]
    )
    st.metric("🟡 Normal Days Left",  round(total_normal_left, 1))
    st.metric("🟣 Récup Days Left",   round(total_recup_left, 1))


# ═══════════════════════════════════════════════════════════════════
# PAGE: TEAM MEMBERS
# ═══════════════════════════════════════════════════════════════════
if page == "👥 Team Members":
    d = get_data()
    st.markdown('<div class="section-header">👥 Team Members</div>', unsafe_allow_html=True)

    edit_id = st.session_state.get("edit_member_id")
    edit_m  = next((m for m in d["members"] if m["id"] == edit_id), None) if edit_id else None

    with st.expander("➕ Add / Edit Member", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            name = st.text_input("Full Name", value=edit_m["name"] if edit_m else "")
        with col2:
            role = st.text_input("Role / Position", value=edit_m.get("role", "") if edit_m else "")
        with col3:
            start_val = date.fromisoformat(edit_m["start"]) if edit_m and edit_m.get("start") else date.today()
            start = st.date_input("Start Date", value=start_val)

        notes_mem = st.text_input("Notes (optional)", value=edit_m.get("notes", "") if edit_m else "")

        c1, c2, _ = st.columns([1, 1, 4])
        with c1:
            save_btn = st.button("💾 Save Member", type="primary", use_container_width=True)
        with c2:
            if edit_m and st.button("✕ Cancel", use_container_width=True):
                st.session_state.pop("edit_member_id", None)
                st.rerun()

        if save_btn:
            if not name.strip():
                st.error("Please enter a name.")
            else:
                if edit_m:
                    edit_m.update({
                        "name": name.strip(), "role": role.strip(),
                        "start": start.isoformat(), "notes": notes_mem.strip()
                    })
                    persist()
                    st.session_state.pop("edit_member_id", None)
                    st.success(f"✅ {name} updated!")
                else:
                    d["members"].append({
                        "id":          d["next_id"],
                        "name":        name.strip(),
                        "role":        role.strip(),
                        "start":       start.isoformat(),
                        "notes":       notes_mem.strip(),
                        "used_normal": 0.0,
                        "used_recup":  0.0,
                    })
                    d["next_id"] += 1
                    persist()
                    st.success(f"✅ {name} added!")
                st.rerun()

    st.divider()

    if not d["members"]:
        st.info("No team members yet. Add your first member above.")
    else:
        h1,h2,h3,h4,h5,h6 = st.columns([2,1.5,1.5,2,2,1.2])
        h1.markdown("**Name**"); h2.markdown("**Role**"); h3.markdown("**Since**")
        h4.markdown("**🟡 Normal Holidays**"); h5.markdown("**🟣 Récupération**"); h6.markdown("**Actions**")
        st.divider()

        for m in d["members"]:
            earned_normal  = calc_normal_holidays(m.get("start", ""))
            used_normal    = m.get("used_normal", 0.0)
            balance_normal = round(earned_normal - used_normal, 1)

            earned_recup   = calc_recup_days(m["id"], d["schedules"])
            used_recup     = m.get("used_recup", 0.0)
            balance_recup  = round(earned_recup - used_recup, 1)

            c1,c2,c3,c4,c5,c6 = st.columns([2,1.5,1.5,2,2,1.2])
            c1.markdown(f"**{m['name']}**")
            c2.write(m.get("role") or "—")
            c3.write(fmt_date(m.get("start", "")))
            c4.markdown(
                f"Earned: **{earned_normal}d** | Used: **{used_normal}d**<br>"
                f"<span class='{'bal-ok' if balance_normal>=1 else 'bal-low'}'>▶ Left: {balance_normal}d</span>",
                unsafe_allow_html=True
            )
            c5.markdown(
                f"Earned: **{earned_recup}d** | Used: **{used_recup}d**<br>"
                f"<span class='{'bal-ok' if balance_recup>=1 else 'bal-low'}'>▶ Left: {balance_recup}d</span>",
                unsafe_allow_html=True
            )
            with c6:
                col_e, col_d = st.columns(2)
                with col_e:
                    if st.button("✏️", key=f"edit_{m['id']}"):
                        st.session_state["edit_member_id"] = m["id"]
                        st.rerun()
                with col_d:
                    if st.button("🗑️", key=f"del_{m['id']}"):
                        d["members"] = [x for x in d["members"] if x["id"] != m["id"]]
                        persist()
                        st.rerun()
            st.divider()


# ═══════════════════════════════════════════════════════════════════
# PAGE: WEEKLY PLANNING
# ═══════════════════════════════════════════════════════════════════
elif page == "📅 Weekly Planning":
    d = get_data()
    st.markdown('<div class="section-header">📅 Weekly Planning</div>', unsafe_allow_html=True)

    if not d["members"]:
        st.info("Add team members first.")
        st.stop()

    if "plan_week" not in st.session_state:
        st.session_state["plan_week"] = get_monday(date.today())

    c1, c2, c3 = st.columns([1, 3, 1])
    with c1:
        if st.button("← Prev"):
            st.session_state["plan_week"] -= timedelta(weeks=1)
            st.rerun()
    wstart = st.session_state["plan_week"]
    wend   = wstart + timedelta(days=6)
    c2.markdown(f"### {wstart.strftime('%d %b')} — {wend.strftime('%d %b %Y')}")
    with c3:
        if st.button("Next →"):
            st.session_state["plan_week"] += timedelta(weeks=1)
            st.rerun()

    wk = week_key(wstart)
    if wk not in d["schedules"]:
        d["schedules"][wk] = {}

    SHIFTS     = ["Work", "Normal Holiday", "Récupération", "Off"]
    week_dates = [wstart + timedelta(days=i) for i in range(7)]

    st.caption("💡 Sunday marked as Work → earns +2 récupération days automatically.")

    changed = False
    for m in d["members"]:
        mid = str(m["id"])
        if mid not in d["schedules"][wk]:
            d["schedules"][wk][mid] = {}

        earned_normal  = calc_normal_holidays(m.get("start", ""))
        balance_normal = round(earned_normal - m.get("used_normal", 0.0), 1)
        earned_recup   = calc_recup_days(m["id"], d["schedules"])
        balance_recup  = round(earned_recup - m.get("used_recup", 0.0), 1)

        with st.expander(
            f"**{m['name']}**  —  {m.get('role','—')}   |   "
            f"🟡 Normal: {balance_normal}d   🟣 Récup: {balance_recup}d",
            expanded=True
        ):
            cols = st.columns(7)
            for i, (col, day_date) in enumerate(zip(cols, week_dates)):
                with col:
                    is_sunday = (i == 6)
                    current   = d["schedules"][wk][mid].get(str(i), "Work")
                    day_label = f"🔴 {DAYS[i][:3]}" if is_sunday else DAYS[i][:3]
                    st.caption(f"{day_label} {day_date.day}/{day_date.month}")
                    new_val = st.selectbox(
                        "s", SHIFTS,
                        index=SHIFTS.index(current) if current in SHIFTS else 0,
                        key=f"cell_{wk}_{mid}_{i}",
                        label_visibility="collapsed"
                    )
                    if new_val != current:
                        # Normal holiday: deduct
                        if new_val == "Normal Holiday" and current != "Normal Holiday":
                            if balance_normal >= 1:
                                m["used_normal"] = round(m.get("used_normal", 0) + 1, 1)
                                d["holiday_log"].insert(0, {
                                    "id": int(datetime.now().timestamp()*1000),
                                    "memberName": m["name"], "date": day_date.isoformat(),
                                    "type": "Normal Holiday used", "days": -1,
                                    "notes": f"Planned — {DAYS[i]}"
                                })
                            else:
                                st.warning("⚠️ No normal holiday days left!")
                                new_val = current
                        # Normal holiday: restore
                        if current == "Normal Holiday" and new_val != "Normal Holiday":
                            m["used_normal"] = max(0, round(m.get("used_normal", 0) - 1, 1))

                        # Recup: deduct
                        if new_val == "Récupération" and current != "Récupération":
                            if balance_recup >= 1:
                                m["used_recup"] = round(m.get("used_recup", 0) + 1, 1)
                                d["holiday_log"].insert(0, {
                                    "id": int(datetime.now().timestamp()*1000),
                                    "memberName": m["name"], "date": day_date.isoformat(),
                                    "type": "Récupération used", "days": -1,
                                    "notes": f"Planned — {DAYS[i]}"
                                })
                            else:
                                st.warning("⚠️ No récupération days left!")
                                new_val = current
                        # Recup: restore
                        if current == "Récupération" and new_val != "Récupération":
                            m["used_recup"] = max(0, round(m.get("used_recup", 0) - 1, 1))

                        d["schedules"][wk][mid][str(i)] = new_val
                        changed = True

    if changed:
        persist()
        st.rerun()

    st.divider()
    counts = {}
    for m in d["members"]:
        mid = str(m["id"])
        for i in range(7):
            s = d["schedules"][wk].get(mid, {}).get(str(i), "Work")
            counts[s] = counts.get(s, 0) + 1

    s1,s2,s3,s4 = st.columns(4)
    s1.metric("Work",           counts.get("Work", 0))
    s2.metric("Normal Holiday", counts.get("Normal Holiday", 0))
    s3.metric("Récupération",   counts.get("Récupération", 0))
    s4.metric("Off",            counts.get("Off", 0))

    st.divider()
    rows = []
    for m in d["members"]:
        mid = str(m["id"])
        row = {"Name": m["name"], "Role": m.get("role", "")}
        for i, day_date in enumerate(week_dates):
            row[f"{DAYS[i][:3]} {day_date.day}/{day_date.month}"] = \
                d["schedules"][wk].get(mid, {}).get(str(i), "Work")
        rows.append(row)
    if rows:
        csv = pd.DataFrame(rows).to_csv(index=False).encode()
        st.download_button("⬇️ Export Week CSV", csv, f"schedule_{wk}.csv", "text/csv")


# ═══════════════════════════════════════════════════════════════════
# PAGE: HOLIDAYS
# ═══════════════════════════════════════════════════════════════════
elif page == "🏖️ Holidays":
    d = get_data()
    st.markdown('<div class="section-header">🏖️ Holiday Management</div>', unsafe_allow_html=True)

    if not d["members"]:
        st.info("Add team members first.")
        st.stop()

    st.subheader("Balances Overview")
    h1,h2,h3,h4 = st.columns([2,1.5,2.5,2.5])
    h1.markdown("**Name**"); h2.markdown("**Role**")
    h3.markdown("**🟡 Normal Holidays**"); h4.markdown("**🟣 Récupération**")
    st.divider()

    for m in d["members"]:
        earned_normal  = calc_normal_holidays(m.get("start", ""))
        used_normal    = m.get("used_normal", 0.0)
        balance_normal = round(earned_normal - used_normal, 1)

        earned_recup   = calc_recup_days(m["id"], d["schedules"])
        used_recup     = m.get("used_recup", 0.0)
        balance_recup  = round(earned_recup - used_recup, 1)

        try:
            weeks_since = (date.today() - date.fromisoformat(m.get("start", date.today().isoformat()))).days // 7
            cycles      = weeks_since // 4
        except:
            weeks_since = cycles = 0

        c1,c2,c3,c4 = st.columns([2,1.5,2.5,2.5])
        c1.markdown(f"**{m['name']}**")
        c2.write(m.get("role") or "—")
        c3.markdown(
            f"Earned: **{earned_normal}d** &nbsp;|&nbsp; Used: **{used_normal}d** &nbsp;|&nbsp; "
            f"<span class='{'bal-ok' if balance_normal>=1 else 'bal-low'}'>Left: {balance_normal}d</span><br>"
            f"<span style='color:#7a7f94;font-size:.72rem'>{weeks_since} wks worked — {cycles} cycles of 4</span>",
            unsafe_allow_html=True
        )
        c4.markdown(
            f"Earned: **{earned_recup}d** &nbsp;|&nbsp; Used: **{used_recup}d** &nbsp;|&nbsp; "
            f"<span class='{'bal-ok' if balance_recup>=1 else 'bal-low'}'>Left: {balance_recup}d</span><br>"
            f"<span style='color:#7a7f94;font-size:.72rem'>From Sundays worked in planning grid</span>",
            unsafe_allow_html=True
        )
        st.divider()

    # Manual adjustment
    with st.expander("📝 Manual Adjustment"):
        col1,col2,col3,col4,col5 = st.columns(5)
        with col1: sel_name = st.selectbox("Member", [m["name"] for m in d["members"]])
        with col2: h_cat    = st.selectbox("Type", ["Normal Holiday", "Récupération"])
        with col3: h_action = st.selectbox("Action", ["Use days", "Add days (correction)"])
        with col4: h_qty    = st.number_input("Days", 0.5, 365.0, 1.0, 0.5)
        with col5: h_note   = st.text_input("Note")
        if st.button("✅ Apply", type="primary"):
            sm = next((m for m in d["members"] if m["name"] == sel_name), None)
            if sm:
                delta = h_qty if h_action == "Add days (correction)" else -h_qty
                if h_cat == "Normal Holiday":
                    sm["used_normal"] = max(0, round(sm.get("used_normal", 0) - delta, 1))
                else:
                    sm["used_recup"] = max(0, round(sm.get("used_recup", 0) - delta, 1))
                d["holiday_log"].insert(0, {
                    "id": int(datetime.now().timestamp()*1000),
                    "memberName": sm["name"], "date": date.today().isoformat(),
                    "type": f"{h_cat} — {h_action}", "days": delta, "notes": h_note
                })
                persist()
                st.success(f"✅ Applied {delta:+g}d ({h_cat}) for {sm['name']}")
                st.rerun()

    # Log
    st.divider()
    st.subheader("Holiday Log")
    if not d["holiday_log"]:
        st.info("No records yet.")
    else:
        rows = [{
            "Date":   fmt_date(l.get("date", "")),
            "Member": l.get("memberName", ""),
            "Type":   l.get("type", ""),
            "Days":   f"{l.get('days', 0):+g}",
            "Notes":  l.get("notes", "") or "—",
        } for l in d["holiday_log"][:100]]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════
# PAGE: STATISTICS
# ═══════════════════════════════════════════════════════════════════
elif page == "📊 Statistics":
    d = get_data()
    st.markdown('<div class="section-header">📊 Statistics</div>', unsafe_allow_html=True)

    if not d["members"]:
        st.info("No team members yet.")
        st.stop()

    members = d["members"]
    total_en = sum(calc_normal_holidays(m.get("start","")) for m in members)
    total_un = sum(m.get("used_normal",0) for m in members)
    total_er = sum(calc_recup_days(m["id"], d["schedules"]) for m in members)
    total_ur = sum(m.get("used_recup",0) for m in members)

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Members",           len(members))
    c2.metric("Normal Earned",     round(total_en,1))
    c3.metric("Normal Left",       round(total_en-total_un,1))
    c4.metric("Récup Earned",      round(total_er,1))
    c5.metric("Récup Left",        round(total_er-total_ur,1))

    st.divider()
    rows = []
    for m in members:
        en = calc_normal_holidays(m.get("start",""))
        un = m.get("used_normal",0)
        er = calc_recup_days(m["id"],d["schedules"])
        ur = m.get("used_recup",0)
        try:
            weeks = (date.today()-date.fromisoformat(m.get("start",date.today().isoformat()))).days//7
        except:
            weeks = 0
        rows.append({
            "Name":          m["name"],
            "Role":          m.get("role","—"),
            "Start":         fmt_date(m.get("start","")),
            "Weeks Worked":  weeks,
            "Normal Earned": en,  "Normal Used": un, "Normal Left": round(en-un,1),
            "Récup Earned":  er,  "Récup Used":  ur, "Récup Left":  round(er-ur,1),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.divider()
    cl,cr = st.columns(2)
    with cl:
        st.subheader("🟡 Normal Holiday Balances")
        st.bar_chart(pd.DataFrame({
            "Name":  [m["name"] for m in members],
            "Left":  [round(calc_normal_holidays(m.get("start",""))-m.get("used_normal",0),1) for m in members]
        }).set_index("Name"))
    with cr:
        st.subheader("🟣 Récupération Balances")
        st.bar_chart(pd.DataFrame({
            "Name":  [m["name"] for m in members],
            "Left":  [round(calc_recup_days(m["id"],d["schedules"])-m.get("used_recup",0),1) for m in members]
        }).set_index("Name"))

    st.divider()
    csv = pd.DataFrame(rows).to_csv(index=False).encode()
    st.download_button("⬇️ Export CSV", csv, "shiftplan_stats.csv", "text/csv")
