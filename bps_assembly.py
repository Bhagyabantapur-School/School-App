import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import gspread
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound
from google.oauth2.service_account import Credentials

# ==========================================
# 1. ADMIN-ONLY GATEKEEPER & SECURITY
# ==========================================
if 'authenticated' not in st.session_state or not st.session_state.authenticated:
    st.warning("🔒 Unauthorized Access. Please log in through the main portal.")
    st.stop()

if st.session_state.get('user_role') != "admin":
    st.error("🚫 Access Denied: The Assembly Planner is strictly reserved for the Head Teacher (Admin).")
    st.stop()

def inject_assembly_css(user_name):
    wm = f"{user_name} - ASSEMBLY NOTEBOOK"
    st.markdown(f"""<style>
        .watermark {{ position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; pointer-events: none; z-index: 9999; background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" viewBox="0 0 300 300"><text x="50" y="150" fill="rgba(200, 200, 200, 0.15)" font-size="20" transform="rotate(-45 150 150)" font-family="Arial, sans-serif">{wm}</text></svg>'); background-repeat: repeat; }}
        .cue-card {{ background: linear-gradient(135deg, #ffffff, #f8f9fa); border: 3px solid #007bff; border-radius: 18px; padding: 25px; margin-bottom: 20px; box-shadow: 0px 8px 20px rgba(0,0,0,0.08); }}
        .cue-title {{ color: #007bff; font-size: 24px; font-weight: 900; margin-bottom: 10px; border-bottom: 2px solid #e9ecef; padding-bottom: 8px; }}
        .cue-section-header {{ font-size: 18px; font-weight: 800; color: #343a40; margin-top: 15px; margin-bottom: 8px; }}
        .cue-point {{ font-size: 18px; line-height: 1.5; color: #212529; margin-bottom: 10px; padding-left: 10px; border-left: 4px solid #28a745; }}
        .cue-notice {{ background-color: #fff3cd; border-left: 5px solid #ffc107; padding: 12px; border-radius: 8px; font-size: 17px; font-weight: bold; color: #856404; margin-top: 10px; }}
        .cue-praise {{ background-color: #d4edda; border-left: 5px solid #28a745; padding: 12px; border-radius: 8px; font-size: 17px; font-weight: bold; color: #155724; margin-top: 10px; }}
        .stButton>button {{ border-radius: 10px; font-weight: bold; height: 3em; }}
    </style><div class="watermark"></div>""", unsafe_allow_html=True)

inject_assembly_css(st.session_state.user_name)

# ==========================================
# 2. GOOGLE SHEETS CONNECTORS ("BPS Assembly")
# ==========================================
@st.cache_resource
def get_google_credentials():
    return Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.readonly"]
    )

@st.cache_resource
def init_assembly_sheet():
    try:
        return gspread.authorize(get_google_credentials()).open("BPS Assembly")
    except SpreadsheetNotFound:
        st.error("🚨 **Critical Error:** Could not find a Google Sheet named `BPS Assembly`.")
        st.info("Please create a blank Google Sheet named **BPS Assembly** in Google Drive and share it with your service account email.")
        st.stop()

def ensure_worksheet(sh, title, headers):
    try:
        ws = sh.worksheet(title)
    except WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=1000, cols=10)
        ws.append_row(headers)
    return ws

@st.cache_data(ttl=300)
def fetch_assembly_logs():
    sh = init_assembly_sheet()
    ws = ensure_worksheet(sh, "assembly_logs", ["Date", "Day", "Theme", "Main_Points", "Special_Announcements", "Student_Appreciation"])
    df = pd.DataFrame(ws.get_all_records()).astype(str)
    df.columns = [str(c).strip() for c in df.columns]
    return df

def save_assembly_log(record_dict):
    sh = init_assembly_sheet()
    ws = ensure_worksheet(sh, "assembly_logs", ["Date", "Day", "Theme", "Main_Points", "Special_Announcements", "Student_Appreciation"])
    
    records = ws.get_all_records()
    df = pd.DataFrame(records).astype(str)
    
    # Replace existing entry for the same date or append
    if not df.empty and 'Date' in df.columns:
        df = df[df['Date'].astype(str).str.strip() != record_dict['Date']]
        
    new_df = pd.concat([df, pd.DataFrame([record_dict])], ignore_index=True) if not df.empty else pd.DataFrame([record_dict])
    ws.clear()
    ws.update([new_df.columns.values.tolist()] + new_df.fillna("").values.tolist())
    fetch_assembly_logs.clear()

