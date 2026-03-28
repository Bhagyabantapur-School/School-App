import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
import pytz
import plotly.express as px

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="BPS Exam Fees", page_icon="💰", layout="wide")

# Set timezone to IST for accurate logging
IST = pytz.timezone('Asia/Kolkata')

st.title("💰 Bhagyabantapur Primary School - Exam Fees")
st.markdown("Record and track examination fee collections seamlessly.")

# --- AUTHENTICATION & CONNECTION ---
@st.cache_resource
def get_gspread_client():
    """Authenticates with Google Sheets using Streamlit Secrets."""
    credentials_dict = dict(st.secrets["gcp_service_account"])
    gc = gspread.service_account_from_dict(credentials_dict)
    return gc

try:
    gc = get_gspread_client()
except Exception as e:
    st.error(f"Authentication failed. Please check your st.secrets. Details: {e}")
    st.stop()

# --- DATA LOADING ---
@st.cache_data(ttl=600)
def load_data():
    """Loads student, teacher, and fee data from Google Sheets by file name."""
    # Open the BPS Database by name
    bps_sheet = gc.open("BPS_Database")
    ws_students = bps_sheet.worksheet("students_master")
    ws_teachers = bps_sheet.worksheet("TEACHERS_DETAIL")
    
    df_students = pd.DataFrame(ws_students.get_all_records())
    df_teachers = pd.DataFrame(ws_teachers.get_all_records())
    
    # Open the Exam Fees log by name
    fees_sheet = gc.open("SCH_Exam_Fees")
    ws_fees = fees_sheet.worksheet("Sheet1") # Ensure your tab is named Sheet1
    df_fees = pd.DataFrame(ws_fees.get_all_records())
    
    return df_students, df_teachers, df_fees

try:
    with st.spinner("Connecting to BPS Database..."):
        df_students, df_teachers, df_fees = load_data()
except Exception as e:
    st.error(f"Error loading data. Ensure the sheets are named exactly 'BPS_Database' and 'SCH_Exam_Fees' and are shared with your service account email. Details: {e}")
    st.stop()

# --- APP LAYOUT (Tabs) ---
tab1, tab2 = st.tabs(["📝 Collect Fees", "📊 Fee Dashboard"])

# ==========================================
# TAB 1: FEE COLLECTION FORM
# ==========================================
with tab1:
    st.subheader("Record New Payment")
    
    with st.form("fee_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
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
        
        st.divider()
        col4, col5, col6 = st.columns(3)
        
        with col4:
            amount = st.number_input("Payment Amount (₹)", min_value=0, step=5)
            
        with col5:
            payer_type = st.radio("Received From:", ["Student", "Guardian", "Teacher"])
        
        with col6:
            received_by_teacher = "N/A"
            if payer_type == "Teacher":
                teacher_names = [t for t in df_teachers['Name'].unique() if str(t).strip()]
                received_by_teacher = st.selectbox("Which Teacher?", options=sorted(teacher_names))

        submit_button = st.form_submit_button("Record Payment", type="primary")

    # --- DATA SUBMISSION LOGIC ---
    if submit_button:
        if not selected_student:
            st.error("Please select a valid student.")
        elif amount <= 0:
            st.warning("Please enter an amount greater than 0.")
        else:
            with st.spinner("Logging transaction to Google Sheets..."):
                try:
                    current_time_ist = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
                    student_info = filtered_students[filtered_students['Name'] == selected_student].iloc[0]
                    
                    student_code = str(student_info.get('Student Code', 'N/A'))
                    roll_no = str(student_info.get('Roll', 'N/A'))
                    
                    # Create the row exactly matching SCH_Exam_Fees headers
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
                    
                    # Append directly to the sheet using gspread by file name
                    fees_sheet = gc.open("SCH_Exam_Fees")
                    ws_fees = fees_sheet.worksheet("Sheet1")
                    ws_fees.append_row(new_row)
                    
                    # Clear the cache so the dashboard updates instantly
                    load_data.clear()
                    
                    st.success(f"Successfully recorded ₹{amount} for {selected_student}!")
                    st.balloons()
                except Exception as e:
                    st.error(f"An error occurred while saving the data: {e}")

# ==========================================
# TAB 2: LIVE DASHBOARD
# ==========================================
with tab2:
    st.subheader("Collection Overview")
    
    if not df_fees.empty and 'Amount' in df_fees.columns:
        df_fees['Amount'] = pd.to_numeric(df_fees['Amount'], errors='coerce').fillna(0)
        
        col_dash1, col_dash2, col_dash3 = st.columns(3)
        with col_dash1:
            st.metric(label="Total Fees Collected", value=f"₹ {df_fees['Amount'].sum():,.2f}")
        with col_dash2:
            st.metric(label="Total Transactions", value=len(df_fees))
        with col_dash3:
            st.metric(label="Latest Collection", value=str(df_fees['Date'].iloc[-1]) if not df_fees.empty else "N/A")

        st.divider()
        
        st.markdown("##### Collection by Class")
        class_totals = df_fees.groupby('Class')['Amount'].sum().reset_index()
        fig = px.bar(
            class_totals, 
            x='Class', 
            y='Amount', 
            text_auto=True,
            color='Amount',
            color_continuous_scale='Viridis'
        )
        fig.update_layout(xaxis_title="Class", yaxis_title="Total Amount (₹)", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("View Recent Transactions"):
            st.dataframe(df_fees.tail(10).iloc[::-1], use_container_width=True)
            
    else:
        st.info("No fee data available yet. Transactions will appear here once recorded.")
