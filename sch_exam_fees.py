import streamlit as st
import gspread
import pandas as pd
from datetime import datetime, timedelta
import pytz
import plotly.express as px
from google.oauth2.service_account import Credentials

# --- GATEKEEPER SECURITY CHECK ---
if 'authenticated' not in st.session_state or not st.session_state.authenticated:
    st.warning("🔒 Unauthorized Access. Please log in through the main portal.")
    st.stop()

IST = pytz.timezone('Asia/Kolkata')

st.title("💰 Bhagyabantapur Primary School - Exam Fees")
st.markdown("Record and track examination fee collections seamlessly.")

# --- AUTHENTICATION & CONNECTION ---
# 🛠️ FIX: Removed @st.cache_resource so the session state is never mangled across reruns.
def get_gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets", 
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]), 
        scopes=scopes
    )
    return gspread.authorize(credentials)

try:
    # Initial connection test
    _test_gc = get_gspread_client()
except Exception as e:
    st.error(f"Authentication failed. Please check your st.secrets. Details: {e}")
    st.stop()

# --- DATA LOADING ---
@st.cache_data(ttl=600)
def load_data():
    # Generate a fresh client inside the data loader
    gc = get_gspread_client()
    
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
    
    if not df_fees.empty:
        # Create row numbers for exact sheet targeting (Row 1 is header, data starts at Row 2)
        df_fees['_Row_Num'] = range(2, len(df_fees) + 2)
        
        # Ensure the Handover_Status exists even if legacy data is present
        if 'Handover_Status' not in df_fees.columns:
            df_fees['Handover_Status'] = 'Pending'
            if 'Teacher_Involved' in df_fees.columns:
                # The Head Teacher's self-collections do not need to be handed over
                df_fees.loc[df_fees['Teacher_Involved'] == 'SUKHAMAY KISKU', 'Handover_Status'] = 'Settled'
    
    return df_students, df_teachers, df_fees, df_mdm

try:
    with st.spinner("Connecting to BPS Database..."):
        df_students, df_teachers, df_fees, df_mdm = load_data()
except Exception as e:
    st.error(f"Error loading data. Ensure the sheets are named correctly and the 'mdm_log' tab exists. Details: {e}")
    st.stop()

# --- APP LAYOUT (Tabs Dynamic Routing) ---
if st.session_state.user_role == "admin":
    tab1, tab2, tab3 = st.tabs(["📝 Collect Fees", "📊 Fee Dashboard", "🤝 Handover Manager"])
else:
    tab1, tab2 = st.tabs(["📝 Collect Fees", "📊 Fee Dashboard"])

