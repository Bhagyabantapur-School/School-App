import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
import pytz
import plotly.express as px

st.set_page_config(page_title="BPS Exam Fee Collector", layout="wide")

# Set timezone to IST for accurate logging
IST = pytz.timezone('Asia/Kolkata')

st.title("💰 BPS Exam Fee Collection")

# --- AUTHENTICATION & CONNECTION ---
@st.cache_resource
def get_gspread_client():
    # Authenticate using the dictionary from Streamlit secrets
    credentials_dict = dict(st.secrets["gcp_service_account"])
    gc = gspread.service_account_from_dict(credentials_dict)
    return gc

gc = get_gspread_client()

# --- DATA LOADING ---
@st.cache_data(ttl=600)
def load_data():
    # Open the BPS Database
    bps_sheet = gc.open_by_url(st.secrets["sheet_urls"]["bps_database"])
    
    # Get worksheets
    ws_students = bps_sheet.worksheet("students_master")
    ws_teachers = bps_sheet.worksheet("TEACHERS_DETAIL")
    
    # Convert to Pandas DataFrames for easy filtering in Streamlit
    df_students = pd.DataFrame(ws_students.get_all_records())
    df_teachers = pd.DataFrame(ws_teachers.get_all_records())
    
    # Open Fees log for dashboard
    fees_sheet = gc.open_by_url(st.secrets["sheet_urls"]["sch_exam_fees"])
    ws_fees = fees_sheet.worksheet("Sheet1") # Ensure your tab is named Sheet1 or update this
    df_fees = pd.DataFrame(ws_fees.get_all_records())
    
    return df_students, df_teachers, df_fees

try:
    df_students, df_teachers, df_fees = load_data()
except Exception as e:
    st.error(f"Error loading data from Google Sheets: {e}")
    st.stop()

# --- APP LAYOUT ---
tab1, tab2 = st.tabs(["📝 Collect Fees", "📊 Fee Dashboard"])

with tab1:
    st.subheader("Record New Payment")
    
    with st.form("fee_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Ensure we don't have empty options
            classes = [c for c in df_students['Class'].unique() if str(c).strip()]
            selected_class = st.selectbox("Select Class", options=sorted(classes))
            
        with col2:
            sections = [s for s in df_students[df_students['Class'] == selected_class]['Section'].unique() if str(s).strip()]
            selected_section = st.selectbox("Select Section", options=sorted(sections))
            
        with col3:
            filtered_students = df_students[
                (df_students['Class'] == selected_class) & 
                (df_students['Section'] == selected_section)
            ]
            student_names = [n for n in filtered_students['Name'].unique() if str(n).strip()]
            selected_student = st.selectbox("Select Student", options=sorted(student_names))
        
        col4, col5 = st.columns(2)
        with col4:
            amount = st.number_input("Payment Amount (₹)", min_value=0, step=5)
            
        with col5:
            payer_type = st.radio("Received From:", ["Student", "Guardian", "Teacher"], horizontal=True)
        
        received_by_teacher = "N/A"
        if payer_type == "Teacher":
            teacher_names = [t for t in df_teachers['Name'].unique() if str(t).strip()]
            received_by_teacher = st.selectbox("Which Teacher?", options=sorted(teacher_names))

        submit_button = st.form_submit_button("Record Payment")

    # --- DATA SUBMISSION ---
    if submit_button:
        if not selected_student:
            st.error("Please select a valid student.")
        else:
            with st.spinner("Recording payment..."):
                current_time_ist = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
                student_info = filtered_students[filtered_students['Name'] == selected_student].iloc[0]
                
                # Retrieve specific codes safely
                student_code = str(student_info.get('Student Code', 'N/A'))
                roll_no = str(student_info.get('Roll', 'N/A'))
                
                # Construct the row EXACTLY in the order of your SCH_Exam_Fees headers
                # Headers: Date, Student_Code, Name, Class, Section, Roll, Amount, Payer_Type, Teacher_Involved
                new_row = [
                    current_time_ist, 
                    student_code, 
                    selected_student, 
                    str(selected_class), 
                    str(selected_section), 
                    roll_no, 
                    amount, 
                    payer_type, 
                    received_by_teacher
                ]
                
                # Append directly to the sheet using gspread (Fast and efficient)
                fees_sheet = gc.open_by_url(st.secrets["sheet_urls"]["sch_exam_fees"])
                ws_fees = fees_sheet.worksheet("Sheet1")
                ws_fees.append_row(new_row)
                
                # Clear the cache so the dashboard updates immediately
                load_data.clear()
                
                st.success(f"Successfully recorded ₹{amount} for {selected_student}!")

with tab2:
    st.subheader("Collection Dashboard")
    if not df_fees.empty and 'Amount' in df_fees.columns:
        # Convert amount to numeric just in case it reads as text
        df_fees['Amount'] = pd.to_numeric(df_fees['Amount'], errors='coerce').fillna(0)
        
        col_dash1, col_dash2 = st.columns(2)
        with col_dash1:
            st.metric(label="Total Fees Collected", value=f"₹ {df_fees['Amount'].sum()}")
            
        with col_dash2:
            st.metric(label="Total Transactions", value=len(df_fees))

        class_totals = df_fees.groupby('Class')['Amount'].sum().reset_index()
        fig = px.bar(class_totals, x='Class', y='Amount', title="Total Fees Collected per Class", text_auto=True)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No fee data available yet.")
