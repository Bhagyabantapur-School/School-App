import streamlit as st
import gspread
import pandas as pd
from datetime import datetime, timedelta
import pytz
import plotly.express as px

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="BPS Exam Fees", page_icon="💰", layout="wide")

IST = pytz.timezone('Asia/Kolkata')

st.title("💰 Bhagyabantapur Primary School - Exam Fees")
st.markdown("Record and track examination fee collections seamlessly.")

# --- AUTHENTICATION & CONNECTION ---
@st.cache_resource
def get_gspread_client():
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
    bps_sheet = gc.open("BPS_Database")
    ws_students = bps_sheet.worksheet("students_master")
    ws_teachers = bps_sheet.worksheet("TEACHERS_DETAIL")
    
    ws_mdm = bps_sheet.worksheet("mdm_log")
    
    df_students = pd.DataFrame(ws_students.get_all_records())
    df_teachers = pd.DataFrame(ws_teachers.get_all_records())
    df_mdm = pd.DataFrame(ws_mdm.get_all_records())
    
    fees_sheet = gc.open("SCH_Exam_Fees")
    ws_fees = fees_sheet.worksheet("Sheet1") 
    df_fees = pd.DataFrame(ws_fees.get_all_records())
    
    return df_students, df_teachers, df_fees, df_mdm

try:
    with st.spinner("Connecting to BPS Database..."):
        df_students, df_teachers, df_fees, df_mdm = load_data()
except Exception as e:
    st.error(f"Error loading data. Ensure the sheets are named correctly and the 'mdm_log' tab exists. Details: {e}")
    st.stop()

# --- APP LAYOUT (Tabs) ---
tab1, tab2 = st.tabs(["📝 Collect Fees", "📊 Fee Dashboard"])

