import streamlit as st
import gspread
import pandas as pd
from datetime import datetime, timedelta
import pytz
import plotly.express as px
import re
import base64
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import AuthorizedSession

# --- GATEKEEPER SECURITY CHECK ---
if 'authenticated' not in st.session_state or not st.session_state.authenticated:
    st.warning("🔒 Unauthorized Access. Please log in through the main portal.")
    st.stop()

IST = pytz.timezone('Asia/Kolkata')

st.title("💰 Bhagyabantapur Primary School - Funds & Fees")
st.markdown("Record and track examination fees and confiscated unauthorized cash.")

# --- AUTHENTICATION & SECURE IMAGE FETCHING ---
@st.cache_resource
def get_google_credentials(): 
    return Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]), 
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.readonly"]
    )

def get_gspread_client():
    return gspread.authorize(get_google_credentials())

@st.cache_resource
def get_drive_session(): 
    return AuthorizedSession(get_google_credentials())

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_secure_image_bytes(file_id):
    try:
        r = get_drive_session().get(f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media")
        return r.content if r.status_code == 200 else None
    except: return None

def get_secure_photo_uri(url):
    fb = "https://www.w3schools.com/howto/img_avatar.png"
    if pd.isna(url) or url == "" or not isinstance(url, str): return fb
    match = re.search(r"(?:id=|/d/)([\w-]+)", url)
    if match:
        b = fetch_secure_image_bytes(match.group(1))
        if b: return f"data:image/jpeg;base64,{base64.b64encode(b).decode()}"
    return url if url.startswith("http") else fb

try:
    _test_gc = get_gspread_client()
except Exception as e:
    st.error(f"Authentication failed. Please check your st.secrets. Details: {e}")
    st.stop()

# --- DATA LOADING ---
@st.cache_data(ttl=600)
def load_data():
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
        df_fees['_Row_Num'] = range(2, len(df_fees) + 2)
        
        if 'Handover_Status' not in df_fees.columns:
            df_fees['Handover_Status'] = 'Pending'
            if 'Teacher_Involved' in df_fees.columns:
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
    tab_pending, tab1, tab2, tab3 = st.tabs(["⚠️ Pending Fees", "📝 Record Funds", "📊 Collection Dashboard", "🤝 Handover Manager"])
else:
    tab_pending, tab1, tab2 = st.tabs(["⚠️ Pending Fees", "📝 Record Funds", "📊 Collection Dashboard"])

# ==========================================
# TAB 0: TODAY's PENDING FEES
# ==========================================
with tab_pending:
    col_hdr, col_btn = st.columns([3, 1])
    with col_hdr:
        st.subheader("⚠️ Today's Pending 'Evaluation-II' Fees")
    with col_btn:
        if st.button("🔄 Refresh List", use_container_width=True):
            load_data.clear()
            st.rerun()
    
    today_str = datetime.now(IST).strftime("%d-%m-%Y")
    
    if df_mdm.empty or 'Date' not in df_mdm.columns:
        st.info("🌸 **Gentle Reminder:** No attendance (MDM) records found. Please complete attendance first.")
    else:
        # Filter MDM for today (Show all classes that have MDM completed)
        today_mdm = df_mdm[df_mdm['Date'].astype(str).str.strip() == today_str].copy()
        
        if today_mdm.empty:
            st.info("🌸 **Gentle Reminder:** It looks like today's attendance (MDM Entry) hasn't been completed yet. Please submit class attendance in the BPS Digital App first to see the list of present students with pending fees.")
        else:
            # Safe key generation to prevent Float vs String mismatch (e.g. "1.0" vs "1")
            def safe_key(cls, roll, name):
                try:
                    r = str(int(float(roll)))
                except:
                    r = str(roll).strip()
                return f"{str(cls).strip().upper()}_{r}_{str(name).strip().upper()}"

            paid_keys = set()
            if not df_fees.empty and 'Collection Type' in df_fees.columns and 'Amount' in df_fees.columns:
                eval_fees = df_fees[df_fees['Collection Type'].astype(str).str.strip() == 'Evaluation-II'].copy()
                eval_fees['Amount'] = pd.to_numeric(eval_fees['Amount'], errors='coerce').fillna(0)
                
                # Get net amount per student
                paid_students = eval_fees.groupby(['Class', 'Roll', 'Name'])['Amount'].sum().reset_index()
                paid_students = paid_students[paid_students['Amount'] > 0]
                
                for _, row in paid_students.iterrows():
                    paid_keys.add(safe_key(row['Class'], row['Roll'], row['Name']))
            
            # Check who is present but hasn't paid
            today_mdm['Match_Key'] = today_mdm.apply(lambda r: safe_key(r.get('Class',''), r.get('Roll',''), r.get('Name','')), axis=1)
            pending_students = today_mdm[~today_mdm['Match_Key'].isin(paid_keys)]
            
            if pending_students.empty:
                st.success("🎉 Fantastic! All students marked present today have paid their Evaluation-II fees.")
            else:
                st.markdown("The following students are **present today** but have **not yet paid** the Evaluation-II fees:")
                
                class_order = {"CLASS PP": 0, "CLASS I": 1, "CLASS II": 2, "CLASS III": 3, "CLASS IV": 4, "CLASS V": 5}
                classes_present = [c for c in pending_students['Class'].unique() if str(c).strip()]
                classes_present.sort(key=lambda x: class_order.get(x, 99))
                
                for cls in classes_present:
                    cls_pending = pending_students[pending_students['Class'] == cls].copy()
                    cls_pending['Roll_Num'] = pd.to_numeric(cls_pending['Roll'], errors='coerce').fillna(999)
                    cls_pending = cls_pending.sort_values('Roll_Num')
                    
                    with st.expander(f"📖 {cls} - {len(cls_pending)} Student(s) Pending", expanded=True):
                        st.dataframe(cls_pending[['Section', 'Roll', 'Name', 'Teacher']], hide_index=True, use_container_width=True)

# ==========================================
# TAB 1: FUND COLLECTION FORM (BATCH MODE)
# ==========================================
with tab1:
    st.markdown("### Step 1: Transaction Details")
    
    transaction_nature = st.radio("Nature of Transaction:", ["📥 Collect Funds (In)", "📤 Return Funds (Out)"], horizontal=True)
    st.write("")
    
    col_fee1, col_fee2, col_fee3 = st.columns(3)
    
    with col_fee1:
        receipt_date = st.date_input("Transaction Date", value=datetime.now(IST).date())
        amount = st.number_input("Amount (₹)", min_value=0, step=5)
        
    with col_fee2:
        collection_type = st.selectbox("Collection Type", ["Evaluation-II", "Britti", "Confiscated Money"], index=0)
        
    with col_fee3:
        if transaction_nature == "📥 Collect Funds (In)":
            payer_type = st.radio("Received From:", ["Student", "Guardian", "Teacher"])
        else:
            payer_type = st.radio("Returned To:", ["Student", "Guardian", "Teacher"])
        
    actual_collector = st.session_state.user_name
    if st.session_state.user_role == "admin":
        st.info("💡 **Admin Override:** If you are logging a transaction on behalf of an assistant teacher, select their name below.")
        
        teacher_names = []
        if not df_teachers.empty:
            for col in ['Name', 'Teacher Name', 'Teacher_Name', 'Full Name']:
                if col in df_teachers.columns:
                    teacher_names = df_teachers[col].dropna().unique().tolist()
                    break
        if not df_fees.empty and 'Teacher_Involved' in df_fees.columns:
            teacher_names.extend(df_fees['Teacher_Involved'].dropna().unique().tolist())
            
        teacher_names = list(set(teacher_names))
        if st.session_state.user_name in teacher_names:
            teacher_names.remove(st.session_state.user_name)
            
        teacher_list = [st.session_state.user_name] + sorted(teacher_names)
        actual_collector = st.selectbox("Transaction Performed By:", teacher_list)

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

    allow_submission = True
    
    if selected_display:
        student_info = filtered_students[filtered_students['Dropdown_Display'] == selected_display].iloc[0]
        pure_name = str(student_info['Name'])
        final_class = str(student_info['Class'])
        roll_no = str(student_info.get('Roll', 'N/A'))
        
        raw_thumb_url = str(student_info.get('Thumb_URL', '')).strip()

        col_profile, col_action = st.columns([1, 4])
        
        with col_profile:
            secure_uri = get_secure_photo_uri(raw_thumb_url)
            st.image(secure_uri, width=85)

        with col_action:
            if not df_fees.empty and 'Amount' in df_fees.columns:
                past_payments = df_fees[
                    (df_fees['Name'].astype(str) == pure_name) & 
                    (df_fees['Class'].astype(str) == final_class) & 
                    (df_fees['Roll'].astype(str) == roll_no)
                ]
                
                has_type_col = 'Collection Type' in df_fees.columns
                if has_type_col:
                    past_payments = past_payments[past_payments['Collection Type'].astype(str).str.strip() == str(collection_type).strip()]
                
                if not past_payments.empty:
                    total_paid = pd.to_numeric(past_payments['Amount'], errors='coerce').fillna(0).sum()
                    
                    if total_paid > 0 and transaction_nature == "📥 Collect Funds (In)":
                        st.warning(f"⚠️ **Duplicate Warning:** {pure_name} already has a recorded net balance of **₹{total_paid}** for **{collection_type}**.")
                        allow_due = st.checkbox(f"Unlock to record an additional entry for {pure_name}")
                        if not allow_due:
                            allow_submission = False
                            
                    elif total_paid <= 0 and transaction_nature == "📤 Return Funds (Out)":
                        st.error(f"🚫 **Action Blocked:** {pure_name} has a net balance of ₹{total_paid} for {collection_type}. You cannot return funds that were not collected.")
                        allow_submission = False
                    else:
                        st.success(f"✅ Ready to process transaction for {pure_name}.")
    
                    with st.expander("View their past records"):
                        display_cols = [c for c in ['Date', 'Amount', 'Collection Type', 'Payer_Type', 'Teacher_Involved'] if c in past_payments.columns]
                        st.dataframe(past_payments[display_cols], hide_index=True, use_container_width=True)
                else:
                    if transaction_nature == "📥 Collect Funds (In)":
                        st.success(f"✅ No past records found. Ready to process collection for {pure_name}.")
                    else:
                        st.error(f"🚫 **Action Blocked:** No collection record found for {pure_name} under {collection_type}. You cannot process a return.")
                        allow_submission = False

    st.write("")
    submit_button = st.button("✅ Record Transaction", type="primary", use_container_width=True, disabled=not allow_submission)
    
    if submit_button:
        if not selected_display:
            st.error("Please find and select a valid student first.")
        elif amount <= 0:
            st.warning("Please enter an amount greater than 0.")
        else:
            with st.spinner("Logging transaction to Google Sheets..."):
                try:
                    final_amount = amount if transaction_nature == "📥 Collect Funds (In)" else -amount
                    
                    current_time = datetime.now(IST).time()
                    final_datetime_ist = datetime.combine(receipt_date, current_time).strftime("%Y-%m-%d %H:%M:%S")
                    final_section = str(student_info['Section'])
                    
                    if st.session_state.user_role == "admin":
                        if actual_collector == st.session_state.user_name:
                            handover_status = "Settled"
                        else:
                            handover_status = "Handed Over"
                    else:
                        handover_status = "Pending"
                    
                    new_row = [
                        final_datetime_ist, 
                        pure_name, 
                        final_class, 
                        final_section, 
                        roll_no, 
                        final_amount, 
                        payer_type, 
                        actual_collector,
                        collection_type,
                        handover_status 
                    ]
                    
                    gc_write = get_gspread_client()
                    ws_fees_write = gc_write.open("SCH_Exam_Fees").worksheet("Sheet1")
                    ws_fees_write.append_row(new_row)
                    
                    load_data.clear()
                    
                    action_word = "collected from" if final_amount > 0 else "returned to"
                    st.success(f"✅ Successfully {action_word} {pure_name} (₹{abs(final_amount)} for {collection_type})!")
                    st.rerun() 
                except Exception as e:
                    st.error(f"An error occurred while saving the data: {e}")


# ==========================================
# TAB 2: LIVE DASHBOARD
# ==========================================
with tab2:
    st.subheader("Collection Overview")
    
    if st.button("🔄 Refresh Dashboard Data"):
        load_data.clear()
        st.rerun()
        
    dash_df = df_fees.copy()
    
    # ----------------------------------------------------
    # ASSISTANT TEACHER DASHBOARD VIEW
    # ----------------------------------------------------
    if st.session_state.user_role != "admin":
        if not dash_df.empty:
            dash_df = dash_df[dash_df['Teacher_Involved'].astype(str).str.strip() == st.session_state.user_name]
        
        st.caption(f"Showing personal transactions managed by: **{st.session_state.user_name}**")
        
        if not dash_df.empty and 'Amount' in dash_df.columns:
            dash_df['Amount'] = pd.to_numeric(dash_df['Amount'], errors='coerce').fillna(0)
            
            gross_coll = dash_df[dash_df['Amount'] > 0]['Amount'].sum()
            total_ret = abs(dash_df[dash_df['Amount'] < 0]['Amount'].sum())
            net_pending = dash_df[dash_df['Handover_Status'] == 'Pending']['Amount'].sum()
            handed_over = dash_df[dash_df['Handover_Status'] == 'Handed Over']['Amount'].sum()
            
            col_t1, col_t2, col_t3 = st.columns(3)
            col_t1.metric("💰 Gross Collected", f"₹ {gross_coll:,.2f}", help="Total cash taken in before returns.")
            col_t2.metric("🤝 Handed to Head Sir", f"₹ {handed_over:,.2f}", help="Total cash given to admin.")
            col_t3.metric("💵 Net Cash in Hand", f"₹ {net_pending:,.2f}", delta=f"-₹{total_ret:,.0f} Returned", delta_color="normal")
            
            st.divider()
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("##### ✅ Handed Over to Head Sir")
                handed_df = dash_df[dash_df['Handover_Status'] == 'Handed Over']
                if not handed_df.empty:
                    st.dataframe(handed_df[['Date', 'Name', 'Class', 'Amount', 'Collection Type']], hide_index=True)
                else:
                    st.info("No funds handed over yet.")
            
            with c2:
                st.markdown("##### ⏳ Cash in Hand Ledger")
                pend_df = dash_df[dash_df['Handover_Status'] == 'Pending']
                if not pend_df.empty:
                    st.dataframe(pend_df[['Date', 'Name', 'Class', 'Amount', 'Collection Type']], hide_index=True)
                else:
                    st.success("All clear! No pending cash.")
        else:
            st.info(f"No data collected by you ({st.session_state.user_name}) yet.")

    # ----------------------------------------------------
    # HEAD TEACHER (ADMIN) DASHBOARD VIEW
    # ----------------------------------------------------
    else:
        st.caption("Showing **All School Transactions** (Head Teacher View)")
            
        if not dash_df.empty and 'Amount' in dash_df.columns:
            dash_df['Amount'] = pd.to_numeric(dash_df['Amount'], errors='coerce').fillna(0)
            
            # Accurate Admin Accounting
            admin_collected = dash_df[dash_df['Teacher_Involved'] == 'SUKHAMAY KISKU']['Amount'].sum()
            teachers_handed_over = dash_df[dash_df['Handover_Status'] == 'Handed Over']['Amount'].sum()
            admin_cash = admin_collected + teachers_handed_over
            total_pending = dash_df[dash_df['Handover_Status'] == 'Pending']['Amount'].sum()
            total_school_net = dash_df['Amount'].sum()
            total_returns = abs(dash_df[dash_df['Amount'] < 0]['Amount'].sum())
            
            col_dash1, col_dash2, col_dash3 = st.columns(3)
            col_dash1.metric("💰 Net School Funds", f"₹ {total_school_net:,.2f}", delta=f"-₹{total_returns:,.0f} Total Returned", delta_color="normal")
            col_dash2.metric("🏦 Admin Cash in Hand", f"₹ {admin_cash:,.2f}")
            col_dash3.metric("💵 Pending with Teachers", f"₹ {total_pending:,.2f}")
    
            st.divider()

            # --- EXPECTED FEE TARGET SUMMARY ---
            st.markdown("##### 🏫 Expected Fee Target Summary")
            st.info("""
            **BHAGYABANTAPUR PRY. SCHOOL**  
            Class PP (14) @₹7 = ₹98  
            Class I (46) @₹6 = ₹276  
            Class II (41) @₹6 = ₹246  
            Class III (24) @₹7 = ₹168  
            Class IV (44) @₹7 = ₹308  
            Class V (17) @₹7 = ₹119  
            **TOTAL (186) : ₹1,215**
            """)
            
            st.divider()
            
            # --- CLASS-WISE LIST & TOTALS ---
            st.markdown("##### 📋 Class-wise Student List & Totals")
            if 'Collection Type' in dash_df.columns:
                ctypes = ["All"] + list(dash_df['Collection Type'].dropna().unique())
                selected_type = st.selectbox("Filter by Collection Type:", ctypes)
                filter_df = dash_df if selected_type == "All" else dash_df[dash_df['Collection Type'] == selected_type]
            else:
                filter_df = dash_df

            if not filter_df.empty:
                # Custom logic to force natural sorting of standard class names
                class_order = {"CLASS PP": 0, "CLASS I": 1, "CLASS II": 2, "CLASS III": 3, "CLASS IV": 4, "CLASS V": 5}
                found_classes = [c for c in filter_df['Class'].unique() if str(c).strip()]
                found_classes.sort(key=lambda x: class_order.get(x, 99))
                
                for cls in found_classes:
                    cls_df = filter_df[filter_df['Class'] == cls].copy()
                    
                    # Force Roll to numeric so it sorts naturally (1, 2, 3... instead of 1, 10, 2)
                    cls_df['Roll_Num'] = pd.to_numeric(cls_df['Roll'], errors='coerce').fillna(999)
                    cls_df = cls_df.sort_values('Roll_Num')
                    
                    cls_total = cls_df['Amount'].sum()
                    unique_students = cls_df[cls_df['Amount'] > 0]['Name'].nunique() 
                    
                    with st.expander(f"📖 {cls} | Total Received: ₹ {cls_total:,.2f} | Paid By: {unique_students} Students"):
                        display_cols = ['Date', 'Roll', 'Name', 'Amount']
                        if selected_type == "All" and 'Collection Type' in cls_df.columns:
                            display_cols.append('Collection Type')
                        display_cols.append('Teacher_Involved')
                        
                        st.dataframe(cls_df[display_cols], hide_index=True, use_container_width=True)
            else:
                st.info("No collections found.")
            
            st.divider()
            
            # --- TEACHER HANDOVER LEDGER ---
            st.markdown("##### 👨‍🏫 Teacher Handover Ledger")
            def calc_teacher_stats(group):
                gross = group[group['Amount'] > 0]['Amount'].sum()
                ret = abs(group[group['Amount'] < 0]['Amount'].sum())
                handed = group[group['Handover_Status'].isin(['Handed Over', 'Settled'])]['Amount'].sum()
                pend = group[group['Handover_Status'] == 'Pending']['Amount'].sum()
                return pd.Series({'Gross Collected': gross, 'Total Returned': ret, 'Handed Over to HT': handed, 'Net Pending Cash': pend})
    
            teacher_summary = dash_df.groupby('Teacher_Involved').apply(calc_teacher_stats).reset_index()
            st.dataframe(teacher_summary, hide_index=True, use_container_width=True)
            
            st.markdown("##### 📜 Detailed Handover Log")
            handed_over_df = dash_df[dash_df['Handover_Status'] == 'Handed Over']
            if not handed_over_df.empty:
                st.dataframe(handed_over_df[['Date', 'Teacher_Involved', 'Name', 'Class', 'Amount', 'Collection Type']], hide_index=True)
            else:
                st.info("No cash has been handed over by teachers yet.")
                
            st.divider()
            st.markdown("##### 📈 Net Funds by Class & Collection Type")
            if 'Collection Type' in dash_df.columns:
                class_totals = dash_df.groupby(['Class', 'Collection Type'])['Amount'].sum().reset_index()
                fig = px.bar(
                    class_totals, 
                    x='Class', 
                    y='Amount', 
                    color='Collection Type',
                    text_auto=True,
                    barmode='group',
                    color_discrete_sequence=px.colors.qualitative.Set2
                )
                fig.update_layout(xaxis_title="Class", yaxis_title="Net Amount (₹)")
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
                fig.update_layout(xaxis_title="Class", yaxis_title="Net Amount (₹)", showlegend=False)
                
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.info("No data available yet. Transactions will appear here once recorded.")

# ==========================================
# TAB 3: ADMIN HANDOVER MANAGER (ADMIN ONLY)
# ==========================================
if st.session_state.user_role == "admin":
    with tab3:
        st.subheader("🤝 Cash Handover Manager")
        st.markdown("Select an assistant teacher to securely receive and verify their pending cash.")
        
        if not df_fees.empty and 'Handover_Status' in df_fees.columns:
            handover_col_idx = df_fees.columns.get_loc('Handover_Status') + 1
            
            df_fees['Amount'] = pd.to_numeric(df_fees['Amount'], errors='coerce').fillna(0)
            pending_df = df_fees[df_fees['Handover_Status'] == 'Pending'].copy()
            
            if not pending_df.empty:
                teachers_with_cash = pending_df['Teacher_Involved'].unique()
                selected_teacher = st.selectbox("Select Teacher to receive cash from:", teachers_with_cash)
                
                teacher_pending = pending_df[pending_df['Teacher_Involved'] == selected_teacher].copy()
                teacher_pending.insert(0, 'Receive', False)
                
                total_owed = teacher_pending['Amount'].sum()
                st.markdown(f"### Net Pending Cash with {selected_teacher}: **₹ {total_owed:,.2f}**")
                st.caption("Check the boxes next to the transactions (both collections and returns) you are processing, then click Confirm.")
                
                edited_df = st.data_editor(
                    teacher_pending[['Receive', 'Date', 'Name', 'Class', 'Amount', 'Collection Type', '_Row_Num']],
                    hide_index=True,
                    disabled=['Date', 'Name', 'Class', 'Amount', 'Collection Type', '_Row_Num'],
                    column_config={'_Row_Num': None}
                )
                
                selected_rows = edited_df[edited_df['Receive'] == True]
                
                if not selected_rows.empty:
                    receiving_amount = selected_rows['Amount'].sum()
                    st.success(f"Ready to reconcile **₹ {receiving_amount:,.2f}** ({len(selected_rows)} transactions).")
                    
                    if st.button("✅ Confirm Receipt of Cash", type="primary"):
                        with st.spinner(f"Verifying receipt of cash from {selected_teacher}..."):
                            try:
                                gc_write = get_gspread_client()
                                ws_fees_write = gc_write.open("SCH_Exam_Fees").worksheet("Sheet1")
                                
                                for r_num in selected_rows['_Row_Num']:
                                    ws_fees_write.update_cell(r_num, handover_col_idx, 'Handed Over')
                                
                                load_data.clear()
                                st.success("Cash securely reconciled and recorded!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to update Google Sheets: {e}")
            else:
                st.success("🎉 All clear! There is no pending cash to receive from any assistant teachers.")
        else:
            st.info("System is waiting for 'Handover_Status' configuration or there is no data available.")
