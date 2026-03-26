import streamlit as st
import gspread
import pandas as pd
from datetime import datetime

# 1. MUST BE THE FIRST STREAMLIT COMMAND
st.set_page_config(page_title="BPS Returns Sync", icon="📈", layout="centered")

# --- DATABASE LOGIC ---
def get_gspread_client():
    """Connects to Google Sheets using Streamlit Secrets."""
    return gspread.service_account_from_dict(st.secrets["gcp_service_account"])

def run_attendance_sync():
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

        # 3. Filter for Present Students
        present_df = df[df['Status'].astype(str).str.upper() == 'TRUE'].copy()

        if present_df.empty:
            st.warning("No 'Present' records found to process.")
            return

        # 4. Pivot Data (Count students by Date and Class)
        report = present_df.groupby(['Date', 'Class']).size().unstack(fill_value=0).reset_index()

        # 5. Date & Day Formatting (DD.MM.YY and MON, TUE...)
        report['dt_obj'] = pd.to_datetime(report['Date'], format='%d-%m-%Y')
        report = report.sort_values('dt_obj') # Keep chronological order
        
        report['Formatted_Date'] = report['dt_obj'].dt.strftime('%d.%m.%y')
        report['Formatted_Day'] = report['dt_obj'].dt.strftime('%a').str.upper()

        # 6. Ensure all Class columns exist to prevent errors
        target_classes = ['CLASS PP', 'CLASS I', 'CLASS II', 'CLASS III', 'CLASS IV', 'CLASS V']
        for cls in target_classes:
            if cls not in report.columns:
                report[cls] = 0

        # 7. Apply BPS Returns Logic
        report['PP_Final'] = report['CLASS PP'] # Only CLASS PP, ignore LPP
        report['I-IV_Sum'] = report['CLASS I'] + report['CLASS II'] + report['CLASS III'] + report['CLASS IV']
        report['I-V_Sum'] = report['I-IV_Sum'] + report['CLASS V']
        report['GT_Sum'] = report['PP_Final'] + report['I-V_Sum']

        # 8. Prepare Final DataFrame for "ROUGH01"
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

        # 9. Write to Destination: BPS_RETURNS -> ROUGH01
        returns_sh = client.open("BPS_RETURNS")
        rough_wks = returns_sh.worksheet("ROUGH01")
        
        # Clear and Update
        rough_wks.clear()
        rough_wks.update([final_df.columns.values.tolist()] + final_df.values.tolist())
        
        st.success("✅ Success! BPS_RETURNS (ROUGH01) has been updated.")
        st.balloons()
        
        # Show a preview in the app
        st.write("### Preview of Synced Data")
        st.dataframe(final_df, use_container_width=True)

    except gspread.exceptions.SpreadsheetNotFound:
        st.error("Could not find 'BPS_RETURNS'. Make sure you created it and shared it with the service account email.")
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")

# --- STREAMLIT UI ---
st.title("📊 BPS Returns Generator")
st.info("This app pulls attendance from BPS_Database and formats it for the BPS_RETURNS sheet.")

if st.button("🚀 Process & Sync Monthly Returns"):
    with st.spinner("Connecting to Google Sheets and calculating totals..."):
        run_attendance_sync()

st.divider()
st.caption("Developed for Bhagyabantapur Primary School Management System")
