import streamlit as st
import pandas as pd
import datetime

# --- App Configuration ---
st.set_page_config(page_title="Life OS Dashboard", layout="wide")

# --- Sidebar Navigation ---
st.sidebar.title("Navigation")
menu = ["Dashboard", "Health", "Financial Growth", "Family Life", "Work/Life Balance", "Skill Development", "Social Life"]
choice = st.sidebar.radio("Go to", menu)

# --- 1. Dashboard Page ---
if choice == "Dashboard":
    st.title("📊 Life OS: Weekly Balance")
    st.write("Welcome to your command center. Here is your balance across all pillars this week.")
    
    # Mock data for a radar chart or progress bars
    col1, col2, col3 = st.columns(3)
    col1.metric("Health Streak", "5 Days", "+1")
    col2.metric("Learning Hours", "8 Hrs", "+2 Hrs")
    col3.metric("Family Time", "12 Hrs", "Stable")
    
    st.divider()
    st.subheader("Daily Quick Capture")
    st.text_input("What is your primary focus for today?")
    st.button("Save Focus")

# --- 2. Health Development Page ---
elif choice == "Health":
    st.title("🧘 Health & Fitness Tracking")
    
    # Input Form
    with st.form("health_log"):
        st.subheader("Log Today's Activity")
        date = st.date_input("Date", datetime.date.today())
        
        # Specific activity selection
        activity = st.selectbox("Activity Type", ["Yoga", "Intense Workout", "Running", "Meditation", "Dance", "Rest Day"])
        duration = st.slider("Duration (minutes)", 0, 120, 30)
        notes = st.text_input("Notes (How did you feel?)")
        
        submit = st.form_submit_button("Log Activity")
        
        if submit:
            st.success(f"Successfully logged {duration} minutes of {activity}!")
            # In a real app, you would append this to a CSV or database here.

# --- 3. Financial Growth Page ---
elif choice == "Financial Growth":
    st.title("📈 Financial Growth")
    st.write("Track your budget, investments, and financial learning here.")
    # Placeholder for financial metrics

# --- 4. Personal Skill Development Page ---
elif choice == "Skill Development":
    st.title("🛠️ Skill Development")
    st.write("Track course progress, coding projects, and content creation.")
    # Placeholder for project tracking

# --- Other Pages (Placeholders) ---
else:
    st.title(f"🚀 {choice}")
    st.write("Module under construction. Add your data tables and forms here!")
