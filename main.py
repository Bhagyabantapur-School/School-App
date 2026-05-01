import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# 1. Page Configuration
st.set_page_config(
    page_title="My Personal Hub",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. Google Sheets Connection Setup
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

# Fetch data from sheet (Fixed: Cache set to 10 minutes to prevent API Quota limits)
@st.cache_data(ttl=600)
def get_tracker_data():
    try:
        sheet = client.open(SHEET_NAME).worksheet("Tracker")
        records = sheet.get_all_records()
        return {row['App Name']: str(row['Last Opened']) for row in records}
    except Exception as e:
        st.error(f"Database connection error: {e}")
        return {}

# 3. Helper Functions for Dates and Buttons
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

def log_and_open(app_name, target_page):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        sheet = client.open(SHEET_NAME).worksheet("Tracker")
        cell = sheet.find(app_name)
        if cell:
            sheet.update_cell(cell.row, 2, now_str)
        else:
            sheet.append_row([app_name, now_str])
            
        # Clear the cache so it pulls the new date when you return
        get_tracker_data.clear()
    except Exception as e:
        print(f"Failed to log time: {e}")
    
    st.switch_page(target_page)

# 4. Custom CSS
st.markdown("""
<style>
    div[data-testid="stButton"] {
        margin-top: -75px; 
        margin-bottom: 25px;
        padding: 0px 20px;
        position: relative;
        z-index: 10;
    }
    div[data-testid="stButton"] button {
        background-color: rgba(255, 255, 255, 0.6);
        border: 1px solid rgba(0, 0, 0, 0.1);
        font-weight: bold;
        color: #333;
    }
    div[data-testid="stButton"] button:hover {
        background-color: white;
        border: 1px solid rgba(0, 0, 0, 0.3);
    }
</style>
""", unsafe_allow_html=True)

# 5. Card Generator Function
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

# 6. Define the Dashboard Function
def show_dashboard():
    tracker_data = get_tracker_data()
    
    # Top Header Section
    col_title, col_count = st.columns([3, 1])
    with col_title:
        st.title("🚀 My Personal Dashboard")
        st.markdown("Welcome back! Here is a summary of your systems:")
    with col_count:
        st.metric("Total Active Apps", "8")
        
    st.write("---") 

    # Grid Layout: 3 columns
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(create_card("📍", "Money & Location", "Latest Log", "Bhagyabantapur", "#E3F2FD", "#1E88E5", "#1565C0", tracker_data), unsafe_allow_html=True)
        if st.button("Open App", key="btn1", use_container_width=True): log_and_open("Money & Location", money_location_page)

        st.markdown(create_card("🗳️", "Election Duty", "Status", "Assigned", "#E8EAF6", "#3949AB", "#283593", tracker_data), unsafe_allow_html=True)
        if st.button("Open App", key="btn4", use_container_width=True): log_and_open("Election Duty", election_page)
        
        st.markdown(create_card("❤️", "Health Hub", "Blood Pressure", "120/80", "#FCE4EC", "#D81B60", "#AD1457", tracker_data), unsafe_allow_html=True)
        if st.button("Open App", key="btn7", use_container_width=True): log_and_open("Health Hub", health_page)

    with col2:
        st.markdown(create_card("💪", "Strong Tracker", "Current Streak", "12 Days", "#FFEBEE", "#E53935", "#C62828", tracker_data), unsafe_allow_html=True)
        if st.button("Open App", key="btn2", use_container_width=True): log_and_open("Strong Tracker", strong_page)

        st.markdown(create_card("📆", "Monthly Tracker", "Current Month", "May 2026", "#E0F2F1", "#00897B", "#00695C", tracker_data), unsafe_allow_html=True)
        if st.button("Open App", key="btn5", use_container_width=True): log_and_open("Monthly Tracker", monthly_page)
            
        st.markdown(create_card("💾", "Backup Tracker", "Last Backup", "2 Hours Ago", "#FFF3E0", "#FB8C00", "#EF6C00", tracker_data), unsafe_allow_html=True)
        if st.button("Open App", key="btn8", use_container_width=True): log_and_open("Backup Tracker", backup_page)

    with col3:
        st.markdown(create_card("🚀", "Project App", "Tasks Completed", "85%", "#F3E5F5", "#8E24AA", "#6A1B9A", tracker_data), unsafe_allow_html=True)
        if st.button("Open App", key="btn3", use_container_width=True): log_and_open("Project App", project_page)

        st.markdown(create_card("💵", "Money Tracker", "Wallet Balance", "₹ 4,250", "#E8F5E9", "#43A047", "#2E7D32", tracker_data), unsafe_allow_html=True)
        if st.button("Open App", key="btn6", use_container_width=True): log_and_open("Money Tracker", money_tracker_page)

# 7. Define all Page Links
dashboard_page = st.Page(show_dashboard, title="Visual Dashboard", icon="🚀", default=True)

money_location_page = st.Page("money_location.py", title="Money & Location", icon="📍")
strong_page = st.Page("strong.py", title="Strong Tracker", icon="💪")
project_page = st.Page("project_app.py", title="Project Tracker", icon="🚀")
election_page = st.Page("election_duty.py", title="Election Duty", icon="🗳️")
monthly_page = st.Page("monthly_app.py", title="Monthly Tracker", icon="📆")
money_tracker_page = st.Page("money_tracker.py", title="Money Tracker", icon="💵")
health_page = st.Page("health_app.py", title="Health Tracker", icon="❤️")
backup_page = st.Page("backup_tracker_app.py", title="Backup Tracker", icon="💾")

# 8. Run Navigation
pg = st.navigation([
    dashboard_page,
    money_location_page, 
    strong_page, 
    project_page, 
    election_page, 
    monthly_page, 
    money_tracker_page,
    health_page,
    backup_page
])

pg.run()
