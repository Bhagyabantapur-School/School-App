import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# 1. GOOGLE SHEETS CONNECTION
@st.cache_resource
def init_gsheets():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    skey = st.secrets["gcp_service_account"]
    credentials = Credentials.from_service_account_info(skey, scopes=scopes)
    return gspread.authorize(credentials)

client = init_gsheets()
SHEET_NAME = "Personal_Dashboard_Data"

@st.cache_data(ttl=600) 
def get_tracker_data():
    try:
        sheet = client.open(SHEET_NAME).worksheet("Tracker")
        records = sheet.get_all_records()
        return {row['App Name']: str(row['Last Opened']) for row in records}
    except Exception as e:
        st.error(f"Database connection error: {e}")
        return {}

# 2. CORE LOGIC FUNCTIONS
def get_time_stats(last_opened_str):
    if not last_opened_str or last_opened_str.strip() == "":
        return "Never", "N/A"
    try:
        last_date = datetime.strptime(last_opened_str, "%Y-%m-%d %H:%M:%S")
        days = (datetime.now() - last_date).days
        date_display = last_date.strftime("%d %b %Y")
        return date_display, f"{days} d ago"
    except:
        return last_opened_str, "N/A"

def log_and_open(app_name, target_file):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        sheet = client.open(SHEET_NAME).worksheet("Tracker")
        cell = sheet.find(app_name)
        if cell:
            sheet.update_cell(cell.row, 2, now_str)
        else:
            sheet.append_row([app_name, now_str])
        get_tracker_data.clear()
    except Exception as e:
        print(f"Failed to log time: {e}")
    st.switch_page(target_file)

# 3. SCOPED STYLING
st.markdown("""
<style>
    html:has(.dashboard-marker) div[data-testid="stButton"] {
        margin-top: -75px; 
        margin-bottom: 25px;
        padding: 0px 20px;
        position: relative;
        z-index: 10;
    }
    html:has(.dashboard-marker) div[data-testid="stButton"] button {
        background-color: rgba(255, 255, 255, 0.6);
        border: 1px solid rgba(0, 0, 0, 0.1);
        font-weight: bold;
        color: #333;
    }
    html:has(.dashboard-marker) div[data-testid="stButton"] button:hover {
        background-color: white;
        border: 1px solid rgba(0, 0, 0, 0.3);
    }
</style>
""", unsafe_allow_html=True)

def create_card(icon, title, data_label, data_value, bg_color, border_color, text_color, tracker_data):
    raw_date = tracker_data.get(title, "")
    last_date, days_ago = get_time_stats(raw_date)
    return f"""
    <div style="background-color: {bg_color}; padding: 20px 20px 95px 20px; border-radius: 12px; border-left: 6px solid {border_color}; box-shadow: 2px 2px 8px rgba(0,0,0,0.05);">
        <div style="font-size: 20px; color: #333;"><b>{icon} {title}</b></div>
        <hr style="margin: 12px 0; border: none; border-top: 2px solid rgba(0,0,0,0.1);">
        <div style="font-size: 15px; color: #555;">
            {data_label}<br>
            <span style="font-size: 24px; font-weight: 900; color: {text_color};">{data_value}</span>
        </div>
        <div style="font-size: 13px; color: #666; margin-top: 10px;">
            🕒 Opened: {last_date} &bull; Last: {days_ago}
        </div>
    </div>
    """

# 4. DASHBOARD UI LAYOUT
st.markdown('<div class="dashboard-marker" style="display:none;"></div>', unsafe_allow_html=True)

tracker_data = get_tracker_data()
col_title, col_count = st.columns([3, 1])
with col_title:
    st.title("🚀 My Personal Dashboard")
    st.markdown("Welcome back! Here is a summary of your systems:")
with col_count:
    st.metric("Total Active Apps", "9") # <-- Updated metric to 9
st.write("---") 

# ROW 1
r1_col1, r1_col2, r1_col3 = st.columns(3)
with r1_col1:
    st.markdown(create_card("📍", "Money & Location", "Latest Log", "Bhagyabantapur", "#E3F2FD", "#1E88E5", "#1565C0", tracker_data), unsafe_allow_html=True)
    if st.button("Open App", key="btn1", use_container_width=True): log_and_open("Money & Location", "money_location.py")
with r1_col2:
    st.markdown(create_card("💪", "Strong Tracker", "Current Streak", "12 Days", "#FFEBEE", "#E53935", "#C62828", tracker_data), unsafe_allow_html=True)
    if st.button("Open App", key="btn2", use_container_width=True): log_and_open("Strong Tracker", "strong.py")
with r1_col3:
    st.markdown(create_card("🚀", "Project App", "Tasks", "85%", "#F3E5F5", "#8E24AA", "#6A1B9A", tracker_data), unsafe_allow_html=True)
    if st.button("Open App", key="btn3", use_container_width=True): log_and_open("Project App", "project_app.py")

# ROW 2
r2_col1, r2_col2, r2_col3 = st.columns(3)
with r2_col1:
    st.markdown(create_card("🗳️", "Election Duty", "Status", "Assigned", "#E8EAF6", "#3949AB", "#283593", tracker_data), unsafe_allow_html=True)
    if st.button("Open App", key="btn4", use_container_width=True): log_and_open("Election Duty", "election_duty.py")
with r2_col2:
    st.markdown(create_card("📆", "Monthly Tracker", "Month", "May 2026", "#E0F2F1", "#00897B", "#00695C", tracker_data), unsafe_allow_html=True)
    if st.button("Open App", key="btn5", use_container_width=True): log_and_open("Monthly Tracker", "monthly_app.py")
with r2_col3:
    st.markdown(create_card("💵", "Money Tracker", "Wallet", "₹ 4,250", "#E8F5E9", "#43A047", "#2E7D32", tracker_data), unsafe_allow_html=True)
    if st.button("Open App", key="btn6", use_container_width=True): log_and_open("Money Tracker", "money_tracker.py")

# ROW 3
r3_col1, r3_col2, r3_col3 = st.columns(3)
with r3_col1:
    st.markdown(create_card("❤️", "Health Hub", "Status", "Active", "#FCE4EC", "#D81B60", "#AD1457", tracker_data), unsafe_allow_html=True)
    if st.button("Open App", key="btn7", use_container_width=True): log_and_open("Health Hub", "health_app.py")
with r3_col2:
    st.markdown(create_card("💾", "Backup Tracker", "Last Backup", "2 Hours Ago", "#FFF3E0", "#FB8C00", "#EF6C00", tracker_data), unsafe_allow_html=True)
    if st.button("Open App", key="btn8", use_container_width=True): log_and_open("Backup Tracker", "backup_tracker_app.py")
with r3_col3:
    # <-- Added the new Routine App here to complete the grid
    st.markdown(create_card("⏱️", "Daily Routine", "Next Session", "Yoga", "#FFF8E1", "#FFB300", "#FF8F00", tracker_data), unsafe_allow_html=True)
    if st.button("Open App", key="btn9", use_container_width=True): log_and_open("Daily Routine", "routine_app.py")
