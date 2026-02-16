import streamlit as st
import pandas as pd
from datetime import datetime
import os
import time

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="BPS Digital",
    page_icon="logo.png" if os.path.exists("logo.png") else "🏫",
    layout="centered"
)

# Professional CSS for Branding
st.markdown(
    """
    <style>
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
        [data-testid="stSidebar"] {display: none;}
        .block-container { padding-top: 1rem; max-width: 600px; }
        
        .logo-box {
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
        }
        .bps-subtext {
            font-size: 14px;
            font-weight: 800;
            color: #007bff;
            margin-top: -5px;
            letter-spacing: 1px;
        }
        .school-title {
            font-size: 24px !important;
            font-weight: 900 !important;
            color: #1a1a1a;
            margin: 0;
            line-height: 1.1;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# --- 2. TEACHER LIST ---
TEACHER_CREDS = {
    "TAPASI RANA": {"id": "TR", "pw": "tr26"},
    "SUJATA BISWAS ROTHA": {"id": "SBR", "pw": "sbr26"},
    "ROHINI SINGH": {"id": "RS", "pw": "rs26"},
    "UDAY NARAYAN JANA": {"id": "UNJ", "pw": "unj26"},
    "BIMAL KUMAR PATRA": {"id": "BKP", "pw": "bkp26"},
    "SUSMITA PAUL": {"id": "SP", "pw": "sp26"},
    "TAPAN KUMAR MANDAL": {"id": "TKM", "pw": "tkm26"},
    "MANJUMA KHATUN": {"id": "MK", "pw": "mk26"}
}

# --- 3. THE BRANDED HEADER ---
col_header = st.columns([1, 4])

with col_header[0]:
    st.markdown('<div class="logo-box">', unsafe_allow_html=True)
    if os.path.exists("logo.png"): 
        st.image("logo.png", width=80) 
    else: 
        st.markdown("<h2 style='margin:0;'>🏫</h2>", unsafe_allow_html=True)
    st.markdown('<p class="bps-subtext">BPS Digital</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with col_header[1]:
    st.markdown('<p class="school-title">Bhagyabantapur<br>Primary School</p>', unsafe_allow_html=True)

st.divider()

# --- 4. NAVIGATION ---
page = st.selectbox("CHOOSE ACTION", ["Assistant Teacher MDM Entry", "Admin Panel", "📅 View Holiday List"])

# --- 5. ASSISTANT TEACHER SECTION (FIXED DROPDOWN) ---
if page == "Assistant Teacher MDM Entry":
    st.subheader("🍱 MDM Daily Entry")
    
    # DROPDOWN FOR TEACHER SELECTION
    teacher_name = st.selectbox("Select Your Name (Assistant Teacher)", list(TEACHER_CREDS.keys()))
    
    teacher_pw = st.text_input("Enter Your Password", type="password")

    if teacher_pw == TEACHER_CREDS[teacher_name]["pw"]:
        st.success(f"Verified: {teacher_name}")
        
        selected_class = st.selectbox("Select Class", ["PP", "1", "2", "3", "4", "5"])
        mdm_count = st.number_input("Enter MDM Student Count", min_value=0, max_value=150)
        
        if st.button("Submit MDM Count"):
            date_str = datetime.now().strftime("%d-%m-%Y")
            now_time = datetime.now().strftime("%I:%M %p")
            
            # Save to MDM Log
            log = pd.DataFrame([{"Date": date_str, "Time": now_time, "Class": selected_class, "Count": mdm_count, "Teacher": teacher_name}])
            log.to_csv('mdm_log.csv', mode='a', index=False, header=not os.path.exists('mdm_log.csv'))
            
            st.success("MDM Count submitted successfully!")
            st.balloons()
    elif teacher_pw != "":
        st.error("Incorrect Password. Please try again.")

# --- 6. ADMIN PANEL ---
elif page == "Admin Panel":
    admin_pw = st.text_input("Enter Admin Password", type="password")
    if admin_pw == "bpsAPP@2026":
        st.success("Welcome, Head Teacher.")
        # Summary and Student Attendance logic here
