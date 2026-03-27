import streamlit as st
import pandas as pd

# ==========================================
# 1. SETUP: DUMMY DATA & SESSION STATE
# ==========================================
# Initialize the main database in Streamlit's memory so it updates in real-time
if 'main_df' not in st.session_state:
    data = {
        'Class': ['PP', 'PP', 'LPP', 'LPP'],
        'Roll': [1, 2, 1, 2],
        'Name': ['MIMMA PARVIN', 'SK AIYUB ALI', 'AMIRA KHATUN', 'RAHUL DAS'],
        'Mobile': ['9999999991', '9999999992', '8888888881', '8888888882'],
        'MDM_Done': [False, False, False, False]
    }
    st.session_state.main_df = pd.DataFrame(data)

# Create a variable to track if attendance was submitted today
if 'attendance_submitted' not in st.session_state:
    st.session_state.attendance_submitted = False

df = st.session_state.main_df

# ==========================================
# 2. THE SMART SCANNER LOGIC
# ==========================================
st.header("MDM Attendance Entry")
st.info("Scanner Ready: Point camera at Student ID")

# SIMULATION: Using a text box to simulate your camera reading the QR code.
# In your real app, this will be your cv2 or streamlit-webrtc variable.
scanned_data = st.text_input("Simulate Camera Scan (Format: NAME, ROLL, MOBILE)", placeholder="e.g., AMIRA KHATUN, 1, 8888888881")

if scanned_data:
    try:
        parts = scanned_data.split(",")
        s_name, s_roll, s_mobile = parts[0].strip(), int(parts[1].strip()), parts[2].strip()
        
        # Find student by Mobile AND Roll
        match = df[(df['Roll'] == s_roll) & (df['Mobile'] == s_mobile)]
        
        if not match.empty:
            s_class = match.iloc[0]['Class']
            widget_key = f"adm_mdm_{s_class}_{s_roll}_{s_name}"
            
            # Update memory and dataframe
            st.session_state[widget_key] = True
            df.loc[(df['Class'] == s_class) & (df['Roll'] == s_roll), 'MDM_Done'] = True
            st.success(f"✅ Scanned successfully: {s_name} ({s_class})")
        else:
            st.error("❌ Student not found.")
    except Exception:
        st.warning("Invalid QR format.")

st.markdown("---")

# ==========================================
# 3. SINGLE PAGE LAYOUT (PP & LPP)
# ==========================================
st.subheader("CLASS PP")
df_pp = df[df['Class'] == 'PP']
for index, row in df_pp.iterrows():
    widget_key = f"adm_mdm_PP_{row['Roll']}_{row['Name']}"
    if widget_key not in st.session_state:
        st.session_state[widget_key] = bool(row['MDM_Done'])
        
    # Checkbox updates the dataframe instantly when manually clicked
    if st.checkbox(f"Roll {row['Roll']}: {row['Name']}", key=widget_key):
        df.loc[(df['Class'] == 'PP') & (df['Roll'] == row['Roll']), 'MDM_Done'] = True
    else:
        df.loc[(df['Class'] == 'PP') & (df['Roll'] == row['Roll']), 'MDM_Done'] = False

st.markdown("---")

st.subheader("CLASS LPP")
df_lpp = df[df['Class'] == 'LPP']
for index, row in df_lpp.iterrows():
    widget_key = f"adm_mdm_LPP_{row['Roll']}_{row['Name']}"
    if widget_key not in st.session_state:
        st.session_state[widget_key] = bool(row['MDM_Done'])
        
    if st.checkbox(f"Roll {row['Roll']}: {row['Name']}", key=widget_key):
        df.loc[(df['Class'] == 'LPP') & (df['Roll'] == row['Roll']), 'MDM_Done'] = True
    else:
        df.loc[(df['Class'] == 'LPP') & (df['Roll'] == row['Roll']), 'MDM_Done'] = False


# ==========================================
# 4. SUBMIT BUTTON
# ==========================================
if st.button("Submit Today's Attendance", type="primary"):
    st.session_state.attendance_submitted = True
    st.success("Attendance officially submitted to Head Teacher!")
    
    # Optional: Here is where you would save to a CSV or Database
    # df.to_csv(f"attendance_{today_date}.csv", index=False)


# ==========================================
# 5. HEAD TEACHER SUMMARY TAB (The "Zero" Feature)
# ==========================================
st.markdown("---")
st.header("Admin / Head Teacher Summary")

if st.session_state.attendance_submitted:
    # Explicitly calculate counts to ensure 0 is shown
    pp_count = len(df[(df['Class'] == 'PP') & (df['MDM_Done'] == True)])
    lpp_count = len(df[(df['Class'] == 'LPP') & (df['MDM_Done'] == True)])
    total_count = pp_count + lpp_count
    
    # Display the metrics beautifully
    col1, col2, col3 = st.columns(3)
    col1.metric("Class PP Present", f"{pp_count} Students")
    col2.metric("Class LPP Present", f"{lpp_count} Students")
    col3.metric("Total Present", f"{total_count} Students")
    
    if total_count == 0:
        st.warning("⚠️ Warning: Attendance was submitted, but ZERO students were marked present across all classes.")
    
    # Show the list of exactly who is present
    st.write("### Detailed List of Present Students")
    present_students = df[df['MDM_Done'] == True][['Class', 'Roll', 'Name']]
    if not present_students.empty:
        st.dataframe(present_students, hide_index=True)
else:
    st.info("Awaiting teacher submission for today.")
