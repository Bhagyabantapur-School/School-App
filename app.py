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

# Professional CSS for Institutional Branding
st.markdown(
    """
    <style>
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
        [data-testid="stSidebar"] {display: none;}
        .block-container { padding-top: 1rem; max-width: 600px; }
        
        /* EXTRA BOLD SCHOOL NAME */
        .school-title {
            font-size: 32px !important;
            font-weight: 900 !important;
            color: #1a1a1a;
            margin: 0;
            line-height: 1.1;
            text-transform: uppercase;
        }

        /* ENHANCED SUMMARY CARD */
        .summary-card {
            background-color: #ffffff;
            border: 3px solid #007bff;
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 25px;
            box-shadow: 0px 10px 20px rgba(0,0,0,0.1);
        }
        .summary-row {
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 2px solid #f0f2f6;
            font-size: 20px;
        }
        .summary-val { 
            color: #007bff; 
            font-weight: 900; 
            font-size: 26px; 
        }
        .grand-total-box {
            margin-top: 20px;
            background-color: #d4edda;
            border: 2px solid #28a745;
            padding: 15px;
            border-radius: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .grand-total-label { font-size: 26px; font-weight: 900; color: #155724; }
        .grand-total-num { font-size: 38px; font-weight: 900; color: #155724; }
        
        /* BIG BUTTONS */
        .stButton>button {
            width: 100%; border-radius: 15px; height: 4.5em;
            background-color: #007bff; color: white; font-weight: 900; font-size: 20px;
            border: none; box-shadow: 0px 4px 6px rgba(0,0,0,0.2);
        }
    </style>
    """,
    unsafe_allow_html=True
)

# --- 2. HEADER (Large Logo beside Extra Bold Name) ---
head_col1, head_col2 = st.columns([1, 3])
with head_col1:
    if os.path.exists("logo.png"): 
        st.image("logo.png", width=120) # Significantly bigger logo
    else: 
        st.markdown("<h1 style='font-size:60px; margin:0;'>🏫</h1>", unsafe_allow_html=True)
with head_col2:
    st.markdown('<p class="school-title">Bhagyabantapur Primary School</p>', unsafe_allow_html=True)

# Date Display
date_today_str = datetime.now().strftime("%d-%m-%Y") 
day_name = datetime.now().strftime('%A')
st.markdown(f"<p style='text-align: center; color: #555; font-size: 18px; font-weight:bold; margin-top:5px;'>{date_today_str} | {day_name}</p>", unsafe_allow_html=True)
st.divider()

# --- 3. NAVIGATION ---
page = st.selectbox("CHOOSE ACTION", ["Teacher MDM Entry", "Admin (Attendance & HT Tools)", "📅 View Holiday List"])

# (The rest of the logic remains the same to maintain stability)

# --- 4. ADMIN PANEL (Summary Logic) ---
if page == "Admin (Attendance & HT Tools)":
    admin_pw = st.text_input("Master Password", type="password")
    if admin_pw == "bpsAPP@2026":
        tabs = st.tabs(["📊 Attendance Summary", "🖋️ Mark Attendance", "👨‍🏫 Staff Records"])
        
        with tabs[0]:
            if os.path.exists('student_attendance_master.csv'):
                att_master = pd.read_csv('student_attendance_master.csv')
                today_att = att_master[att_master['Date'] == date_today_str]
                
                if not today_att.empty:
                    pp_t = today_att[today_att['Class'].astype(str).str.upper() == 'PP']['Present'].sum()
                    i_iv_t = today_att[today_att['Class'].astype(str).isin(['1', '2', '3', '4'])]['Present'].sum()
                    v_t = today_att[today_att['Class'].astype(str) == '5']['Present'].sum()
                    
                    st.markdown(f"""
                    <div class="summary-card">
                        <div class="summary-row"><span>Class PP Total</span><span class="summary-val">{pp_t}</span></div>
                        <div class="summary-row"><span>Class I - IV Total</span><span class="summary-val">{i_iv_t}</span></div>
                        <div class="summary-row"><span>Class V Total</span><span class="summary-val">{v_t}</span></div>
                        <div class="grand-total-box">
                            <span class="grand-total-label">GRAND TOTAL</span>
                            <span class="grand-total-num">{pp_t + i_iv_t + v_t}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else: 
                    st.info("No records for today yet.")
            else: 
                st.info("Mark attendance to see summary.")

        # Mark Attendance Tab
        with tabs[1]:
            st.subheader("🖋️ Student Attendance")
            c_target = st.selectbox("Select Class", ["PP", "1", "2", "3", "4", "5"])
            # (Roster Logic...)