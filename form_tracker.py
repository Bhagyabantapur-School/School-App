import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import gspread
from google.oauth2.service_account import Credentials

# --- 1. CONFIGURATION & STYLING ---
st.set_page_config(page_title="BPS Form Tracker", page_icon="📝", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 2rem; max-width: 1100px;}
        .alert-box { padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 5px solid; }
        .alert-success { background-color: #d4edda; border-color: #28a745; color: #155724; }
        .alert-warning { background-color: #fff3cd; border-color: #ffc107; color: #856404; }
        .alert-danger { background-color: #f8d7da; border-color: #dc3545; color: #721c24; }
        .alert-info { background-color: #e2e3e5; border-color: #6c757d; color: #383d41; }
        .stButton>button { border-radius: 8px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.title("📝 BPS Form Distribution & Return Tracker")

# --- 2. TIME & HELPERS ---
utc_now = datetime.utcnow()
now = utc_now + timedelta(hours=5, minutes=30)
curr_date_str = now.strftime("%d-%m-%Y")

# --- 3. DATABASE CONNECTION ---
@st.cache_resource
def init_gsheets():
    try:
        skey = dict(st.secrets["gcp_service_account"])
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        credentials = Credentials.from_service_account_info(skey, scopes=scopes)
        gc = gspread.authorize(credentials)
        return gc.open("BPS_Database")
    except Exception as e:
        st.error("⚠️ Google Sheets Connection Failed! Check Streamlit Secrets.")
        st.stop()

sh = init_gsheets()

@st.cache_data(ttl=5)
def fetch_sheet_data(sheet_name):
    try:
        ws = sh.worksheet(sheet_name)
        df = pd.DataFrame(ws.get_all_records())
        return df
    except:
        return pd.DataFrame()

def clear_cache():
    fetch_sheet_data.clear()

def overwrite_sheet_df(sheet_name, df):
    try: ws = sh.worksheet(sheet_name)
    except: ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=20)
    ws.clear()
    df = df.fillna("").astype(str)
    if not df.empty:
        ws.update(values=[df.columns.values.tolist()] + df.values.tolist(), range_name='A1')
    clear_cache()

def append_sheet_df(sheet_name, df):
    if df.empty: return
    try: ws = sh.worksheet(sheet_name)
    except:
        ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=20)
        ws.append_row(list(df.columns))
    df = df.fillna("").astype(str)
    ws.append_rows(df.values.tolist())
    clear_cache()

def get_local_csv(file):
    if os.path.exists(file): 
        try: return pd.read_csv(file)
        except: return pd.DataFrame()
    return pd.DataFrame()

# --- 4. LOAD DATA (Upgraded to handle Return columns) ---
students_df = get_local_csv('students.csv')
if not students_df.empty and 'Section' not in students_df.columns: 
    students_df['Section'] = 'A'

mdm_df = fetch_sheet_data('mdm_log')
if mdm_df.empty:
    mdm_df = pd.DataFrame(columns=['Date', 'Teacher', 'Class', 'Section', 'Roll', 'Name', 'Time', 'UID'])
else:
    mdm_df['UID'] = mdm_df['Class'].astype(str) + "_" + mdm_df['Section'].astype(str) + "_" + mdm_df['Roll'].astype(str)

form_df = fetch_sheet_data('form_distribution_log')

# ADDED NEW COLUMNS for tracking returns
expected_columns = [
    'Class', 'Section', 'Roll', 'Student Name', 
    'Date (form generated)', 'Date (receive form)', 
    'Date (returned)', 'Return Status'
]

if form_df.empty:
    form_df = pd.DataFrame(columns=expected_columns + ['UID'])
else:
    # Auto-upgrade existing database with new columns
    for col in expected_columns:
        if col not in form_df.columns:
            if col == 'Return Status' or col == 'Date (returned)':
                form_df[col] = "Pending"
            else:
                form_df[col] = ""
    form_df['UID'] = form_df['Class'].astype(str) + "_" + form_df['Section'].astype(str) + "_" + form_df['Roll'].astype(str)

# --- 5. UI TABS ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🖨️ 1. Generated", 
    "🤝 2. Distribute", 
    "📥 3. Returns", 
    "📊 4. Master Log", 
    "📈 5. Summary"
])

# ==========================================
# TAB 1: LOG PRINTED FORMS
# ==========================================
with tab1:
    st.subheader("Step 1: Record Generated Forms")
    if students_df.empty:
        st.warning("No student data found in students.csv.")
    else:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            classes = sorted(students_df['Class'].dropna().unique())
            sel_class = st.selectbox("Select Class", classes, key="t1_c")
        with col2:
            sections = sorted(students_df[students_df['Class'] == sel_class]['Section'].unique())
            sel_sec = st.selectbox("Select Section", sections, key="t1_s")
        with col3:
            gen_date_obj = st.date_input("Generation Date", now.date())
            gen_date_str = gen_date_obj.strftime("%d-%m-%Y")
            
        filtered_students = students_df[(students_df['Class'] == sel_class) & (students_df['Section'] == sel_sec)]
        
        st.write(f"**Select students whose forms were generated on {gen_date_str}:**")
        select_all = st.checkbox("Select All Students in this Section")
        
        if select_all:
            selected_idx = filtered_students.index.tolist()
        else:
            selected_idx = st.multiselect(
                "Choose specific students:", 
                filtered_students.index, 
                format_func=lambda i: f"Roll {filtered_students.loc[i].get('Roll', 'N/A')} - {filtered_students.loc[i]['Name']}"
            )
            
        if st.button("💾 Save to Generated Database", type="primary"):
            if selected_idx:
                new_logs = []
                for i in selected_idx:
                    row = filtered_students.loc[i]
                    uid = f"{row['Class']}_{row['Section']}_{row['Roll']}"
                    
                    is_duplicate = False
                    if not form_df.empty:
                        existing = form_df[(form_df['UID'] == uid) & (form_df['Date (receive form)'] == "Pending")]
                        if not existing.empty: is_duplicate = True
                    
                    if not is_duplicate:
                        new_logs.append({
                            'Class': row['Class'], 
                            'Section': row['Section'], 
                            'Roll': row['Roll'], 
                            'Student Name': row['Name'], 
                            'Date (form generated)': gen_date_str, 
                            'Date (receive form)': 'Pending',
                            'Date (returned)': 'Pending',
                            'Return Status': 'Pending'
                        })
                
                if new_logs:
                    append_sheet_df('form_distribution_log', pd.DataFrame(new_logs))
                    st.success(f"✅ {len(new_logs)} forms marked as Generated on {gen_date_str} for {sel_class} - {sel_sec}!")
                    st.rerun() 
                else:
                    st.warning("All selected students already have a 'Pending' form in the database.")
            else:
                st.error("Please select at least one student.")

# ==========================================
# TAB 2: MDM AUTO-DISTRIBUTE
# ==========================================
with tab2:
    st.subheader("Step 2: Sync with MDM & Auto-Distribute")
    
    if students_df.empty:
        st.warning("No student data found in students.csv.")
    else:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            classes_t2 = sorted(students_df['Class'].dropna().unique())
            sel_class_t2 = st.selectbox("Select Class", classes_t2, key="t2_c")
        with col2:
            sections_t2 = sorted(students_df[students_df['Class'] == sel_class_t2]['Section'].unique())
            sel_sec_t2 = st.selectbox("Select Section", sections_t2, key="t2_s")
        with col3:
            sync_date_obj = st.date_input("Select MDM Date to Sync", now.date(), key="t2_d")
            sync_date_str = sync_date_obj.strftime("%d-%m-%Y")
        
        st.info(f"Looking for **{sel_class_t2} - {sel_sec_t2}** students who ate MDM on **{sync_date_str}** and have a Pending form.")
        
        if mdm_df.empty:
            st.error("No MDM data found in the database. Please ensure teachers have submitted MDM.")
        else:
            target_mdm = mdm_df[
                (mdm_df['Date'].astype(str) == sync_date_str) & 
                (mdm_df['Class'].astype(str) == str(sel_class_t2)) & 
                (mdm_df['Section'].astype(str) == str(sel_sec_t2))
            ]
            
            if target_mdm.empty:
                st.warning(f"No MDM entries found for {sel_class_t2} - {sel_sec_t2} on the selected date ({sync_date_str}).")
            else:
                target_mdm_uids = target_mdm['UID'].tolist()
                
                pending_forms = form_df[
                    (form_df['Date (receive form)'] == 'Pending') & 
                    (form_df['Class'].astype(str) == str(sel_class_t2)) & 
                    (form_df['Section'].astype(str) == str(sel_sec_t2))
                ]
                pending_uids = pending_forms['UID'].tolist() if not pending_forms.empty else []
                
                ready_to_distribute = pending_forms[pending_forms['UID'].isin(target_mdm_uids)].copy()
                mdm_no_form_uids = [u for u in target_mdm_uids if u not in pending_uids]
                missing_forms = target_mdm[target_mdm['UID'].isin(mdm_no_form_uids)]
                absent_forms = pending_forms[~pending_forms['UID'].isin(target_mdm_uids)]
                
                st.divider()
                
                st.markdown(f"<div class='alert-box alert-success'><h4>✅ Ready to Distribute ({len(ready_to_distribute)})</h4><p>These students have forms printed AND are present for MDM today. Uncheck anyone who didn't actually receive the form.</p></div>", unsafe_allow_html=True)
                if not ready_to_distribute.empty:
                    ready_to_distribute['Distributed'] = True
                    
                    edited_ready_df = st.data_editor(
                        ready_to_distribute[['Distributed', 'Class', 'Section', 'Roll', 'Student Name', 'Date (form generated)']],
                        hide_index=True,
                        use_container_width=True,
                        disabled=['Class', 'Section', 'Roll', 'Student Name', 'Date (form generated)']
                    )
                    
                    if st.button(f"📦 Confirm Distribution & Update Database for {sel_class_t2} - {sel_sec_t2}", type="primary"):
                        actually_distributed = edited_ready_df[edited_ready_df['Distributed'] == True]
                        
                        if not actually_distributed.empty:
                            confirmed_uids = ready_to_distribute.loc[actually_distributed.index, 'UID'].tolist()
                            
                            updated_form_df = form_df.copy()
                            mask = (updated_form_df['UID'].isin(confirmed_uids)) & (updated_form_df['Date (receive form)'] == 'Pending')
                            updated_form_df.loc[mask, 'Date (receive form)'] = sync_date_str
                            
                            updated_form_df = updated_form_df.drop(columns=['UID'], errors='ignore')
                            overwrite_sheet_df('form_distribution_log', updated_form_df)
                            
                            st.success(f"Database updated! {len(confirmed_uids)} Forms safely marked as received on {sync_date_str}.")
                            st.rerun()
                        else:
                            st.warning("No students were selected for distribution.")

                st.markdown(f"<div class='alert-box alert-warning'><h4>⚠️ Present but NO FORM ({len(missing_forms)})</h4><p>These students ate MDM, but no form has been generated for them yet.</p></div>", unsafe_allow_html=True)
                if not missing_forms.empty:
                    st.dataframe(missing_forms[['Class', 'Section', 'Roll', 'Name']], hide_index=True, use_container_width=True)

                st.markdown(f"<div class='alert-box alert-info'><h4>📭 Form Pending but ABSENT ({len(absent_forms)})</h4><p>Forms are printed, but these students did not eat MDM. Do not distribute.</p></div>", unsafe_allow_html=True)
                if not absent_forms.empty:
                    st.dataframe(absent_forms[['Class', 'Section', 'Roll', 'Student Name']], hide_index=True, use_container_width=True)

# ==========================================
# TAB 3: LOG RETURNED FORMS
# ==========================================
with tab3:
    st.subheader("Step 3: Log Returned & Checked Forms")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        classes_t3 = sorted(students_df['Class'].dropna().unique())
        sel_class_t3 = st.selectbox("Select Class", classes_t3, key="t3_c")
    with col2:
        sections_t3 = sorted(students_df[students_df['Class'] == sel_class_t3]['Section'].unique())
        sel_sec_t3 = st.selectbox("Select Section", sections_t3, key="t3_s")
    with col3:
        ret_date_obj = st.date_input("Return Date", now.date(), key="t3_d")
        ret_date_str = ret_date_obj.strftime("%d-%m-%Y")
        
    # Only show students who HAVE received the form, but are NOT YET Complete.
    if not form_df.empty:
        return_target_df = form_df[
            (form_df['Date (receive form)'] != 'Pending') & 
            (form_df['Return Status'] != 'Complete') & 
            (form_df['Class'].astype(str) == str(sel_class_t3)) & 
            (form_df['Section'].astype(str) == str(sel_sec_t3))
        ].copy()
        
        if return_target_df.empty:
            st.success(f"All distributed forms for {sel_class_t3} - {sel_sec_t3} have been returned and marked Complete!")
        else:
            st.info(f"Showing students who received their form. Update their status below.")
            
            # Interactive Data Editor with Dropdowns for Status
            edited_returns = st.data_editor(
                return_target_df[['Roll', 'Student Name', 'Return Status', 'Date (receive form)']],
                column_config={
                    "Return Status": st.column_config.SelectboxColumn(
                        "Review Status",
                        help="Select the status of the returned form",
                        width="medium",
                        options=["Pending", "Complete", "Incomplete"],
                        required=True
                    )
                },
                hide_index=True,
                use_container_width=True,
                disabled=['Roll', 'Student Name', 'Date (receive form)']
            )
            
            if st.button(f"💾 Save Return Updates for {sel_class_t3} - {sel_sec_t3}", type="primary"):
                updated_form_df = form_df.copy()
                changes_made = 0
                
                # Compare edited rows with original
                for idx in return_target_df.index:
                    old_status = return_target_df.loc[idx, 'Return Status']
                    new_status = edited_returns.loc[idx, 'Return Status']
                    
                    if old_status != new_status:
                        updated_form_df.loc[idx, 'Return Status'] = new_status
                        # If status changed to Complete/Incomplete, update the date. If back to pending, reset date.
                        if new_status in ['Complete', 'Incomplete']:
                            updated_form_df.loc[idx, 'Date (returned)'] = ret_date_str
                        else:
                            updated_form_df.loc[idx, 'Date (returned)'] = "Pending"
                        changes_made += 1
                
                if changes_made > 0:
                    updated_form_df = updated_form_df.drop(columns=['UID'], errors='ignore')
                    overwrite_sheet_df('form_distribution_log', updated_form_df)
                    st.success(f"✅ Successfully updated {changes_made} return records!")
                    st.rerun()
                else:
                    st.warning("No status changes were made.")

# ==========================================
# TAB 4: MASTER LOG
# ==========================================
with tab4:
    st.subheader("Database View: form_distribution_log")
    if not form_df.empty:
        display_df = form_df.drop(columns=['UID'], errors='ignore')
        st.dataframe(display_df, hide_index=True, use_container_width=True)
        
        col_csv, col_clear = st.columns([1, 1])
        with col_csv:
            st.download_button("📥 Download Master Log CSV", display_df.to_csv(index=False).encode('utf-8'), "BPS_Master_Log.csv", "text/csv")
        with col_clear:
            with st.expander("⚠ Emergency Reset"):
                if st.button("Clear Distribution Database"):
                    overwrite_sheet_df('form_distribution_log', pd.DataFrame(columns=expected_columns))
                    st.success("Database Cleared!")
                    st.rerun()
    else:
        st.info("No forms have been logged yet.")

# ==========================================
# TAB 5: SUMMARY & PROGRESS
# ==========================================
with tab5:
    st.subheader("📈 Class-Wise Distribution & Return Summary")
    
    if students_df.empty:
        st.warning("No student data found to generate a summary.")
    else:
        summary_df = students_df.groupby(['Class', 'Section']).size().reset_index(name='Total Students')
        
        if not form_df.empty:
            gen_counts = form_df.groupby(['Class', 'Section']).size().reset_index(name='Forms Generated')
            
            dist_df = form_df[form_df['Date (receive form)'] != 'Pending']
            dist_counts = dist_df.groupby(['Class', 'Section']).size().reset_index(name='Distributed')
            
            # New Calculations for Returns
            comp_df = form_df[form_df['Return Status'] == 'Complete']
            comp_counts = comp_df.groupby(['Class', 'Section']).size().reset_index(name='Returned (Complete)')
            
            incomp_df = form_df[form_df['Return Status'] == 'Incomplete']
            incomp_counts = incomp_df.groupby(['Class', 'Section']).size().reset_index(name='Returned (Incomplete)')
            
            summary_df = pd.merge(summary_df, gen_counts, on=['Class', 'Section'], how='left').fillna(0)
            summary_df = pd.merge(summary_df, dist_counts, on=['Class', 'Section'], how='left').fillna(0)
            summary_df = pd.merge(summary_df, comp_counts, on=['Class', 'Section'], how='left').fillna(0)
            summary_df = pd.merge(summary_df, incomp_counts, on=['Class', 'Section'], how='left').fillna(0)
            
            # Form Math
            summary_df['Outstanding (With Guardian)'] = summary_df['Distributed'] - (summary_df['Returned (Complete)'] + summary_df['Returned (Incomplete)'])
            summary_df['Pending Desk Stack'] = summary_df['Forms Generated'] - summary_df['Distributed']
            summary_df['Not Generated Yet'] = summary_df['Total Students'] - summary_df['Forms Generated']
            
            cols_to_int = ['Total Students', 'Forms Generated', 'Distributed', 'Returned (Complete)', 'Returned (Incomplete)', 'Outstanding (With Guardian)', 'Pending Desk Stack', 'Not Generated Yet']
            for col in cols_to_int:
                summary_df[col] = summary_df[col].astype(int)
        else:
            for col in ['Forms Generated', 'Distributed', 'Returned (Complete)', 'Returned (Incomplete)', 'Outstanding (With Guardian)', 'Pending Desk Stack']:
                summary_df[col] = 0
            summary_df['Not Generated Yet'] = summary_df['Total Students']

        # Custom Sorting
        custom_dict = {
            'CLASS PP': 0, 'PP': 0,
            'CLASS I': 1, 'I': 1,
            'CLASS II': 2, 'II': 2,
            'CLASS III': 3, 'III': 3,
            'CLASS IV': 4, 'IV': 4,
            'CLASS V': 5, 'V': 5
        }
        
        summary_df['Sort_Order'] = summary_df['Class'].map(custom_dict).fillna(99)
        summary_df = summary_df.sort_values(by=['Sort_Order', 'Section']).drop(columns=['Sort_Order'])

        # Total Row
        total_row = pd.DataFrame([{
            'Class': 'TOTAL',
            'Section': '',
            'Total Students': summary_df['Total Students'].sum(),
            'Forms Generated': summary_df['Forms Generated'].sum(),
            'Distributed': summary_df['Distributed'].sum(),
            'Returned (Complete)': summary_df['Returned (Complete)'].sum(),
            'Returned (Incomplete)': summary_df['Returned (Incomplete)'].sum(),
            'Outstanding (With Guardian)': summary_df['Outstanding (With Guardian)'].sum(),
            'Pending Desk Stack': summary_df['Pending Desk Stack'].sum(),
            'Not Generated Yet': summary_df['Not Generated Yet'].sum()
        }])
        
        summary_df = pd.concat([summary_df, total_row], ignore_index=True)

        # Top Level Metrics UI
        st.markdown("##### Overall School Progress")
        
        # Row 1 of metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Students", summary_df.loc[summary_df['Class'] == 'TOTAL', 'Total Students'].values[0])
        m2.metric("Forms Generated", summary_df.loc[summary_df['Class'] == 'TOTAL', 'Forms Generated'].values[0])
        m3.metric("Forms Distributed", summary_df.loc[summary_df['Class'] == 'TOTAL', 'Distributed'].values[0])
        
        # Row 2 of metrics
        st.markdown("<br>", unsafe_allow_html=True)
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("✅ Complete Returns", summary_df.loc[summary_df['Class'] == 'TOTAL', 'Returned (Complete)'].values[0])
        r2.metric("⚠️ Incomplete Returns", summary_df.loc[summary_df['Class'] == 'TOTAL', 'Returned (Incomplete)'].values[0])
        r3.metric("🏠 Outstanding with Guardian", summary_df.loc[summary_df['Class'] == 'TOTAL', 'Outstanding (With Guardian)'].values[0])
        r4.metric("📭 Desk Stack (Not Given)", summary_df.loc[summary_df['Class'] == 'TOTAL', 'Pending Desk Stack'].values[0])
        
        st.divider()
        
        st.markdown("##### Detailed Breakdown by Section")
        st.dataframe(summary_df, hide_index=True, use_container_width=True)
        
        st.download_button("📥 Download Summary Report", summary_df.to_csv(index=False).encode('utf-8'), f"BPS_Return_Summary_Report_{curr_date_str}.csv", "text/csv")