# ==========================================
# TAB 1: FEE COLLECTION FORM (BATCH MODE)
# ==========================================
with tab1:
    st.markdown("### Step 1: Fee Details (Batch Setup)")
    
    col_fee1, col_fee2, col_fee3 = st.columns(3)
    
    with col_fee1:
        receipt_date = st.date_input("Receipt Date", value=datetime.now(IST).date())
        amount = st.number_input("Payment Amount (₹)", min_value=0, step=5)
        
    with col_fee2:
        exam_type = st.selectbox("Exam Type", ["Evaluation-II", "Britti"], index=0)
        
    with col_fee3:
        payer_type = st.radio("Received From:", ["Student", "Guardian", "Teacher"])
        
    st.divider()
    
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
        
        if not df_mdm.empty and 'Date' in df_mdm.columns:
            df_mdm['Parsed_Date'] = pd.to_datetime(df_mdm['Date'], errors='coerce', dayfirst=True).dt.date
            ten_days_ago = receipt_date - timedelta(days=10)
            recent_mdm = df_mdm[(df_mdm['Parsed_Date'] >= ten_days_ago) & (df_mdm['Parsed_Date'] <= receipt_date)]
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

    # --- DUPLICATE CHECKER ---
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
            
            has_exam_col = 'Exam Type' in df_fees.columns
            if has_exam_col:
                past_payments = past_payments[past_payments['Exam Type'].astype(str).str.strip() == str(exam_type).strip()]
            
            if not past_payments.empty:
                total_paid = pd.to_numeric(past_payments['Amount'], errors='coerce').fillna(0).sum()
                if total_paid > 0:
                    if has_exam_col:
                        st.warning(f"⚠️ **Duplicate Entry Warning:** {pure_name} has already paid a total of **₹{total_paid}** specifically for **{exam_type}**.")
                    else:
                        st.warning(f"⚠️ **Duplicate Entry Warning:** {pure_name} has past payments totaling **₹{total_paid}**. (Note: 'Exam Type' column is missing in your Google Sheet)")
                    
                    with st.expander("View their past payments"):
                        display_cols = [c for c in ['Date', 'Amount', 'Exam Type', 'Payer_Type', 'Teacher_Involved'] if c in past_payments.columns]
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
                    final_teacher = st.session_state.user_name
                    
                    # The Head Teacher defaults to "Settled" since they hold the final cash. Assistants default to "Pending".
                    handover_status = "Settled" if st.session_state.user_role == "admin" else "Pending"
                    
                    # Target Order: Date, Name, Class, Section, Roll, Amount, Payer_Type, Teacher_Involved, Exam Type, Handover_Status
                    new_row = [
                        final_datetime_ist, 
                        pure_name, 
                        final_class, 
                        final_section, 
                        roll_no, 
                        amount, 
                        payer_type, 
                        final_teacher,
                        exam_type,
                        handover_status 
                    ]
                    
                    # Call fresh client for write operations
                    gc_write = get_gspread_client()
                    ws_fees_write = gc_write.open("SCH_Exam_Fees").worksheet("Sheet1")
                    ws_fees_write.append_row(new_row)
                    
                    load_data.clear()
                    
                    st.success(f"✅ Successfully recorded ₹{amount} for {pure_name} ({exam_type}) on {receipt_date.strftime('%d-%m-%Y')}!")
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
        
    dash_df = df_fees.copy()
    
    # ----------------------------------------------------
    # ASSISTANT TEACHER DASHBOARD VIEW
    # ----------------------------------------------------
    if st.session_state.user_role != "admin":
        if not dash_df.empty:
            dash_df = dash_df[dash_df['Teacher_Involved'].astype(str).str.strip() == st.session_state.user_name]
        
        st.caption(f"Showing personal collections managed by: **{st.session_state.user_name}**")
        
        if not dash_df.empty and 'Amount' in dash_df.columns:
            dash_df['Amount'] = pd.to_numeric(dash_df['Amount'], errors='coerce').fillna(0)
            
            total_coll = dash_df['Amount'].sum()
            handed_over = dash_df[dash_df['Handover_Status'] == 'Handed Over']['Amount'].sum()
            pending = dash_df[dash_df['Handover_Status'] == 'Pending']['Amount'].sum()
            
            col_t1, col_t2, col_t3 = st.columns(3)
            col_t1.metric("💰 Total Collection", f"₹ {total_coll:,.2f}")
            col_t2.metric("🤝 Handed to Head Sir", f"₹ {handed_over:,.2f}")
            col_t3.metric("💵 Remaining Cash in Hand", f"₹ {pending:,.2f}")
            
            st.divider()
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("##### ✅ Handed Over to Head Sir")
                handed_df = dash_df[dash_df['Handover_Status'] == 'Handed Over']
                if not handed_df.empty:
                    st.dataframe(handed_df[['Date', 'Name', 'Class', 'Amount', 'Exam Type']], hide_index=True)
                else:
                    st.info("No funds handed over yet.")
            
            with c2:
                st.markdown("##### ⏳ Cash in Hand (Pending)")
                pend_df = dash_df[dash_df['Handover_Status'] == 'Pending']
                if not pend_df.empty:
                    st.dataframe(pend_df[['Date', 'Name', 'Class', 'Amount', 'Exam Type']], hide_index=True)
                else:
                    st.success("All clear! No pending cash.")
        else:
            st.info(f"No fee data collected by you ({st.session_state.user_name}) yet.")

    # ----------------------------------------------------
    # HEAD TEACHER (ADMIN) DASHBOARD VIEW
    # ----------------------------------------------------
    else:
        st.caption("Showing **All School Collections** (Head Teacher View)")
            
        if not dash_df.empty and 'Amount' in dash_df.columns:
            dash_df['Amount'] = pd.to_numeric(dash_df['Amount'], errors='coerce').fillna(0)
            
            # Accurate Admin Accounting
            admin_collected = dash_df[dash_df['Teacher_Involved'] == 'SUKHAMAY KISKU']['Amount'].sum()
            teachers_handed_over = dash_df[dash_df['Handover_Status'] == 'Handed Over']['Amount'].sum()
            admin_cash = admin_collected + teachers_handed_over
            total_pending = dash_df[dash_df['Handover_Status'] == 'Pending']['Amount'].sum()
            
            col_dash1, col_dash2, col_dash3 = st.columns(3)
            col_dash1.metric("💰 Total School Collection", f"₹ {dash_df['Amount'].sum():,.2f}")
            col_dash2.metric("🏦 Admin Cash in Hand", f"₹ {admin_cash:,.2f}")
            col_dash3.metric("💵 Pending with Teachers", f"₹ {total_pending:,.2f}")
    
            st.divider()
            
            st.markdown("##### 👨‍🏫 Teacher Handover Ledger")
            def calc_teacher_stats(group):
                total = group['Amount'].sum()
                handed = group[group['Handover_Status'].isin(['Handed Over', 'Settled'])]['Amount'].sum()
                pend = group[group['Handover_Status'] == 'Pending']['Amount'].sum()
                return pd.Series({'Total Collected': total, 'Handed Over to HT': handed, 'Pending Cash': pend})
    
            teacher_summary = dash_df.groupby('Teacher_Involved').apply(calc_teacher_stats).reset_index()
            st.dataframe(teacher_summary, hide_index=True, use_container_width=True)
            
            st.markdown("##### 📜 Detailed Handover Log (Received Students)")
            handed_over_df = dash_df[dash_df['Handover_Status'] == 'Handed Over']
            if not handed_over_df.empty:
                st.dataframe(handed_over_df[['Date', 'Teacher_Involved', 'Name', 'Class', 'Amount', 'Exam Type']], hide_index=True)
            else:
                st.info("No cash has been handed over by teachers yet.")
                
            st.divider()
            st.markdown("##### 📈 Collection by Class & Exam Type")
            if 'Exam Type' in dash_df.columns:
                class_totals = dash_df.groupby(['Class', 'Exam Type'])['Amount'].sum().reset_index()
                fig = px.bar(
                    class_totals, 
                    x='Class', 
                    y='Amount', 
                    color='Exam Type',
                    text_auto=True,
                    barmode='group',
                    color_discrete_sequence=px.colors.qualitative.Set2
                )
                fig.update_layout(xaxis_title="Class", yaxis_title="Total Amount (₹)")
            else:
                class_totals = dash_df.groupby('Class')['Amount'].sum().reset_index()
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
            
        else:
            st.info("No fee data available yet. Transactions will appear here once recorded.")

