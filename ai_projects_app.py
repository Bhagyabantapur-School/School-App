import streamlit as st
# --- BACK BUTTON ---
if st.button("⬅️ Back to Hub", type="secondary"):
    st.switch_page("routine_app.py") 
st.write("---") 
# -------------------
import pandas as pd
from datetime import datetime, timedelta, timezone
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. SETUP & HELPER FUNCTIONS
# ==========================================
st.set_page_config(page_title="AI Projects Tracker", page_icon="🤖", layout="centered")

def get_ist_now():
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)

if 'locked_date' not in st.session_state: 
    st.session_state.locked_date = get_ist_now().date()

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

# --- SMART CACHING ENGINE ---
@st.cache_data(ttl=600)
def load_config():
    try: return pd.DataFrame(sh.worksheet("CONFIG").get_all_records())
    except: return pd.DataFrame()

config_df = load_config()

def get_list(column_name):
    if column_name in config_df.columns:
        raw_list = [str(val).strip() for val in config_df[column_name].dropna().tolist() if str(val).strip() != ""]
        return list(dict.fromkeys(raw_list))
    return []

# ==========================================
# APP LAYOUT
# ==========================================
st.title("🤖 AI Generation & Projects")
st.write("Track your AI freelance work, app builds, and prompt sales.")

with st.expander("Log AI Project Details", expanded=True):
    ai_opts = get_list("AI_Platforms")
    if not ai_opts: ai_opts = ["Direct Client", "Upwork", "Fiverr", "Gumroad", "-- Type New --"]
    elif "-- Type New --" not in ai_opts: ai_opts.append("-- Type New --")
        
    ai_plat_sel = st.selectbox("Platform / Source", ai_opts, key="ai_plat_sel")
    ai_platform = st.text_input("Type New Platform Name", key="ai_new_plat") if ai_plat_sel == "-- Type New --" else ai_plat_sel

    ai_project = st.text_input("Project or Task Name (e.g., 'Streamlit App Build')")
    
    ai_c1, ai_c2, ai_c3 = st.columns([1.5, 1, 1.5])
    with ai_c1: ai_date = st.date_input("Date Logged", value=st.session_state.locked_date, key="ai_date")
    with ai_c2: ai_hours = st.number_input("Hours Spent", min_value=0.0, step=0.5, key="ai_hrs")
    with ai_c3: ai_revenue = st.number_input("Estimated Revenue (₹)", min_value=0.0, step=100.0, key="ai_rev")
        
    ai_status = st.selectbox("Payment Status", ["Pending / Unbilled", "Invoice Sent", "✅ Paid"], key="ai_status")

    if st.button("💾 Save AI Income Log", use_container_width=True, type="primary"):
        if ai_platform and ai_project:
            try:
                date_str = ai_date.strftime("%d-%m-%Y")
                try: ai_ws = sh.worksheet("AI_INCOME_LOG")
                except gspread.exceptions.WorksheetNotFound:
                    ai_ws = sh.add_worksheet(title="AI_INCOME_LOG", rows="100", cols="6")
                    ai_ws.append_row(["Date", "Platform", "Project_Name", "Hours_Spent", "Estimated_Revenue", "Status"])
                
                ai_ws.append_row([date_str, ai_platform, ai_project, ai_hours, ai_revenue, ai_status])
                st.success(f"✅ Logged AI project: {ai_project}!")
                if ai_status == "✅ Paid": st.info("Remember to log the actual cash received in the main Money app!")
            except Exception as e: st.error(f"Error: {e}")
        else: st.warning("⚠️ Please provide both the Platform and the Project Name.")
