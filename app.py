import streamlit as st
import pandas as pd
from datetime import datetime
import os

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="BPS Digital", page_icon="logo.png", layout="centered")

st.markdown(
    """
    <style>
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
        [data-testid="stSidebar"] {display: none;}
        .block-container { padding-top: 1rem; max-width: 600px; }
        .summary-card {
            background-color: #f8f9fa;
            border: 1px solid #007bff;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
        }
        .summary-val { color: #007bff; font-weight: bold; font-size: 1.2em; }
    </style>
    """,
    unsafe_allow_html=True
)

# --- 2. DATA LOADING ---
date_today_str = datetime.now().strftime("%d-%m-%Y") 

@st.cache_data
def load_data(file):
    if os.path.exists(file):
        try: return pd.read_csv(file, encoding='utf-8-sig')
        except: return pd.read_csv(file)
    return None

students_df = load_data('students.csv')

# --- 3. ADMIN PANEL (HT TOOLS) ---
# (Assuming current navigation logic is active)
# Inside the Admin Panel -> Student Attendance Tab

st.subheader("📊 Attendance Summary")

if os.path.exists('student_attendance_master.csv'):
    att_df = pd.read_csv('student_attendance_master.csv')
    
    # Filter for today's records
    today_data = att_df[att_df['Date'] == date_today_str]
    
    if not today_data.empty:
        # 1. Class PP (Pre-Primary)
        pp_total = today_data[today_data['Class'].astype(str).str.upper() == 'PP']['Present'].sum()
        
        # 2. Class I - IV
        classes_1_4 = ['1', '2', '3', '4']
        i_iv_total = today_data[today_data['Class'].astype(str).isin(classes_1_4)]['Present'].sum()
        
        # 3. Class V
        v_total = today_data[today_data['Class'].astype(str) == '5']['Present'].sum()
        
        # 4. Grand Total
        grand_total = pp_total + i_iv_total + v_total

        # Display Summary Cards
        st.markdown(f"""
        <div class="summary-card">
            <table style="width:100%">
                <tr>
                    <td><b>Class PP Total:</b></td>
                    <td class="summary-val">{pp_total}</td>
                </tr>
                <tr>
                    <td><b>Class I - IV Total:</b></td>
                    <td class="summary-val">{i_iv_total}</td>
                </tr>
                <tr>
                    <td><b>Class V Total:</b></td>
                    <td class="summary-val">{v_total}</td>
                </tr>
                <tr style="border-top: 2px solid #007bff;">
                    <td><br><b>TOTAL SCHOOL ATTENDANCE:</b></td>
                    <td><br><span style="font-size:1.5em; color:green;">{grand_total}</span></td>
                </tr>
            </table>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("No attendance records found for today yet.")
else:
    st.warning("Attendance master file not created yet.")

# --- 4. ATTENDANCE ENTRY TABLE ---
st.divider()
st.subheader("🖋️ Mark New Attendance")
# (Existing attendance marking logic here)