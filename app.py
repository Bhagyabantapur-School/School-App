import streamlit as st
import pandas as pd
from datetime import datetime
import os
import time
from streamlit_qrcode_scanner import qrcode_scanner

# --- 1. PWA & APP CONFIGURATION ---
st.set_page_config(
    page_title="BPS Digital",
    page_icon="logo.png" if os.path.exists("logo.png") else "🏫",
    layout="centered"
)

# Advanced CSS: Hides Sidebar, Hides Streamlit UI, and styles for a "Native App" feel
st.markdown(
    """
    <head>
        <link rel="manifest" href="./manifest.json">
        <meta name="mobile-web-app-capable" content="yes">
        <meta name="theme-color" content="#007bff">
    </head>
    <style>
        /* Hide all Streamlit default elements */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        [data-testid="stSidebar"] {display: none;}
        
        /* App Background and Padding */
        .block-container { padding-top: 1.5rem; max-width: 500px; }
        
        /* Professional Button Styling */
        .stButton>button {
            width: 100%;
            border-radius: 15px;
            height: 3.5em;
            background-color: #007bff;
            color: white;
            font-weight: bold;
            border: none;
            box-shadow: 0px 4px 10px rgba(0,0,0,0.1);
            transition: 0.3s;
        }
        .stButton>button:active {
            transform: scale(0.98);
            background-color: #0056b3;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# --- 2. DATE & DATA LOADING ---
date_today_dt = datetime.now()
date_today_str = date_today_dt.strftime("%d-%m-%Y") 
day_name = date_today_dt.strftime('%A')

@st.cache_data
def load_data(file):
    if os.path.exists(file):
        try: return pd.read_csv(file, encoding='utf-8-sig')
        except: return pd.read_csv(file)
    return None

students_df = load_data('students.csv')
routine_df = load_data('routine.csv')
holidays_df = load_data('holidays.csv')

# --- 3. LOGO & HEADER ---
col1, col2, col3 = st.columns([1, 3, 1])
with col2:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    else:
        st.markdown("<h2 style='text-align: center;'>🏫 Bhagyabantapur PS</h2>", unsafe_allow_html=True)
    
    st.markdown(f"<p style='text-align: center; color: gray;'>{date_today_str} | {day_name}</p>", unsafe_allow_html=True)

# Last Submission Info
if os.path.exists('mdm_log.csv'):
    try:
        df_l = pd.read_csv('mdm_log.csv')
        if not df_l.empty:
            last = df_l.iloc[-1]
            st.markdown(f"<p style='text-align: center; font-size: 0.8em; color: green;'>✅ Last Submit: {last['Time']}</p>", unsafe_allow_html=True)
    except: pass

st.divider()

# --- 4. NAVIGATION (App Buttons) ---
# We use a selectbox that looks like a clean app menu
page = st.selectbox("Navigation Menu", ["Teacher Dashboard", "Admin Panel", "📅 Holidays"])

# --- 5. APP PAGES ---

# HOLIDAYS
if page == "📅 Holidays":
    st.subheader("🗓️ School Holidays 2026")
    if holidays_df is not None:
        st.table(holidays_df[['Date', 'Occasion']])

# TEACHER DASHBOARD
elif page == "Teacher Dashboard":
    # Holiday Check
    is_h = False
    if day_name == "Sunday": is_h = True
    elif holidays_df is not None and date_today_str in holidays_df['Date'].values: is_h = True
    
    if is_h:
        st.error("🚫 School is closed today.")
    else:
        name = st.selectbox("Your Name", list({
            "TAPASI RANA": "tr26", "SUJATA BISWAS ROTHA": "sbr26", 
            "ROHINI SINGH": "rs26", "UDAY NARAYAN JANA": "unj26", 
            "BIMAL KUMAR PATRA": "bkp26", "SUSMITA PAUL": "sp26", 
            "TAPAN KUMAR MANDAL": "tkm26", "MANJUMA KHATUN": "mk26"
        }.keys()))
        
        pw = st.text_input("Password", type="password")
        
        # Hardcoded Passwords for speed
        pws = {"TAPASI RANA":"tr26", "SUJATA BISWAS ROTHA":"sbr26", "ROHINI SINGH":"rs26", 
               "UDAY NARAYAN JANA":"unj26", "BIMAL KUMAR PATRA":"bkp26", "SUSMITA PAUL":"sp26", 
               "TAPAN KUMAR MANDAL":"tkm26", "MANJUMA KHATUN":"mk26"}

        if pw == pws.get(name):
            st.success(f"Verified: {name}")
            
            # (Logic for QR Scanning and MDM Table follows here)
            st.subheader("📸 QR Scanner")
            qr = qrcode_scanner(key='qr')
            
            st.divider()
            if st.button("Submit"):
                st.balloons()
                st.success("MDM Report Saved!")
        elif pw != "":
            st.error("Invalid Password")

# ADMIN PANEL
elif page == "Admin Panel":
    st.subheader("🔐 Admin Access")
    admin_pw = st.text_input("Enter Admin Password", type="password")
    if admin_pw == "bpsAPP@2026":
        st.success("Welcome HT")
        # Admin Tabs (Attendance, System)
        t1, t2 = st.tabs(["Staff Attendance", "System"])
        with t1:
            st.write("Mark Teacher Presence")
            if st.button("Save Staff Register"):
                st.success("Register Updated")
    elif admin_pw != "":
        st.error("Access Denied")