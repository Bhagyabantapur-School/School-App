import streamlit as st
# --- BACK BUTTON ---
if st.button("⬅️ Back to BPS Home", type="secondary"):
    st.switch_page("bps_dashboard.py")
st.write("---") 
# -------------------
import gspread
import pandas as pd
from datetime import datetime

# --- FAILSAFE PAGE CONFIG ---
try:
    st.set_page_config(page_title="BPS Monthly Returns", icon="📈", layout="centered")
except Exception:
    pass

# --- 🛠️ HELPER FUNCTIONS ---
def get_gspread_client():
    """Connects to Google Sheets using Streamlit Secrets."""
    return gspread.service_account_from_dict(st.secrets["gcp_service_account"])

def run_attendance_sync(date_start, date_end):
    """Fetches attendance, filters by range, calculates totals, and writes to BPS_RETURNS."""
    
    if date_start > date_end:
        st.error("Error: Start date cannot be after the end date.")
        return

    try:
        client = get_gspread_client()
        
        # 2. Access Source: BPS_Database -> student_attendance_master
        master_sh = client.open("BPS_Database")
        attendance_wks = master_sh.worksheet("student_attendance_master")
        raw_data = attendance_wks.get_all_records()
        
        if not raw_data:
            st.warning("No data found in student_attendance_master.")
            return

        df = pd.DataFrame(raw_data)

        # 3. Handle Date Formatting & Filtering
        df['data_date_obj'] = pd.to_datetime(df['Date'], format='%d-%m-%Y').dt.date
        
        mask = (df['data_date_obj'] >= date_start) & (df['data_date_obj'] <= date_end)
        filtered_df = df.loc[mask].copy()

        if filtered_df.empty:
            start_str = date_start.strftime("%d.%m.%y")
            end_str = date_end.strftime("%d.%m.%y")
            st.warning(f"No records found in BPS_Database for the period {start_str} to {end_str}.")
            return

        # 4. Filter for Present Students
        present_df = filtered_df[filtered_df['Status'].astype(str).str.upper() == 'TRUE'].copy()

        # 5. Pivot Data
        report = present_df.groupby(['Date', 'Class']).size().unstack(fill_value=0).reset_index()

        # 6. Final Date & Day Formatting
        report['dt_obj'] = pd.to_datetime(report['Date'], format='%d-%m-%Y')
        report = report.sort_values('dt_obj') 
        
        report['Formatted_Date'] = report['dt_obj'].dt.strftime('%d.%m.%y')
        report['Formatted_Day'] = report['dt_obj'].dt.strftime('%a').str.upper()

        # 7. Ensure all Class columns exist
        target_classes = ['CLASS PP', 'CLASS I', 'CLASS II', 'CLASS III', 'CLASS IV', 'CLASS V']
        for cls in target_classes:
            if cls not in report.columns:
                report[cls] = 0

        # 8. Apply Returns Logic
        report['PP_Final'] = report['CLASS PP'] 
        report['I-IV_Sum'] = report['CLASS I'] + report['CLASS II'] + report['CLASS III'] + report['CLASS IV']
        report['I-V_Sum'] = report['I-IV_Sum'] + report['CLASS V']
        report['GT_Sum'] = report['PP_Final'] + report['I-V_Sum']

        # 9. Prepare Final DataFrame
        final_df = report[[
            'Formatted_Date', 'Formatted_Day', 'PP_Final', 
            'CLASS I', 'CLASS II', 'CLASS III', 'CLASS IV', 'I-IV_Sum', 
            'CLASS V', 'I-V_Sum', 'GT_Sum'
        ]].rename(columns={
            'Formatted_Date': 'Date',
            'Formatted_Day': 'Day',
            'PP_Final': 'PP',
            'CLASS I': 'I',
            'CLASS II': 'II',
            'CLASS III': 'III',
            'CLASS IV': 'IV',
            'I-IV_Sum': 'I-IV',
            'CLASS V': 'V',
            'I-V_Sum': 'I-V',
            'GT_Sum': 'GT'
        })

        # 10. Write to Destination
        returns_sh = client.open("BPS_RETURNS")
        rough_wks = returns_sh.worksheet("ROUGH01")
        
        rough_wks.clear()
        rough_wks.update([final_df.columns.values.tolist()] + final_df.values.tolist())
        
        st.success("✅ Success! BPS_RETURNS (ROUGH01) has been updated for the selected period.")
        st.balloons()
        
        # --- NEW HIGHLIGHT LOGIC ---
        st.write("### Preview of Synced Data")
        
        # Apply a light background color to specific columns
        styled_df = final_df.style.set_properties(
            **{'background-color': '#f0f8ff'}, # You can change this hex code if you want a different color
            subset=['PP', 'I-IV', 'V']
        )
        
        # Display the styled dataframe
        st.dataframe(styled_df, use_container_width=True)
        # ---------------------------

    except gspread.exceptions.SpreadsheetNotFound:
        st.error("Could not find 'BPS_RETURNS'. Make sure you created it and shared it with the service account email.")
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")

# --- 🏫 STREAMLIT UI ---

# 1. School Header
col1, col2 = st.columns([1, 4]) 

with col1:
    try:
        st.image("logo.png", width=100) 
    except FileNotFoundError:
        st.warning("logo.png not found.")

with col2:
    st.markdown("""
    <div style="text-align: right; padding-top: 15px;">
        <h1 style="margin: 0;">BHAGYABANTAPUR PRIMARY SCHOOL</h1>
        <h3 style="margin: 0; color: gray;">(BPS DIGITAL)</h3>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# 2. Main Controls
st.subheader("1. Select Reporting Period")
st.info("Choose the date range for which you want to generate the Rough Returns.")

today = datetime.now().date()
first_day_current_month = today.replace(day=1)

selected_dates = st.date_input(
    "Select date range for returns",
    value=(first_day_current_month, today),
    help="Select start and end date."
)

st.write("---")
st.subheader("2. Sync to BPS_RETURNS")

date_start = None
date_end = None

if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
    date_start, date_end = selected_dates
    start_str = date_start.strftime("%d.%m.%y")
    end_str = date_end.strftime("%d.%m.%y")
    
    st.success(f"Ready to process data from **{start_str}** to **{end_str}**.")
    
    if st.button("🚀 Process & Sync Monthly Returns"):
        with st.spinner(f"Connecting to database and calculating totals for {start_str} to {end_str}..."):
            run_attendance_sync(date_start, date_end)
else:
    st.warning("⚠️ Please select both a start and an end date to enable syncing.")
    st.button("🚀 Process & Sync Monthly Returns", disabled=True)

st.divider()
st.caption("Developed for Bhagyabantapur Primary School Management System")
