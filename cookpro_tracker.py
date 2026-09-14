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
# 1. AUTHENTICATION & SECURITY
# ==========================================
if 'authenticated' not in st.session_state or not st.session_state.authenticated:
    st.warning("🔒 Unauthorized Access. Please log in through the main portal.")
    st.stop()

# ==========================================
# ⚙️ CONFIGURATION & SETUP
# ==========================================
st.set_page_config(page_title="CookPro Tracker", page_icon="👩‍🍳", layout="centered")
IST = pytz.timezone('Asia/Kolkata')

COOKS = ["AKLIMA BIBI", "ASIMA MANDAL", "ASPIYA BIBI"]

# ⚠️ Paste Cook Photo Google Drive Links Here
COOK_PHOTOS = {
    "AKLIMA BIBI": "",
    "ASIMA MANDAL": "",
    "ASPIYA BIBI": ""
}

current_user_name = st.session_state.get('user_name', 'Unknown User')
user_role = st.session_state.get('user_role', 'admin')

TEACHER_INITIALS = {
    "SUKHAMAY KISKU": "SK", "TAPASI RANA": "TR", "SUJATA BISWAS ROTHA": "SBR", 
    "ROHINI SINGH": "RS", "UDAY NARAYAN JANA": "UNJ", "BIMAL KUMAR PATRA": "BKP", 
    "SUSMITA PAUL": "SP", "TAPAN KUMAR MANDAL": "TKM", "MANJUMA KHATUN": "MK"
}
INV_TEACHER_INITIALS = {v: k for k, v in TEACHER_INITIALS.items()}

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
    try: return gspread.authorize(get_google_credentials()).open("COOKPRO TRACKER")
    except Exception: st.error("⚠️ Connection Failed! Ensure sheet is named 'COOKPRO TRACKER'."); st.stop()

@st.cache_resource
def init_routine_sheet():
    try: return gspread.authorize(get_google_credentials()).open("bps_routine")
    except Exception: return None

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

@st.cache_data(ttl=600)
def fetch_routine():
    sh = init_routine_sheet()
    if sh:
        try: return pd.DataFrame(sh.worksheet("Sheet1").get_all_records())
        except Exception: pass
    return pd.DataFrame()

@st.cache_data(ttl=60)
def fetch_schedule():
    sh = init_cookpro_sheet()
    try: return pd.DataFrame(sh.worksheet("CookPro_Schedule").get_all_records())
    except WorksheetNotFound: return pd.DataFrame()

@st.cache_data(ttl=5)
def fetch_data():
    sh = init_cookpro_sheet()
    try: return pd.DataFrame(sh.worksheet("CookPro_Data").get_all_records())
    except WorksheetNotFound: return pd.DataFrame()

def overwrite_sheet_df(sheet_name, df):
    sh = init_cookpro_sheet()
    try: ws = sh.worksheet(sheet_name)
    except WorksheetNotFound: ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=12)
    except Exception: return
    try: 
        ws.clear()
        df = df.fillna("").astype(str)
        ws.update(values=[df.columns.values.tolist()] + df.values.tolist(), range_name='A1') if not df.empty else None
    except Exception as e: st.error(f"⚠️ Failed to update database: {e}")

# ==========================================
# 🎨 CUSTOM UI STYLING
# ==========================================
st.markdown("""
<style>
    .kpi-card {
        background: linear-gradient(135deg, #fff3e0, #ffe0b2);
        padding: 15px; border-radius: 10px;
        text-align: center; border: 1px solid #ffb74d;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .cook-img {
        border-radius: 50%; border: 2px solid #ddd; object-fit: cover;
    }
    div[data-testid="stForm"] { border-left: 5px solid #007bff; border-radius: 10px; margin-bottom: 25px; }
    .time-label { font-size: 13px; font-weight: bold; color: #555; margin-bottom: -10px; display: block;}
</style>
""", unsafe_allow_html=True)

st.markdown("<h2 style='text-align: center; color: #e67e22;'>👩‍🍳 CookPro Task Tracker</h2>", unsafe_allow_html=True)
st.write("---")

