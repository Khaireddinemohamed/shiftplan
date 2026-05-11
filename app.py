import streamlit as st
import pandas as pd
import json
import calendar
from datetime import date, datetime, timedelta
from pathlib import Path

st.set_page_config(
    page_title="ShiftPlan — Team Holiday Manager",
    page_icon="🗓️",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_FILE = Path("shiftplan_data.json")
DAYS_SHORT = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
DAYS_FULL  = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
MONTHS     = ["January","February","March","April","May","June",
              "July","August","September","October","November","December"]

SHIFT_COLORS = {
    "Morning":       ("#f5c842", "#f5c84230"),
    "Afternoon":     ("#4af0b8", "#4af0b830"),
    "Night":         ("#a78bfa", "#a78bfa30"),
    "Normal Holiday":("#f07a4a", "#f07a4a30"),
    "Récupération":  ("#60a5fa", "#60a5fa30"),
    "Sunday Work":   ("#f43f5e", "#f43f5e30"),
    "National Holiday":("#34d399","#34d39930"),
    "Off":           ("#444",    "#44444430"),
    "Work":          ("#6b7280", "#6b728030"),
}

# ── Persistence ───────────────────────────────────────────────────
def load_data():
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text())
        except:
            pass
    return {
        "members": [],
        "schedules": {},          # wk -> mid -> day_idx -> shift
        "night_quarters": {},     # "YYYY-Q#" -> [member_ids]
        "sunday_assignments": {}, # wk -> [member_ids]
        "national_holidays": {},  # "YYYY-MM-DD" -> {"name": str, "team": [member_ids]}
        "holiday_log": [],
        "next_id": 1
    }

def save_data(d):
    DATA_FILE.write_text(json.dumps(d, indent=2, default=str))

def get_data():
    if "data" not in st.session_state:
        st.session_state["data"] = load_data()
    return st.session_state["data"]

def persist():
    save_data(get_data())