def delete_assembly_log(date_str):
    sh = init_assembly_sheet()
    ws = ensure_worksheet(sh, "assembly_logs", ["Date", "Day", "Theme", "Main_Points", "Special_Announcements", "Student_Appreciation"])
    
    records = ws.get_all_records()
    df = pd.DataFrame(records).astype(str)
    
    if not df.empty and 'Date' in df.columns:
        filtered_df = df[df['Date'].astype(str).str.strip() != date_str]
        ws.clear()
        if not filtered_df.empty:
            ws.update([filtered_df.columns.values.tolist()] + filtered_df.fillna("").values.tolist())
        else:
            ws.append_row(["Date", "Day", "Theme", "Main_Points", "Special_Announcements", "Student_Appreciation"])
    fetch_assembly_logs.clear()

# ==========================================
# 3. DATE & TIME HELPER
# ==========================================
utc_now = datetime.now(timezone.utc)
now = utc_now + timedelta(hours=5, minutes=30)
curr_date_str = now.strftime("%d-%m-%Y")
curr_day_str = now.strftime("%A")

# Built-in Primary School Themes
THEME_PRESETS = [
    "Custom Topic...",
    "🌿 Eco Club & Cleanliness (Mission LiFE)",
    "⏰ Punctuality & Morning Habits",
    "🍱 MDM Hygiene & Handwashing",
    "🤝 Respecting Teachers, Elders & Classmates",
    "📚 Regular Attendance & Joy of Reading",
    "🇮🇳 Moral Values & Good Citizenship",
    "🐕 Safety Around Animals & Campus Discipline"
]

# ==========================================
# 4. MAIN USER INTERFACE
# ==========================================
st.markdown("<h2>🎙️ Morning Assembly Planner & Cue Card</h2>", unsafe_allow_html=True)
st.caption("Plan your speech, track announcements, and use the live speaker card outdoors.")

tabs = st.tabs(["📋 Plan Today's Assembly", "🎙️ Live Speaker Cue Card", "🗄️ Past Assembly Archive"])

logs_df = fetch_assembly_logs()
today_log = logs_df[logs_df['Date'].astype(str).str.strip() == curr_date_str] if not logs_df.empty and 'Date' in logs_df.columns else pd.DataFrame()

# ---------------------------------------------------------
# TAB 1: PLAN TODAY'S TALK
# ---------------------------------------------------------
with tabs[0]:
    st.markdown("#### ✏️ Write or Update Assembly Note")
    
    # Pre-fill defaults if today already has a saved talk
    default_theme = "Custom Topic..."
    default_custom_theme = ""
    default_points = ""
    default_notice = ""
    default_praise = ""
    
    if not today_log.empty:
        saved_theme = today_log.iloc[0].get('Theme', '')
        if saved_theme in THEME_PRESETS:
            default_theme = saved_theme
        else:
            default_theme = "Custom Topic..."
            default_custom_theme = saved_theme
            
        default_points = today_log.iloc[0].get('Main_Points', '').replace(' || ', '\n')
        default_notice = today_log.iloc[0].get('Special_Announcements', '')
        default_praise = today_log.iloc[0].get('Student_Appreciation', '')

    with st.form("assembly_plan_form"):
        c1, c2 = st.columns([1, 2])
        plan_date = c1.date_input("Assembly Date", datetime.now()).strftime("%d-%m-%Y")
        selected_preset = c2.selectbox("Select Talk Theme", THEME_PRESETS, index=THEME_PRESETS.index(default_theme))
        
        custom_theme = ""
        if selected_preset == "Custom Topic...":
            custom_theme = st.text_input("Enter Custom Topic Theme", value=default_custom_theme, placeholder="e.g., Importance of Sports & Exercise")
            
        final_theme = custom_theme.strip() if selected_preset == "Custom Topic..." else selected_preset
        
        st.markdown("##### 💬 Main Speaking Points (1 Point Per Line)")
        points_input = st.text_area(
            "Write 3–4 short bullet points you want to talk about:",
            value=default_points,
            height=130,
            placeholder="1. Cleanliness starts from our own classroom bench.\n2. Do not throw plastic packets on the playground.\n3. Water the plants before leaving for home."
        )
        
        c3, c4 = st.columns(2)
        notice_input = c3.text_area(
            "📢 Special School Announcements / Reminders",
            value=default_notice,
            height=90,
            placeholder="e.g., Computer class schedule after Tiffin / Cultural rehearsal at 2 PM."
        )
        praise_input = c4.text_area(
            "🌟 Student / Class Appreciation (Good Work)",
            value=default_praise,
            height=90,
            placeholder="e.g., Applaud Class IV-A for highest attendance this week."
        )
        
        if st.form_submit_button("💾 Save Assembly Plan", type="primary"):
            if not final_theme:
                st.error("Please select or enter a topic theme.")
            else:
                formatted_points = " || ".join([p.strip() for p in points_input.split('\n') if p.strip()])
                record = {
                    "Date": plan_date,
                    "Day": datetime.strptime(plan_date, "%d-%m-%Y").strftime("%A"),
                    "Theme": final_theme,
                    "Main_Points": formatted_points,
                    "Special_Announcements": notice_input.strip(),
                    "Student_Appreciation": praise_input.strip()
                }
                save_assembly_log(record)
                st.success(f"✅ Assembly plan saved to 'BPS Assembly' for {plan_date}!")
                st.rerun()