# ==========================================
# TAB 3: ADMIN HANDOVER MANAGER (ADMIN ONLY)
# ==========================================
if st.session_state.user_role == "admin":
    with tab3:
        st.subheader("🤝 Cash Handover Manager")
        st.markdown("Select an assistant teacher to securely receive and verify their pending cash collections.")
        
        if not df_fees.empty and 'Handover_Status' in df_fees.columns:
            # Locate the exact column index for Handover_Status
            handover_col_idx = df_fees.columns.get_loc('Handover_Status') + 1
            
            df_fees['Amount'] = pd.to_numeric(df_fees['Amount'], errors='coerce').fillna(0)
            pending_df = df_fees[df_fees['Handover_Status'] == 'Pending'].copy()
            
            if not pending_df.empty:
                teachers_with_cash = pending_df['Teacher_Involved'].unique()
                selected_teacher = st.selectbox("Select Teacher to receive cash from:", teachers_with_cash)
                
                teacher_pending = pending_df[pending_df['Teacher_Involved'] == selected_teacher].copy()
                teacher_pending.insert(0, 'Receive', False)
                
                total_owed = teacher_pending['Amount'].sum()
                st.markdown(f"### Pending Cash with {selected_teacher}: **₹ {total_owed:,.2f}**")
                st.caption("Check the boxes next to the students' fees you are receiving, then click Confirm.")
                
                # Interactive Editor for Admin to verify rows
                edited_df = st.data_editor(
                    teacher_pending[['Receive', 'Date', 'Name', 'Class', 'Amount', 'Exam Type', '_Row_Num']],
                    hide_index=True,
                    disabled=['Date', 'Name', 'Class', 'Amount', 'Exam Type', '_Row_Num'],
                    column_config={'_Row_Num': None} # Hides the technical row target from UI
                )
                
                selected_rows = edited_df[edited_df['Receive'] == True]
                
                if not selected_rows.empty:
                    receiving_amount = selected_rows['Amount'].sum()
                    st.success(f"Ready to receive **₹ {receiving_amount:,.2f}** ({len(selected_rows)} student transactions).")
                    
                    if st.button("✅ Confirm Receipt of Cash", type="primary"):
                        with st.spinner(f"Verifying receipt of cash from {selected_teacher}..."):
                            try:
                                # Fetch a fresh client for writing
                                gc_write = get_gspread_client()
                                ws_fees_write = gc_write.open("SCH_Exam_Fees").worksheet("Sheet1")
                                
                                # Highly stable singular cell update
                                for r_num in selected_rows['_Row_Num']:
                                    ws_fees_write.update_cell(r_num, handover_col_idx, 'Handed Over')
                                
                                load_data.clear()
                                st.success("Cash securely received and recorded!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to update Google Sheets: {e}")
            else:
                st.success("🎉 All clear! There is no pending cash to receive from any assistant teachers.")
        else:
            st.info("System is waiting for 'Handover_Status' configuration or there is no fee data available. Ensure 'Handover_Status' is exactly added as a column header in your Google Sheet.")