# ── Calculations ──────────────────────────────────────────────────
def calc_normal_holidays(start_str):
    if not start_str:
        return 0.0
    try:
        start = date.fromisoformat(start_str)
        today = date.today()
        if today <= start:
            return 0.0
        weeks = (today - start).days / 7
        return round(int(weeks // 4) * 2.5, 1)
    except:
        return 0.0

def calc_recup_earned(member_id, data):
    """Auto recup: Sundays worked + national holidays assigned to member."""
    mid = str(member_id)
    total = 0
    # Sundays from schedule
    for wk, week_data in data["schedules"].items():
        if mid in week_data:
            s = week_data[mid].get("6", "Work")
            if s == "Sunday Work":
                total += 2
    # Sunday permanence assignments
    for wk, members in data.get("sunday_assignments", {}).items():
        if member_id in members:
            # check not already counted via schedule
            if mid not in data["schedules"].get(wk, {}):
                total += 2
    # National holidays
    for day_str, nh in data.get("national_holidays", {}).items():
        if member_id in nh.get("team", []):
            total += 2
    return total

def get_monday(d):
    return d - timedelta(days=d.weekday())

def week_key(d):
    return get_monday(d).isoformat()

def quarter_key(d):
    q = (d.month - 1) // 3 + 1
    return f"{d.year}-Q{q}"

def quarter_label(qk):
    year, q = qk.split("-")
    months = {1:"Jan–Mar", 2:"Apr–Jun", 3:"Jul–Sep", 4:"Oct–Dec"}
    return f"Q{q[1]} {year} ({months[int(q[1])]})"

def fmt_date(s):
    if not s:
        return "—"
    try:
        return datetime.fromisoformat(s).strftime("%d %b %Y")
    except:
        return s

def member_name(mid, members):
    m = next((x for x in members if x["id"] == mid), None)
    return m["name"] if m else "?"

# ── CSS ───────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Mono:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'DM Mono', monospace; }
section[data-testid="stSidebar"] { background: #16181f !important; }
section[data-testid="stSidebar"] * { color: #e8eaf0 !important; }
.stApp { background: #0e0f13; color: #e8eaf0; }
.section-header {
    font-weight:800; font-size:1.15rem; color:#f5c842;
    border-bottom:1px solid #2a2d38; padding-bottom:8px; margin-bottom:18px;
}
div[data-testid="metric-container"] {
    background:#16181f; border:1px solid #2a2d38; border-radius:10px; padding:14px;
}
div[data-testid="metric-container"] label { color:#7a7f94 !important; font-size:.7rem !important; }
div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
    font-size:1.8rem !important; color:#f5c842 !important;
}
.bal-ok  { color:#4af0b8; font-weight:600; }
.bal-low { color:#f07a4a; font-weight:600; }
/* Calendar grid */
.cal-grid { display:grid; grid-template-columns:repeat(7,1fr); gap:4px; margin-top:8px; }
.cal-header { text-align:center; font-size:.7rem; color:#7a7f94; padding:4px;
              text-transform:uppercase; letter-spacing:1px; }
.cal-day {
    min-height:70px; border-radius:6px; padding:4px 6px;
    border:1px solid #2a2d38; background:#16181f;
    font-size:.72rem; cursor:pointer; position:relative;
}
.cal-day.today { border-color:#f5c842 !important; }
.cal-day.other-month { opacity:.35; }
.cal-day .day-num { font-size:.8rem; font-weight:700; margin-bottom:3px; }
.cal-day .shift-tag {
    display:inline-block; padding:1px 5px; border-radius:3px;
    font-size:.62rem; margin:1px 0; white-space:nowrap;
    overflow:hidden; text-overflow:ellipsis; max-width:100%;
}
.cal-day.national-holiday { background:#34d39915; border-color:#34d39955; }
.legend-dot { display:inline-block; width:10px; height:10px;
              border-radius:3px; margin-right:5px; }
.shift-select-row { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:4px; }
</style>
""", unsafe_allow_html=True)

# ── SIDEBAR ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🗓️ ShiftPlan")
    st.caption("Team Holiday & Shift Manager")
    st.divider()
    page = st.radio("Navigate", [
        "👥 Team Members",
        "📅 Planning",
        "🌙 Night Shift (Quarterly)",
        "🏖️ Holidays",
        "📊 Statistics"
    ], label_visibility="collapsed")
    st.divider()
    d = get_data()
    st.metric("Team Members", len(d["members"]))
    total_nl = sum(
        round(calc_normal_holidays(m.get("start","")) - m.get("used_normal",0), 1)
        for m in d["members"]
    )
    total_rl = sum(
        round(calc_recup_earned(m["id"], d) - m.get("used_recup",0), 1)
        for m in d["members"]
    )
    st.metric("🟡 Normal Days Left", round(total_nl, 1))
    st.metric("🟣 Récup Days Left",  round(total_rl, 1))

    # Legend
    st.divider()
    st.caption("SHIFT LEGEND")
    for name, (fg, bg) in SHIFT_COLORS.items():
        st.markdown(
            f'<span class="legend-dot" style="background:{fg}"></span>'
            f'<span style="font-size:.72rem">{name}</span>',
            unsafe_allow_html=True
        )


# ═══════════════════════════════════════════════════════════════════
# PAGE: TEAM MEMBERS
# ═══════════════════════════════════════════════════════════════════
if page == "👥 Team Members":
    d = get_data()
    st.markdown('<div class="section-header">👥 Team Members</div>', unsafe_allow_html=True)

    edit_id = st.session_state.get("edit_member_id")
    edit_m  = next((m for m in d["members"] if m["id"] == edit_id), None) if edit_id else None

    with st.expander("➕ Add / Edit Member", expanded=True):
        c1,c2,c3 = st.columns(3)
        with c1: name  = st.text_input("Full Name",       value=edit_m["name"]         if edit_m else "")
        with c2: role  = st.text_input("Role / Position", value=edit_m.get("role","")  if edit_m else "")
        with c3:
            sv = date.fromisoformat(edit_m["start"]) if edit_m and edit_m.get("start") else date.today()
            start = st.date_input("Start Date", value=sv)
        notes = st.text_input("Notes (optional)", value=edit_m.get("notes","") if edit_m else "")

        # Manual recup input
        recup_manual = st.number_input(
            "➕ Manual Récupération days to add",
            min_value=0.0, max_value=365.0,
            value=float(edit_m.get("recup_manual",0)) if edit_m else 0.0,
            step=0.5,
            help="Days added manually by manager (not from schedule)"
        )

        ca,cb,_ = st.columns([1,1,4])
        with ca: save_btn = st.button("💾 Save", type="primary", use_container_width=True)
        with cb:
            if edit_m and st.button("✕ Cancel", use_container_width=True):
                st.session_state.pop("edit_member_id", None); st.rerun()

        if save_btn:
            if not name.strip():
                st.error("Enter a name.")
            else:
                if edit_m:
                    edit_m.update({
                        "name": name.strip(), "role": role.strip(),
                        "start": start.isoformat(), "notes": notes.strip(),
                        "recup_manual": recup_manual
                    })
                    persist(); st.session_state.pop("edit_member_id", None)
                    st.success(f"✅ {name} updated!"); st.rerun()
                else:
                    d["members"].append({
                        "id": d["next_id"], "name": name.strip(), "role": role.strip(),
                        "start": start.isoformat(), "notes": notes.strip(),
                        "used_normal": 0.0, "used_recup": 0.0, "recup_manual": recup_manual
                    })
                    d["next_id"] += 1; persist()
                    st.success(f"✅ {name} added!"); st.rerun()

    st.divider()
    if not d["members"]:
        st.info("No team members yet.")
    else:
        h1,h2,h3,h4,h5,h6 = st.columns([2,1.5,1.5,2.2,2.2,1.2])
        for h,t in zip([h1,h2,h3,h4,h5,h6],
                       ["Name","Role","Since","🟡 Normal Holidays","🟣 Récupération","Actions"]):
            h.markdown(f"**{t}**")
        st.divider()

        for m in d["members"]:
            en  = calc_normal_holidays(m.get("start",""))
            un  = m.get("used_normal", 0.0)
            bn  = round(en - un, 1)
            er_auto   = calc_recup_earned(m["id"], d)
            er_manual = m.get("recup_manual", 0.0)
            er_total  = round(er_auto + er_manual, 1)
            ur  = m.get("used_recup", 0.0)
            br  = round(er_total - ur, 1)

            c1,c2,c3,c4,c5,c6 = st.columns([2,1.5,1.5,2.2,2.2,1.2])
            c1.markdown(f"**{m['name']}**")
            c2.write(m.get("role") or "—")
            c3.write(fmt_date(m.get("start","")))
            c4.markdown(
                f"Earned: **{en}d** | Used: **{un}d**<br>"
                f"<span class='{'bal-ok' if bn>=1 else 'bal-low'}'>▶ Left: {bn}d</span>",
                unsafe_allow_html=True)
            c5.markdown(
                f"Auto: **{er_auto}d** + Manual: **{er_manual}d** | Used: **{ur}d**<br>"
                f"<span class='{'bal-ok' if br>=1 else 'bal-low'}'>▶ Left: {br}d</span>",
                unsafe_allow_html=True)
            with c6:
                ce,cd = st.columns(2)
                with ce:
                    if st.button("✏️", key=f"e_{m['id']}"):
                        st.session_state["edit_member_id"] = m["id"]; st.rerun()
                with cd:
                    if st.button("🗑️", key=f"d_{m['id']}"):
                        d["members"] = [x for x in d["members"] if x["id"] != m["id"]]
                        persist(); st.rerun()
            st.divider()


# ═══════════════════════════════════════════════════════════════════
# PAGE: PLANNING
# ═══════════════════════════════════════════════════════════════════
elif page == "📅 Planning":
    d = get_data()
    st.markdown('<div class="section-header">📅 Planning</div>', unsafe_allow_html=True)

    if not d["members"]:
        st.info("Add team members first."); st.stop()

    # ── Top controls ──────────────────────────────────────────────
    view_mode = st.radio("View", ["📅 Calendar", "📋 Table"], horizontal=True)
    st.divider()

    # Week navigation
    if "plan_week" not in st.session_state:
        st.session_state["plan_week"] = get_monday(date.today())
    if "plan_month" not in st.session_state:
        st.session_state["plan_month"] = date.today().replace(day=1)

    members = d["members"]
    member_options = {m["name"]: m["id"] for m in members}

    # ── NATIONAL HOLIDAYS manager ─────────────────────────────────
    with st.expander("🌍 National Holidays Manager"):
        nh_col1, nh_col2, nh_col3 = st.columns(3)
        with nh_col1: nh_date = st.date_input("Holiday Date", value=date.today(), key="nh_date")
        with nh_col2: nh_name = st.text_input("Holiday Name", placeholder="e.g. Independence Day")
        with nh_col3:
            nh_team = st.multiselect(
                "Assign Team (gets +2 recup each)",
                options=list(member_options.keys())
            )
        if st.button("➕ Add National Holiday", type="primary"):
            if nh_name.strip():
                dk = nh_date.isoformat()
                d["national_holidays"][dk] = {
                    "name": nh_name.strip(),
                    "team": [member_options[n] for n in nh_team]
                }
                persist()
                st.success(f"✅ {nh_name} added on {fmt_date(dk)}")
                st.rerun()
            else:
                st.error("Enter a holiday name.")

        if d["national_holidays"]:
            st.markdown("**Existing National Holidays:**")
            for dk, nh in sorted(d["national_holidays"].items()):
                team_names = [member_name(mid, members) for mid in nh.get("team",[])]
                col_a, col_b = st.columns([4,1])
                col_a.markdown(
                    f"📅 **{fmt_date(dk)}** — {nh['name']} "
                    f"| Team: {', '.join(team_names) if team_names else 'None'}"
                )
                with col_b:
                    if st.button("🗑️", key=f"nh_del_{dk}"):
                        del d["national_holidays"][dk]; persist(); st.rerun()

    st.divider()

    # ──────────────────────────────────────────────────────────────
    # CALENDAR VIEW
    # ──────────────────────────────────────────────────────────────
    if view_mode == "📅 Calendar":
        # Month nav
        cn1,cn2,cn3,_,cn4 = st.columns([1,2,1,2,3])
        with cn1:
            if st.button("◀", key="cal_prev"):
                pm = st.session_state["plan_month"]
                st.session_state["plan_month"] = (pm.replace(day=1) - timedelta(days=1)).replace(day=1)
                st.rerun()
        pm = st.session_state["plan_month"]
        cn2.markdown(f"### {MONTHS[pm.month-1]} {pm.year}")
        with cn3:
            if st.button("▶", key="cal_next"):
                nm = pm.replace(day=28) + timedelta(days=4)
                st.session_state["plan_month"] = nm.replace(day=1)
                st.rerun()
        with cn4:
            cal_member_filter = st.selectbox(
                "Show member", ["All"] + list(member_options.keys()), key="cal_member"
            )

        # Build calendar
        year, month = pm.year, pm.month
        first_day = date(year, month, 1)
        last_day  = date(year, month, calendar.monthrange(year,month)[1])

        # Pad start to Monday
        start_pad = first_day - timedelta(days=first_day.weekday())
        end_pad   = last_day + timedelta(days=6 - last_day.weekday())

        # Header row
        header_html = "".join(
            f'<div class="cal-header">{d_}</div>' for d_ in DAYS_SHORT
        )

        # Build day cells
        cells_html = ""
        cur = start_pad
        while cur <= end_pad:
            dk   = cur.isoformat()
            wk   = week_key(cur)
            dow  = cur.weekday()  # 0=Mon, 6=Sun
            is_today      = (cur == date.today())
            is_other_month= (cur.month != month)
            is_national   = dk in d["national_holidays"]
            is_sunday     = (dow == 6)

            cls = "cal-day"
            if is_today:        cls += " today"
            if is_other_month:  cls += " other-month"
            if is_national:     cls += " national-holiday"

            inner = f'<div class="day-num">{cur.day}{"🌍" if is_national else "🔴" if is_sunday else ""}</div>'

            # National holiday label
            if is_national:
                nh_info = d["national_holidays"][dk]
                inner += f'<div class="shift-tag" style="background:#34d39930;color:#34d399">🌍 {nh_info["name"]}</div>'

            # Member shifts
            for m in members:
                if cal_member_filter != "All" and m["name"] != cal_member_filter:
                    continue
                mid = str(m["id"])
                shift = d["schedules"].get(wk, {}).get(mid, {}).get(str(dow), "")

                # Sunday assignment
                if is_sunday and m["id"] in d.get("sunday_assignments", {}).get(wk, []):
                    shift = "Sunday Work"

                # Night quarter
                qk = quarter_key(cur)
                if m["id"] in d.get("night_quarters", {}).get(qk, []):
                    if not shift:
                        shift = "Night"

                if shift and shift != "Work":
                    fg, bg = SHIFT_COLORS.get(shift, ("#888","#88888830"))
                    label  = m["name"] if cal_member_filter == "All" else shift
                    inner += f'<div class="shift-tag" style="background:{bg};color:{fg}">{label}: {shift}</div>'

            cells_html += f'<div class="{cls}">{inner}</div>'
            cur += timedelta(days=1)

        st.markdown(
            f'<div class="cal-grid">{header_html}{cells_html}</div>',
            unsafe_allow_html=True
        )

    # ──────────────────────────────────────────────────────────────
    # TABLE VIEW
    # ──────────────────────────────────────────────────────────────
    else:
        # Week nav
        t1,t2,t3 = st.columns([1,3,1])
        with t1:
            if st.button("← Prev Week"):
                st.session_state["plan_week"] -= timedelta(weeks=1); st.rerun()
        wstart = st.session_state["plan_week"]
        wend   = wstart + timedelta(days=6)
        t2.markdown(f"### {wstart.strftime('%d %b')} — {wend.strftime('%d %b %Y')}")
        with t3:
            if st.button("Next Week →"):
                st.session_state["plan_week"] += timedelta(weeks=1); st.rerun()

        wk         = week_key(wstart)
        week_dates = [wstart + timedelta(days=i) for i in range(7)]
        if wk not in d["schedules"]: d["schedules"][wk] = {}
        if "sunday_assignments" not in d: d["sunday_assignments"] = {}
        if wk not in d["sunday_assignments"]: d["sunday_assignments"][wk] = []

        WEEK_SHIFTS = ["Work","Morning","Afternoon","Normal Holiday","Récupération","Off"]

        # ── Sunday permanence ──────────────────────────────────
        st.markdown("#### 🔴 Sunday Permanence")
        sun_date   = wstart + timedelta(days=6)
        sun_dk     = sun_date.isoformat()
        is_nat_sun = sun_dk in d["national_holidays"]

        cur_sunday_names = [
            m["name"] for m in members
            if m["id"] in d["sunday_assignments"].get(wk, [])
        ]
        new_sunday = st.multiselect(
            f"Members working Sunday {sun_date.day}/{sun_date.month}"
            + (f" 🌍 {d['national_holidays'][sun_dk]['name']}" if is_nat_sun else ""),
            options=list(member_options.keys()),
            default=cur_sunday_names,
            key=f"sun_{wk}"
        )
        if sorted([member_options[n] for n in new_sunday]) != sorted(d["sunday_assignments"].get(wk,[])):
            old_ids = d["sunday_assignments"].get(wk, [])
            new_ids = [member_options[n] for n in new_sunday]
            # Add recup for newly added sunday workers
            for mid in new_ids:
                if mid not in old_ids:
                    m = next((x for x in members if x["id"] == mid), None)
                    if m:
                        d["holiday_log"].insert(0, {
                            "id": int(datetime.now().timestamp()*1000),
                            "memberName": m["name"],
                            "date": sun_date.isoformat(),
                            "type": "Récupération earned (Sunday work)",
                            "days": +2,
                            "notes": f"Sunday {sun_date.strftime('%d %b %Y')}"
                        })
                        if is_nat_sun:
                            d["holiday_log"].insert(0, {
                                "id": int(datetime.now().timestamp()*1000)+1,
                                "memberName": m["name"],
                                "date": sun_date.isoformat(),
                                "type": "Récupération earned (National Holiday)",
                                "days": +2,
                                "notes": d['national_holidays'][sun_dk]['name']
                            })
            d["sunday_assignments"][wk] = new_ids
            persist(); st.rerun()

        st.divider()

        # ── Morning / Afternoon shifts ─────────────────────────
        st.markdown("#### ☀️ Morning & Afternoon Shifts")
        st.caption("Click a cell to assign shift. Night shifts are managed in the Night Shift (Quarterly) page.")

        changed = False
        for m in members:
            mid = str(m["id"])
            if mid not in d["schedules"][wk]: d["schedules"][wk][mid] = {}

            en  = calc_normal_holidays(m.get("start",""))
            bn  = round(en - m.get("used_normal",0), 1)
            er  = round(calc_recup_earned(m["id"],d) + m.get("recup_manual",0) - m.get("used_recup",0), 1)
            qk  = quarter_key(wstart)
            is_night = m["id"] in d.get("night_quarters",{}).get(qk,[])

            with st.expander(
                f"**{m['name']}** — {m.get('role','—')}   "
                f"{'🌙 Night Shift (Quarterly)' if is_night else ''}   "
                f"🟡 {bn}d  🟣 {er}d",
                expanded=not is_night
            ):
                if is_night:
                    st.info("🌙 This member is on night shift this quarter. Managed in Night Shift page.")
                    continue

                cols = st.columns(7)
                for i, (col, day_date) in enumerate(zip(cols, week_dates)):
                    with col:
                        is_sun = (i == 6)
                        is_nat = day_date.isoformat() in d["national_holidays"]
                        sun_assigned = is_sun and m["id"] in d["sunday_assignments"].get(wk,[])

                        day_label = (
                            f"🌍 {DAYS_SHORT[i]}" if is_nat else
                            f"🔴 {DAYS_SHORT[i]}" if is_sun else
                            DAYS_SHORT[i]
                        )
                        st.caption(f"{day_label} {day_date.day}/{day_date.month}")

                        if sun_assigned:
                            st.markdown(
                                '<div style="background:#f43f5e20;color:#f43f5e;'
                                'border:1px solid #f43f5e50;border-radius:4px;'
                                'padding:4px 8px;font-size:.75rem;text-align:center">'
                                '🔴 Sunday Work</div>',
                                unsafe_allow_html=True
                            )
                            continue

                        if is_nat and not is_sun:
                            st.markdown(
                                f'<div style="background:#34d39920;color:#34d399;'
                                f'border:1px solid #34d39950;border-radius:4px;'
                                f'padding:4px 8px;font-size:.75rem;text-align:center">'
                                f'🌍 National Holiday</div>',
                                unsafe_allow_html=True
                            )

                        current = d["schedules"][wk][mid].get(str(i), "Work")
                        new_val = st.selectbox(
                            "s", WEEK_SHIFTS,
                            index=WEEK_SHIFTS.index(current) if current in WEEK_SHIFTS else 0,
                            key=f"cell_{wk}_{mid}_{i}",
                            label_visibility="collapsed"
                        )
                        if new_val != current:
                            # Deduct normal holiday
                            if new_val == "Normal Holiday" and current != "Normal Holiday":
                                if bn >= 1:
                                    m["used_normal"] = round(m.get("used_normal",0)+1, 1)
                                    d["holiday_log"].insert(0,{"id":int(datetime.now().timestamp()*1000),
                                        "memberName":m["name"],"date":day_date.isoformat(),
                                        "type":"Normal Holiday used","days":-1,"notes":f"{DAYS_FULL[i]}"})
                                else:
                                    st.warning("No normal holiday days!"); new_val = current
                            if current == "Normal Holiday" and new_val != "Normal Holiday":
                                m["used_normal"] = max(0, round(m.get("used_normal",0)-1, 1))

                            # Deduct recup
                            if new_val == "Récupération" and current != "Récupération":
                                er_now = round(calc_recup_earned(m["id"],d)+m.get("recup_manual",0)-m.get("used_recup",0),1)
                                if er_now >= 1:
                                    m["used_recup"] = round(m.get("used_recup",0)+1, 1)
                                    d["holiday_log"].insert(0,{"id":int(datetime.now().timestamp()*1000),
                                        "memberName":m["name"],"date":day_date.isoformat(),
                                        "type":"Récupération used","days":-1,"notes":f"{DAYS_FULL[i]}"})
                                else:
                                    st.warning("No récupération days!"); new_val = current
                            if current == "Récupération" and new_val != "Récupération":
                                m["used_recup"] = max(0, round(m.get("used_recup",0)-1, 1))

                            d["schedules"][wk][mid][str(i)] = new_val
                            changed = True

        if changed:
            persist(); st.rerun()

        # Summary row
        st.divider()
        counts = {}
        for m in members:
            mid = str(m["id"])
            for i in range(7):
                s = d["schedules"][wk].get(mid,{}).get(str(i),"Work")
                counts[s] = counts.get(s,0)+1
        # Add sunday permanence count
        counts["Sunday Work"] = counts.get("Sunday Work",0) + len(d["sunday_assignments"].get(wk,[]))

        s1,s2,s3,s4,s5 = st.columns(5)
        s1.metric("Morning",        counts.get("Morning",0))
        s2.metric("Afternoon",      counts.get("Afternoon",0))
        s3.metric("Sunday Work",    counts.get("Sunday Work",0))
        s4.metric("Normal Holiday", counts.get("Normal Holiday",0))
        s5.metric("Récupération",   counts.get("Récupération",0))

        # Export
        st.divider()
        rows = []
        for m in members:
            mid = str(m["id"])
            row = {"Name": m["name"], "Role": m.get("role","")}
            for i, dd in enumerate(week_dates):
                qk  = quarter_key(dd)
                is_night  = m["id"] in d.get("night_quarters",{}).get(qk,[])
                is_sun    = (i==6) and m["id"] in d["sunday_assignments"].get(wk,[])
                shift = ("Night" if is_night else
                         "Sunday Work" if is_sun else
                         d["schedules"][wk].get(mid,{}).get(str(i),"Work"))
                row[f"{DAYS_SHORT[i]} {dd.day}/{dd.month}"] = shift
            rows.append(row)
        csv = pd.DataFrame(rows).to_csv(index=False).encode()
        st.download_button("⬇️ Export Week CSV", csv, f"schedule_{wk}.csv","text/csv")


# ═══════════════════════════════════════════════════════════════════
# PAGE: NIGHT SHIFT (QUARTERLY)
# ═══════════════════════════════════════════════════════════════════
elif page == "🌙 Night Shift (Quarterly)":
    d = get_data()
    st.markdown('<div class="section-header">🌙 Night Shift — Quarterly Assignment</div>', unsafe_allow_html=True)

    if not d["members"]:
        st.info("Add team members first."); st.stop()

    if "night_quarters" not in d: d["night_quarters"] = {}

    # Quarter selector
    today = date.today()
    quarters = []
    for year in [today.year - 1, today.year, today.year + 1]:
        for q in range(1, 5):
            quarters.append(f"{year}-Q{q}")
    current_qk   = quarter_key(today)
    default_idx  = quarters.index(current_qk) if current_qk in quarters else 4
    selected_qk  = st.selectbox("Select Quarter", quarters, index=default_idx)

    st.markdown(f"#### {quarter_label(selected_qk)}")

    # Which months are in this quarter
    q_num  = int(selected_qk.split("Q")[1])
    q_year = int(selected_qk.split("-")[0])
    q_months = [(q_num-1)*3 + i + 1 for i in range(3)]
    q_start  = date(q_year, q_months[0], 1)
    q_end_m  = q_months[-1]
    q_end    = date(q_year, q_end_m, calendar.monthrange(q_year, q_end_m)[1])
    st.caption(f"Period: {fmt_date(q_start.isoformat())} → {fmt_date(q_end.isoformat())}")

    member_options = {m["name"]: m["id"] for m in d["members"]}
    current_night  = d["night_quarters"].get(selected_qk, [])
    current_names  = [m["name"] for m in d["members"] if m["id"] in current_night]

    new_night = st.multiselect(
        "Assign members to Night Shift for this quarter",
        options=list(member_options.keys()),
        default=current_names,
        help="These members will show as Night Shift on the calendar for the entire quarter"
    )

    if st.button("💾 Save Night Shift Assignment", type="primary"):
        d["night_quarters"][selected_qk] = [member_options[n] for n in new_night]
        persist()
        st.success(f"✅ Night shift saved for {quarter_label(selected_qk)}")
        st.rerun()

    st.divider()

    # Show all quarters
    st.subheader("All Quarter Assignments")
    if not d["night_quarters"]:
        st.info("No quarters assigned yet.")
    else:
        rows = []
        for qk, mids in sorted(d["night_quarters"].items()):
            names = [member_name(mid, d["members"]) for mid in mids]
            rows.append({
                "Quarter": quarter_label(qk),
                "Members on Night Shift": ", ".join(names) if names else "None"
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════
# PAGE: HOLIDAYS
# ═══════════════════════════════════════════════════════════════════
elif page == "🏖️ Holidays":
    d = get_data()
    st.markdown('<div class="section-header">🏖️ Holiday Management</div>', unsafe_allow_html=True)

    if not d["members"]:
        st.info("Add team members first."); st.stop()

    st.subheader("Balances Overview")
    h1,h2,h3,h4 = st.columns([2,1.5,2.5,2.5])
    for h,t in zip([h1,h2,h3,h4],["Name","Role","🟡 Normal Holidays","🟣 Récupération"]):
        h.markdown(f"**{t}**")
    st.divider()

    for m in d["members"]:
        en  = calc_normal_holidays(m.get("start",""))
        un  = m.get("used_normal", 0.0)
        bn  = round(en - un, 1)
        er_auto   = calc_recup_earned(m["id"], d)
        er_manual = m.get("recup_manual", 0.0)
        er_total  = round(er_auto + er_manual, 1)
        ur  = m.get("used_recup", 0.0)
        br  = round(er_total - ur, 1)
        try:
            weeks  = (date.today()-date.fromisoformat(m.get("start",date.today().isoformat()))).days//7
            cycles = weeks // 4
        except:
            weeks = cycles = 0

        c1,c2,c3,c4 = st.columns([2,1.5,2.5,2.5])
        c1.markdown(f"**{m['name']}**")
        c2.write(m.get("role") or "—")
        c3.markdown(
            f"Earned: **{en}d** | Used: **{un}d** | "
            f"<span class='{'bal-ok' if bn>=1 else 'bal-low'}'>Left: {bn}d</span><br>"
            f"<span style='color:#7a7f94;font-size:.72rem'>{weeks} wks / {cycles} cycles of 4</span>",
            unsafe_allow_html=True)
        c4.markdown(
            f"Auto: **{er_auto}d** + Manual: **{er_manual}d** | Used: **{ur}d** | "
            f"<span class='{'bal-ok' if br>=1 else 'bal-low'}'>Left: {br}d</span><br>"
            f"<span style='color:#7a7f94;font-size:.72rem'>Sundays + National Holidays + Manual</span>",
            unsafe_allow_html=True)
        st.divider()

    # Manual adjustment
    with st.expander("📝 Manual Adjustment / Correction"):
        a,b,c,dd,e = st.columns(5)
        with a: sn  = st.selectbox("Member", [m["name"] for m in d["members"]])
        with b: hcat= st.selectbox("Type", ["Normal Holiday","Récupération"])
        with c: hact= st.selectbox("Action", ["Use days","Add days (correction)"])
        with dd:hqty= st.number_input("Days",0.5,365.0,1.0,0.5)
        with e: hnote=st.text_input("Note")
        if st.button("✅ Apply", type="primary"):
            sm = next((m for m in d["members"] if m["name"]==sn), None)
            if sm:
                delta = hqty if hact=="Add days (correction)" else -hqty
                if hcat=="Normal Holiday":
                    sm["used_normal"] = max(0, round(sm.get("used_normal",0)-delta,1))
                else:
                    sm["used_recup"] = max(0, round(sm.get("used_recup",0)-delta,1))
                d["holiday_log"].insert(0,{
                    "id":int(datetime.now().timestamp()*1000),
                    "memberName":sm["name"],"date":date.today().isoformat(),
                    "type":f"{hcat} — {hact}","days":delta,"notes":hnote})
                persist(); st.success(f"✅ {delta:+g}d ({hcat}) for {sm['name']}"); st.rerun()

    st.divider()
    st.subheader("Holiday Log")
    if not d["holiday_log"]:
        st.info("No records yet.")
    else:
        rows = [{"Date":fmt_date(l.get("date","")),"Member":l.get("memberName",""),
                 "Type":l.get("type",""),"Days":f"{l.get('days',0):+g}",
                 "Notes":l.get("notes","") or "—"} for l in d["holiday_log"][:100]]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════
# PAGE: STATISTICS
# ═══════════════════════════════════════════════════════════════════
elif page == "📊 Statistics":
    d = get_data()
    st.markdown('<div class="section-header">📊 Statistics</div>', unsafe_allow_html=True)

    if not d["members"]:
        st.info("No team members yet."); st.stop()

    members = d["members"]
    total_en = sum(calc_normal_holidays(m.get("start","")) for m in members)
    total_un = sum(m.get("used_normal",0) for m in members)
    total_er = sum(calc_recup_earned(m["id"],d)+m.get("recup_manual",0) for m in members)
    total_ur = sum(m.get("used_recup",0) for m in members)

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Members",       len(members))
    c2.metric("Normal Earned", round(total_en,1))
    c3.metric("Normal Left",   round(total_en-total_un,1))
    c4.metric("Récup Earned",  round(total_er,1))
    c5.metric("Récup Left",    round(total_er-total_ur,1))

    st.divider()
    rows = []
    for m in members:
        en = calc_normal_holidays(m.get("start",""))
        un = m.get("used_normal",0)
        er = round(calc_recup_earned(m["id"],d)+m.get("recup_manual",0),1)
        ur = m.get("used_recup",0)
        qk = quarter_key(date.today())
        is_night = m["id"] in d.get("night_quarters",{}).get(qk,[])
        try:
            weeks = (date.today()-date.fromisoformat(m.get("start",date.today().isoformat()))).days//7
        except: weeks=0
        rows.append({
            "Name":m["name"],"Role":m.get("role","—"),
            "Start":fmt_date(m.get("start","")),
            "Weeks":weeks, "Current Shift":"🌙 Night" if is_night else "☀️ Day",
            "Normal Earned":en,"Normal Used":un,"Normal Left":round(en-un,1),
            "Récup Earned":er,"Récup Used":ur,"Récup Left":round(er-ur,1),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.divider()
    cl,cr = st.columns(2)
    with cl:
        st.subheader("🟡 Normal Holiday Balances")
        st.bar_chart(pd.DataFrame({
            "Name":[m["name"] for m in members],
            "Left":[round(calc_normal_holidays(m.get("start",""))-m.get("used_normal",0),1) for m in members]
        }).set_index("Name"))
    with cr:
        st.subheader("🟣 Récupération Balances")
        st.bar_chart(pd.DataFrame({
            "Name":[m["name"] for m in members],
            "Left":[round(calc_recup_earned(m["id"],d)+m.get("recup_manual",0)-m.get("used_recup",0),1) for m in members]
        }).set_index("Name"))

    st.divider()
    csv = pd.DataFrame(rows).to_csv(index=False).encode()
    st.download_button("⬇️ Export CSV", csv, "shiftplan_stats.csv","text/csv")
