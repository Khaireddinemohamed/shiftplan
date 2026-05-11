import streamlit as st
import pandas as pd
import json
import calendar
from datetime import date, datetime, timedelta
from pathlib import Path

st.set_page_config(
    page_title="ShiftPlan",
    page_icon="🗓️",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_FILE = Path("shiftplan_data.json")

DAYS_SHORT = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
DAYS_FULL  = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
MONTHS     = ["January","February","March","April","May","June",
              "July","August","September","October","November","December"]

# Professional muted palette — no icons
SHIFT_STYLE = {
    "Morning":          {"fg":"#b8860b","bg":"#b8860b18","border":"#b8860b40"},
    "Afternoon":        {"fg":"#2e7d6e","bg":"#2e7d6e18","border":"#2e7d6e40"},
    "Night":            {"fg":"#5c6bc0","bg":"#5c6bc018","border":"#5c6bc040"},
    "Sunday Work":      {"fg":"#c0392b","bg":"#c0392b18","border":"#c0392b40"},
    "Normal Holiday":   {"fg":"#7b5ea7","bg":"#7b5ea718","border":"#7b5ea740"},
    "Récupération":     {"fg":"#2471a3","bg":"#2471a318","border":"#2471a340"},
    "National Holiday": {"fg":"#1e8449","bg":"#1e844918","border":"#1e844940"},
    "Off":              {"fg":"#707070","bg":"#70707012","border":"#70707030"},
}

# ── Persistence ───────────────────────────────────────────────────
def load_data():
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text())
        except:
            pass
    return default_data()

def default_data():
    return {
        "members": [],
        # Weekly shift groups: week_key -> {"morning":[ids], "afternoon":[ids]}
        "weekly_shifts": {},
        # Sunday permanence: week_key -> [ids]
        "sunday_assignments": {},
        # Night quarters: "YYYY-Q#" -> {"a":[ids], "b":[ids], "active":"a"}
        "night_quarters": {},
        # National holidays: "YYYY-MM-DD" -> {"name":str, "team":[ids]}
        "national_holidays": {},
        # Individual overrides: week_key -> member_id -> day_idx -> shift
        "overrides": {},
        "holiday_log": [],
        "next_id": 1,
    }

def ensure_keys(d):
    dd = default_data()
    for k, v in dd.items():
        d.setdefault(k, v)
    for m in d["members"]:
        m.setdefault("used_normal", 0.0)
        m.setdefault("used_recup",  0.0)
        m.setdefault("recup_manual", 0.0)
        m.setdefault("role", "")
        m.setdefault("notes", "")
    return d

def save_data(d):
    DATA_FILE.write_text(json.dumps(d, indent=2, default=str))

def get_data():
    if "data" not in st.session_state:
        st.session_state["data"] = ensure_keys(load_data())
    return ensure_keys(st.session_state["data"])

def persist():
    save_data(get_data())

# ── Holiday calculations ──────────────────────────────────────────
def calc_normal_holidays(start_str):
    """Every 4 weeks from start = 2.5 days."""
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
    """Auto recup from: sunday assignments + national holidays."""
    total = 0
    for wk, ids in data.get("sunday_assignments", {}).items():
        if member_id in ids:
            total += 2
    for dk, nh in data.get("national_holidays", {}).items():
        if member_id in nh.get("team", []):
            total += 2
    return total

def get_member_shift(member_id, wk, data):
    """Return the base shift for a member in a given week."""
    ws = data.get("weekly_shifts", {}).get(wk, {})
    if member_id in ws.get("morning", []):
        return "Morning"
    if member_id in ws.get("afternoon", []):
        return "Afternoon"
    qk = quarter_key(date.fromisoformat(wk))
    nq = data.get("night_quarters", {}).get(qk, {})
    if member_id in nq.get("a", []) or member_id in nq.get("b", []):
        return "Night"
    return None

# ── Date helpers ──────────────────────────────────────────────────
def get_monday(d):
    return d - timedelta(days=d.weekday())

def week_key(d):
    return get_monday(d).isoformat()

def quarter_key(d):
    """Quarters start June: Q1=Jun-Aug, Q2=Sep-Nov, Q3=Dec-Feb, Q4=Mar-May"""
    m = d.month
    if m in (6,7,8):   return f"{d.year}-Q1"
    if m in (9,10,11): return f"{d.year}-Q2"
    if m == 12:        return f"{d.year}-Q3"
    if m in (1,2):     return f"{d.year-1}-Q3"
    return f"{d.year}-Q4"  # 3,4,5

def quarter_label(qk):
    year, q = qk.split("-")
    labels = {1:"Jun–Aug", 2:"Sep–Nov", 3:"Dec–Feb", 4:"Mar–May"}
    return f"Q{q[1]} {year}  ({labels[int(q[1])]})"

def all_quarters():
    today = date.today()
    result = []
    for year in [today.year-1, today.year, today.year+1]:
        for q in range(1,5):
            result.append(f"{year}-Q{q}")
    return result

def fmt_date(s):
    if not s: return "—"
    try: return datetime.fromisoformat(s).strftime("%d %b %Y")
    except: return s

def member_name(mid, members):
    m = next((x for x in members if x["id"] == mid), None)
    return m["name"] if m else "?"

