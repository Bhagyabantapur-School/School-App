import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import time
import plotly.express as px

# ==========================================
# 1. Configuration & Styling
# ==========================================
st.set_page_config(page_title="Project Tracker", page_icon="📊", layout="wide")

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
    # Ensure you have your secrets configured in .streamlit/secrets.toml
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scopes
    )
    return gspread.authorize(creds)

def get_sheet(tab_name):
    client = init_connection()
    return client.open("MY ROUTINE 2026").worksheet(tab_name)

@st.cache_data(ttl=300)
def get_project_tasks():
    client = init_connection()
    ss = client.open("MY ROUTINE 2026")
    try:
        sheet = ss.worksheet("project_tasks")
    except gspread.exceptions.WorksheetNotFound:
        sheet = ss.add_worksheet(title="project_tasks", rows="200", cols="5")
        sheet.append_row(["Task Name", "Project Name", "Status", "Start Date", "End Date"])
    data = sheet.get_all_values()
    if len(data) <= 1:
        return pd.DataFrame(columns=["Task Name", "Project Name", "Status", "Start Date", "End Date", "row_index"])
    
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 5: df[df.shape[1]] = ""
    df = df.iloc[:, :5]
    df.columns = ["Task Name", "Project Name", "Status", "Start Date", "End Date"]
    df['row_index'] = df.index + 2 
    return df

# ==========================================
# 3. Main Dashboard UI
# ==========================================
st.title("📊 Project Tracking Dashboard")

col1, col2 = st.columns([5, 1])
with col2:
    if st.button("🔄 Sync Data", use_container_width=True):
        get_project_tasks.clear()
        st.toast("Synced with Google Sheets!")
        time.sleep(0.5)
        st.rerun()

try:
    proj_df = get_project_tasks()
    status_colors = {"Completed": "#2e7b32", "In Progress": "#0068c9", "Not Started": "#ff9f36"}
    
    if not proj_df.empty:
        plot_df = proj_df.copy()
        plot_df['Start Date'] = pd.to_datetime(plot_df['Start Date'], errors='coerce')
        plot_df['End Date'] = pd.to_datetime(plot_df['End Date'], errors='coerce')
        plot_df = plot_df.dropna(subset=['Start Date', 'End Date'])
        
        if not plot_df.empty:
            # --- OVERALL PROGRESS CARDS ---
            st.markdown("### 📈 Overall Progress")
            project_stats = plot_df.groupby('Project Name').apply(
                lambda x: (x['Status'].str.strip().str.title() == 'Completed').sum() / len(x)
            ).reset_index(name='Progress')
            
            cols = st.columns(4) # Using 4 columns since layout is 'wide'
            for i, row in project_stats.iterrows():
                with cols[i % 4]:
                    percent_complete = int(row['Progress'] * 100)
                    st.markdown(f"""
                    <div style='background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 5px; height: 110px;'>
                        <p style='margin: 0; font-size: 16px; font-weight: 600; color: #333; line-height: 1.2; word-wrap: break-word;'>{row['Project Name']}</p>
                        <h2 style='margin: 0; color: #0068c9; padding-top: 5px;'>{percent_complete}%</h2>
                    </div>
                    """, unsafe_allow_html=True)
                    st.progress(row['Progress'])
                    st.markdown("<br>", unsafe_allow_html=True)
            
            st.markdown("---")
            
            # --- CHARTS SECTION ---
            col_gantt, col_pie = st.columns([2, 1])
            
            with col_gantt:
                st.markdown("#### 🗓️ Task Timeline")
                plot_df['Status'] = plot_df['Status'].str.strip().str.title()
                plot_df = plot_df.sort_values('Start Date')
                
                fig_gantt = px.timeline(plot_df, x_start="Start Date", x_end="End Date", y="Task Name", 
                                        color="Status", color_discrete_map=status_colors, hover_data=["Project Name"])
                fig_gantt.update_yaxes(autorange="reversed", tickmode='linear')
                fig_gantt.update_layout(margin=dict(l=0, r=0, t=30, b=0), xaxis_title="", yaxis_title="", showlegend=False)
                st.plotly_chart(fig_gantt, use_container_width=True)
                
            with col_pie:
                st.markdown("#### 📌 Task Status Breakdown")
                status_counts = plot_df['Status'].value_counts().reset_index()
                status_counts.columns = ['Status', 'Count']
                
                fig_pie = px.pie(status_counts, names='Status', values='Count', 
                                 color='Status', color_discrete_map=status_colors, hole=0.45)
                fig_pie.update_layout(margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Project dates are missing or invalid. Please update them in the Google Sheet.")
    else:
        st.info("No project tasks found. Add your first task below!")
        
    st.markdown("---")    
    
    # --- ADD NEW TASK FORM ---
    with st.expander("➕ Add New Project Task", expanded=proj_df.empty):
        with st.form("add_project_task", clear_on_submit=True):
            p_task = st.text_input("Task Name")
            
            if not proj_df.empty:
                existing_projects = ["-- Select Existing Project --"] + sorted(list(set(proj_df['Project Name'].dropna().tolist())))
            else:
                existing_projects = ["-- Select Existing Project --"]
            
            col_p1, col_p2 = st.columns(2)
            with col_p1: p_name_sel = st.selectbox("Existing Project", existing_projects)
            with col_p2: p_name_new = st.text_input("OR New Project Name", placeholder="Type new name here")
            
            col_s, col_d1, col_d2 = st.columns(3)
            with col_s: p_status = st.selectbox("Status", ["Not Started", "In Progress", "Completed"])
            with col_d1: p_start = st.date_input("Start Date")
            with col_d2: p_end = st.date_input("End Date")
            
            if st.form_submit_button("Add Task", type="primary", use_container_width=True):
                final_p_name = p_name_new.strip() if p_name_new.strip() else (p_name_sel if p_name_sel != "-- Select Existing Project --" else "")
                
                if p_task and final_p_name:
                    psheet = get_sheet("project_tasks")
                    psheet.append_row([p_task.strip(), final_p_name, p_status, p_start.strftime('%Y-%m-%d'), p_end.strftime('%Y-%m-%d')])
                    get_project_tasks.clear() 
                    st.success("Task added successfully!")
                    time.sleep(1)
                    st.rerun()
                else: 
                    st.error("Task Name and Project Name are both required.")

except Exception as e:
    st.error(f"System Error: {e}")
