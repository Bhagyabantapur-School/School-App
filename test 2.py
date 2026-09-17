import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import pytz
import gspread
from google.oauth2.service_account import Credentials

# --- Configuration & Timezone ---
st.set_page_config(page_title="Dual-Mode Productivity OS", layout="wide")
IST = pytz.timezone('Asia/Kolkata')

# --- Google Sheets Connection ---
@st.cache_resource
def init_connection():
    # Looks for your credentials in .streamlit/secrets.toml
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

# --- Initialize Local Session State (For the Dashboard) ---
if 'task_db' not in st.session_state:
    st.session_state.task_db = pd.DataFrame(columns=[
        'Timestamp', 'Task', 'Category', 'Urgent', 'Important', 'Duration (mins)'
    ])

if 'energy_db' not in st.session_state:
    st.session_state.energy_db = pd.DataFrame(columns=[
        'Timestamp', 'Time of Day', 'Energy Level (1-10)', 'Notes'
    ])

# ==========================================
# SIDEBAR: THE UNIFIED MASTER FORM
# ==========================================
st.sidebar.title("⚡ Master Task Scheduler")
st.sidebar.caption("Pushes to Cloud ☁️ & Updates Dashboard 📊")

with st.sidebar.form("master_task_form", clear_on_submit=True):
    st.markdown("**1. Core Details**")
    f_name = st.text_input("Task Name", placeholder="e.g., Fix Attendance Bug")
    f_act = st.selectbox("Activity Category (GSheets)", ["WORK", "HEALTH", "SCH WORK", "HOME", "PEOPLE"])
    f_type = st.radio("Task Type", ["Sub-Activity", "Checklist"], horizontal=True)
    
    st.markdown("**2. Scheduling & Time**")
    col_fd, col_ft = st.columns(2)
    with col_fd: f_date = st.date_input("Due Date", value=datetime.now(IST).date())
    
    time_opts = [f"{str(h).zfill(2)}:{str(m).zfill(2)}" for h in range(24) for m in range(60)]
    with col_ft: f_time = st.selectbox("Due Time", options=time_opts, index=time_opts.index(datetime.now(IST).strftime('%H:%M')))
    
    # Duration is needed for the local Pie Chart analytics
    f_duration = st.number_input("Est. Duration (minutes)", min_value=5, step=5, value=30)

    st.markdown("**3. Dual-Mode Strategy (Context & Matrix)**")
    f_role = st.selectbox("Role Context", ["Head Teacher (BPS)", "Developer (BPS Digital)", "YouTube Creator", "Personal / Yoga", "Transition"])
    
    col_u, col_i = st.columns(2)
    f_urg = col_u.checkbox("🔥 Urgent")
    f_imp = col_i.checkbox("⭐ Important")
    
    f_energy = st.slider("Energy Requirement (1-10)", 1, 10, 5, help="1 = Routine/Draining, 10 = High Focus/Creative")
    
    submit_master = st.form_submit_button("🚀 Push to Sheets & Dashboard", type="primary")
    
    if submit_master:
        if f_name:
            try:
                # ---------------------------------------------------------
                # ACTION 1: Push to Google Sheets (future_tasks)
                # ---------------------------------------------------------
                client = init_connection()
                sheet = client.open("MY ROUTINE 2026").worksheet("future_tasks")
                
                row_data = [
                    f_date.strftime('%Y-%m-%d'),     # 1. Due_Date
                    f_time,                          # 2. Due_Time
                    f_act,                           # 3. Activity
                    f_type,                          # 4. Type
                    f_name.strip(),                  # 5. Task_Name
                    "Personal",                      # 6. Entity
                    "Pending",                       # 7. Status
                    "",                              # 8. Cancel_Reason
                    f_role,                          # 9. Role
                    str(f_urg).upper(),              # 10. Urgent
                    str(f_imp).upper(),              # 11. Important
                    f_energy                         # 12. Energy_Level
                ]
                sheet.append_row(row_data, value_input_option="USER_ENTERED")
                
                # ---------------------------------------------------------
                # ACTION 2: Update Local Streamlit Dashboard (task_db)
                # ---------------------------------------------------------
                timestamp_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
                
                new_task = pd.DataFrame([{
                    'Timestamp': timestamp_str,
                    'Task': f_name.strip(),
                    'Category': f_role,              # Map Role to Pie Chart Category
                    'Urgent': f_urg,
                    'Important': f_imp,
                    'Duration (mins)': f_duration
                }])
                st.session_state.task_db = pd.concat([st.session_state.task_db, new_task], ignore_index=True)
                
                # ---------------------------------------------------------
                # ACTION 3: Update Local Streamlit Dashboard (energy_db)
                # ---------------------------------------------------------
                # Simple logic to guess Time of Day for the chart based on current hour
                curr_hour = datetime.now(IST).hour
                if curr_hour < 12: tod = "Morning"
                elif curr_hour < 17: tod = "Mid-Day"
                else: tod = "Evening"

                new_energy = pd.DataFrame([{
                    'Timestamp': timestamp_str,
                    'Time of Day': tod,
                    'Energy Level (1-10)': f_energy,
                    'Notes': f_name.strip()
                }])
                st.session_state.energy_db = pd.concat([st.session_state.energy_db, new_energy], ignore_index=True)

                st.sidebar.success(f"✅ Synced '{f_name}' to Cloud & Dashboard!")
            
            except Exception as e:
                st.sidebar.error(f"❌ Connection Error: {e}")
        else:
            st.sidebar.error("⚠️ Task Name is required.")


