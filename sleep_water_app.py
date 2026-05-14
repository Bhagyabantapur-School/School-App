import streamlit as st
# --- BACK BUTTON ---
if st.button("⬅️ Back to Dashboard", type="secondary"):
    st.switch_page("dashboard.py") 
st.write("---") 
# -------------------
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import pytz
import time

st.set_page_config(page_title="Health Hub", page_icon="🌙", layout="centered")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 4rem; padding-bottom: 2rem;}
    div[data-testid="metric-container"] {
        text-align: center; 
        background-color: #f0f2f6; 
        padding: 10px; 
        border-radius: 10px; 
        margin-bottom: 15px;
    }
    </style>
""", unsafe_allow_html=True)

GS_FORMULA = '=IF(INDIRECT("C"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("C"&ROW())-INDIRECT("B"&ROW()), 1), "h:mm"), ""))'

# ==========================================
# Database Connection & Caching Helpers
# ==========================================
@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

def get_main_spreadsheet():
    return init_connection().open("MY ROUTINE 2026")

def smart_append_row(sheet, row_data):
    col_a = sheet.col_values(1)
    next_row = len(col_a) + 1
    try: sheet.update(range_name=f"A{next_row}", values=[row_data], value_input_option="USER_ENTERED")
    except TypeError: sheet.update(f"A{next_row}", [row_data], value_input_option="USER_ENTERED")

@st.cache_data(ttl=300)
def get_activity_log():
    data = get_main_spreadsheet().worksheet("activity_log").get_all_values()
    if len(data) <= 1: return pd.DataFrame(columns=["Date", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "Notes"])
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 8: df[df.shape[1]] = ""
    df = df.iloc[:, :8]
    df.columns = ["Date", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "Notes"]
    df = df[df["Date"].astype(str).str.strip() != ""] 
    return df

@st.cache_data(ttl=300)
def get_water_log():
    ss = get_main_spreadsheet()
    try: sheet = ss.worksheet("water_log")
    except gspread.exceptions.WorksheetNotFound:
        sheet = ss.add_worksheet(title="water_log", rows="1000", cols="3")
        smart_append_row(sheet, ["Date", "Time", "Amount_ml"])
    data = sheet.get_all_values()
    if len(data) <= 1: return pd.DataFrame(columns=["Date", "Time", "Amount_ml"])
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 3: df[df.shape[1]] = ""
    df = df.iloc[:, :3]
    df.columns = ["Date", "Time", "Amount_ml"]
    df = df[df["Date"].astype(str).str.strip() != ""] 
    df['Amount_ml'] = pd.to_numeric(df['Amount_ml'], errors='coerce').fillna(0)
    return df

# ==========================================
# Main App UI
# ==========================================
try:
    log_df = get_activity_log() 
    water_df = get_water_log()
    
    ist_timezone = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist_timezone)
    today_str = now.strftime('%Y-%m-%d')
    
    st.markdown("<h2 style='text-align: center; color: #555; margin-top: 0px;'>🌙 Sleep & Hydration Hub</h2>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["💤 Sleep Analyzer", "💧 Hydration Tracker"])

    # ==========================================
    # TAB 1: SLEEP
    # ==========================================
    with tab1:
        with st.expander("📝 Manual Sleep Log", expanded=False):
            st.markdown("**(Use 24-Hour Format. If End Time is earlier than Start Time, the app automatically calculates it crossing midnight.)**")
            log_date = st.date_input("Night of (Date)", value=now.date(), key="sleep_log_date")
            
            hours = [f"{i:02d}" for i in range(24)]
            minutes = [f"{i:02d}" for i in range(60)]
            
            col1, col2 = st.columns(2)
            with col1: 
                st.markdown("<div style='font-size: 14px; font-weight: bold; margin-bottom: 5px; color: #333;'>Fell Asleep At</div>", unsafe_allow_html=True)
                c_sh, c_sm = st.columns(2)
                s_hour = c_sh.selectbox("Start Hour", hours, index=23, key="sleep_s_hour", label_visibility="collapsed")
                s_min = c_sm.selectbox("Start Min", minutes, index=0, key="sleep_s_min", label_visibility="collapsed")
                
            with col2: 
                st.markdown("<div style='font-size: 14px; font-weight: bold; margin-bottom: 5px; color: #333;'>Woke Up At</div>", unsafe_allow_html=True)
                c_eh, c_em = st.columns(2)
                e_hour = c_eh.selectbox("End Hour", hours, index=6, key="sleep_e_hour", label_visibility="collapsed")
                e_min = c_em.selectbox("End Min", minutes, index=0, key="sleep_e_min", label_visibility="collapsed")
            
            sleep_type = st.radio("Sleep Type", ["NIGHT SLEEP", "DAY NAP"], horizontal=True)
            sleep_notes = st.text_input("Notes (Dreams, how you felt, etc.)", key="sleep_notes")
            
            if st.button("💾 Save Sleep Log", use_container_width=True, type="primary"):
                smart_append_row(get_main_spreadsheet().worksheet("activity_log"), [
                    log_date.strftime('%Y-%m-%d'), 
                    f"{s_hour}:{s_min}", 
                    f"{e_hour}:{e_min}", 
                    GS_FORMULA, 
                    "SLEEP", 
                    sleep_type, 
                    "", 
                    sleep_notes
                ])
                get_activity_log.clear() 
                st.success("Sleep Logged!")
                time.sleep(1.0)
                st.rerun()

        st.markdown("---")
        st.markdown("<h3 style='text-align: center; color: #555;'>📈 Sleep Cycles (Last 7 Days)</h3>", unsafe_allow_html=True)
        
        sleep_logs = log_df[(log_df['Activity'].str.strip().str.upper() == 'SLEEP') & (log_df['End_Time'] != 'RUNNING')].copy()
        
        if not sleep_logs.empty:
            # Advanced Parsing logic for mixed day sleep
            def parse_sleep_dts(row):
                d_str = str(row['Date']).strip()
                s_str = str(row['Start_Time']).strip()
                e_str = str(row['End_Time']).strip()
                try:
                    s_dt = pd.to_datetime(f"{d_str} {s_str}")
                    e_dt = pd.to_datetime(f"{d_str} {e_str}")
                    if e_dt < s_dt: e_dt += timedelta(days=1)
                    return s_dt, e_dt
                except: return pd.NaT, pd.NaT
                
            sleep_logs[['Start_DT', 'End_DT']] = sleep_logs.apply(parse_sleep_dts, axis=1, result_type='expand')
            sleep_logs = sleep_logs.dropna(subset=['Start_DT', 'End_DT'])
            
            # Substract 12 hours from Start Time to group by the 'Night' (e.g. 1 AM sleep belongs to previous night)
            sleep_logs['Night_Of'] = (sleep_logs['Start_DT'] - timedelta(hours=12)).dt.date
            
            # Filter to last 7 days
            last_7 = now.date() - timedelta(days=7)
            recent_sleep = sleep_logs[sleep_logs['Night_Of'] >= last_7].sort_values('Night_Of', ascending=False)
            
            grouped = recent_sleep.groupby('Night_Of')
            
            for night, group in grouped:
                sorted_group = group.sort_values('Start_DT')
                total_sleep_sec = 0
                breaks_sec = 0
                prev_end = None
                
                for _, r in sorted_group.iterrows():
                    total_sleep_sec += (r['End_DT'] - r['Start_DT']).total_seconds()
                    if prev_end:
                        gap = (r['Start_DT'] - prev_end).total_seconds()
                        if gap > 0: breaks_sec += gap
                    prev_end = r['End_DT']
                
                sleep_hours = total_sleep_sec / 3600
                break_mins = int(breaks_sec / 60)
                interruptions = len(group) - 1
                
                # Quality logic
                if sleep_hours >= 7 and interruptions <= 1: qual = "🟢 Excellent"
                elif sleep_hours >= 6 and interruptions <= 2: qual = "🟡 Good"
                elif sleep_hours >= 5: qual = "🟠 Fair"
                else: qual = "🔴 Poor"
                
                sh, sm = divmod(int(total_sleep_sec / 60), 60)
                
                with st.expander(f"Night of {night.strftime('%d %b %Y')}  |  {qual}  |  {sh}h {sm:02d}m"):
                    st.markdown(f"**Total Sleep:** {sh}h {sm:02d}m")
                    st.markdown(f"**Interruptions:** {interruptions} time(s) (Total Awake Time: {break_mins}m)")
                    
                    html = "<div style='margin-top: 10px; font-size: 13px;'>"
                    for _, r in sorted_group.iterrows():
                        notes = f" - <i>{r['Notes']}</i>" if str(r['Notes']).strip() else ""
                        html += f"<div style='padding: 5px; background: #f0f2f6; border-radius: 4px; margin-bottom: 4px;'>💤 {r['Start_DT'].strftime('%I:%M %p')} to {r['End_DT'].strftime('%I:%M %p')} ({r['Sub_Activities']}){notes}</div>"
                    html += "</div>"
                    st.markdown(html, unsafe_allow_html=True)
        else:
            st.info("No sleep logs found.")

    # ==========================================
    # TAB 2: HYDRATION
    # ==========================================
    with tab2:
        st.markdown("<h3 style='text-align: center; color: #0288d1;'>💧 Smart Hydration Tracker</h3>", unsafe_allow_html=True)
        
        # Target Selection
        if 'water_target' not in st.session_state:
            st.session_state.water_target = 3000
            
        col_t1, col_t2 = st.columns([1, 2])
        with col_t1:
            target_sel = st.selectbox("Daily Target (ml)", [2000, 2500, 3000, 3500, 4000], index=[2000, 2500, 3000, 3500, 4000].index(st.session_state.water_target))
            st.session_state.water_target = target_sel
            
        water_df['Date_dt'] = pd.to_datetime(water_df['Date'], errors='coerce')
        today_sum = water_df[water_df['Date'] == today_str]['Amount_ml'].sum()
        
        with col_t2:
            st.markdown(f"<h3 style='color: #0288d1; margin-top: 25px; text-align: right;'>{int(today_sum)} / {st.session_state.water_target} ml</h3>", unsafe_allow_html=True)
        
        st.progress(min(today_sum / st.session_state.water_target, 1.0))
        
        # Hourly Pacing Guide
        current_hour = now.hour
        hours_left = max(1, 21 - current_hour) # Assume bedtime is around 9 PM (21:00) for pacing
        remaining = max(0, st.session_state.water_target - today_sum)
        hourly_rate = int(remaining / hours_left)
        
        if remaining == 0:
            st.success("🎉 You've reached your hydration target for today!")
        elif current_hour >= 21:
            st.warning(f"⚠️ You are short by {int(remaining)}ml. Try to limit intake now to avoid waking up at night!")
        else:
            st.info(f"⏱️ **Pacing Guide:** Drink approx **{hourly_rate} ml per hour** until 9:00 PM to reach your target.")

        st.markdown("<br>", unsafe_allow_html=True)
        
        col_w1, col_w2, col_w3 = st.columns(3)
        with col_w1:
            if st.button("🥃 + 250 ml", use_container_width=True):
                smart_append_row(get_main_spreadsheet().worksheet("water_log"), [today_str, now.strftime('%H:%M'), 250])
                get_water_log.clear() 
                st.rerun()
        with col_w2:
            if st.button("🚰 + 500 ml", use_container_width=True):
                smart_append_row(get_main_spreadsheet().worksheet("water_log"), [today_str, now.strftime('%H:%M'), 500])
                get_water_log.clear() 
                st.rerun()
        with col_w3:
            if st.button("🥛 + 1000 ml", use_container_width=True):
                smart_append_row(get_main_spreadsheet().worksheet("water_log"), [today_str, now.strftime('%H:%M'), 1000])
                get_water_log.clear() 
                st.rerun()

        t_week, t_month = st.tabs(["Past 7 Days", "This Month"])
        with t_week:
            last_7 = water_df[water_df['Date_dt'] >= (pd.to_datetime(today_str) - timedelta(days=6))].copy()
            if not last_7.empty: st.bar_chart(last_7.groupby(last_7['Date_dt'].dt.strftime('%a, %b %d'))['Amount_ml'].sum(), color="#29b6f6")
        with t_month:
            this_month = water_df[water_df['Date_dt'].dt.month == pd.to_datetime(today_str).month].copy()
            if not this_month.empty: st.line_chart(this_month.groupby(this_month['Date_dt'].dt.day)['Amount_ml'].sum(), color="#0288d1")
            
        st.markdown("---")
        st.markdown("""
        <div style='background-color: #e3f2fd; padding: 15px; border-radius: 8px; border-left: 5px solid #0288d1;'>
            <h4 style='color: #0288d1; margin-top: 0px;'>💡 Hydration & Sleep Recommendations</h4>
            <ul style='color: #333; margin-bottom: 0px;'>
                <li><b>Daily Limit:</b> Average recommended intake is ~3 Liters (3000ml). Do not exceed 1000ml in a single hour to protect your kidneys.</li>
                <li><b>Sleep Quality:</b> Stop heavy water intake <b>2 hours before bed</b> to prevent sleep interruptions.</li>
                <li><b>Night Thirst:</b> If thirsty before bed, limit to tiny sips (under 100ml).</li>
                <li><b>Morning Routine:</b> Drink 500ml immediately upon waking up to jumpstart metabolism.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

except Exception as e: st.error(f"System Error: {e}")
