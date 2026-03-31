import streamlit as st
import pandas as pd
from datetime import datetime

# Format the date to Day, DD.MM.YY (e.g., FRI, 27.03.26)
today_date = datetime.now().strftime("%a, %d.%m.%y").upper()

st.set_page_config(page_title="MDM Attendance", layout="centered")

# ==========================================
# 1. SETUP: DATABASE & SESSION STATE
# ==========================================
if 'main_df' not in st.session_state:
    # Initializing the active list of students
    data = {
        'Class': ['PP', 'PP', 'LPP', 'LPP'],
        'Roll': [1, 2, 1, 2],
        'Name': ['MIMMA PARVIN', 'SK AIYUB ALI', 'AMIRA KHATUN', 'RAHUL DAS'],
        'Mobile': ['9999999991', '9999999992', '8888888881', '8888888882'],
        'MDM_Done': [False, False, False, False]
    }
    st.session_state.main_df = pd.DataFrame(data)

# Flag to track if the teacher has clicked submit
if 'attendance_submitted' not in st.session_state:
    st.session_state.attendance_submitted = False

df = st.session_state.main_df

st.title("Bhagyabantapur Primary School")
st.markdown(f"**Date:** {today_date}")

# Create tabs to easily switch between Teacher and Admin views
tab_teacher, tab_admin = st.tabs(["Teacher Entry", "Head Teacher Summary"])

# ==========================================
# 2. TEACHER ENTRY TAB
# ==========================================
with tab_teacher:
    st.header("MDM Attendance Entry")
    
    # --- SMART SCANNER ---
    st.info("Scanner Ready: Point camera at Student ID")
    # Simulating the camera feed for testing purposes
    scanned_data = st.text_input("Simulate Camera Scan (Format: NAME, ROLL, MOBILE)", placeholder="e.g., AMIRA KHATUN, 1, 8888888881")

    if scanned_data:
        try:
            parts = scanned_data.split(",")
            if len(parts) == 3:
                s_name = parts[0].strip()
                s_roll = int(parts[1].strip())
                s_mobile = parts[2].strip()
                
                # Filter by both Roll and Mobile to guarantee uniqueness
                match = df[(df['Roll'] == s_roll) & (df['Mobile'] == s_mobile)]
                
                if not match.empty:
                    s_class = match.iloc[0]['Class']
                    widget_key = f"adm_mdm_{s_class}_{s_roll}_{s_name}"
                    
                    st.session_state[widget_key] = True
                    df.loc[(df['Class'] == s_class) & (df['Roll'] == s_roll), 'MDM_Done'] = True
                    st.success(f"✅ Scanned successfully: {s_name} ({s_class})")
                else:
                    st.error("❌ Student not found.")
        except Exception:
            st.warning("Invalid QR format. Please ensure the card prints correctly.")

    st.markdown("---")

    # --- CLASS PP SECTION ---
    st.subheader("CLASS PP")
    df_pp = df[df['Class'] == 'PP']
    for index, row in df_pp.iterrows():
        widget_key = f"adm_mdm_PP_{row['Roll']}_{row['Name']}"
        
        if widget_key not in st.session_state:
            st.session_state[widget_key] = bool(row['MDM_Done'])
            
        # UI Checkbox (Value param removed to fix Streamlit warning)
        if st.checkbox(f"Roll {row['Roll']}: {row['Name']}", key=widget_key):
            df.loc[(df['Class'] == 'PP') & (df['Roll'] == row['Roll']), 'MDM_Done'] = True
        else:
            df.loc[(df['Class'] == 'PP') & (df['Roll'] == row['Roll']), 'MDM_Done'] = False

    st.markdown("---")

    # --- CLASS LPP SECTION ---
    st.subheader("CLASS LPP")
    df_lpp = df[df['Class'] == 'LPP']
    for index, row in df_lpp.iterrows():
        widget_key = f"adm_mdm_LPP_{row['Roll']}_{row['Name']}"
        
        if widget_key not in st.session_state:
            st.session_state[widget_key] = bool(row['MDM_Done'])
            
        # UI Checkbox
        if st.checkbox(f"Roll {row['Roll']}: {row['Name']}", key=widget_key):
            df.loc[(df['Class'] == 'LPP') & (df['Roll'] == row['Roll']), 'MDM_Done'] = True
        else:
            df.loc[(df['Class'] == 'LPP') & (df['Roll'] == row['Roll']), 'MDM_Done'] = False

    # --- SUBMIT BUTTON ---
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Submit Today's Attendance", type="primary"):
        st.session_state.attendance_submitted = True
        st.success("Attendance officially submitted to the Head Teacher!")


# ==========================================
# 3. HEAD TEACHER SUMMARY TAB
# ==========================================
with tab_admin:
    st.header("MDM Entry Summary")
    st.markdown(f"**Report Date:** {today_date}")

    col1, col2, col3 = st.columns(3)

    if st.session_state.attendance_submitted:
        # Calculate exactly who is marked True
        pp_count = len(df[(df['Class'] == 'PP') & (df['MDM_Done'] == True)])
        lpp_count = len(df[(df['Class'] == 'LPP') & (df['MDM_Done'] == True)])
        
        # Applying the summation rule: total reflects PP only
        summed_total = pp_count 
        
        col1.metric("Class PP Present", f"{pp_count} Students")
        col2.metric("Class LPP Present", f"{lpp_count} Students")
        col3.metric("Total (PP Only)", f"{summed_total} Students")
        
        # The true zero logic
        if pp_count == 0 and lpp_count == 0:
            st.warning("⚠️ Attendance was officially submitted, but 0 students were marked present today.")
        else:
            st.write("### Detailed List of Present Students")
            present_students = df[df['MDM_Done'] == True][['Class', 'Roll', 'Name']]
            st.dataframe(present_students, hide_index=True)
            
    else:
        # Before submission, display pending status
        col1.metric("Class PP Present", "-- Pending --")
        col2.metric("Class LPP Present", "-- Pending --")
        col3.metric("Total (PP Only)", "-- Pending --")
        
        st.info("Waiting for the class teacher to submit today's attendance.")