# ==========================================
# TAB 1: FEE COLLECTION FORM (BATCH MODE)
# ==========================================
with tab1:
    
    # --- STEP 1: BATCH SETTINGS ---
    st.markdown("### Step 1: Fee Details (Batch Setup)")
    
    col_fee1, col_fee2, col_fee3 = st.columns(3)
    
    with col_fee1:
        receipt_date = st.date_input("Receipt Date", value=datetime.now(IST).date())
        amount = st.number_input("Payment Amount (₹)", min_value=0, step=5)
        
    with col_fee2:
        payer_type = st.radio("Received From:", ["Student", "Guardian", "Teacher"])
        
    with col_fee3:
        teacher_names = [t for t in df_teachers['Name'].unique() if str(t).strip()]
        teacher_options = ["Not Applicable"] + sorted(teacher_names)
        received_by_teacher = st.selectbox("Which Teacher? (If applicable)", options=teacher_options)
        
    st.divider()
    
    # --- STEP 2: STUDENT SELECTION ---
    st.markdown("### Step 2: Select Student & Record")
    
    search_mode = st.radio("Search Method:", ["Filter by Class & Section", "Search by Name"], horizontal=True, label_visibility="collapsed")
    
    filtered_students = pd.DataFrame()
    selected_display = None
    
    if search_mode == "Search by Name":
        search_query = st.text_input("🔍 Enter part of the student's name (e.g., 'saj')")
        if search_query:
            filtered_students = df_students[df_students['Name'].str.contains(search_query, case=False, na=False)].copy()
        else:
            st.caption("Start typing above to search the whole school...")
            
    else: 
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            classes = [c for c in df_students['Class'].unique() if str(c).strip()]
            selected_class = st.selectbox("Select Class", options=sorted(classes))
            
        with col_s2:
            sections = [s for s in df_students[df_students['Class'] == selected_class]['Section'].unique() if str(s).strip()]
            selected_section = st.selectbox("Select Section", options=sorted(sections))
            
        filtered_students = df_students[
            (df_students['Class'] == selected_class) & 
            (df_students['Section'] == selected_section)
        ].copy()

    # DISPLAY RESULTS IN DROPDOWN
    if not filtered_students.empty:
        filtered_students['Roll_Numeric'] = pd.to_numeric(filtered_students['Roll'], errors='coerce').fillna(999)
        filtered_students = filtered_students.sort_values('Roll_Numeric')
        
        # --- NEW: Check who was present in the last 10 days ---
        if not df_mdm.empty and 'Date' in df_mdm.columns:
            df_mdm['Parsed_Date'] = pd.to_datetime(df_mdm['Date'], errors='coerce', dayfirst=True).dt.date
            
            # Calculate the date 10 days before the selected receipt_date
            ten_days_ago = receipt_date - timedelta(days=10)
            
            # Filter the MDM log for any records within this 10-day window
            recent_mdm = df_mdm[(df_mdm['Parsed_Date'] >= ten_days_ago) & (df_mdm['Parsed_Date'] <= receipt_date)]
            
            # Create a fast lookup set of students present recently
            present_keys = set(zip(
                recent_mdm['Class'].astype(str), 
                recent_mdm['Section'].astype(str), 
                recent_mdm['Roll'].astype(str)
            ))
        else:
            present_keys = set()
        
        def format_dropdown(row):
            roll_val = str(row['Roll']).strip()
            name_val = str(row['Name']).strip()
            class_val = str(row['Class']).strip()
            sec_val = str(row['Section']).strip()
            
            is_present = (class_val, sec_val, roll_val) in present_keys
            presence_marker = "✅ " if is_present else ""
            
            if search_mode == "Search by Name":
                return f"{presence_marker}{name_val} - Class {class_val} '{sec_val}' (Roll {roll_val})"
            else:
                if roll_val and roll_val.lower() != 'nan':
                    return f"{presence_marker}Roll {roll_val} - {name_val}"
                return f"{presence_marker}{name_val}"
                
        filtered_students['Dropdown_Display'] = filtered_students.apply(format_dropdown, axis=1)
        display_options = filtered_students['Dropdown_Display'].tolist()
        
        st.markdown("##### Select Profile (✅ = Present in the last 10 days)")
        selected_display = st.selectbox("Choose the correct student:", options=display_options, label_visibility="collapsed")
        
    elif search_mode == "Search by Name" and search_query:
        st.warning(f"No students found containing '{search_query}'.")

    st.write("") 

    # --- DUPLICATE CHECKER & DUE AMOUNT LOGIC ---
    allow_submission = True
    
    if selected_display:
        student_info = filtered_students[filtered_students['Dropdown_Display'] == selected_display].iloc[0]
        pure_name = str(student_info['Name'])
        final_class = str(student_info['Class'])
        roll_no = str(student_info.get('Roll', 'N/A'))
        
        if not df_fees.empty and 'Amount' in df_fees.columns:
            past_payments = df_fees[
                (df_fees['Name'].astype(str) == pure_name) & 
                (df_fees['Class'].astype(str) == final_class) & 
                (df_fees['Roll'].astype(str) == roll_no)
            ]
            
            if not past_payments.empty:
                total_paid = pd.to_numeric(past_payments['Amount'], errors='coerce').fillna(0).sum()
                
                if total_paid > 0:
                    st.warning(f"⚠️ **Duplicate Entry Warning:** {pure_name} has already paid a total of **₹{total_paid}**.")
                    
                    with st.expander("View their past payments"):
                        display_cols = [c for c in ['Date', 'Amount', 'Payer_Type', 'Teacher_Involved'] if c in past_payments.columns]
                        st.dataframe(past_payments[display_cols], hide_index=True, use_container_width=True)
                    
                    allow_due = st.checkbox(f"Unlock to record an additional/due payment for {pure_name}")
                    if not allow_due:
                        allow_submission = False

    # --- DATA SUBMISSION LOGIC ---
    submit_button = st.button("✅ Record Payment", type="primary", use_container_width=True, disabled=not allow_submission)
    
    if submit_button:
        if not selected_display:
            st.error("Please find and select a valid student first.")
        elif amount <= 0:
            st.warning("Please enter an amount greater than 0.")
        else:
            with st.spinner("Logging transaction to Google Sheets..."):
                try:
                    current_time = datetime.now(IST).time()
                    final_datetime_ist = datetime.combine(receipt_date, current_time).strftime("%Y-%m-%d %H:%M:%S")
                    
                    final_section = str(student_info['Section'])
                    final_teacher = received_by_teacher if payer_type == "Teacher" else "N/A"
                    
                    new_row = [
                        final_datetime_ist, 
                        pure_name, 
                        final_class, 
                        final_section, 
                        roll_no, 
                        amount, 
                        payer_type, 
                        final_teacher
                    ]
                    
                    fees_sheet = gc.open("SCH_Exam_Fees")
                    ws_fees = fees_sheet.worksheet("Sheet1")
                    ws_fees.append_row(new_row)
                    
                    load_data.clear()
                    
                    st.success(f"✅ Successfully recorded ₹{amount} for {pure_name} on {receipt_date.strftime('%d-%m-%Y')}!")
                    st.rerun() 
                except Exception as e:
                    st.error(f"An error occurred while saving the data: {e}")

# ==========================================
# TAB 2: LIVE DASHBOARD
# ==========================================
with tab2:
    st.subheader("Collection Overview")
    
    if st.button("🔄 Refresh Data"):
        load_data.clear()
        st.rerun()
        
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
            st.dataframe(df_fees.tail(15).iloc[::-1], use_container_width=True)
            
    else:
        st.info("No fee data available yet. Transactions will appear here once recorded.")
