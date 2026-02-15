import streamlit as st
import pandas as pd
from datetime import datetime
import os
import time
from streamlit_qrcode_scanner import qrcode_scanner

# --- 1. PWA & MOBILE APP CONFIGURATION ---
st.set_page_config(
    page_title="BPS Digital",
    page_icon="logo.png" if os.path.exists("logo.png") else "🏫",
    layout="wide",
    initial_sidebar_state="auto"
)

# Advanced CSS to force Mobile App Appearance and Sidebar behavior
st.markdown(
    """
    <head>
        <link rel="manifest" href="./manifest.json">
        <meta name="mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="theme-color" content="#007bff">
    </head>
    <style>
        /* Hide Streamlit Header/Footer */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* Mobile optimization: Make the app fill the screen */
        .block-container { padding-top: 1rem; padding-bottom: 1rem; }
        
        /* Ensure the Sidebar button is visible on small screens */
        .st-emotion-cache-18ni7ve { color: #007bff !important; }
        
        /* Button Styling */
        .stButton>button {
            width: 100%;
            border-radius: 12px;
            height: 3.5em;
            background-color: #007bff;
            color: white;
            font-weight: bold;
            border: none;
            box-shadow: 0px 4px 6px rgba(0,0,0,0.1);
        }
    </style>
    """,
    unsafe_allow_html=True
)

# --- 2. DATE & TIME LOGIC ---
date_today_dt = datetime.now()
date_today_str = date_today_dt.strftime("%d-%m-%Y") 
day_name = date_today_dt.strftime('%A')

# --- 3. DATA LOADING ---
@st.cache_data
def load_data(file):
    if os.path.exists(file):
        try:
            return pd.read_csv(file, encoding='utf-8-sig')
        except:
            return pd.read_csv(file)
    return None

students_df = load_data('students.csv')
routine_df = load_data('routine.csv')
holidays_df = load_data('holidays.csv')

# --- 4. HOLIDAY & COUNTDOWN ---
is_holiday = False
holiday_reason = ""
days_until_next = None
next_holiday_name = ""

if holidays_df is not None:
    holidays_df['dt'] = pd.to_datetime(holidays_df['Date'], format='%d-%m-%Y')
    if date_today_str in holidays_df['Date'].values:
        is_holiday = True
        holiday_reason = holidays_df[holidays_df['Date'] == date_today_str]['Occasion'].values[0]
    
    future = holidays_df[holidays_df['dt'] > date_today_dt].sort_values('dt')
    if not future.empty:
        next_h = future.iloc[0]
        days_until_next = (next_h['dt'] - date_today_dt).days + 1
        next_holiday_name = next_h['Occasion']

if day_name == "Sunday":
    is_holiday = True
    holiday_reason = "Sunday (Weekly Off)"

# --- 5. TEACHER PASSWORDS ---
SECRET_PASSWORD = "bpsAPP@2026"
TEACHER_DATA = {
    "TAPASI RANA": {"id": "TR", "pw": "tr26"},
    "SUJATA BISWAS ROTHA": {"id": "SBR", "pw": "sbr26"},
    "ROHINI SINGH": {"id": "RS", "pw": "rs26"},
    "UDAY NARAYAN JANA": {"id": "UNJ", "pw": "unj26"},
    "BIMAL KUMAR PATRA": {"id": "BKP", "pw": "bkp26"},
    "SUSMITA PAUL": {"id": "SP", "pw": "sp26"},
    "TAPAN KUMAR MANDAL": {"id": "TKM", "pw": "tkm26"},
    "MANJUMA KHATUN": {"id": "MK", "pw": "mk26"}
}

if 'sub_map' not in st.session_state:
    st.session_state.sub_map = {} 

# --- 6. SIDEBAR MENU ---
if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", use_container_width=True)
else:
    st.sidebar.title("🏫 BPS Digital")

if os.path.exists('mdm_log.csv'):
    try:
        df_log = pd.read_csv('mdm_log.csv')
        if not df_log.empty:
            last = df_log.iloc[-1]
            st.sidebar.info(f"✅ Last Submit: {last['Time']} ({last['Date']})")
    except: pass

st.sidebar.divider()
st.sidebar.write(f"📅 {date_today_str} | {day_name}")

if days_until_next is not None and not is_holiday:
    st.sidebar.success(f"🎉 {days_until_next} Days to {next_holiday_name}")

role = st.sidebar.radio("Main Menu:", ["Teacher Login", "Admin Panel", "📅 Holidays"])

# --- 7. APP LOGIC ---

if role == "📅 Holidays":
    st.header("🗓️ School Holidays 2026")
    if holidays_df is not None:
        st.table(holidays_df[['Date', 'Occasion']])

elif role == "Teacher Login":
    if is_holiday:
        st.error(f"🚫 School Closed: {holiday_reason}")