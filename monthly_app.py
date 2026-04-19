import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import pytz
import time

# ==========================================
# 1. Configuration & Styling
# ==========================================
st.set_page_config(page_title="Monthly Tasks", page_icon="📆", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 2rem; padding-bottom: 2rem;}
    
    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
        border-radius: 0px !important;
        border: 1px solid #cccccc !important;
        background-color: #ffffff !important;
        box-shadow: none !important;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. Database Connection
# ==========================================
@st.cache_resource
def init_connection():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scopes
    )
    return gspread.authorize(creds)

@st.cache_resource
def get_main_spreadsheet():
    client = init_connection()
    return client.open("MY ROUTINE 2026")

def get_sheet(tab_name):
    ss = get_main_spreadsheet()
    return ss.worksheet(tab_name)

@st.cache_data(ttl=300)
def get_monthly_tasks():
    ss = get_main_spreadsheet()
    try:
        sheet = ss.worksheet("monthly_tasks")
    except gspread.exceptions.WorksheetNotFound:
        sheet = ss.add_worksheet(title="monthly_tasks", rows="100", cols="4")
        sheet.append_row(["Task Name", "Category", "Target Day", "Last_Done_Date"])
        
    data = sheet.get_all_values()
    if len(data) <= 1:
        return pd.DataFrame(columns=["Task Name", "Category", "Target Day", "Last_Done_Date", "row_index"])
    
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 4: df[df.shape[1]] = ""
    df = df.iloc[:, :4]
    df.columns = ["Task Name", "Category", "Target Day", "Last_Done_Date"]
    df['row_index'] = df.index + 2 
    return df

@st.cache_data(ttl=300)
def get_activity_log():
    sheet = get_sheet("activity_log")
    data = sheet.get_all_values()
    if len(data) <= 1:
        return pd.DataFrame()
    df = pd.DataFrame(data[1:], columns=data[0])
    return df

# ==========================================
# 3. Main Dashboard Logic
# ==========================================
ist_timezone = pytz.timezone('Asia/Kolkata')
now = datetime.now(ist_timezone)
current_month_prefix = now.strftime('%Y-%m') # e.g., "2026-04"
current_day = now.day
today_str = now.strftime('%Y-%m-%d')
current_time_str = now.strftime('%H:%M')

col1, col2 = st.columns([5, 1])
with col1:
    st.title("📆 Monthly Recurring Tasks")
with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Sync", use_container_width=True):
        get_monthly_tasks.clear()
        st.toast("Synced with Google Sheets!")
        time.sleep(0.5)
        st.rerun()

