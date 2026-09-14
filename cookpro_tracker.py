import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import gspread
import re
import base64
from gspread.exceptions import WorksheetNotFound, APIError
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import AuthorizedSession

# ==========================================
# ⚙️ CONFIGURATION & SETUP
# ==========================================
st.set_page_config(page_title="CookPro Tracker", page_icon="👩‍🍳", layout="centered")
IST = pytz.timezone('Asia/Kolkata')

COOKS = ["AKLIMA BIBI", "ASIMA MANDAL", "ASPIYA BIBI"]

# ⚠️ IMPORTANT: Paste Cook Photo Google Drive Links Here!
COOK_PHOTOS = {
    "AKLIMA BIBI": "",  
    "ASIMA MANDAL": "",
    "ASPIYA BIBI": ""
}

current_user_name = st.session_state.get('user_name', 'Head Teacher')

# ==========================================
# 🔌 GOOGLE SHEETS & DRIVE CONNECTORS
# ==========================================
@st.cache_resource
def get_google_credentials(): 
    return Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]), 
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.readonly"]
    )

@st.cache_resource
def init_cookpro_sheet():
    try: 
        return gspread.authorize(get_google_credentials()).open("COOKPRO TRACKER")
    except Exception: 
        st.error("⚠️ Google Sheets Connection Failed! Make sure the sheet is named exactly 'COOKPRO TRACKER' and is shared with the service account.")
        st.stop()

