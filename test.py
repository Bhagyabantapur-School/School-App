import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import pytz

# --- Configuration & Timezone ---
st.set_page_config(page_title="Dual-Mode Productivity OS", layout="wide")
IST = pytz.timezone('Asia/Kolkata')

# --- Initialize Session State (Mock Database) ---
# In production, you can replace this by pulling/pushing to Google Sheets using gspread
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

# 1. Task Logger
st.sidebar.subheader("Log a Task")
with st.sidebar.form("task_form"):
    task_name = st.text_input("Task Description")
    category = st.selectbox("Category", ["School Admin", "Software Dev (Streamlit)", "YouTube Creator", "Personal/Yoga"])
    duration = st.number_input("Duration (minutes)", min_value=5, step=5)
    
    # Eisenhower Matrix inputs
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
        st.sidebar.success("Task Logged!")

st.sidebar.divider()

# 2. Energy Logger
st.sidebar.subheader("🔋 Log Energy Level")
with st.sidebar.form("energy_form"):
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
        st.sidebar.success("Energy Logged!")


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
            # Group duration by category
            time_dist = st.session_state.task_db.groupby('Category')['Duration (mins)'].sum().reset_index()
            fig_pie = px.pie(time_dist, values='Duration (mins)', names='Category', title="Time Distribution by Role", hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.write("Awaiting task data for chart generation...")
            
    with col_b:
        if not st.session_state.energy_db.empty:
            # Line chart for energy levels over time
            fig_line = px.line(st.session_state.energy_db, x='Timestamp', y='Energy Level (1-10)', 
                               title="Energy Level Tracking", markers=True, color='Time of Day')
            # Fix Y-axis to 1-10 scale
            fig_line.update_layout(yaxis=dict(range=[0, 11]))
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.write("Awaiting energy data for chart generation...")

# --- TAB 3: Raw Logs ---
with tab3:
    st.subheader("Database View")
    st.write("You can later map these Pandas DataFrames to Google Sheets using `gspread` and `google-auth`.")
    
    st.write("**Task Database**")
    st.dataframe(st.session_state.task_db, use_container_width=True)
    
    st.write("**Energy Database**")
    st.dataframe(st.session_state.energy_db, use_container_width=True)
