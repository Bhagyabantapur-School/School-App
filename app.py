import streamlit as st
import pandas as pd
from datetime import datetime
import os

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="BPS Digital",
    page_icon="logo.png" if os.path.exists("logo.png") else "🏫",
    layout="centered"
)

# Professional CSS
st.markdown(
    """
    <style>
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
        [data-testid="stSidebar"] {display: none;}
        .block-container { padding-top: 1rem; max-width: 600px; }
        .bird-box {
            background-color: #ffffff; padding: 15px; border-radius: 12px;
            border: 1px solid #e0e0e0; margin-bottom: 12px;
            box-shadow: 0px 2px 4px rgba(0,0,0,0.05);
        }
        .mdm-badge {
            background-color: #28a745; color: white; padding: 2px 8px;
            border-radius: 10px; font-size: 0.9em; font-weight: bold;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# --- 2. DATA LOADING & STATE ---
date_today_dt = datetime.now()
date_today_str = date_today_dt.strftime("%d-%m-%Y") 
day_name = date_today_dt.strftime('%A')

if 'sub_map' not in st.session_state:
    st.session_state.sub_map = {}

@st.cache_data
def load_data(file):
    if os.path.exists(file):
        try: return pd.read_csv(file, encoding='utf-8-sig')
        except: return pd.read_csv(file)
    return None

routine_df = load_data('routine.csv')
mapping = {"TAPASI RANA":"TR", "SUJATA BISWAS ROTHA":"SBR", "ROHINI SINGH":"RS", "UDAY NARAYAN JANA":"UNJ", "BIMAL KUMAR PATRA":"BKP", "SUSMITA PAUL":"SP", "TAPAN KUMAR MANDAL":"TKM", "MANJUMA KHATUN":"MK"}
rev_mapping = {v: k for k, v in mapping.items()}

# --- 3. HEADER (Logo beside School Name) ---
head_col1, head_col2 = st.columns([1, 4])
with head_col1:
    if os.path.exists("logo.png"): st.image("logo.png", width=70)
with head_col2:
    st.markdown("<h2 style='margin:0; padding-top:10px;'>Bhagyabantapur Primary School</h2>", unsafe_allow_html=True)
st.divider()

# --- 4. NAVIGATION ---
page = st.selectbox("Navigation Menu", ["Teacher Dashboard", "Admin Panel", "📅 View Holiday List"])

# --- 5. ADMIN PANEL ---
if page == "Admin Panel":
    admin_pw = st.text_input("Admin Password", type="password")
    if admin_pw == "bpsAPP@2026":
        tabs = st.tabs(["🦅 Bird's Eye View", "🔄 Substitution Mode", "👨‍🏫 Staff Attendance"])
        
        with tabs[0]:
            st.subheader(f"📍 School Status & MDM - {date_today_str}")
            
            # Load latest MDM log to show counts
            mdm_counts = {}
            if os.path.exists('mdm_log.csv'):
                df_mdm = pd.read_csv('mdm_log.csv')
                # Filter for today only
                today_mdm = df_mdm[df_mdm['Date'] == date_today_str]
                # Get the most recent count for each class
                for _, r in today_mdm.iterrows():
                    mdm_counts[str(r['Class'])] = r['Count']

            if routine_df is not None:
                today_routine = routine_df[routine_df['Day'] == day_name].copy()
                
                if not today_routine.empty:
                    for _, row in today_routine.iterrows():
                        orig_init = row['Teacher']
                        curr_init = st.session_state.sub_map.get(orig_init, orig_init)
                        is_sub = orig_init in st.session_state.sub_map
                        
                        curr_name = rev_mapping.get(curr_init, curr_init)
                        class_id = str(row['Class'])
                        # Get the count if submitted, else 0
                        ate_count = mdm_counts.get(class_id, "Pending")

                        # Bird's Eye Display
                        st.markdown(f"""
                        <div class="bird-box">
                            <span style="float:right;" class="mdm-badge">MDM: {ate_count}</span>
                            <b style="font-size:1.1em; color:#007bff;">Class {class_id}</b><br>
                            👤 <b>Teacher:</b> {curr_name} {"(Substituted)" if is_sub else ""}<br>
                            <small>Subject: {row['Subject']}</small>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("No routine found for today.")