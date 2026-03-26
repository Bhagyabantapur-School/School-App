import streamlit as st
import gspread
import pandas as pd
from datetime import datetime

def get_gspread_client():
    return gspread.service_account_from_dict(st.secrets["gcp_service_account"])

def run_attendance_sync():
    client = get_gspread_client()
    
    # 1. Access Source: BPS_Database
    master_sh = client.open("BPS_Database")
    attendance_wks = master_sh.worksheet("student_attendance_master")
    df = pd.DataFrame(attendance_wks.get_all_records())

    # 2. Filter for Present Students
    present_df = df[df['Status'].astype(str).str.upper() == 'TRUE'].copy()

    # 3. Create Pivot Table (Counts by Date & Class)
    report = present_df.groupby(['Date', 'Class']).size().unstack(fill_value=0).reset_index()

    # 4. Apply Date Formatting (DD.MM.YY) and Day Formatting (MON, TUE)
    # Convert string 'DD-MM-YYYY' to datetime objects
    report['dt_obj'] = pd.to_datetime(report['Date'], format='%d-%m-%Y')
    
    # Format the columns as requested
    report['Date'] = report['dt_obj'].dt.strftime('%d.%m.%y')
    report['Day'] = report['dt_obj'].dt.strftime('%a').str.upper()

    # 5. Calculation Logic
    # Ensure all required class columns exist in the dataframe to avoid KeyErrors
    classes = ['CLASS PP', 'CLASS I', 'CLASS II', 'CLASS III', 'CLASS IV', 'CLASS V']
    for cls in classes:
        if cls not in report.columns:
            report[cls] = 0

    # PP Rule: Only count CLASS PP (ignore LPP)
    report['PP_Col'] = report['CLASS PP']
    
    # Totals
    report['I-IV'] = report['CLASS I'] + report['CLASS II'] + report['CLASS III'] + report['CLASS IV']
    report['I-V'] = report['I-IV'] + report['CLASS V']
    report['GT'] = report['PP_Col'] + report['I-V']

    # 6. Map to BPS_RETURNS Headers: Date, Day, PP, I, II, III, IV, I-IV, V, I-V, GT
    final_df = report[[
        'Date', 'Day', 'PP_Col', 'CLASS I', 'CLASS II', 'CLASS III', 'CLASS IV', 
        'I-IV', 'CLASS V', 'I-V', 'GT'
    ]].rename(columns={
        'PP_Col': 'PP', 'CLASS I': 'I', 'CLASS II': 'II', 
        'CLASS III': 'III', 'CLASS IV': 'IV', 'CLASS V': 'V'
    })

    # 7. Write to BPS_RETURNS -> ROUGH01
    try:
        returns_sh = client.open("BPS_RETURNS")
        rough_wks = returns_sh.worksheet("ROUGH01")
        
        # Overwrite with clean data
        rough_wks.clear()
        rough_wks.update([final_df.columns.values.tolist()] + final_df.values.tolist())
        st.success("BPS_RETURNS: ROUGH01 has been updated with the new formats.")
    except Exception as e:
        st.error(f"Spreadsheet Error: {e}")

# Streamlit Interface
st.set_page_config(page_title="BPS Returns Sync", icon="📈")
st.title("📈 Monthly Attendance Returns")

if st.button("Generate ROUGH01 Report"):
    with st.spinner("Calculating and formatting data..."):
        run_attendance_sync()