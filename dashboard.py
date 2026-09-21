import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pytz

# Clean styling for taller, easy-to-tap buttons to fit the "Last opened" text
st.markdown("""
<style>
    div[data-testid="stButton"] button {
        height: 85px;
        font-size: 15px;
        font-weight: bold;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

st.title("🚀 My Personal Dashboard")
st.write("---")

# ==========================================
# Database Connection for App Tracking
# ==========================================
@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

@st.cache_data(ttl=300, show_spinner=False)
def get_tracker_data():
    try:
        client = init_connection()
        sheet = client.open("Personal_Dashboard_Data").worksheet("Tracker")
        records = sheet.get_all_records()
        return {row['App Name']: str(row['Last Opened']) for row in records}
    except Exception:
        return {}

def get_app_time_str(app_name, tracker_data, now_dt):
    val = tracker_data.get(app_name, "")
    if not val: return "Never"
    try:
        dt_naive = datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
        dt_aware = now_dt.tzinfo.localize(dt_naive)
        diff = now_dt - dt_aware
        if diff.days > 0: return f"{diff.days}d ago"
        elif diff.seconds >= 3600: return f"{diff.seconds // 3600}h ago"
        elif diff.seconds >= 60: return f"{diff.seconds // 60}m ago"
        else: return "Just now"
    except: return "N/A"

# Fetch Tracking Data
ist_timezone = pytz.timezone('Asia/Kolkata')
now = datetime.now(ist_timezone)
tracker_data = get_tracker_data()

# ==========================================
# APP DICTIONARY (Categorized Launchpad)
# ==========================================
app_groups = {
    "MONEY": [
        ("Money App", "money_app.py", "💰"), 
        ("Money Incomplete", "money_incomplete.py", "⏳"),
        ("Money Utilities", "money_utilities.py", "💳"), 
        ("Money Tracker", "money_tracker.py", "💵"), 
        ("Product Inventory", "product_inventory.py", "📦")
    ],
    "LOCATION": [
        ("Location App", "location_app.py", "📍"), 
        ("Packing Tracker", "packing_app.py", "🎒")
    ],
    "ROUTINE": [
        ("Live Routine Hub", "routine_app.py", "⏱️"), 
        ("Routine Audit", "routine_audit.py", "🔍"), 
        ("Routine Editor", "routine_editor.py", "✏️"), 
        ("Project App", "project_app.py", "🚀"), 
        ("AI Video Tracker", "ai_video_tracker.py", "🤖"),
        ("Courses", "courses.py", "🎓")
    ],
    "HEALTH": [
        ("Health Hub", "health_app.py", "❤️"), 
        ("Sleep & Water", "sleep_water_app.py", "💧")
    ],
    "SCH WORK": [
        ("MDM Returns", "mdm_return_log.py", "📦"), 
        ("Video Manager", "bps_ytfb_videos.py", "🎬"), 
        ("Speech Mastery", "speech_prep_app.py", "🎙️"),
        ("Portal Registry", "portal_registry_app.py", "🔗"),
        ("Image Resizer", "resizer.py", "🖼️")
    ],
    "HOME": [
        ("Trace Inventory", "trace.py", "🏷️"), 
        ("Monthly Tracker", "monthly_app.py", "📆")
    ],
    "HARDWARE": [
        ("Backup Tracker", "backup_tracker_app.py", "💾")
    ],
    "BALANCE": [
        ("Strong Tracker", "strong.py", "💪")
    ],
    "ONES": [
        ("Election Duty", "election_duty.py", "🗳️"), 
        ("App Updater", "app_update.py", "🔄"),
        ("Notes", "notes.py", "📝"),
        ("Solar Proposal", "solar_proposal_app.py", "☀️")
    ]
}

# ==========================================
# DYNAMIC GRID GENERATOR
# ==========================================
for group_name, apps in app_groups.items():
    # Styled header matching routine_app.py exactly
    st.markdown(f"<div style='color: #0068c9; font-weight: bold; margin-top: 10px; margin-bottom: 5px; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;'>{group_name}</div>", unsafe_allow_html=True)
    
    # 3-Column Grid Builder
    for i in range(0, len(apps), 3):
        cols = st.columns(3)
        for j in range(3):
            if i + j < len(apps):
                app_name, file_name, icon = apps[i + j]
                last_str = get_app_time_str(app_name, tracker_data, now)
                
                with cols[j]:
                    if st.button(f"{icon} {app_name}\n(Last: {last_str})", key=f"dash_{file_name}", use_container_width=True):
                        st.switch_page(file_name)
            else:
                with cols[j]:
                    st.empty() # Fills empty columns to keep the grid perfectly aligned
                    
    # Separator matching routine_app.py exactly
    st.markdown("<hr style='margin: 5px 0px 10px 0px; border: 0; border-top: 1px solid #f0f2f6;'>", unsafe_allow_html=True)