try:
    df_tasks = get_monthly_tasks()
    
    if not df_tasks.empty:
        # --- DATA PROCESSING ---
        def check_status(row):
            last_done = str(row['Last_Done_Date']).strip()
            target_day_str = str(row['Target Day']).strip()
            
            try: target_day = int(target_day_str)
            except: target_day = 31
            
            if last_done.startswith(current_month_prefix):
                return "Completed", "#2e7b32" # Green
            elif current_day > target_day:
                return "Overdue", "#d32f2f" # Red
            else:
                return "Pending", "#f57c00" # Orange

        df_tasks[['Status', 'Color']] = df_tasks.apply(check_status, axis=1, result_type='expand')
        
        completed_tasks = df_tasks[df_tasks['Status'] == 'Completed']
        pending_tasks = df_tasks[df_tasks['Status'].isin(['Pending', 'Overdue'])].copy()
        
        # Sort pending by Target Day
        pending_tasks['Target Day Num'] = pd.to_numeric(pending_tasks['Target Day'], errors='coerce').fillna(31)
        pending_tasks = pending_tasks.sort_values('Target Day Num')
        
        # --- METRICS ---
        total = len(df_tasks)
        done = len(completed_tasks)
        progress = done / total if total > 0 else 0
        
        st.markdown(f"### Progress for {now.strftime('%B %Y')}")
        st.progress(progress)
        st.markdown(f"<p style='text-align: right; color: #666;'>{done} of {total} tasks completed</p>", unsafe_allow_html=True)
        st.markdown("---")

        # --- PENDING TASKS SECTION ---
        st.markdown("<h4 style='color: #d84315;'>⏳ Action Required This Month</h4>", unsafe_allow_html=True)
        
        if pending_tasks.empty:
            st.success("🎉 All monthly tasks are complete! Great job!")
        else:
            for idx, row in pending_tasks.iterrows():
                bg_color = "#fff3e0" if row['Status'] == 'Pending' else "#ffebee"
                border_color = row['Color']
                day_text = f"Target: {row['Target Day']}th" if str(row['Target Day']).strip() else "No specific date"
                
                col_info, col_btn = st.columns([4, 1])
                
                with col_info:
                    st.markdown(f"""
                    <div style='background-color: {bg_color}; border-left: 5px solid {border_color}; padding: 12px; border-radius: 6px; margin-bottom: 10px;'>
                        <strong style='font-size: 16px; color: #333;'>{row['Task Name']}</strong> 
                        <span style='color: {border_color}; font-weight: bold; font-size: 12px; margin-left: 10px;'>[{row['Status']}]</span><br>
                        <span style='color: #666; font-size: 14px;'>Category: {row['Category']} | {day_text}</span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                with col_btn:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("✅ Mark Done", key=f"done_{row['row_index']}", use_container_width=True):
                        # 1. Update Monthly Tasks Sheet
                        sheet = get_sheet("monthly_tasks")
                        sheet.update_cell(row['row_index'], 4, today_str)
                        
                        # 2. Log to Activity Log (Integrates with your Timeline!)
                        log_sheet = get_sheet("activity_log")
                        cat = row['Category'].upper() if row['Category'] else "WORK"
                        gs_formula = '=IFERROR(TEXT(MOD(INDIRECT("C"&ROW())-INDIRECT("B"&ROW()), 1), "h:mm"), "")'
                        log_sheet.append_row([
                            today_str, current_time_str, current_time_str, gs_formula, 
                            cat, row['Task Name'], "", "Monthly Task Completed"
                        ], value_input_option="USER_ENTERED")
                        
                        get_monthly_tasks.clear()
                        get_activity_log.clear()
                        st.success(f"Marked '{row['Task Name']}' as done!")
                        time.sleep(1)
                        st.rerun()
                        
        st.markdown("<br>", unsafe_allow_html=True)

        # --- COMPLETED TASKS SECTION ---
        with st.expander(f"✅ Completed This Month ({done})", expanded=False):
            if completed_tasks.empty:
                st.info("No tasks completed yet this month.")
            else:
                for idx, row in completed_tasks.iterrows():
                    st.markdown(f"""
                    <div style='background-color: #e8f5e9; border-left: 5px solid #2e7b32; padding: 10px; border-radius: 6px; margin-bottom: 8px;'>
                        <strong style='font-size: 15px; color: #333;'>{row['Task Name']}</strong><br>
                        <span style='color: #2e7b32; font-size: 13px;'>Completed on: {row['Last_Done_Date']}</span>
                    </div>
                    """, unsafe_allow_html=True)

    else:
        st.info("No monthly tasks setup yet. Add your first one below!")

    st.markdown("---")

    # ==========================================
    # 4. Add New Task Form
    # ==========================================
    with st.expander("➕ Add New Monthly Recurring Task"):
        with st.form("add_monthly_task", clear_on_submit=True):
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                new_task = st.text_input("Task Name", placeholder="e.g. Server Backup")
            with col_t2:
                new_cat = st.selectbox("Category", ["WORK", "HOME", "FINANCE", "HEALTH", "SCHOOL", "YOUTUBE"])
                
            new_target = st.number_input("Target Day of Month (1-31)", min_value=1, max_value=31, value=15)
            
            if st.form_submit_button("Save Recurring Task", type="primary", use_container_width=True):
                if new_task:
                    sheet = get_sheet("monthly_tasks")
                    # Leave Last_Done_Date blank initially so it shows up as Pending
                    sheet.append_row([new_task.strip(), new_cat, new_target, ""])
                    get_monthly_tasks.clear()
                    st.success("Monthly task added successfully!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Please enter a Task Name.")

except Exception as e:
    st.error(f"System Error: {e}")
