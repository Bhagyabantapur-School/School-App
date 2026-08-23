import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. SETUP & HELPER FUNCTIONS
# ==========================================
st.set_page_config(page_title="Course & Learning Tracker", page_icon="🎓", layout="centered")

# --- BACK BUTTON ---
if st.button("⬅️ Back to Hub", type="secondary"):
    st.switch_page("routine_app.py") 
st.write("---") 
# -------------------

def get_ist_now():
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)

@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    return client.open("sk_money_location")

try:
    sh = init_connection()
except Exception as e:
    st.error(f"Could not connect to Google Sheets. Error: {e}")
    st.stop()

@st.cache_data(ttl=60)
def load_money_data():
    # Helper to clear cache when auto-syncing payments
    try: return pd.DataFrame(sh.worksheet("MONEY_DATA").get_all_records())
    except: return pd.DataFrame()

# ==========================================
# APP LAYOUT
# ==========================================
st.title("🎓 Course & Learning Tracker")
st.write("Track your workshops, app logins, and automatically sync payments.")

with st.expander("📝 Add New Course / Workshop", expanded=True):
    c1, c2 = st.columns(2)
    with c1:
        course_name = st.text_input("Course / Workshop Name", placeholder="e.g., AI Tools Workshop")
        course_type = st.radio("Purpose / Type", ["Personal", "School"])
    with c2:
        provider = st.text_input("Provider / Platform", placeholder="e.g., be10x")
        finance_type = st.radio("Finance Type", ["Paid", "Free"])

    # Only show the cost input if the course is Paid
    cost = 0.0
    if finance_type == "Paid":
        cost = st.number_input("Course Fee (₹)", min_value=0.0, step=50.0, format="%.2f")

    schedule_date = st.text_input("Schedule Date & Time", placeholder="e.g., 30-Aug-2026 11:00 AM")
    
    login_details = st.text_area(
        "Login / Access Details", 
        placeholder="e.g., Downloaded Android app be10x, joined WhatsApp group..."
    )

    if st.button("💾 Save Course Data", use_container_width=True, type="primary"):
        if course_name and provider:
            try:
                date_logged = get_ist_now().strftime("%d-%m-%Y")
                time_logged = get_ist_now().strftime("%H:%M")
                
                # 1. Log the details to COURSE_LOG tab
                try: 
                    course_ws = sh.worksheet("COURSE_LOG")
                except gspread.exceptions.WorksheetNotFound:
                    course_ws = sh.add_worksheet(title="COURSE_LOG", rows="100", cols="8")
                    course_ws.append_row(["Date_Logged", "Course_Name", "Provider", "Type", "Finance", "Cost_INR", "Schedule", "Login_Details"])
                
                course_ws.append_row([
                    date_logged, course_name, provider, course_type, finance_type, cost, schedule_date, login_details
                ])
                
                # 2. AUTOMATICALLY sync with Main MONEY_DATA if it is a Paid course
                if finance_type == "Paid" and cost > 0:
                    money_ws = sh.worksheet("MONEY_DATA")
                    
                    # Dynamically set Entity based on Type (PERS for Personal, WORK for School/Teaching)
                    entity = "PERS" if course_type == "Personal" else "WORK"
                    
                    # Money leaves MB account (OUT)
                    money_row = [
                        date_logged, time_logged, "", cost, "MB", "Salary", 
                        entity, "EDUCATION", "Course/Workshop", course_name, "", provider, "Auto-logged Course Fee"
                    ]
                    
                    money_ws.append_row(money_row)
                    load_money_data.clear() # Clears cache in the main app
                    
                    st.success(f"✅ Course saved and ₹{cost} payment synced to Money Tracker!")
                else:
                    st.success("✅ Free course details saved successfully!")
                    
                st.balloons()
            except Exception as e:
                st.error(f"Error saving to Google Sheets: {e}")
        else:
            st.warning("⚠️ Please provide at least the Course Name and Provider.")
