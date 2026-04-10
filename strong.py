import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import pytz
import plotly.express as px

# --- Timezone Setup ---
IST = pytz.timezone('Asia/Kolkata')

def get_current_time():
    """Returns the current time in IST formatted as a string."""
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

# --- App Configuration ---
st.set_page_config(page_title="Balance OS", layout="wide", page_icon="⚖️")

# --- Database Connection ---
@st.cache_resource
def init_connection():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = dict(st.secrets["gcp_service_account"])
    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(credentials)
    return client.open("strong")

try:
    sh = init_connection()
except Exception as e:
    st.error(f"Failed to connect to Google Sheets: {e}")
    st.stop()

# --- Helper Functions ---
def get_data(worksheet_name):
    """Fetches data from a specific tab and returns a Pandas DataFrame."""
    try:
        worksheet = sh.worksheet(worksheet_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error reading tab '{worksheet_name}': {e}")
        return pd.DataFrame()

def append_data(worksheet_name, row_data):
    """Appends a new row of data to the bottom of a specific tab."""
    try:
        worksheet = sh.worksheet(worksheet_name)
        worksheet.append_row(row_data)
    except Exception as e:
        st.error(f"Error saving to tab '{worksheet_name}': {e}")

def next_step_widget(page_name):
    """A modular widget to log and view next steps for a specific page."""
    st.divider()
    st.subheader(f"🎯 Next Action: {page_name}")
    
    # 1. Form to log the next step
    with st.form(f"next_step_form_{page_name}", clear_on_submit=True):
        col1, col2 = st.columns([4, 1])
        with col1:
            action = st.text_input("What is the immediate next step?", placeholder="e.g., Draft email, review budget...")
        with col2:
            st.write("") # Spacing to align button
            st.write("") 
            submitted = st.form_submit_button("Log Action")
            
            if submitted and action:
                new_row = [get_current_time(), page_name, action, "Pending"]
                append_data("Next Steps", new_row)
                st.success("Next action logged!")

    # 2. Display pending steps for this specific category (Always Visible)
    df_steps = get_data("Next Steps")
    if not df_steps.empty and "Category" in df_steps.columns:
        # Filter data for the current page and only show "Pending" tasks
        pending = df_steps[(df_steps["Category"] == page_name) & (df_steps["Status"] == "Pending")]
        if not pending.empty:
            st.markdown(f"**📌 Pending Actions for {page_name}**")
            st.dataframe(pending[["Date", "Next Step"]], hide_index=True, use_container_width=True)


# --- Navigation ---
st.sidebar.title("Navigation")
tabs = [
    "Health", "Financial Growth", "Family Life", 
    "Work Life Balance", "Skill Development", 
    "Social Life", "Idea", "Update"
]
choice = st.sidebar.radio("Go to:", tabs)


# --- Tab Pages ---

if choice == "Idea":
    st.title("💡 Idea Capture")
    st.write("Drop your thoughts here before you lose them.")
    
    with st.form("idea_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            idea_category = st.selectbox("Category", ["App Dev", "YouTube", "School Management", "General"])
        with col2:
            idea_impact = st.select_slider("Potential Impact", options=["Low", "Medium", "High"])
            
        idea_text = st.text_area("What's the idea?", placeholder="e.g., App update strategy, new video concept...")
        submitted = st.form_submit_button("Save Idea")
        
        if submitted and idea_text:
            new_row = [get_current_time(), idea_category, idea_impact, idea_text]
            append_data("Idea", new_row)
            st.success("Idea saved successfully!")

    st.divider()
    st.subheader("Idea Vault")
    df_ideas = get_data("Idea")
    if not df_ideas.empty:
        st.dataframe(df_ideas, use_container_width=True)
    else:
        st.info("No ideas logged yet. Add your first one above!")
        
    next_step_widget("Idea")

elif choice == "Health":
    st.title("🧘 Health Development")
    
    with st.form("health_form", clear_on_submit=True):
        date = st.date_input("Date")
        activity = st.selectbox("Activity", ["Yoga", "Running", "Intense Workout", "Dance", "Meditation"])
        duration = st.number_input("Duration (minutes)", min_value=0, max_value=180, step=5)
        submitted = st.form_submit_button("Log Activity")
        
        if submitted:
            new_row = [str(date), activity, duration]
            append_data("Health", new_row)
            st.success("Health log saved!")
            
    st.divider()
    df_health = get_data("Health")
    if not df_health.empty:
        st.dataframe(df_health, use_container_width=True)
    else:
         st.info("Log your first activity above!")
         
    next_step_widget("Health")

elif choice == "Financial Growth":
    st.title("📈 Financial Growth")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        with st.form("finance_form", clear_on_submit=True):
            st.subheader("Log Entry")
            fin_category = st.selectbox("Category", ["Stock Market Course Progress (%)", "Savings Deposit", "YouTube Revenue", "Expense"])
            amount = st.number_input("Value / Amount", min_value=0.0, step=10.0)
            notes = st.text_input("Notes")
            submitted = st.form_submit_button("Save Entry")
            
            if submitted:
                new_row = [get_current_time(), fin_category, amount, notes]
                append_data("Financial Growth", new_row)
                st.success("Entry saved!")

    with col2:
        st.subheader("Trends")
        df_finance = get_data("Financial Growth")
        if not df_finance.empty:
            fig = px.bar(df_finance, x="Date", y="Amount/Progress", color="Category", title="Financial Growth Over Time")
            st.plotly_chart(fig, use_container_width=True)
            
            with st.expander("View Raw Data"):
                st.dataframe(df_finance, use_container_width=True)
        else:
            st.info("Log your first entry to see the chart!")
            
    next_step_widget("Financial Growth")

elif choice == "Skill Development":
    st.title("🛠️ Skill Development")
    
    col1, col2 = st.columns(2)
    
    with col1:
        with st.form("skill_form", clear_on_submit=True):
            st.subheader("Log Project Time")
            project = st.selectbox("Project / Focus", [
                "BPS Digital App", 
                "YouTube Channel Management", 
                "Learning/Coursework", 
                "Other App Dev"
            ])
            status = st.selectbox("Status", ["Planning", "In Progress", "Testing", "Completed"])
            hours = st.number_input("Hours Spent Today", min_value=0.0, max_value=24.0, step=0.5)
            
            submitted = st.form_submit_button("Log Time")
            
            if submitted:
                new_row = [get_current_time(), project, status, hours]
                append_data("Skill Development", new_row)
                st.success(f"Logged {hours} hours for {project}!")

    with col2:
        st.subheader("Time Allocation")
        df_skills = get_data("Skill Development")
        if not df_skills.empty:
            fig_pie = px.pie(df_skills, values='Time Spent (Hours)', names='Project', title='Time Distribution')
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Log project time to see your distribution chart!")
            
    next_step_widget("Skill Development")

else:
    # Placeholder for Family Life, Work Life Balance, Social Life, and Update
    st.title(f"🚀 {choice}")
    st.write(f"The workspace for **{choice}** is under construction. Ready for future modules!")
    
    next_step_widget(choice)
