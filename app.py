import streamlit as st
import pandas as pd
from datetime import datetime
import os
import time
import random
from streamlit_qrcode_scanner import qrcode_scanner

# --- 1. PWA & MOBILE APP CONFIGURATION ---
st.set_page_config(
    page_title="BPS Digital",
    page_icon="logo.png" if os.path.exists("logo.png") else "🏫",
    layout="centered"
)

# Advanced CSS: App-like Styling
st.markdown(
    """
    <style>
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
        [data-testid="stSidebar"] {display: none;}
        .block-container { padding-top: 1.5rem; max-width: 500px; }
        .stButton>button {
            width: 100%; border-radius: 12px; height: 3.5em;
            background-color: #007bff; color: white; font-weight: bold; border: none;
        }
        .notice-box {
            background-color: #fff3cd; padding: 15px; border-radius: 10px;
            border: 1px solid #ffeeba; color: #856404; margin-bottom: 20px; text-align: center;
        }
        .feedback-card {
            background-color: #f8f9fa; padding: 10px; border-radius: 8px;
            border: 1px solid #dee2e6; margin-bottom: 10px;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# --- 2. DATA HANDLERS ---
date_today_dt = datetime.now()
date_today_str = date_today_dt.strftime("%d-%m-%Y") 

def handle_notice(action="get", text=""):
    filename = "notice.txt"
    if action == "save":
        with open(filename, "w", encoding="utf-8") as f: f.write(text)
    elif action == "get":
        return open(filename, "r", encoding="utf-8").read() if os.path.exists(filename) else "Welcome to BPS Digital."

@st.cache_data
def load_data(file):
    if os.path.exists(file):
        try: return pd.read_csv(file, encoding='utf-8-sig')
        except: return pd.read_csv(file)
    return None

students_df = load_data('students.csv')
routine_df = load_data('routine.csv')

# --- 3. HEADER ---
col1, col2, col3 = st.columns([1, 3, 1])
with col2:
    if os.path.exists("logo.png"): st.image("logo.png", use_container_width=True)
    else: st.markdown("<h2 style='text-align: center;'>🏫 Bhagyabantapur PS</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center; color: gray;'>{date_today_str}</p>", unsafe_allow_html=True)

st.divider()
page = st.selectbox("Menu", ["Teacher Dashboard", "Admin Panel", "📅 Holidays"])

# --- 4. TEACHER DASHBOARD ---
if page == "Teacher Dashboard":
    st.markdown(f"<div class='notice-box'>📢 {handle_notice('get')}</div>", unsafe_allow_html=True)
    
    t_pws = {"TAPASI RANA": "tr26", "SUJATA BISWAS ROTHA": "sbr26", "ROHINI SINGH": "rs26", "UDAY NARAYAN JANA": "unj26", "BIMAL KUMAR PATRA": "bkp26", "SUSMITA PAUL": "sp26", "TAPAN KUMAR MANDAL": "tkm26", "MANJUMA KHATUN": "mk26"}
    name = st.selectbox("Select Name", list(t_pws.keys()))
    pw = st.text_input("Password", type="password")

    if pw == t_pws.get(name):
        st.success(f"Hello, {name}")
        # MDM Logic (Scanner/Table) here...
        
        with st.expander("📝 Send Feedback to Head Teacher"):
            msg = st.text_area("Write your message or suggestion:")
            if st.button("Send Message"):
                f_data = pd.DataFrame([{"Date": date_today_str, "From": name, "Message": msg}])
                f_data.to_csv('feedback.csv', mode='a', index=False, header=not os.path.exists('feedback.csv'))
                st.success("Message sent to HT!")

# --- 5. ADMIN PANEL ---
elif page == "Admin Panel":
    admin_pw = st.text_input("Admin Password", type="password")
    if admin_pw == "bpsAPP@2026":
        tabs = st.tabs(["📢 Notice", "✉️ Teacher Inbox", "📊 Reports"])
        
        with tabs[0]:
            new_notice = st.text_area("Update School Notice:", handle_notice("get"))
            if st.button("Update Notice"):
                handle_notice("save", new_notice)
                st.success("Notice Updated!")
                
        with tabs[1]:
            st.subheader("Messages from Teachers")
            if os.path.exists('feedback.csv'):
                fb_df = pd.read_csv('feedback.csv').iloc[::-1] # Newest first
                for _, row in fb_df.iterrows():
                    st.markdown(f"<div class='feedback-card'><b>{row['From']}</b> ({row['Date']})<br>{row['Message']}</div>", unsafe_allow_html=True)
            else:
                st.info("No messages in the inbox.")