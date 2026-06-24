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
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

# --- Initialize Session State (Mock Database for daily tracking) ---
if 'task_db' not in st.session_state:
    st.session_state.task_db = pd.DataFrame(columns=[
        'Timestamp', 'Task', 'Category', 'Urgent', 'Important', 'Duration (mins)'
    ])

if 'energy_db' not in st.session_state:
    st.session_state.energy_db = pd.DataFrame(columns=[
        'Timestamp', 'Time of Day', 'Energy Level (1-10)', 'Notes'
    ])

# --- Sidebar: Data Entry ---
st.sidebar.title("⚡ Quick Logging")

# 1. Task Logger (Saves Locally to App)
st.sidebar.subheader("Log a Task")
with st.sidebar.form("task_form", clear_on_submit=True):
    task_name = st.text_input("Task Description")
    category = st.selectbox("Category", ["School Admin", "Software Dev (Streamlit)", "YouTube Creator", "Personal/Yoga"])
    duration = st.number_input("Duration (minutes)", min_value=5, step=5)
    
    st.write("Eisenhower Categorization:")
    col1, col2 = st.columns(2)
    is_urgent = col1.checkbox("Urgent")
    is_important = col2.checkbox("Important")
    
    submit_task = st.form_submit_button("Log Task")
    
    if submit_task and task_name:
        new_task = pd.DataFrame([{
            'Timestamp': datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S"),
            'Task': task_name,
            'Category': category,
            'Urgent': is_urgent,
            'Important': is_important,
            'Duration (mins)': duration
        }])
        st.session_state.task_db = pd.concat([st.session_state.task_db, new_task], ignore_index=True)
        st.sidebar.success("Task Logged to Dashboard!")

st.sidebar.divider()

# 2. Energy Logger (Saves Locally to App)
st.sidebar.subheader("🔋 Log Energy Level")
with st.sidebar.form("energy_form", clear_on_submit=True):
    time_of_day = st.selectbox("Time", ["Morning (Post-Yoga)", "Mid-Day (School)", "Evening (Creator/Dev)"])
    energy_level = st.slider("Energy Level", 1, 10, 5)
    notes = st.text_input("Context (e.g., 'Burnt out from meetings')")
    
    submit_energy = st.form_submit_button("Log Energy")
    
    if submit_energy:
        new_energy = pd.DataFrame([{
            'Timestamp': datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S"),
            'Time of Day': time_of_day,
            'Energy Level (1-10)': energy_level,
            'Notes': notes
        }])
        st.session_state.energy_db = pd.concat([st.session_state.energy_db, new_energy], ignore_index=True)
        st.sidebar.success("Energy Logged to Dashboard!")

st.sidebar.divider()

# 3. Future Task Scheduler (PUSHES TO GOOGLE SHEETS)
st.sidebar.subheader("🗓️ Schedule Future Task")
st.sidebar.caption("Saves directly to 'MY ROUTINE 2026'")
with st.sidebar.form("future_task_form", clear_on_submit=True):
    f_name = st.text_input("Task Name", placeholder="e.g., Fix Attendance Bug")
    f_act = st.selectbox("Activity Category", ["WORK", "HEALTH", "SCH WORK", "HOME", "PEOPLE"])
    f_type = st.radio("Task Type", ["Sub-Activity", "Checklist"], horizontal=True)
    
    col_fd, col_ft = st.columns(2)
    with col_fd: f_date = st.date_input("Due Date", value=datetime.now(IST).date())
    
    time_opts = [f"{str(h).zfill(2)}:{str(m).zfill(2)}" for h in range(24) for m in range(60)]
    with col_ft: f_time = st.selectbox("Due Time", options=time_opts, index=time_opts.index(datetime.now(IST).strftime('%H:%M')))

    st.write("Context & Energy Strategy")
    f_role = st.selectbox("Role Context", ["Head Teacher (BPS)", "Developer (BPS Digital)", "YouTube Creator", "Personal", "Transition"])
    col_u, col_i = st.columns(2)
    f_urg = col_u.checkbox("🔥 Urgent")
    f_imp = col_i.checkbox("⭐ Important")
    f_energy = st.slider("Expected Energy Req.", 1, 10, 5)
    
    submit_future = st.form_submit_button("🚀 Push to Sheets")
    
    if submit_future:
        if f_name:
            try:
                client = init_connection()
                sheet = client.open("MY ROUTINE 2026").worksheet("future_tasks")
                
                # Construct the 12-item array matching your backend
                row_data = [
                    f_date.strftime('%Y-%m-%d'),
                    f_time,
                    f_act,
                    f_type,
                    f_name.strip(),
                    "Personal",
                    "Pending",
                    "",
                    f_role,
                    str(f_urg).upper(),
                    str(f_imp).upper(),
                    f_energy
                ]
                sheet.append_row(row_data, value_input_option="USER_ENTERED")
                st.sidebar.success(f"✅ Sent '{f_name}' to future_tasks!")
            except Exception as e:
                st.sidebar.error(f"❌ Connection Error: Ensure your st.secrets are correct. Details: {e}")
        else:
            st.sidebar.error("⚠️ Enter a Task Name.")

# --- Main Dashboard ---
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
        st.write("Log tasks in the sidebar to populate your matrix.")

# --- TAB 2: Analytics using Plotly ---
with tab2:
    st.subheader("Where is your time going?")
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        if not st.session_state.task_db.empty:
            time_dist = st.session_state.task_db.groupby('Category')['Duration (mins)'].sum().reset_index()
            fig_pie = px.pie(time_dist, values='Duration (mins)', names='Category', title="Time Distribution by Role", hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.write("Awaiting task data for chart generation...")
            
    with col_b:
        if not st.session_state.energy_db.empty:
            fig_line = px.line(st.session_state.energy_db, x='Timestamp', y='Energy Level (1-10)', 
                               title="Energy Level Tracking", markers=True, color='Time of Day')
            fig_line.update_layout(yaxis=dict(range=[0, 11]))
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.write("Awaiting energy data for chart generation...")

# --- TAB 3: Raw Logs ---
with tab3:
    st.subheader("Database View")
    st.write("The Top and Middle forms save here temporarily. The Bottom form pushes directly to Google Sheets.")
    
    st.write("**Local Task Database**")
    st.dataframe(st.session_state.task_db, use_container_width=True)
    
    st.write("**Local Energy Database**")
    st.dataframe(st.session_state.energy_db, use_container_width=True)