@st.cache_resource
def get_drive_session(): 
    return AuthorizedSession(get_google_credentials())

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_secure_image_bytes(file_id):
    try:
        r = get_drive_session().get(f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media")
        return r.content if r.status_code == 200 else None
    except Exception: return None

@st.cache_data(ttl=3600, show_spinner=False)
def get_secure_photo_uri(url):
    fb = "https://www.w3schools.com/howto/img_avatar.png"
    if pd.isna(url) or url == "" or not isinstance(url, str): return fb
    match = re.search(r"(?:id=|/d/)([\w-]+)", url)
    if match:
        b = fetch_secure_image_bytes(match.group(1))
        if b: return f"data:image/jpeg;base64,{base64.b64encode(b).decode()}"
    return url if url.startswith("http") else fb

@st.cache_data(ttl=60)
def fetch_schedule():
    sh = init_cookpro_sheet()
    try:
        ws = sh.worksheet("CookPro_Schedule")
        records = ws.get_all_records()
        return pd.DataFrame(records)
    except WorksheetNotFound:
        st.error("⚠️ 'CookPro_Schedule' tab not found in the Google Sheet.")
        return pd.DataFrame()

@st.cache_data(ttl=5)
def fetch_data():
    sh = init_cookpro_sheet()
    try:
        ws = sh.worksheet("CookPro_Data")
        records = ws.get_all_records()
        return pd.DataFrame(records)
    except WorksheetNotFound:
        st.error("⚠️ 'CookPro_Data' tab not found in the Google Sheet.")
        return pd.DataFrame()

# ==========================================
# 🎨 CUSTOM UI STYLING
# ==========================================
st.markdown("""
<style>
    .cook-card {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 10px;
        border-left: 6px solid #28a745;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    .kpi-card {
        background: linear-gradient(135deg, #fff3e0, #ffe0b2);
        padding: 15px; border-radius: 10px;
        text-align: center; border: 1px solid #ffb74d;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .cook-img {
        border-radius: 50%;
        border: 2px solid #ddd;
        object-fit: cover;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("<h2 style='text-align: center; color: #e67e22;'>👩‍🍳 CookPro Task & Point Tracker</h2>", unsafe_allow_html=True)
st.write("---")

tab1, tab2, tab3 = st.tabs(["📝 Daily Tracker", "🏆 Leaderboard", "📊 History"])

# ==========================================
# 📝 TAB 1: DAILY TRACKER (Logic & Submission)
# ==========================================
with tab1:
    today_ist = datetime.now(IST).date()
    selected_date = st.date_input("Select Date", today_ist)
    
    day_name = selected_date.strftime("%A")
    st.markdown(f"#### 📅 Schedule for: **{day_name}**")
    
    schedule_df = fetch_schedule()
    data_df = fetch_data()
    
    if not schedule_df.empty:
        today_schedule = schedule_df[schedule_df['Day_of_Week'].str.lower() == day_name.lower()]
    else:
        today_schedule = pd.DataFrame()

    with st.form("daily_tracker_form"):
        st.caption("Points Breakdown: Present (10) | Cooking (5) | Cleaning (5) = Max 20/day")
        
        results = {}
        
        for cook in COOKS:
            st.markdown(f"<div class='cook-card'>", unsafe_allow_html=True)
            
            # Photo and Name Layout
            h_col1, h_col2 = st.columns([1, 4])
            with h_col1:
                photo_uri = get_secure_photo_uri(COOK_PHOTOS.get(cook, ""))
                st.markdown(f"<img src='{photo_uri}' width='70' height='70' class='cook-img'>", unsafe_allow_html=True)
            with h_col2:
                st.markdown(f"<h3 style='margin:15px 0 0 0; color:#333;'>{cook}</h3>", unsafe_allow_html=True)
            
            st.write("") # Spacer
            
            cook_sch = today_schedule[today_schedule['Cook_Name'].str.strip().str.upper() == cook.upper()] if not today_schedule.empty else pd.DataFrame()
            
            is_cooking_assigned = False
            room_assigned = ""
            
            if not cook_sch.empty:
                will_cook = str(cook_sch.iloc[0].get('Will_Cook_Today', '')).strip().lower()
                is_cooking_assigned = will_cook in ['yes', 'y', 'true', '1']
                room_assigned = str(cook_sch.iloc[0].get('Room_To_Clean', '')).strip()
                if room_assigned.lower() in ['nan', 'none', '']:
                    room_assigned = ""

            c1, c2 = st.columns([1, 2])
            with c1:
                attendance = st.radio(f"Attendance:", ["Present", "Absent"], horizontal=True, key=f"att_{cook}")
            
            with c2:
                did_cook = False
                did_clean = False
                
                if attendance == "Present":
                    if is_cooking_assigned:
                        did_cook = st.checkbox("🍳 Completed Cooking Duty?", value=True, key=f"cook_{cook}")
                    else:
                        st.write("🍳 *No cooking duty today*")
                        
                    if room_assigned:
                        did_clean = st.checkbox(f"🧹 Cleaned **{room_assigned}**?", value=True, key=f"clean_{cook}")
                    else:
                        st.write("🧹 *No cleaning duty today*")
                else:
                    st.error("❌ Marked Absent (0 Points)")
            
            st.markdown("</div>", unsafe_allow_html=True)
            
            results[cook] = {
                "attendance": attendance,
                "did_cook": did_cook,
                "did_clean": did_clean,
                "room": room_assigned if did_clean else ""
            }
            
        submit_btn = st.form_submit_button("💾 Save Daily Points", type="primary", use_container_width=True)
        
        if submit_btn:
            date_str = selected_date.strftime("%d-%m-%Y")
            timestamp_str = datetime.now(IST).strftime("%d-%m-%Y %I:%M:%S %p")
            
            if not data_df.empty and date_str in data_df['Date'].values:
                st.error(f"⚠️ Data for {date_str} already exists! Please check the History tab.")
            else:
                sh = init_cookpro_sheet()
                ws = sh.worksheet("CookPro_Data")
                
                rows_to_append = []
                for cook, data in results.items():
                    # SEPARATED POINT CALCULATIONS
                    att_pts = 10 if data["attendance"] == "Present" else 0
                    cook_pts = 5 if data["did_cook"] else 0
                    clean_pts = 5 if data["did_clean"] else 0
                    total_pts = att_pts + cook_pts + clean_pts
                    
                    cooked_val = "Yes" if data["did_cook"] else "No"
                    cleaned_val = data["room"] if data["did_clean"] else "None"
                    
                    # 11 Columns match the new Google Sheet format
                    rows_to_append.append([
                        date_str, cook, data["attendance"], att_pts, cooked_val, 
                        cook_pts, cleaned_val, clean_pts, total_pts, current_user_name, timestamp_str
                    ])
                
                ws.append_rows(rows_to_append, value_input_option='USER_ENTERED')
                fetch_data.clear()
                st.success(f"✅ Awesome! Points successfully logged for {date_str}.")
                st.rerun()

# ==========================================
# 🏆 TAB 2: MONTHLY LEADERBOARD
# ==========================================
with tab2:
    st.markdown("### 🏆 Kitchen Stars Leaderboard")
    data_df = fetch_data()
    
    if data_df.empty:
        st.info("No points data available yet.")
    else:
        # Ensure points are numeric
        data_df['Total_Pts'] = pd.to_numeric(data_df.get('Total_Pts', 0), errors='coerce').fillna(0)
        data_df['Att_Pts'] = pd.to_numeric(data_df.get('Att_Pts', 0), errors='coerce').fillna(0)
        data_df['Cook_Pts'] = pd.to_numeric(data_df.get('Cook_Pts', 0), errors='coerce').fillna(0)
        data_df['Clean_Pts'] = pd.to_numeric(data_df.get('Clean_Pts', 0), errors='coerce').fillna(0)
        
        # Group and calculate points
        leaderboard = data_df.groupby('Cook_Name')[['Total_Pts', 'Att_Pts', 'Cook_Pts', 'Clean_Pts']].sum().reset_index()
        leaderboard = leaderboard.sort_values(by='Total_Pts', ascending=False).reset_index(drop=True)
        
        medals = ["🥇", "🥈", "🥉"]
        cols = st.columns(3)
        
        for idx, row in leaderboard.iterrows():
            if idx < 3:
                medal = medals[idx]
                cook_name = row['Cook_Name']
                photo_uri = get_secure_photo_uri(COOK_PHOTOS.get(cook_name, ""))
                
                with cols[idx]:
                    st.markdown(f"""
                    <div class='kpi-card'>
                        <h1 style='margin:0; font-size:40px;'>{medal}</h1>
                        <img src='{photo_uri}' width='60' height='60' style='border-radius: 50%; object-fit: cover; margin: 10px 0; border: 2px solid white;'>
                        <h4 style='margin:5px 0;'>{cook_name}</h4>
                        <h2 style='margin:0; color:#d35400;'>{int(row['Total_Pts'])} pts</h2>
                    </div>
                    """, unsafe_allow_html=True)
        
        st.write("---")
        st.markdown("##### 📊 Detailed Points Breakdown")
        st.dataframe(
            leaderboard, 
            hide_index=True, 
            use_container_width=True,
            column_config={
                "Cook_Name": "Cook",
                "Total_Pts": st.column_config.NumberColumn("Total 🏆", format="%d"),
                "Att_Pts": st.column_config.NumberColumn("Attendance (10)", format="%d"),
                "Cook_Pts": st.column_config.NumberColumn("Cooking (5)", format="%d"),
                "Clean_Pts": st.column_config.NumberColumn("Cleaning (5)", format="%d"),
            }
        )

# ==========================================
# 📊 TAB 3: HISTORY & AUDIT
# ==========================================
with tab3:
    st.markdown("### 📊 Raw Tracking Data")
    if st.button("🔄 Refresh Data"):
        fetch_data.clear()
        fetch_schedule.clear()
        
    data_df = fetch_data()
    if data_df.empty:
        st.info("No records found.")
    else:
        data_df = data_df.iloc[::-1]
        
        def highlight_pts(val):
            try:
                if int(val) == 20: return 'background-color: #d4edda; font-weight: bold; color: green;'
                if int(val) == 0: return 'background-color: #f8d7da; color: red;'
            except: pass
            return ''
            
        if 'Total_Pts' in data_df.columns:
            styled_df = data_df.style.map(highlight_pts, subset=['Total_Pts'])
            st.dataframe(styled_df, hide_index=True, use_container_width=True)
        else:
            st.dataframe(data_df, hide_index=True, use_container_width=True)