def shift_pill(shift, text=None):
    s = SHIFT_STYLE.get(shift, SHIFT_STYLE["Off"])
    label = text or shift
    return (f'<span style="background:{s["bg"]};color:{s["fg"]};'
            f'border:1px solid {s["border"]};padding:2px 8px;'
            f'border-radius:4px;font-size:.72rem;white-space:nowrap;font-weight:500">{label}</span>')

# ── CSS ───────────────────────────────────────────────────────────
st.markdown("""
<style>
html,body,[class*="css"]{ font-family:'Inter','Segoe UI',sans-serif; }
.stApp { background:#f7f8fa; color:#1a1d23; }
/* Sidebar */
section[data-testid="stSidebar"] { background:#ffffff !important; border-right:1px solid #e5e7eb; }
section[data-testid="stSidebar"] * { color:#374151 !important; }
section[data-testid="stSidebar"] .stRadio label { font-size:.85rem !important; }
/* Section header */
.section-header {
    font-size:1.05rem; font-weight:600; color:#111827;
    border-bottom:2px solid #e5e7eb; padding-bottom:10px; margin-bottom:20px;
    letter-spacing:.01em;
}
/* Metrics */
div[data-testid="metric-container"] {
    background:#ffffff; border:1px solid #e5e7eb;
    border-radius:8px; padding:14px 18px;
}
div[data-testid="metric-container"] label { color:#6b7280 !important; font-size:.72rem !important; text-transform:uppercase; letter-spacing:.05em; }
div[data-testid="metric-container"] div[data-testid="stMetricValue"] { font-size:1.6rem !important; color:#111827 !important; font-weight:600 !important; }
/* Balance colors */
.bal-ok  { color:#1e6f50; font-weight:600; }
.bal-low { color:#b45309; font-weight:600; }
/* Cards */
.shift-card { background:#ffffff; border:1px solid #e5e7eb; border-radius:8px; padding:16px 20px; margin-bottom:12px; }
.shift-card-title { font-size:.85rem; font-weight:600; margin-bottom:10px; color:#374151; text-transform:uppercase; letter-spacing:.06em; }
.member-chip { display:inline-block; padding:3px 10px; border-radius:4px; font-size:.75rem; margin:2px; font-weight:500; }
/* Calendar */
.cal-wrap { overflow-x:auto; }
.cal-table { width:100%; border-collapse:collapse; min-width:700px; }
.cal-th { text-align:center; padding:8px 4px; font-size:.68rem; text-transform:uppercase; letter-spacing:.06em; color:#6b7280; border-bottom:1px solid #e5e7eb; font-weight:500; }
.cal-td { vertical-align:top; border:1px solid #f3f4f6; padding:6px; min-width:90px; min-height:76px; background:#ffffff; }
.cal-td.today { border:2px solid #374151 !important; }
.cal-td.othermon { opacity:.35; }
.cal-td.natday { background:#f0fdf4; }
.cal-day-num { font-size:.82rem; font-weight:600; margin-bottom:4px; color:#111827; }
.cal-tag { display:block; padding:2px 5px; border-radius:3px; font-size:.63rem; margin-bottom:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-weight:500; }
/* Weekly table */
.wtable { width:100%; border-collapse:collapse; font-size:.82rem; }
.wtable th { padding:10px 12px; background:#f9fafb; font-size:.68rem; text-transform:uppercase; letter-spacing:.06em; color:#6b7280; border:1px solid #e5e7eb; text-align:center; font-weight:500; }
.wtable td { padding:8px 12px; border:1px solid #e5e7eb; text-align:center; background:#ffffff; }
.wtable tr:hover td { background:#f9fafb; }
/* Table header row */
.tbl-hdr { font-size:.68rem; text-transform:uppercase; letter-spacing:.06em; color:#6b7280; padding:8px 0; border-bottom:1px solid #e5e7eb; font-weight:500; }
/* Buttons */
button[data-testid="baseButton-secondary"] { border:1px solid #d1d5db !important; border-radius:6px !important; font-size:.8rem !important; color:#374151 !important; background:#ffffff !important; }
button[data-testid="baseButton-secondary"]:hover { background:#f9fafb !important; }
button[data-testid="baseButton-primary"] { border-radius:6px !important; font-size:.8rem !important; background:#1e3a5f !important; border:none !important; }
/* Inputs */
input, select, textarea { border-radius:6px !important; font-size:.85rem !important; }
/* Expander */
details { border:1px solid #e5e7eb !important; border-radius:8px !important; background:#ffffff; }
/* Info/success */
div[data-testid="stAlert"] { border-radius:8px !important; font-size:.85rem !important; }
</style>
""", unsafe_allow_html=True)