tab1, tab2, tab3 = st.tabs(["📝 Daily Timeline", "🏆 Leaderboard", "📊 History"])

# ==========================================
# 📝 TAB 1: DAILY TRACKER (Auto-Logic System)
# ==========================================
with tab1:
    today_ist = datetime.now(IST).date()
    selected_date = st.date_input("Select Date", today_ist)
    date_str = selected_date.strftime("%d-%m-%Y")
    day_name = selected_date.strftime("%A")
    
    st.markdown(f"#### 📅 Schedule for: **{day_name}**")
    
    schedule_df = fetch_schedule()
    data_df = fetch_data()
    
    today_schedule = schedule_df[schedule_df['Day_of_Week'].str.lower() == day_name.lower()] if not schedule_df.empty else pd.DataFrame()

    # --- UPSERT DATABASE LOGIC ---
    def save_data_chunk(updates_dict):
        df = fetch_data()
        timestamp_str = datetime.now(IST).strftime("%d-%m-%Y %I:%M:%S %p")
        cols = ["Date", "Cook_Name", "Attendance", "Morning_In", "Duty_Out", "Duty_In", "Cooked_Today", "Cleaned_Room", "Points_Earned", "Submitted_By", "Timestamp"]
        if df.empty: df = pd.DataFrame(columns=cols)
        
        for cook, new_vals in updates_dict.items():
            mask = (df['Date'] == date_str) & (df['Cook_Name'] == cook)
            if mask.any():
                idx = df[mask].index[0]
                for k, v in new_vals.items(): df.at[idx, k] = v
                df.at[idx, "Timestamp"] = timestamp_str
                df.at[idx, "Submitted_By"] = current_user_name
            else:
                new_row = {
                    "Date": date_str, "Cook_Name": cook, 
                    "Attendance": new_vals.get("Attendance", "Pending"), 
                    "Morning_In": new_vals.get("Morning_In", ""),
                    "Duty_Out": new_vals.get("Duty_Out", ""),
                    "Duty_In": new_vals.get("Duty_In", ""),
                    "Cooked_Today": new_vals.get("Cooked_Today", "Pending"), 
                    "Cleaned_Room": new_vals.get("Cleaned_Room", "Pending"), 
                    "Points_Earned": 0, "Submitted_By": current_user_name, "Timestamp": timestamp_str
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                
        # Master Point Recalculator
        mask_date = df['Date'] == date_str
        for idx in df[mask_date].index:
            pts = 0
            att = str(df.at[idx, "Attendance"]).strip()
            if att == "Present":
                pts += 10
                if str(df.at[idx, "Cooked_Today"]).strip() == "Yes": pts += 5
                cl = str(df.at[idx, "Cleaned_Room"]).strip()
                if cl not in ["No", "None", "Pending", ""]: pts += 5
            else:
                df.at[idx, "Cooked_Today"] = "No"
                df.at[idx, "Cleaned_Room"] = "None"
                df.at[idx, "Morning_In"] = ""
                df.at[idx, "Duty_Out"] = ""
                df.at[idx, "Duty_In"] = ""
                
            df.at[idx, "Points_Earned"] = pts 

        for c in cols: 
            if c not in df.columns: df[c] = ""
        overwrite_sheet_df("CookPro_Data", df[cols])
        fetch_data.clear()

    def get_db_state(cook_name):
        if not data_df.empty and 'Date' in data_df.columns:
            mask = (data_df['Date'] == date_str) & (data_df['Cook_Name'] == cook_name)
            if mask.any(): return data_df[mask].iloc[0].to_dict()
        return {}

    # -----------------------------------------------------
    # 🌅 STEP 1: ATTENDANCE, TIME & AUTO-COOKING
    # -----------------------------------------------------
    st.markdown("### 🌅 Step 1: Morning Attendance & Time Log")
    
    is_admin = user_role == 'admin'
    
    with st.form("att_form"):
        st.caption("🔒 Admin Only: Record attendance and specific movement times.")
        
        if not is_admin:
            st.warning("🔒 **Locked:** Only the Admin can record attendance and movement times.")
            
        att_results = {}
        time_results = {}
        
        for cook in COOKS:
            db_state = get_db_state(cook)
            curr_att = db_state.get("Attendance", "Present")
            idx = 0 if curr_att == "Present" else (1 if curr_att == "Absent" else 0)
            
            c1, c2 = st.columns([1, 4])
            with c1: 
                st.markdown(f"<img src='{get_secure_photo_uri(COOK_PHOTOS.get(cook, ''))}' width='55' height='55' class='cook-img'>", unsafe_allow_html=True)
            with c2: 
                att_results[cook] = st.radio(f"**{cook}**", ["Present", "Absent"], index=idx, horizontal=True, key=f"att_{cook}", disabled=not is_admin)
            
            t1, t2, t3 = st.columns(3)
            with t1: min_in = st.text_input("🟢 Morning In", value=db_state.get("Morning_In", ""), placeholder="e.g. 9:00 AM", key=f"min_{cook}", disabled=not is_admin)
            with t2: dout = st.text_input("🔴 Out (During Duty)", value=db_state.get("Duty_Out", ""), placeholder="e.g. 11:30 AM", key=f"dout_{cook}", disabled=not is_admin)
            with t3: din = st.text_input("🟡 In (Return)", value=db_state.get("Duty_In", ""), placeholder="e.g. 12:15 PM", key=f"din_{cook}", disabled=not is_admin)
                
            time_results[cook] = {"in": min_in, "out": dout, "ret": din}
            st.markdown("<hr style='margin: 10px 0 20px 0;'>", unsafe_allow_html=True)

        if st.form_submit_button("💾 Save Attendance & Times", type="primary", disabled=not is_admin):
            updates = {}
            for cook, att in att_results.items():
                c_sch = today_schedule[today_schedule['Cook_Name'].str.strip().str.upper() == cook.upper()] if not today_schedule.empty else pd.DataFrame()
                will_cook = False
                if not c_sch.empty:
                    val = str(c_sch.iloc[0].get('Will_Cook_Today', '')).strip().lower()
                    will_cook = val in ['yes', 'y', 'true', '1']
                
                cooked = "Yes" if (att == "Present" and will_cook) else "No"
                updates[cook] = {
                    "Attendance": att,
                    "Morning_In": time_results[cook]["in"] if att == "Present" else "",
                    "Duty_Out": time_results[cook]["out"] if att == "Present" else "",
                    "Duty_In": time_results[cook]["ret"] if att == "Present" else "",
                    "Cooked_Today": cooked
                }
            save_data_chunk(updates)
            st.success("✅ Attendance, Movement Times, and Cooking duties successfully updated!")
            st.rerun()

    # -----------------------------------------------------
    # 🧹 STEP 2: DYNAMIC CLEANING VERIFICATION
    # -----------------------------------------------------
    st.markdown("### 🧹 Step 2: Cleaning Verification")
    
    routine_df = fetch_routine()
    
    # Text Parser: Extracts class names & finds first-period teachers for those classes
    def get_authorized_teachers_for_room(rooms_str, day_name, routine_df):
        auth_teachers = set()
        # Find all patterns like "Class IV A", "Class PP A", "Class I B", etc.
        matches = re.finditer(r"Class\s+(PP|I{1,3}|IV|V)\s+([A-C])", str(rooms_str), flags=re.IGNORECASE)
        for match in matches:
            cls = f"CLASS {match.group(1).upper()}"
            sec = match.group(2).upper()
            
            if not routine_df.empty and 'Day' in routine_df.columns:
                day_routine = routine_df[(routine_df['Day'].str.lower() == day_name.lower()) & 
                                         (routine_df['Class'].astype(str).str.strip().str.upper() == cls) & 
                                         (routine_df['Section'].astype(str).str.strip().str.upper() == sec)]
                if not day_routine.empty:
                    min_time = day_routine['Start_Time'].min()
                    first_period_df = day_routine[day_routine['Start_Time'] == min_time]
                    initials = first_period_df['Teacher'].dropna().unique().tolist()
                    for i in initials:
                        full_name = INV_TEACHER_INITIALS.get(i.strip(), i.strip())
                        if full_name != "--- UNASSIGNED ---":
                            auth_teachers.add(full_name)
        return list(auth_teachers)

    with st.form("clean_form"):
        st.caption("Bonus Points: Verified Cleaning = +5 pts. Only the Admin or the First-Period Teacher of the assigned class can verify.")
        
        clean_results = {}
        has_clean_duty = False
        can_save_anything = False
        
        for cook in COOKS:
            c_sch = today_schedule[today_schedule['Cook_Name'].str.strip().str.upper() == cook.upper()] if not today_schedule.empty else pd.DataFrame()
            room = str(c_sch.iloc[0].get('Room_To_Clean', '')).strip() if not c_sch.empty else ""
            if room.lower() in ['nan', 'none', '']: room = ""
            
            if room:
                has_clean_duty = True
                db_state = get_db_state(cook)
                
                # Check authorization specifically for this cook's assigned rooms
                auth_teachers = get_authorized_teachers_for_room(room, day_name, routine_df)
                is_authorized = (user_role == 'admin') or (current_user_name in auth_teachers)
                
                if is_authorized:
                    can_save_anything = True
                
                if db_state.get("Attendance", "Pending") == "Absent":
                    st.error(f"❌ {cook} is marked Absent (Cannot clean {room}).")
                    clean_results[cook] = "None"
                else:
                    is_done = True if db_state.get("Cleaned_Room", "Pending") not in ["No", "None", "Pending", ""] else False
                    
                    if not is_authorized:
                        auth_names = ", ".join(auth_teachers) if auth_teachers else "Admin Only"
                        st.warning(f"🔒 **Locked for {cook}:** Cleans **{room}**. Only **{auth_names}** can verify.")
                        
                    ans = st.checkbox(f"🧹 **{cook}** cleaned the **{room}**?", value=is_done, key=f"clean_{cook}", disabled=not is_authorized)
                    
                    if is_authorized:
                        clean_results[cook] = room if ans else "None"
                    
        if not has_clean_duty: st.info("No cleaning duties are scheduled today.")
        
        # Button is enabled only if the logged-in user is authorized for at least one scheduled cook
        if st.form_submit_button("💾 Verify & Save Cleaning", type="primary", disabled=not can_save_anything and has_clean_duty):
            if clean_results:
                updates = {c: {"Cleaned_Room": clean_results[c]} for c in clean_results}
                save_data_chunk(updates)
                st.success("✅ Cleaning duties verified and updated!")
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
        data_df['Points_Earned'] = pd.to_numeric(data_df['Points_Earned'], errors='coerce').fillna(0)
        leaderboard = data_df.groupby('Cook_Name')['Points_Earned'].sum().reset_index()
        leaderboard = leaderboard.sort_values(by='Points_Earned', ascending=False).reset_index(drop=True)
        
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
                        <h2 style='margin:0; color:#d35400;'>{int(row['Points_Earned'])} pts</h2>
                    </div>
                    """, unsafe_allow_html=True)
        
        st.write("")
        st.markdown("##### 📈 Attendance Overview")
        attendance_counts = data_df[data_df['Attendance'] == 'Present'].groupby('Cook_Name').size().reset_index(name='Days_Present')
        st.dataframe(attendance_counts, hide_index=True, use_container_width=True)

# ==========================================
# 📊 TAB 3: HISTORY & AUDIT
# ==========================================
with tab3:
    st.markdown("### 📊 Raw Tracking Data")
    if st.button("🔄 Refresh Data"):
        fetch_data.clear()
        fetch_schedule.clear()
        fetch_routine.clear()
        
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
            
        styled_df = data_df.style.map(highlight_pts, subset=['Points_Earned'])
        display_cols = ["Date", "Cook_Name", "Attendance", "Morning_In", "Duty_Out", "Duty_In", "Cooked_Today", "Cleaned_Room", "Points_Earned", "Submitted_By", "Timestamp"]
        existing_cols = [c for c in display_cols if c in data_df.columns]
        st.dataframe(styled_df, column_order=existing_cols, hide_index=True, use_container_width=True)
