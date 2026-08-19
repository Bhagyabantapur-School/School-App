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
st.set_page_config(page_title="YouTube Tracker", page_icon="▶️", layout="centered")

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
st.title("▶️ YouTube Analytics & Revenue")
st.write("Track daily or weekly performance across all your channels.")

with st.expander("Log Channel Stats", expanded=True):
    channel_opts = get_list("YouTube_Channels") 
    if not channel_opts: channel_opts = ["techfeatureslife9451", "-- Type New --"]
    elif "-- Type New --" not in channel_opts: channel_opts.append("-- Type New --")
    
    yt_channel_sel = st.selectbox("Select Channel", channel_opts, key="yt_chan")
    yt_channel = st.text_input("Type New Channel") if yt_channel_sel == "-- Type New --" else yt_channel_sel
    
    yt_c1, yt_c2 = st.columns(2)
    with yt_c1:
        yt_date = st.date_input("Analytics Date", value=st.session_state.locked_date, key="yt_date")
        yt_views = st.number_input("Views", min_value=0, step=100)
        yt_subs = st.number_input("Subscribers Gained", min_value=0, step=1)
    
    with yt_c2:
        yt_title = st.text_input("Video Title (Optional)")
        yt_hours = st.number_input("Watch Hours", min_value=0.0, step=1.0)
        yt_revenue = st.number_input("Estimated Revenue (₹)", min_value=0.0, step=10.0)

    if st.button("💾 Save YouTube Log", use_container_width=True, type="primary"):
        if yt_channel:
            try:
                date_str = yt_date.strftime("%d-%m-%Y")
                
                try: 
                    yt_ws = sh.worksheet("YOUTUBE_LOG")
                except gspread.exceptions.WorksheetNotFound:
                    yt_ws = sh.add_worksheet(title="YOUTUBE_LOG", rows="100", cols="7")
                    yt_ws.append_row(["Date", "Channel_Name", "Video_Title", "Views", "Watch_Hours", "Subscribers_Gained", "Estimated_Revenue"])
                
                yt_ws.append_row([date_str, yt_channel, yt_title, yt_views, yt_hours, yt_subs, yt_revenue])
                st.success(f"✅ Logged stats for {yt_channel}!")
                st.balloons()
            except Exception as e: 
                st.error(f"Error: {e}")
        else: 
            st.warning("⚠️ Please provide a channel name.")
