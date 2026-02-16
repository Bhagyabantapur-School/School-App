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

# Professional CSS for Specific Branding Layout
st.markdown(
    """
    <style>
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
        [data-testid="stSidebar"] {display: none;}
        .block-container { padding-top: 1rem; max-width: 600px; }
        
        /* HEADER LAYOUT */
        .header-wrapper {
            display: flex;
            align-items: center;
            justify-content: flex-start;
            gap: 20px;
        }
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
            font-size: 26px !important;
            font-weight: 900 !important;
            color: #1a1a1a;
            margin: 0;
            line-height: 1.1;
        }

        /* SUMMARY CARD */
        .summary-card {
            background-color: #ffffff;
            border: 2px solid #007bff;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0px 4px 10px rgba(0,0,0,0.05);
        }
        .summary-row {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #f0f2f6;
            font-size: 18px;
        }
        .summary-val { color: #007bff; font-weight: 900; font-size: 22px; }
        .grand-total-box {
            margin-top: 15px;
            background-color: #d4edda;
            padding: 10px;
            border-radius: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .grand-total-num { font-size: 30px; font-weight: 900; color: #155724; }
    </style>
    """,
    unsafe_allow_html=True
)

# --- 2. THE BRANDED HEADER ---
# This creates the Side-by-Side Logo/Name and Subtext under Logo
col_header = st.columns([1, 4])

with col_header[0]:
    # Logo and BPS Digital Subtext
    st.markdown('<div class="logo-box">', unsafe_allow_html=True)
    if os.path.exists("logo.png"): 
        st.image("logo.png", width=80) # Decreased size to 80px
    else: 
        st.markdown("<h2 style='margin:0;'>🏫</h2>", unsafe_allow_html=True)
    st.markdown('<p class="bps-subtext">BPS Digital</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with col_header[1]:
    # School Name beside the logo
    st.markdown('<p class="school-title">Bhagyabantapur<br>Primary School</p>', unsafe_allow_html=True)

# Date and Day
date_str = datetime.now().strftime("%d-%m-%Y") 
day_str = datetime.now().strftime('%A')
st.markdown(f"<p style='text-align: right; color: #666; font-weight:bold;'>{date_str} | {day_str}</p>", unsafe_allow_html=True)
st.divider()

# --- 3. NAVIGATION & LOGIC ---
page = st.selectbox("CHOOSE ACTION", ["Teacher MDM Entry", "Admin (Attendance & HT Tools)", "📅 View Holiday List"])

# (Admin Summary logic remains optimized for PP, I-IV, and V grouping)
if page == "Admin (Attendance & HT Tools)":
    admin_pw = st.text_input("Master Password", type="password")
    if admin_pw == "bpsAPP@2026":
        tabs = st.tabs(["📊 Summary", "🖋️ Students", "👨‍🏫 Staff"])
        with tabs[0]:
            if os.path.exists('student_attendance_master.csv'):
                df = pd.read_csv('student_attendance_master.csv')
                today = df[df['Date'] == date_str]
                if not today.empty:
                    pp = today[today['Class'].astype(str).str.upper() == 'PP']['Present'].sum()
                    i_iv = today[today['Class'].astype(str).isin(['1', '2', '3', '4'])]['Present'].sum()
                    v = today[today['Class'].astype(str) == '5']['Present'].sum()
                    
                    st.markdown(f"""
                    <div class="summary-card">
                        <div class="summary-row"><span>Class PP</span><span class="summary-val">{pp}</span></div>
                        <div class="summary-row"><span>Class I - IV</span><span class="summary-val">{i_iv}</span></div>
                        <div class="summary-row"><span>Class V</span><span class="summary-val">{v}</span></div>
                        <div class="grand-total-box">
                            <span style="font-weight:900;">GRAND TOTAL</span>
                            <span class="grand-total-num">{pp + i_iv + v}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
