import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import pytz
import time

st.set_page_config(page_title="Task Planner", page_icon="📝", layout="centered")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 2rem; padding-bottom: 2rem;}
    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
        border-radius: 6px !important;
        border: 1px solid #cccccc !important;
    }
    .task-card {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 12px;
        border-left: 5px solid #0068c9;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# Database Connection & Initialization
# ==========================================
@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

@st.cache_resource
def get_cached_sheet(sheet_name):
    return init_connection().open(sheet_name)

def smart_append_row(sheet, row_data):
    sheet.append_row(row_data, value_input_option="USER_ENTERED")

@st.cache_data(ttl=60, show_spinner="Fetching tasks...")
def get_tasks_data():
    main_ss = get_cached_sheet("MY ROUTINE 2026")
    
    try:
        rm_data = main_ss.worksheet("routine_master").get_all_values()
    except:
        rm_data = []
        
    try:
        ft_data = main_ss.worksheet("future_tasks").get_all_values()
    except:
        ft_data = []

    # Get unique activities from routine master for the dropdown
    activities = []
    if len(rm_data) > 1:
        for row in rm_data[1:]:
            if len(row) > 4 and str(row[4]).strip():
                activities.append(str(row[4]).strip().upper())
    unique_activities = sorted(list(set(activities)))

    # Process future tasks (Now expecting 15 columns)
    expected_cols = 15
    col_names = ["Due_Date", "Due_Time", "Activity", "Type", "Task_Name", "Entity", "Status", 
                 "Cancel_Reason", "Role", "Urgent", "Important", "Energy_Level", 
                 "Location", "Created_date_time", "Done_within"]
                 
    if not ft_data or len(ft_data) <= 1:
        ft_df = pd.DataFrame(columns=col_names)
    else:
        records = []
        for row in ft_data[1:]:
            padded_row = row + [""] * (expected_cols - len(row)) if len(row) < expected_cols else row
            records.append(padded_row[:expected_cols])
        ft_df = pd.DataFrame(records, columns=col_names)
        ft_df['row_index'] = ft_df.index + 2

    return unique_activities, ft_df

# ==========================================
# Main App Logic
# ==========================================
try:
    ist_timezone = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist_timezone)
    
    unique_acts, future_df = get_tasks_data()

    col1, col2 = st.columns([8, 2])
    with col1:
        st.markdown("<h2 style='margin-top:0px;'>📝 Advanced Task Planner</h2>", unsafe_allow_html=True)
    with col2:
        if st.button("🔄 Sync", use_container_width=True):
            get_tasks_data.clear()
            st.rerun()

    tab_add, tab_view = st.tabs(["➕ Schedule New Task", "📋 Pending Backlog"])

    # ---------------------------------------------------------
    # TAB 1: ADD NEW TASK
    # ---------------------------------------------------------
    with tab_add:
        with st.form("dedicated_task_form", clear_on_submit=True):
            st.markdown("### Task Details")
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                f_act = st.selectbox("Parent Category", unique_acts)
            with col_a2:
                f_act_custom = st.text_input("Custom Category (Overrides dropdown)", placeholder="Type here...")
            
            f_name = st.text_input("Task Name / Details", placeholder="e.g., Renew internet connection")
            f_type = st.radio("Task Type", ["Checklist", "Sub-Activity"], horizontal=True)
            
            st.markdown("---")
            st.markdown("### Timing & Location")
            col_t1, col_t2 = st.columns(2)
            time_opts = [f"{str(h).zfill(2)}:{str(m).zfill(2)}" for h in range(24) for m in range(60)]
            curr_time_str = now.replace(second=0, microsecond=0).strftime('%H:%M')
            
            with col_t1:
                f_date = st.date_input("Target Due Date", value=now.date())
                f_time = st.selectbox("Target Due Time", options=time_opts, index=time_opts.index(curr_time_str))
            with col_t2:
                f_done_date = st.date_input("Must Be Done Within (Date)", value=now.date() + timedelta(days=1))
                f_done_time = st.selectbox("Must Be Done Within (Time)", options=time_opts, index=time_opts.index("18:00"))
            
            f_loc = st.text_input("Location", placeholder="e.g., BPS School, Haldia Township, Online...")

            st.markdown("---")
            st.markdown("### Priority Matrix & Context")
            col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
            with col_f1:
                f_role = st.selectbox("Role Context", ["Head Teacher (BPS)", "Developer (BPS Digital)", "YouTube Creator", "Personal / Yoga", "Transition"])
            with col_f2: 
                f_urg = st.checkbox("🔥 Urgent")
            with col_f3: 
                f_imp = st.checkbox("⭐ Important")
            
            f_energy = st.slider("Expected Energy Requirement", 1, 10, 5, help="1 = Routine/Draining, 10 = High Focus/Creative")
            
            submit = st.form_submit_button("💾 Save Task to Ecosystem", type="primary", use_container_width=True)

            if submit:
                final_act = f_act_custom.strip().upper() if f_act_custom.strip() else f_act.strip().upper()
                if not f_name.strip():
                    st.error("Task Name is required.")
                else:
                    created_dt = now.strftime("%Y-%m-%d %H:%M:%S")
                    done_within_dt = f"{f_done_date.strftime('%Y-%m-%d')} {f_done_time}"
                    
                    row_to_insert = [
                        f_date.strftime('%Y-%m-%d'),      # 1. Due_Date
                        f_time,                           # 2. Due_Time
                        final_act,                        # 3. Activity
                        f_type,                           # 4. Type
                        f_name.strip(),                   # 5. Task_Name
                        "Personal",                       # 6. Entity
                        "Pending",                        # 7. Status
                        "",                               # 8. Cancel_Reason
                        f_role,                           # 9. Role
                        str(f_urg),                       # 10. Urgent
                        str(f_imp),                       # 11. Important
                        str(f_energy),                    # 12. Energy_Level
                        f_loc.strip(),                    # 13. Location
                        created_dt,                       # 14. Created_date_time
                        done_within_dt                    # 15. Done_within
                    ]
                    
                    main_ss = get_cached_sheet("MY ROUTINE 2026")
                    smart_append_row(main_ss.worksheet("future_tasks"), row_to_insert)
                    get_tasks_data.clear()
                    st.success(f"✅ '{f_name}' scheduled successfully!")
                    time.sleep(1)
                    st.rerun()

    # ---------------------------------------------------------
    # TAB 2: VIEW PENDING TASKS
    # ---------------------------------------------------------
    with tab_view:
        st.markdown("### 📋 Active Backlog")
        
        if not future_df.empty:
            pending_df = future_df[future_df['Status'].str.strip().str.upper() == 'PENDING'].copy()
            
            if pending_df.empty:
                st.info("No pending tasks. You are all caught up!")
            else:
                # Add sorting logic (Urgent + Important first)
                pending_df['U_val'] = pending_df['Urgent'].str.lower() == 'true'
                pending_df['I_val'] = pending_df['Important'].str.lower() == 'true'
                pending_df['E_val'] = pd.to_numeric(pending_df['Energy_Level'], errors='coerce').fillna(0)
                pending_df['Score'] = (pending_df['U_val'].astype(int) * 2) + pending_df['I_val'].astype(int)
                
                # Sort: Priority Score -> Energy Level -> Due Date
                pending_df = pending_df.sort_values(by=['Score', 'E_val', 'Due_Date'], ascending=[False, False, True])
                
                for _, row in pending_df.iterrows():
                    u_flag = row['U_val']
                    i_flag = row['I_val']
                    
                    if u_flag and i_flag: p_icon = "🔥⭐ Do First"
                    elif not u_flag and i_flag: p_icon = "⭐ Schedule"
                    elif u_flag and not i_flag: p_icon = "🔥 Delegate"
                    else: p_icon = "☕ Backlog"
                    
                    st.markdown(f'''
                    <div class="task-card">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
                            <strong style="font-size: 16px; color: #111;">{row["Task_Name"]}</strong>
                            <span style="font-size: 12px; background: #f0f2f6; padding: 2px 8px; border-radius: 12px; color: #444; font-weight: bold;">{p_icon}</span>
                        </div>
                        <div style="display: flex; gap: 15px; font-size: 13px; color: #555; margin-bottom: 8px;">
                            <span>📁 {row["Activity"]}</span>
                            <span>🎯 Due: {row["Due_Date"]} {row["Due_Time"]}</span>
                            <span>⚡ {row["Energy_Level"]}</span>
                        </div>
                        <div style="font-size: 12px; color: #777; border-top: 1px dashed #eee; padding-top: 6px;">
                            <span>📍 {row["Location"] if row["Location"] else "No Location"}</span> &nbsp;|&nbsp; 
                            <span>⏳ Done Within: {row["Done_within"] if row["Done_within"] else "N/A"}</span>
                        </div>
                    </div>
                    ''', unsafe_allow_html=True)
        else:
            st.info("No tasks found in the database.")

except Exception as e:
    st.error(f"System Error: {e}")