# ── SIDEBAR ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ShiftPlan")
    st.caption("Team Holiday & Shift Manager")
    st.divider()
    page = st.radio("Navigate", [
        "Team Members",
        "Weekly Planning",
        "Night Shift (Quarterly)",
        "Calendar",
        "Holidays",
        "Statistics",
    ], label_visibility="collapsed")
    st.divider()
    d = get_data()
    st.metric("Members", len(d["members"]))
    nl = sum(round(calc_normal_holidays(m.get("start","")) - m.get("used_normal",0),1) for m in d["members"])
    rl = sum(round(calc_recup_earned(m["id"],d) + m.get("recup_manual",0) - m.get("used_recup",0),1) for m in d["members"])
    st.metric("Normal Days Left", round(nl,1))
    st.metric("Recup Days Left",  round(rl,1))
    st.divider()
    st.caption("SHIFTS")
    for sname, s in SHIFT_STYLE.items():
        st.markdown(
            f'<span style="display:inline-block;width:8px;height:8px;background:{s["fg"]};'
            f'border-radius:2px;margin-right:8px"></span>'
            f'<span style="font-size:.78rem;color:#374151">{sname}</span>',
            unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# PAGE: TEAM MEMBERS
# ═══════════════════════════════════════════════════════════════════
ROLES = ["Médecin", "Infirmier", "Aide-soignant"]

if page == "Team Members":
    d = get_data()
    st.markdown('<div class="section-header">Team Members</div>', unsafe_allow_html=True)

    edit_id = st.session_state.get("edit_member_id")
    edit_m  = next((m for m in d["members"] if m["id"] == edit_id), None) if edit_id else None

    # ── Form ──────────────────────────────────────────────────────
    form_title = "Edit Member" if edit_m else "New Member"
    with st.expander(form_title, expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            name = st.text_input("Full Name", value=edit_m["name"] if edit_m else "", placeholder="e.g. Ahmed Bouali")
        with c2:
            role_idx = ROLES.index(edit_m["role"]) if edit_m and edit_m.get("role") in ROLES else 0
            role = st.selectbox("Role", ROLES, index=role_idx)
        with c3:
            sv    = date.fromisoformat(edit_m["start"]) if edit_m and edit_m.get("start") else date.today()
            start = st.date_input("Start Date", value=sv)
        with c4:
            recup_manual = st.number_input(
                "Manual Récup. Days", min_value=0.0, max_value=365.0,
                value=float(edit_m.get("recup_manual", 0)) if edit_m else 0.0,
                step=0.5)

        ca, cb, _ = st.columns([1, 1, 5])
        with ca:
            save_btn = st.button("Save", type="primary", use_container_width=True)
        with cb:
            if edit_m and st.button("Cancel", use_container_width=True):
                st.session_state.pop("edit_member_id", None); st.rerun()

        if save_btn:
            if not name.strip():
                st.error("Full name is required.")
            else:
                payload = {"name": name.strip(), "role": role,
                           "start": start.isoformat(), "recup_manual": recup_manual,
                           "used_normal": edit_m.get("used_normal", 0.0) if edit_m else 0.0,
                           "used_recup":  edit_m.get("used_recup",  0.0) if edit_m else 0.0,
                           "notes": ""}
                if edit_m:
                    edit_m.update(payload)
                    st.session_state.pop("edit_member_id", None)
                    st.success(f"{name} updated.")
                else:
                    payload["id"] = d["next_id"]
                    d["members"].append(payload)
                    d["next_id"] += 1
                    st.success(f"{name} added.")
                persist(); st.rerun()

    # ── Table ─────────────────────────────────────────────────────
    if not d["members"]:
        st.info("No team members yet. Add your first member above.")
    else:
        # Filter bar
        fc1, fc2, fc3 = st.columns([2, 2, 4])
        with fc1:
            filter_role = st.selectbox("Filter by role", ["All"] + ROLES, label_visibility="collapsed",
                                       key="tm_filter_role")
        with fc2:
            filter_search = st.text_input("Search by name", placeholder="Search...",
                                          label_visibility="collapsed", key="tm_search")

        members_shown = [
            m for m in d["members"]
            if (filter_role == "All" or m.get("role") == filter_role)
            and (filter_search.lower() in m["name"].lower())
        ]

        if not members_shown:
            st.caption("No members match the current filter.")
        else:
            # Header row
            st.markdown("""
            <div style="display:grid;grid-template-columns:2fr 1.2fr 1.2fr 1.8fr 1.8fr 0.8fr;
                        gap:0;padding:8px 12px;border-bottom:1px solid #2a2d38;
                        font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;color:#7a7f94;">
                <div>Name</div><div>Role</div><div>Since</div>
                <div>Normal Holidays</div><div>Récupération</div><div></div>
            </div>""", unsafe_allow_html=True)

            for m in members_shown:
                en = calc_normal_holidays(m.get("start", ""))
                un = m.get("used_normal", 0.0)
                bn = round(en - un, 1)
                er = round(calc_recup_earned(m["id"], d) + m.get("recup_manual", 0.0), 1)
                ur = m.get("used_recup", 0.0)
                br = round(er - ur, 1)

                n_color = "#4af0b8" if bn >= 1 else "#f07a4a"
                r_color = "#4af0b8" if br >= 1 else "#f07a4a"

                c1, c2, c3, c4, c5, c6 = st.columns([2, 1.2, 1.2, 1.8, 1.8, 0.8])
                c1.markdown(f"**{m['name']}**")
                c2.write(m.get("role", "—"))
                c3.write(fmt_date(m.get("start", "")))
                c4.markdown(
                    f"<span style='font-size:.8rem'>Earned <b>{en}d</b> &nbsp; Used <b>{un}d</b></span><br>"
                    f"<span style='color:{n_color};font-size:.82rem;font-weight:600'>Left: {bn}d</span>",
                    unsafe_allow_html=True)
                c5.markdown(
                    f"<span style='font-size:.8rem'>Earned <b>{er}d</b> &nbsp; Used <b>{ur}d</b></span><br>"
                    f"<span style='color:{r_color};font-size:.82rem;font-weight:600'>Left: {br}d</span>",
                    unsafe_allow_html=True)
                with c6:
                    ca2, cd2 = st.columns(2)
                    with ca2:
                        if st.button("Edit", key=f"e_{m['id']}", use_container_width=True):
                            st.session_state["edit_member_id"] = m["id"]; st.rerun()
                    with cd2:
                        if st.button("Del", key=f"d_{m['id']}", use_container_width=True):
                            d["members"] = [x for x in d["members"] if x["id"] != m["id"]]
                            persist(); st.rerun()

                st.markdown("<div style='border-bottom:0.5px solid #1e2029;margin:0 0 2px'></div>",
                            unsafe_allow_html=True)

        # Footer summary
        if d["members"]:
            total = len(d["members"])
            by_role = {r: sum(1 for m in d["members"] if m.get("role")==r) for r in ROLES}
            summary = " &nbsp;|&nbsp; ".join(f"<b>{v}</b> {k}" for k,v in by_role.items() if v>0)
            st.markdown(
                f"<div style='margin-top:12px;font-size:.78rem;color:#7a7f94'>"
                f"Total: <b>{total}</b> &nbsp;|&nbsp; {summary}</div>",
                unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# PAGE: WEEKLY PLANNING
# ═══════════════════════════════════════════════════════════════════
elif page == "Weekly Planning":
    d = get_data()
    st.markdown('<div class="section-header">Weekly Planning</div>', unsafe_allow_html=True)

    if not d["members"]:
        st.info("Add team members first."); st.stop()

    # Week nav
    if "plan_week" not in st.session_state:
        st.session_state["plan_week"] = get_monday(date.today())
    c1,c2,c3 = st.columns([1,3,1])
    with c1:
        if st.button("← Prev"):
            st.session_state["plan_week"] -= timedelta(weeks=1); st.rerun()
    wstart = st.session_state["plan_week"]
    wend   = wstart + timedelta(days=6)
    c2.markdown(f"### {wstart.strftime('%d %b')} — {wend.strftime('%d %b %Y')}")
    with c3:
        if st.button("Next →"):
            st.session_state["plan_week"] += timedelta(weeks=1); st.rerun()

    wk          = week_key(wstart)
    week_dates  = [wstart + timedelta(days=i) for i in range(7)]
    members     = d["members"]
    member_opts = {m["name"]: m["id"] for m in members}
    qk          = quarter_key(wstart)

    # Who is on night this quarter
    night_ids = (
        d.get("night_quarters",{}).get(qk,{}).get("a",[]) +
        d.get("night_quarters",{}).get(qk,{}).get("b",[])
    )
    # Available for morning/afternoon (not on night)
    day_members = [m for m in members if m["id"] not in night_ids]
    day_opts    = {m["name"]: m["id"] for m in day_members}

    if wk not in d["weekly_shifts"]: d["weekly_shifts"][wk] = {"morning":[],"afternoon":[]}
    if wk not in d["sunday_assignments"]: d["sunday_assignments"][wk] = []

    st.caption(f"Quarter: **{quarter_label(qk)}** — Night shift members are excluded from weekly assignment.")

    # ── Night shift info ──────────────────────────────────────────
    if night_ids:
        night_names = [member_name(mid, members) for mid in night_ids]
        st.markdown(
            f'<div class="shift-card" style="border-color:#a78bfa55">'
            f'<div class="shift-card-title" style="color:#5c6bc0">Night Shift — Quarterly</div>'
            + "".join(
                f'<span class="member-chip" style="background:#5c6bc018;color:#5c6bc0;border:1px solid #5c6bc040">{n}</span>'
                for n in night_names
            ) +
            f'<br><small style="color:#7a7f94">Assigned for the full quarter. Edit in Night Shift page.</small>'
            f'</div>',
            unsafe_allow_html=True)

    # ── Morning assignment ────────────────────────────────────────
    st.markdown(
        '<div class="shift-card-title" style="color:#b8860b;margin-top:12px">Morning Shift — This Week</div>',
        unsafe_allow_html=True)
    cur_morning_names = [m["name"] for m in members if m["id"] in d["weekly_shifts"][wk].get("morning",[])]
    new_morning = st.multiselect(
        "Assign members to Morning shift",
        options=list(day_opts.keys()),
        default=[n for n in cur_morning_names if n in day_opts],
        key=f"morning_{wk}",
        label_visibility="collapsed"
    )

    # ── Afternoon assignment ──────────────────────────────────────
    st.markdown(
        '<div class="shift-card-title" style="color:#2e7d6e;margin-top:8px">Afternoon Shift — This Week</div>',
        unsafe_allow_html=True)
    # Exclude already assigned to morning
    morning_ids_new = [day_opts[n] for n in new_morning]
    aft_opts = {n: mid for n, mid in day_opts.items() if mid not in morning_ids_new}
    cur_aft_names = [m["name"] for m in members if m["id"] in d["weekly_shifts"][wk].get("afternoon",[])]
    new_afternoon = st.multiselect(
        "Assign members to Afternoon shift",
        options=list(aft_opts.keys()),
        default=[n for n in cur_aft_names if n in aft_opts],
        key=f"afternoon_{wk}",
        label_visibility="collapsed"
    )

    # ── Sunday permanence ─────────────────────────────────────────
    st.markdown(
        '<div class="shift-card-title" style="color:#c0392b;margin-top:8px">Sunday Permanence</div>',
        unsafe_allow_html=True)
    sun_date = wstart + timedelta(days=6)
    sun_dk   = sun_date.isoformat()
    is_nat   = sun_dk in d["national_holidays"]
    cur_sun_names = [m["name"] for m in members if m["id"] in d["sunday_assignments"].get(wk,[])]
    new_sunday = st.multiselect(
        f"Members working Sunday {sun_date.strftime('%d %b')}"
        + (f" 🌍 {d['national_holidays'][sun_dk]['name']}" if is_nat else "")
        + " (+2 récup each)",
        options=list(member_opts.keys()),
        default=[n for n in cur_sun_names if n in member_opts],
        key=f"sun_{wk}",
        label_visibility="collapsed"
    )

    # ── Save button ───────────────────────────────────────────────
    if st.button("💾 Save Week Assignment", type="primary"):
        new_morning_ids  = [day_opts[n] for n in new_morning]
        new_aft_ids      = [day_opts.get(n, member_opts.get(n)) for n in new_afternoon]
        new_sunday_ids   = [member_opts[n] for n in new_sunday]

        old_sunday_ids   = d["sunday_assignments"].get(wk, [])

        d["weekly_shifts"][wk] = {"morning": new_morning_ids, "afternoon": new_aft_ids}

        # Log recup for new sunday workers
        for mid in new_sunday_ids:
            if mid not in old_sunday_ids:
                m = next((x for x in members if x["id"] == mid), None)
                if m:
                    d["holiday_log"].insert(0,{
                        "id": int(datetime.now().timestamp()*1000),
                        "memberName": m["name"], "date": sun_dk,
                        "type": "Récupération earned (Sunday)", "days": +2,
                        "notes": f"Sunday {sun_date.strftime('%d %b %Y')}"
                    })
                    if is_nat:
                        d["holiday_log"].insert(0,{
                            "id": int(datetime.now().timestamp()*1000)+1,
                            "memberName": m["name"], "date": sun_dk,
                            "type": "Récupération earned (National Holiday)", "days": +2,
                            "notes": d["national_holidays"][sun_dk]["name"]
                        })

        d["sunday_assignments"][wk] = new_sunday_ids
        persist()
        st.success("✅ Week assignment saved!")
        st.rerun()

    st.divider()

    # ── Weekly Table View ─────────────────────────────────────────
    st.markdown("#### 📋 Week Table")

    saved_morning  = d["weekly_shifts"].get(wk, {}).get("morning", [])
    saved_aft      = d["weekly_shifts"].get(wk, {}).get("afternoon", [])
    saved_sunday   = d["sunday_assignments"].get(wk, [])

    def get_shift_for_day(member_id, day_idx):
        if member_id in night_ids:            return "Night"
        if day_idx == 6 and member_id in saved_sunday: return "Sunday Work"
        if member_id in saved_morning:        return "Morning"
        if member_id in saved_aft:            return "Afternoon"
        return "—"

    # Build table HTML
    day_headers = "".join(
        f'<th class="wtable">'
        f'{"🔴 " if i==6 else ""}{DAYS_SHORT[i]}<br>'
        f'<span style="font-weight:300;font-size:.65rem">{wd.day}/{wd.month}</span></th>'
        for i, wd in enumerate(week_dates)
    )
    rows_html = ""
    for m in members:
        cells = ""
        for i, wd in enumerate(week_dates):
            shift = get_shift_for_day(m["id"], i)
            dk    = wd.isoformat()
            if dk in d["national_holidays"]:
                s = SHIFT_STYLE["National Holiday"]
                cells += f'<td style="background:{s["bg"]};color:{s["fg"]}">🌍 National</td>'
            elif shift == "—":
                cells += '<td style="color:#444">—</td>'
            else:
                s = SHIFT_STYLE.get(shift, SHIFT_STYLE["Off"])
                cells += f'<td style="background:{s["bg"]};color:{s["fg"]}">{s["icon"]} {shift}</td>'
        rows_html += f'<tr><td style="font-weight:600;white-space:nowrap">{m["name"]}</td><td style="color:#7a7f94;font-size:.8rem">{m.get("role","—")}</td>{cells}</tr>'

    table_html = f"""
    <div class="cal-wrap">
    <table class="wtable">
      <thead><tr>
        <th>Member</th><th>Role</th>{day_headers}
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
    </div>"""
    st.markdown(table_html, unsafe_allow_html=True)

    # Summary
    st.divider()
    shift_counts = {"Morning":0,"Afternoon":0,"Night":0,"Sunday Work":0}
    for m in members:
        shift_counts["Night"]       += 1 if m["id"] in night_ids else 0
        shift_counts["Morning"]     += 1 if m["id"] in saved_morning else 0
        shift_counts["Afternoon"]   += 1 if m["id"] in saved_aft else 0
        shift_counts["Sunday Work"] += 1 if m["id"] in saved_sunday else 0

    s1,s2,s3,s4 = st.columns(4)
    s1.metric("🌅 Morning",   shift_counts["Morning"])
    s2.metric("☀️ Afternoon", shift_counts["Afternoon"])
    s3.metric("🌙 Night",     shift_counts["Night"])
    s4.metric("🔴 Sunday",    shift_counts["Sunday Work"])

    # CSV export
    st.divider()
    rows = []
    for m in members:
        row = {"Name":m["name"],"Role":m.get("role","")}
        for i,wd in enumerate(week_dates):
            row[f"{DAYS_SHORT[i]} {wd.day}/{wd.month}"] = get_shift_for_day(m["id"],i)
        rows.append(row)
    csv = pd.DataFrame(rows).to_csv(index=False).encode()
    st.download_button("⬇️ Export CSV", csv, f"week_{wk}.csv","text/csv")

    # ── National Holiday Manager ──────────────────────────────────
    st.divider()
    with st.expander("🌍 National Holidays Manager"):
        na,nb,nc = st.columns(3)
        with na: nh_date = st.date_input("Date", value=date.today(), key="nh_d")
        with nb: nh_name = st.text_input("Holiday Name", key="nh_n")
        with nc:
            nh_team = st.multiselect("Assign Team (+2 récup)", list(member_opts.keys()), key="nh_t")
        if st.button("➕ Add National Holiday", type="primary"):
            if nh_name.strip():
                d["national_holidays"][nh_date.isoformat()] = {
                    "name": nh_name.strip(),
                    "team": [member_opts[n] for n in nh_team]
                }
                persist(); st.success("✅ Saved!"); st.rerun()
            else:
                st.error("Enter a name.")
        if d.get("national_holidays"):
            for dk, nh in sorted(d["national_holidays"].items()):
                names = [member_name(mid, members) for mid in nh.get("team",[])]
                ca,cb = st.columns([5,1])
                ca.markdown(f"📅 **{fmt_date(dk)}** — {nh['name']} | {', '.join(names) or 'No team'}")
                with cb:
                    if st.button("🗑️", key=f"nh_{dk}"):
                        del d["national_holidays"][dk]; persist(); st.rerun()


# ═══════════════════════════════════════════════════════════════════
# PAGE: NIGHT SHIFT QUARTERLY
# ═══════════════════════════════════════════════════════════════════
elif page == "Night Shift (Quarterly)":
    d = get_data()
    st.markdown('<div class="section-header">Night Shift — Quarterly Assignment</div>', unsafe_allow_html=True)

    if not d["members"]: st.info("Add team members first."); st.stop()

    members     = d["members"]
    member_opts = {m["name"]: m["id"] for m in members}

    quarters    = all_quarters()
    current_qk  = quarter_key(date.today())
    default_idx = quarters.index(current_qk) if current_qk in quarters else 4
    sel_q_label = st.selectbox(
        "Select Quarter",
        [quarter_label(q) for q in quarters],
        index=default_idx
    )
    selected_qk = quarters[[quarter_label(q) for q in quarters].index(sel_q_label)]

    st.markdown(f"#### {sel_q_label}")
    q_num  = int(selected_qk.split("Q")[1])
    q_year = int(selected_qk.split("-")[0])
    q_month_map = {1:(6,8), 2:(9,11), 3:(12,2), 4:(3,5)}
    if q_num == 3:
        q_start = date(q_year,12,1)
        q_end   = date(q_year+1,2, calendar.monthrange(q_year+1,2)[1])
    else:
        ms,me = q_month_map[q_num]
        q_start = date(q_year, ms, 1)
        q_end   = date(q_year, me, calendar.monthrange(q_year,me)[1])
    st.caption(f"Period: {fmt_date(q_start.isoformat())} → {fmt_date(q_end.isoformat())}")

    nq = d["night_quarters"].get(selected_qk, {"a":[],"b":[]})

    st.divider()
    ca,cb = st.columns(2)
    with ca:
        st.markdown('<div style="color:#5c6bc0;font-weight:600;font-size:.82rem;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">Group A</div>', unsafe_allow_html=True)
        cur_a = [m["name"] for m in members if m["id"] in nq.get("a",[])]
        new_a = st.multiselect("Group A members", list(member_opts.keys()), default=cur_a, key=f"nqa_{selected_qk}")
    with cb:
        st.markdown('<div style="color:#3a5a8c;font-weight:600;font-size:.82rem;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">Group B</div>', unsafe_allow_html=True)
        a_ids = [member_opts[n] for n in new_a]
        b_opts = {n:mid for n,mid in member_opts.items() if mid not in a_ids}
        cur_b = [m["name"] for m in members if m["id"] in nq.get("b",[])]
        new_b = st.multiselect("Group B members", list(b_opts.keys()), default=[n for n in cur_b if n in b_opts], key=f"nqb_{selected_qk}")

    if st.button("💾 Save Night Shift Quarter", type="primary"):
        d["night_quarters"][selected_qk] = {
            "a": [member_opts[n] for n in new_a],
            "b": [b_opts[n] for n in new_b],
        }
        persist()
        st.success(f"✅ Night shift saved for {sel_q_label}")
        st.rerun()

    st.divider()
    st.subheader("All Quarter Assignments")
    if not any(v for v in d["night_quarters"].values()):
        st.info("No quarters assigned yet.")
    else:
        rows = []
        for qk, nq in sorted(d["night_quarters"].items()):
            a_names = [member_name(mid,members) for mid in nq.get("a",[])]
            b_names = [member_name(mid,members) for mid in nq.get("b",[])]
            rows.append({
                "Quarter": quarter_label(qk),
                "Group A": ", ".join(a_names) or "—",
                "Group B": ", ".join(b_names) or "—",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════
# PAGE: CALENDAR
# ═══════════════════════════════════════════════════════════════════
elif page == "Calendar":
    d = get_data()
    st.markdown('<div class="section-header">Calendar</div>', unsafe_allow_html=True)

    if "cal_month" not in st.session_state:
        st.session_state["cal_month"] = date.today().replace(day=1)

    members     = d["members"]
    member_opts = {m["name"]: m["id"] for m in members}

    # Controls
    c1,c2,c3,_,c4 = st.columns([1,2,1,1,3])
    with c1:
        if st.button("◀ Prev"):
            pm = st.session_state["cal_month"]
            st.session_state["cal_month"] = (pm - timedelta(days=1)).replace(day=1); st.rerun()
    pm = st.session_state["cal_month"]
    c2.markdown(f"### {MONTHS[pm.month-1]} {pm.year}")
    with c3:
        if st.button("Next ▶"):
            nm = pm.replace(day=28)+timedelta(days=4)
            st.session_state["cal_month"] = nm.replace(day=1); st.rerun()
    with c4:
        cal_filter = st.selectbox("Filter member", ["All"]+list(member_opts.keys()), key="cal_f")

    year, month = pm.year, pm.month
    first_day   = date(year, month, 1)
    last_day    = date(year, month, calendar.monthrange(year,month)[1])
    start_pad   = first_day - timedelta(days=first_day.weekday())
    end_pad     = last_day  + timedelta(days=6-last_day.weekday())

    # Build calendar HTML
    header = "".join(f'<th class="cal-th">{d_}</th>' for d_ in DAYS_SHORT)
    rows_cal = ""
    cur = start_pad
    while cur <= end_pad:
        if cur.weekday() == 0:
            rows_cal += "<tr>"
        dk  = cur.isoformat()
        wk  = week_key(cur)
        dow = cur.weekday()
        qk  = quarter_key(cur)
        is_today    = cur == date.today()
        is_other    = cur.month != month
        is_nat      = dk in d["national_holidays"]
        is_sunday   = dow == 6

        td_class = "cal-td"
        if is_today:   td_class += " today"
        if is_other:   td_class += " othermon"
        if is_nat:     td_class += " natday"

        inner = f'<div class="cal-day-num">{cur.day}{"🌍" if is_nat else " 🔴" if is_sunday else ""}</div>'

        if is_nat:
            nh = d["national_holidays"][dk]
            s  = SHIFT_STYLE["National Holiday"]
            inner += f'<span class="cal-tag" style="background:{s["bg"]};color:{s["fg"]}">🌍 {nh["name"]}</span>'

        # Build shift tags per member
        night_ids = (
            d.get("night_quarters",{}).get(qk,{}).get("a",[]) +
            d.get("night_quarters",{}).get(qk,{}).get("b",[])
        )
        morning_ids  = d.get("weekly_shifts",{}).get(wk,{}).get("morning",[])
        aft_ids      = d.get("weekly_shifts",{}).get(wk,{}).get("afternoon",[])
        sunday_ids   = d.get("sunday_assignments",{}).get(wk,[])

        show_members = members if cal_filter == "All" else [m for m in members if m["name"]==cal_filter]

        for m in show_members:
            mid = m["id"]
            if is_sunday and mid in sunday_ids:
                shift = "Sunday Work"
            elif mid in night_ids:
                shift = "Night"
            elif mid in morning_ids:
                shift = "Morning"
            elif mid in aft_ids:
                shift = "Afternoon"
            else:
                continue

            s     = SHIFT_STYLE[shift]
            label = m["name"] if cal_filter=="All" else shift
            inner += f'<span class="cal-tag" style="background:{s["bg"]};color:{s["fg"]}">{s["icon"]} {label}</span>'

        rows_cal += f'<td class="{td_class}">{inner}</td>'
        if cur.weekday() == 6:
            rows_cal += "</tr>"
        cur += timedelta(days=1)

    cal_html = f"""
    <div class="cal-wrap">
    <table class="cal-table">
      <thead><tr>{header}</tr></thead>
      <tbody>{rows_cal}</tbody>
    </table>
    </div>"""
    st.markdown(cal_html, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# PAGE: HOLIDAYS
# ═══════════════════════════════════════════════════════════════════
elif page == "Holidays":
    d = get_data()
    st.markdown('<div class="section-header">Holiday Management</div>', unsafe_allow_html=True)

    if not d["members"]: st.info("Add team members first."); st.stop()

    members = d["members"]
    st.subheader("Balances Overview")
    hc = st.columns([2,1.5,2.5,2.5])
    for h,t in zip(hc,["Name","Role","🟡 Normal Holidays","🟣 Récupération"]):
        h.markdown(f"**{t}**")
    st.divider()

    for m in members:
        en  = calc_normal_holidays(m.get("start",""))
        un  = m.get("used_normal",0.0)
        bn  = round(en-un,1)
        er  = round(calc_recup_earned(m["id"],d)+m.get("recup_manual",0.0),1)
        ur  = m.get("used_recup",0.0)
        br  = round(er-ur,1)
        try:
            weeks  = (date.today()-date.fromisoformat(m.get("start",date.today().isoformat()))).days//7
            cycles = weeks//4
        except: weeks=cycles=0

        c1,c2,c3,c4 = st.columns([2,1.5,2.5,2.5])
        c1.markdown(f"**{m['name']}**")
        c2.write(m.get("role") or "—")
        c3.markdown(
            f"Earned:**{en}d** Used:**{un}d** "
            f"<span class='{'bal-ok' if bn>=1 else 'bal-low'}'>▶ Left:{bn}d</span><br>"
            f"<span style='color:#7a7f94;font-size:.7rem'>{weeks}wks / {cycles} cycles of 4</span>",
            unsafe_allow_html=True)
        c4.markdown(
            f"Earned:**{er}d** Used:**{ur}d** "
            f"<span class='{'bal-ok' if br>=1 else 'bal-low'}'>▶ Left:{br}d</span><br>"
            f"<span style='color:#7a7f94;font-size:.7rem'>Auto(Sundays+NatHolidays) + Manual({m.get('recup_manual',0)}d)</span>",
            unsafe_allow_html=True)
        st.divider()

    with st.expander("📝 Manual Adjustment"):
        a,b,c,dd,e = st.columns(5)
        with a: sn  = st.selectbox("Member",[m["name"] for m in members])
        with b: hcat= st.selectbox("Type",["Normal Holiday","Récupération"])
        with c: hact= st.selectbox("Action",["Use days","Add days"])
        with dd:hqty= st.number_input("Days",0.5,365.0,1.0,0.5)
        with e: hn  = st.text_input("Note")
        if st.button("✅ Apply",type="primary"):
            sm = next((m for m in members if m["name"]==sn),None)
            if sm:
                delta = hqty if hact=="Add days" else -hqty
                if hcat=="Normal Holiday":
                    sm["used_normal"]=max(0,round(sm.get("used_normal",0)-delta,1))
                else:
                    sm["used_recup"]=max(0,round(sm.get("used_recup",0)-delta,1))
                d["holiday_log"].insert(0,{"id":int(datetime.now().timestamp()*1000),
                    "memberName":sm["name"],"date":date.today().isoformat(),
                    "type":f"{hcat} — {hact}","days":delta,"notes":hn})
                persist(); st.success(f"✅ {delta:+g}d for {sm['name']}"); st.rerun()

    st.divider()
    st.subheader("Holiday Log")
    if not d["holiday_log"]:
        st.info("No records yet.")
    else:
        rows = [{"Date":fmt_date(l.get("date","")),"Member":l.get("memberName",""),
                 "Type":l.get("type",""),"Days":f"{l.get('days',0):+g}",
                 "Notes":l.get("notes","") or "—"} for l in d["holiday_log"][:100]]
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)


# ═══════════════════════════════════════════════════════════════════
# PAGE: STATISTICS
# ═══════════════════════════════════════════════════════════════════
elif page == "Statistics":
    d = get_data()
    st.markdown('<div class="section-header">Statistics</div>', unsafe_allow_html=True)

    if not d["members"]: st.info("No team members yet."); st.stop()

    members = d["members"]
    qk      = quarter_key(date.today())
    night_ids = (
        d.get("night_quarters",{}).get(qk,{}).get("a",[]) +
        d.get("night_quarters",{}).get(qk,{}).get("b",[])
    )

    total_en = sum(calc_normal_holidays(m.get("start","")) for m in members)
    total_un = sum(m.get("used_normal",0) for m in members)
    total_er = sum(calc_recup_earned(m["id"],d)+m.get("recup_manual",0) for m in members)
    total_ur = sum(m.get("used_recup",0) for m in members)

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Members",      len(members))
    c2.metric("Normal Earned",round(total_en,1))
    c3.metric("Normal Left",  round(total_en-total_un,1))
    c4.metric("Récup Earned", round(total_er,1))
    c5.metric("Récup Left",   round(total_er-total_ur,1))

    st.divider()
    rows = []
    for m in members:
        en = calc_normal_holidays(m.get("start",""))
        un = m.get("used_normal",0)
        er = round(calc_recup_earned(m["id"],d)+m.get("recup_manual",0),1)
        ur = m.get("used_recup",0)
        try: weeks=(date.today()-date.fromisoformat(m.get("start",date.today().isoformat()))).days//7
        except: weeks=0
        current_shift = "Night" if m["id"] in night_ids else "Day"
        rows.append({
            "Name":m["name"],"Role":m.get("role","—"),
            "Start":fmt_date(m.get("start","")),
            "Weeks":weeks,"Current":current_shift,
            "Normal Earned":en,"Normal Used":un,"Normal Left":round(en-un,1),
            "Récup Earned":er,"Récup Used":ur,"Récup Left":round(er-ur,1),
        })
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)

    st.divider()
    cl,cr = st.columns(2)
    with cl:
        st.subheader("🟡 Normal Holiday Left")
        st.bar_chart(pd.DataFrame({
            "Name":[m["name"] for m in members],
            "Left":[round(calc_normal_holidays(m.get("start",""))-m.get("used_normal",0),1) for m in members]
        }).set_index("Name"))
    with cr:
        st.subheader("🟣 Récupération Left")
        st.bar_chart(pd.DataFrame({
            "Name":[m["name"] for m in members],
            "Left":[round(calc_recup_earned(m["id"],d)+m.get("recup_manual",0)-m.get("used_recup",0),1) for m in members]
        }).set_index("Name"))

    st.divider()
    csv = pd.DataFrame(rows).to_csv(index=False).encode()
    st.download_button("⬇️ Export CSV", csv, "stats.csv","text/csv")
