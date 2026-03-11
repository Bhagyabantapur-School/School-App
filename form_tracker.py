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
        .block-container { padding-top: 2rem; max-width: 1000px;}
        .alert-box { padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 5px solid; }
        .alert-success { background-color: #d4edda; border-color: #28a745; color: #155724; }
        .alert-warning { background-color: #fff3cd; border-color: #ffc107; color: #856404; }
        .alert-info { background-color: #e2e3e5; border-color: #6c757d; color: #383d41; }
        .stButton>button { border-radius: 8px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.title("📝 BPS Form Distribution Tracker")

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

# --- 4. LOAD DATA ---
students_df = get_local_csv('students.csv')
if not students_df.empty and 'Section' not in students_df.columns: 
    students_df['Section'] = 'A'

mdm_df = fetch_sheet_data('mdm_log')
if not mdm_df.empty:
    mdm_df['UID'] = mdm_df['Class'].astype(str) + "_" + mdm_df['Section'].astype(str) + "_" + mdm_df['Roll'].astype(str)

form_df = fetch_sheet_data('form_distribution_log')
expected_columns = ['Class', 'Section', 'Roll', 'Student Name', 'Date (form generated)', 'Date (receive form)']

if form_df.empty:
    form_df = pd.DataFrame(columns=expected_columns)
else:
    # Ensure all expected columns exist
    for col in expected_columns:
        if col not in form_df.columns:
            form_df[col] = ""
    form_df['UID'] = form_df['Class'].astype(str) + "_" + form_df['Section'].astype(str) + "_" + form_df['Roll'].astype(str)

# --- 5. UI TABS ---
tab1, tab2, tab3 = st.tabs(["🖨️ 1. Log Generated Forms", "🤝 2. MDM Auto-Distribute", "📊 3. Master Log"])

# ==========================================
# TAB 1: LOG PRINTED FORMS
# ==========================================
with tab1:
    st.subheader("Step 1: Record Generated Forms")
    if students_df.empty:
        st.warning("No student data found in students.csv.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            classes = sorted(students_df['Class'].dropna().unique())
            sel_class = st.selectbox("Select Class", classes, key="t1_c")
        with col2:
            sections = sorted(students_df[students_df['Class'] == sel_class]['Section'].unique())
            sel_sec = st.selectbox("Select Section", sections, key="t1_s")
            
        filtered_students = students_df[(students_df['Class'] == sel_class) & (students_df['Section'] == sel_sec)]
        
        st.write(f"**Select students whose forms were generated today ({curr_date_str}):**")
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
                    
                    # Prevent duplicate active generation logs
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
                            'Date (form generated)': curr_date_str, 
                            'Date (receive form)': 'Pending'
                        })
                
                if new_logs:
                    append_sheet_df('form_distribution_log', pd.DataFrame(new_logs))
                    st.success(f"✅ {len(new_logs)} forms marked as Generated for {sel_class} - {sel_sec}!")
                else:
                    st.warning("All selected students already have a 'Pending' form in the database.")
            else:
                st.error("Please select at least one student.")

# ==========================================
# TAB 2: MDM AUTO-DISTRIBUTE
# ==========================================
with tab2:
    st.subheader(f"Step 2: Sync with Today's MDM ({curr_date_str})")
    
    if st.button("🔄 Check MDM & Distribute", type="primary"):
        if mdm_df.empty:
            st.error("No MDM data found. Please ensure teachers have submitted MDM for today.")
        else:
            today_mdm = mdm_df[mdm_df['Date'].astype(str) == curr_date_str]
            if today_mdm.empty:
                st.warning(f"No MDM entries found for today ({curr_date_str}).")
            else:
                today_mdm_uids = today_mdm['UID'].tolist()
                
                pending_forms = form_df[form_df['Date (receive form)'] == 'Pending']
                pending_uids = pending_forms['UID'].tolist() if not pending_forms.empty else []
                
                # 1. MATCH: In MDM and has Pending Form
                ready_to_distribute = pending_forms[pending_forms['UID'].isin(today_mdm_uids)].copy()
                
                # 2. MISSING FORM: In MDM but NO Pending Form
                mdm_no_form_uids = [u for u in today_mdm_uids if u not in pending_uids]
                missing_forms = today_mdm[today_mdm['UID'].isin(mdm_no_form_uids)]
                
                # 3. ABSENT: Has Pending Form but NOT in MDM
                absent_forms = pending_forms[~pending_forms['UID'].isin(today_mdm_uids)]
                
                st.divider()
                
                # UI: Ready to Distribute
                st.markdown(f"<div class='alert-box alert-success'><h4>✅ Ready to Distribute ({len(ready_to_distribute)})</h4><p>These students have forms printed AND are present for MDM today.</p></div>", unsafe_allow_html=True)
                if not ready_to_distribute.empty:
                    st.dataframe(ready_to_distribute[['Class', 'Section', 'Roll', 'Student Name', 'Date (form generated)']], hide_index=True, use_container_width=True)
                    
                    if st.button("📦 Confirm Distribution & Update Database", type="primary"):
                        updated_form_df = form_df.copy()
                        # Mark 'Date (receive form)' as today for the matched UIDs
                        mask = (updated_form_df['UID'].isin(today_mdm_uids)) & (updated_form_df['Date (receive form)'] == 'Pending')
                        updated_form_df.loc[mask, 'Date (receive form)'] = curr_date_str
                        
                        # Clean up the UID column before pushing to cloud
                        updated_form_df = updated_form_df.drop(columns=['UID'], errors='ignore')
                        overwrite_sheet_df('form_distribution_log', updated_form_df)
                        st.success("Database updated! Forms safely marked as received.")
                        st.rerun()

                # UI: Missing Form Alert
                st.markdown(f"<div class='alert-box alert-warning'><h4>⚠️ Present but NO FORM ({len(missing_forms)})</h4><p>These students are eating MDM today, but no form has been generated for them yet.</p></div>", unsafe_allow_html=True)
                if not missing_forms.empty:
                    st.dataframe(missing_forms[['Class', 'Section', 'Roll', 'Name']], hide_index=True, use_container_width=True)

                # UI: Absent Alert
                st.markdown(f"<div class='alert-box alert-info'><h4>📭 Form Pending but ABSENT ({len(absent_forms)})</h4><p>Forms are printed, but these students did not eat MDM today. Do not distribute.</p></div>", unsafe_allow_html=True)
                if not absent_forms.empty:
                    st.dataframe(absent_forms[['Class', 'Section', 'Roll', 'Student Name']], hide_index=True, use_container_width=True)

# ==========================================
# TAB 3: MASTER LOG
# ==========================================
with tab3:
    st.subheader("Database View: form_distribution_log")
    if not form_df.empty:
        display_df = form_df.drop(columns=['UID'], errors='ignore')
        st.dataframe(display_df, hide_index=True, use_container_width=True)
        
        col_csv, col_clear = st.columns([1, 1])
        with col_csv:
            st.download_button("📥 Download Distribution Log CSV", display_df.to_csv(index=False).encode('utf-8'), "BPS_Form_Log.csv", "text/csv")
        with col_clear:
            with st.expander("⚠ Emergency Reset"):
                if st.button("Clear Distribution Database"):
                    overwrite_sheet_df('form_distribution_log', pd.DataFrame(columns=expected_columns))
                    st.success("Database Cleared!")
                    st.rerun()
    else:
        st.info("No forms have been logged yet.")