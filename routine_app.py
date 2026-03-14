import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# 1. Configuration
st.set_page_config(page_title="Live Routine", page_icon="⏱️", layout="centered")

# --- Safe Auto-Refresh ---
# Refreshes the app every 60 seconds (60000 ms) without freezing the server
st_autorefresh(interval=60000, key="routine_refresh")

# Hide standard Streamlit menus for a clean, app-like mobile experience
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 2rem; padding-bottom: 2rem;}
    input[type="text"] {font-size: 16px;}
    </style>
""", unsafe_allow_html=True)

# 2. Tabs Setup
tab1, tab2 = st.tabs(["📱 Mobile Live View", "💻 Desktop Widget (Tkinter)"])

# ==========================================
# TAB 1: MOBILE WEB APP (Google Sheets API)
# ==========================================
with tab1:
    @st.cache_resource
    def init_connection():
        # Full scopes required to write/edit the Google Sheet
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=scopes
        )
        return gspread.authorize(creds)

    def get_sheet():
        client = init_connection()
        return client.open("MY ROUTINE 2026").sheet1

    @st.cache_data(ttl=60) 
    def get_routine_data():
        sheet = get_sheet()
        data = sheet.get_all_records()
        return pd.DataFrame(data)

    try:
        df = get_routine_data()
        
        # 4. Live Time Tracking (Strictly synced to IST)
        ist_timezone = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist_timezone)
        
        current_day = now.strftime('%A')
        current_time = now.time()

        st.markdown(f"<h3 style='text-align: center; color: #888;'>{current_day} | {now.strftime('%I:%M %p')}</h3>", unsafe_allow_html=True)

        current_activity = "FREE TIME"

        # Match current time with the routine slots
        for _, row in df.iterrows():
            if str(row.get('Day')).strip() == current_day:
                try:
                    start_t = datetime.strptime(str(row['Start_Time']).strip(), '%H:%M').time()
                    end_str = str(row['End_Time']).strip()
                    
                    # Handling the midnight transition
                    if end_str == '0:00':
                        end_t = datetime.strptime('23:59:59', '%H:%M:%S').time()
                    else:
                        end_t = datetime.strptime(end_str, '%H:%M').time()

                    if start_t <= current_time <= end_t:
                        current_activity = str(row['Activity']).strip().upper()
                        break
                except ValueError:
                    continue

        # Dynamic UI Coloring
        if current_activity in ["SUBORNO CARE", "BRING SUBORNO", "FAMILY"]:
            color = "#ff4b4b" 
        elif current_activity in ["WORK", "REPORT", "TASK"]:
            color = "#0068c9" 
        elif current_activity == "HEALTH":
            color = "#2e7b32" 
        elif current_activity in ["SLEEP", "PRE", "TEA", "OUT"]:
            color = "#ff9f36" 
        else:
            color = "#333333" 

        st.markdown(f"<h1 style='text-align: center; font-size: 4.5rem; color: {color}; margin-top: 30px; margin-bottom: 50px; line-height: 1.2;'>{current_activity}</h1>", unsafe_allow_html=True)

        # Update Form (Mobile Editor)
        with st.expander("✏️ Quick Add / Edit Routine"):
            with st.form("edit_routine_form", clear_on_submit=True):
                st.markdown("### Add New Time Slot")
                
                days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                col1, col2 = st.columns(2)
                with col1:
                    input_day = st.selectbox("Day", days_of_week, index=days_of_week.index(current_day))
                with col2:
                    input_activity = st.text_input("Activity (e.g., WORK, HEALTH)")
                
                col3, col4 = st.columns(2)
                with col3:
                    input_start = st.time_input("Start Time", value=now.time())
                with col4:
                    input_end = st.time_input("End Time", value=now.time())
                    
                submitted = st.form_submit_button("Update Sheet", use_container_width=True)
                
                if submitted:
                    if input_activity:
                        start_str = input_start.strftime('%H:%M')
                        end_str = input_end.strftime('%H:%M')
                        
                        start_dt = datetime.combine(now.date(), input_start)
                        end_dt = datetime.combine(now.date(), input_end)
                        if end_dt < start_dt:
                            end_dt = end_dt.replace(day=end_dt.day + 1)
                        duration_td = end_dt - start_dt
                        hours, remainder = divmod(duration_td.seconds, 3600)
                        minutes = remainder // 60
                        duration_str = f"{hours}:{minutes:02d}"

                        sheet = get_sheet()
                        sheet.append_row([input_day, start_str, end_str, duration_str, input_activity.upper()])
                        
                        st.cache_data.clear()
                        st.success(f"Added '{input_activity.upper()}' to {input_day}!")
                    else:
                        st.error("Please enter an activity name.")

    except Exception as e:
        st.error(f"System Error: {e}")

# ==========================================
# TAB 2: DESKTOP TKINTER DOWNLOAD
# ==========================================
with tab2:
    st.markdown("### Desktop Widget Download")
    st.write("Tkinter creates a standalone window on your computer, so it cannot run inside a web browser. Download the script below to run your desktop widget locally.")
    
    tkinter_code = """import tkinter as tk
import csv
from datetime import datetime

class RoutineApp:
    def __init__(self, root, csv_file):
        self.root = root
        self.root.title("Desktop Routine")
        self.root.geometry("400x200")
        self.root.attributes('-topmost', True)
        self.csv_file = csv_file
        
        self.time_label = tk.Label(root, font=('Helvetica', 14))
        self.time_label.pack(pady=20)
        
        self.activity_label = tk.Label(root, font=('Helvetica', 24, 'bold'), fg="#0052cc")
        self.activity_label.pack(pady=10)
        
        self.update_activity()

    def load_routine(self):
        routine = []
        try:
            with open(self.csv_file, mode='r', encoding='utf-8-sig') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    routine.append(row)
        except FileNotFoundError:
            pass
        return routine

    def update_activity(self):
        now = datetime.now()
        current_day = now.strftime('%A')
        current_time = now.time()
        
        self.time_label.config(text=f"{current_day}  |  {now.strftime('%I:%M %p')}")
        current_activity = "FREE TIME"
        
        routine_data = self.load_routine() 
        for item in routine_data:
            if str(item.get('Day')).strip() == current_day:
                try:
                    start_t = datetime.strptime(str(item['Start_Time']).strip(), '%H:%M').time()
                    end_str = str(item['End_Time']).strip()
                    
                    if end_str == '0:00':
                        end_t = datetime.strptime('23:59:59', '%H:%M:%S').time()
                    else:
                        end_t = datetime.strptime(end_str, '%H:%M').time()

                    if start_t <= current_time <= end_t:
                        current_activity = str(item['Activity']).strip().upper()
                        break
                except ValueError:
                    continue
        
        self.activity_label.config(text=current_activity)
        self.root.after(60000, self.update_activity)

if __name__ == "__main__":
    root = tk.Tk()
    app = RoutineApp(root, "MY ROUTINE 2026 - Sheet1.csv")
    root.mainloop()
"""
    
    st.code(tkinter_code, language='python')
    
    st.download_button(
        label="⬇️ Download desktop_routine.py",
        data=tkinter_code,
        file_name="desktop_routine.py",
        mime="text/x-python"
    )
    
    st.info("Ensure your downloaded `MY ROUTINE 2026 - Sheet1.csv` is in the same folder as this Python script before running it on your PC.")