# ==========================================
# MAIN DASHBOARD UI
# ==========================================
st.title("🎯 BPS Digital: Founder's Dashboard")
st.write("Manage School Admin, Content Creation, and Development Context Switching.")

tab1, tab2, tab3 = st.tabs(["The Eisenhower Matrix", "Time & Energy Analytics", "Raw Logs"])

# --- TAB 1: Eisenhower Matrix ---
with tab1:
    st.subheader("Action Matrix")
    
    if not st.session_state.task_db.empty:
        df = st.session_state.task_db
        
        q1, q2 = st.columns(2)
        q3, q4 = st.columns(2)
        
        with q1:
            st.info("**Urgent & Important (Do Now)**\n\n*School crises, critical bugs*")
            st.dataframe(df[(df['Urgent'] == True) & (df['Important'] == True)][['Task', 'Category']], use_container_width=True, hide_index=True)
            
        with q2:
            st.success("**Not Urgent & Important (Schedule)**\n\n*Building apps, editing videos*")
            st.dataframe(df[(df['Urgent'] == False) & (df['Important'] == True)][['Task', 'Category']], use_container_width=True, hide_index=True)
            
        with q3:
            st.warning("**Urgent & Not Important (Delegate/Minimize)**\n\n*Routine emails, minor inquiries*")
            st.dataframe(df[(df['Urgent'] == True) & (df['Important'] == False)][['Task', 'Category']], use_container_width=True, hide_index=True)
            
        with q4:
            st.error("**Not Urgent & Not Important (Eliminate)**\n\n*Distractions*")
            st.dataframe(df[(df['Urgent'] == False) & (df['Important'] == False)][['Task', 'Category']], use_container_width=True, hide_index=True)
    else:
        st.write("Submit a task in the sidebar to populate your matrix.")

# --- TAB 2: Analytics using Plotly ---
with tab2:
    st.subheader("Where is your focus going?")
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        if not st.session_state.task_db.empty:
            time_dist = st.session_state.task_db.groupby('Category')['Duration (mins)'].sum().reset_index()
            fig_pie = px.pie(time_dist, values='Duration (mins)', names='Category', title="Time Distribution by Role Context", hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.write("Awaiting task data for chart generation...")
            
    with col_b:
        if not st.session_state.energy_db.empty:
            fig_line = px.line(st.session_state.energy_db, x='Timestamp', y='Energy Level (1-10)', 
                               title="Energy Level Tracking", markers=True, color='Time of Day', text='Notes')
            fig_line.update_traces(textposition="bottom right")
            fig_line.update_layout(yaxis=dict(range=[0, 11]))
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.write("Awaiting energy data for chart generation...")

# --- TAB 3: Raw Logs ---
with tab3:
    st.subheader("Local Session Database")
    st.write("This data represents what is currently driving your charts. It reflects exactly what was just pushed to your Google Sheet.")
    
    st.write("**Local Task Database**")
    st.dataframe(st.session_state.task_db, use_container_width=True)
    
    st.write("**Local Energy Database**")
    st.dataframe(st.session_state.energy_db, use_container_width=True)