# ---------------------------------------------------------
# TAB 2: LIVE SPEAKER CUE CARD (OUTDOOR MODE)
# ---------------------------------------------------------
with tabs[1]:
    st.markdown("#### 📱 Outdoor Speaker View")
    st.caption("Large, distraction-free text to glance at while addressing students.")
    
    view_date = st.date_input("Select Date for Cue Card", datetime.now(), key="cue_date").strftime("%d-%m-%Y")
    card_log = logs_df[logs_df['Date'].astype(str).str.strip() == view_date] if not logs_df.empty and 'Date' in logs_df.columns else pd.DataFrame()
    
    if card_log.empty:
        st.warning(f"No assembly plan found for **{view_date}**. Please write one in the first tab!")
    else:
        data = card_log.iloc[0]
        theme_str = data.get('Theme', 'No Theme')
        points_list = [p.strip() for p in str(data.get('Main_Points', '')).split(' || ') if p.strip()]
        notice_str = str(data.get('Special_Announcements', '')).strip()
        praise_str = str(data.get('Student_Appreciation', '')).strip()
        
        # Large Styled Card HTML
        st.markdown(f"""
        <div class="cue-card">
            <div class="cue-title">🏫 {theme_str}</div>
            <p style="color:gray; font-weight:bold; margin-top:-5px; margin-bottom:15px;">📅 {view_date} ({data.get('Day', '')})</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("### 💬 Main Speaking Points")
        if points_list:
            for pt in points_list:
                st.markdown(f'<div class="cue-point">👉 {pt}</div>', unsafe_allow_html=True)
        else:
            st.info("No main points entered.")
            
        if notice_str:
            st.markdown("### 📢 Announcements")
            st.markdown(f'<div class="cue-notice">🔔 {notice_str}</div>', unsafe_allow_html=True)
            
        if praise_str:
            st.markdown("### 🌟 Appreciation")
            st.markdown(f'<div class="cue-praise">👏 {praise_str}</div>', unsafe_allow_html=True)

# ---------------------------------------------------------
# TAB 3: PAST ASSEMBLY ARCHIVE
# ---------------------------------------------------------
with tabs[2]:
    st.markdown("#### 🗄️ History of Assembly Speeches")
    
    if not logs_df.empty and 'Date' in logs_df.columns:
        display_df = logs_df.copy()
        display_df['Main_Points'] = display_df['Main_Points'].str.replace(' || ', ' • ')
        st.dataframe(
            display_df[['Date', 'Day', 'Theme', 'Main_Points', 'Special_Announcements', 'Student_Appreciation']],
            hide_index=True,
            use_container_width=True
        )
        
        st.markdown("---")
        del_date = st.selectbox("Select Date to Delete Record", ["Select..."] + display_df['Date'].tolist())
        if del_date != "Select..." and st.button("🗑️ Delete Selected Assembly Record"):
            delete_assembly_log(del_date)
            st.success("Deleted from 'BPS Assembly'!")
            st.rerun()
    else:
        st.info("No past assembly records stored yet.")
