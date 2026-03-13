import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import gspread
from google.oauth2.service_account import Credentials
from fpdf import FPDF

# --- 1. CONFIGURATION & STYLING ---
st.set_page_config(page_title="BPS Form Manager", page_icon="📝", layout="wide")

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

st.title("📝 BPS Form Generator & Tracker")

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
        ws.freeze(rows=1) 
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

# --- 4. PDF GENERATOR CLASS ---
class BPS_Survey(FPDF):
    def __init__(self):
        super().__init__(orientation='P', unit='mm', format='A5')
        self.add_font('Bengali', '', 'Bengali.ttf')
        self.set_text_shaping(True) 
        self.set_auto_page_break(auto=False)

    def draw_digit_boxes(self, x, y, box_size=8):
        for i in range(10):
            self.rect(x + (i * box_size), y, box_size, box_size)

    def draw_single_form(self, row):
        x = 10 
        y = 10
        self.set_xy(x, y)
        
        try: self.image('logo.png', x, y, 20) 
        except:
            self.rect(x, y, 20, 20)
            self.set_font('Helvetica', 'B', 8)
            self.text(x + 3, y + 10, "LOGO")

        self.set_font('Helvetica', 'B', 14) 
        self.set_xy(x + 24, y + 2)
        self.cell(100, 8, "Bhagyabantapur Primary School (BPS)", ln=True)
        
        self.set_font('Bengali', '', 12) 
        self.set_x(x + 24)
        self.cell(100, 8, u"অভিভাবক তথ্য যাচাই ফর্ম", ln=True)
        
        curr_y = 35 
        self.rect(x, curr_y, 128, 36) 
        
        mobile_val = str(row['Mobile']).split('.')[0] if pd.notna(row['Mobile']) and str(row['Mobile']).strip() != "" else "N/A"
        roll_val = str(row['Roll']).split('.')[0] if 'Roll' in row and pd.notna(row['Roll']) and str(row['Roll']).strip() != "" else "N/A"
        
        dob_val = "N/A"
        if 'DOB' in row and pd.notna(row['DOB']) and str(row['DOB']).strip() != "":
            try:
                parsed_date = pd.to_datetime(row['DOB'], dayfirst=True)
                dob_val = parsed_date.strftime('%d-%m-%Y')
            except:
                dob_val = str(row['DOB'])
        
        self.set_font('Helvetica', '', 11)
        self.text(x + 3, curr_y + 7, f"Student: {row['Name']}")
        self.text(x + 70, curr_y + 7, f"DOB: {dob_val}")
        self.text(x + 3, curr_y + 15, f"Father: {row['Father']}")
        self.text(x + 70, curr_y + 15, f"Class: {row['Class']}")
        self.text(x + 3, curr_y + 23, f"Mother: {row['Mother']}")
        self.text(x + 70, curr_y + 23, f"Section: {row['Section']}")
        self.text(x + 3, curr_y + 31, f"Mobile: {mobile_val}")
        self.text(x + 70, curr_y + 31, f"Roll: {roll_val}") 
        
        curr_y = 78
        self.set_xy(x, curr_y)
        
        self.set_font('Bengali', '', 11)
        self.cell(26, 6, u"সঠিক ঘরে টিক (")
        self.set_font('ZapfDingbats', '', 10) 
        self.cell(4, 6, "4") 
        self.set_font('Bengali', '', 11)
        self.cell(15, 6, u") দিন:")
        self.ln(10)
        
        curr_y = self.get_y()
        self.set_xy(x, curr_y)
        self.cell(60, 8, u"এই মোবাইল নম্বরটি কি সঠিক?")
        self.set_x(x + 65)
        self.cell(10, 8, u"হ্যাঁ")
        self.rect(x + 75, curr_y + 1.5, 5, 5) 
        self.set_x(x + 85)
        self.cell(10, 8, u"না")
        self.rect(x + 95, curr_y + 1.5, 5, 5) 
        self.set_xy(x, curr_y + 10)
        self.cell(0, 8, u"সঠিক না হলে, সঠিক নম্বরটি দিন:", ln=True)
        self.draw_digit_boxes(x, self.get_y() + 2, box_size=8)
        self.ln(15)
        
        curr_y = self.get_y()
        self.set_xy(x, curr_y)
        self.cell(65, 8, u"এটি কি আপনার হোয়াটসঅ্যাপ নম্বর?")
        self.set_x(x + 70)
        self.cell(10, 8, u"হ্যাঁ")
        self.rect(x + 80, curr_y + 1.5, 5, 5) 
        self.set_x(x + 90)
        self.cell(10, 8, u"না")
        self.rect(x + 100, curr_y + 1.5, 5, 5) 
        self.set_xy(x, curr_y + 10)
        self.cell(0, 8, u"হোয়াটসঅ্যাপ নম্বর না হলে সেটি দিন:", ln=True)
        self.draw_digit_boxes(x, self.get_y() + 2, box_size=8)
        self.ln(15)
        
        curr_y = self.get_y()
        self.set_xy(x, curr_y)
        self.cell(82, 8, u"ছাত্র/ছাত্রীর কি SC / ST / OBC সার্টিফিকেট আছে?")
        self.set_x(x + 85)
        self.cell(10, 8, u"হ্যাঁ")
        self.rect(x + 95, curr_y + 1.5, 5, 5) 
        self.set_x(x + 105)
        self.cell(10, 8, u"না")
        self.rect(x + 115, curr_y + 1.5, 5, 5) 
        self.set_xy(x, curr_y + 10)
        self.cell(0, 8, u"হ্যাঁ হলে, সার্টিফিকেটের জেরক্স (Xerox) কপি জমা দিন।", ln=True)
        
        curr_y = self.get_y() + 15 
        self.set_font('Helvetica', '', 10)
        self.text(x, curr_y, "__________________________")
        self.text(x + 75, curr_y, "__________________________")
        
        self.set_font('Bengali', '', 10)
        self.set_xy(x, curr_y + 2)
        self.cell(40, 6, u"অভিভাবকের স্বাক্ষর")
        self.set_xy(x + 75, curr_y + 2)
        self.cell(40, 6, u"তারিখ")

# --- 5. LOAD DATA FROM CLOUD ---
students_df = fetch_sheet_data('students_master')
if not students_df.empty:
    if 'Section' not in students_df.columns: 
        students_df['Section'] = 'A'
    students_df['UID'] = students_df['Class'].astype(str) + "_" + students_df['Section'].astype(str) + "_" + students_df['Roll'].astype(str)
else:
    st.error("⚠️ 'students_master' tab missing or empty in BPS_Database. Please copy your students.csv data into Google Sheets.")
    st.stop()

mdm_df = fetch_sheet_data('mdm_log')
if mdm_df.empty:
    mdm_df = pd.DataFrame(columns=['Date', 'Teacher', 'Class', 'Section', 'Roll', 'Name', 'Time', 'UID'])
else:
    mdm_df['UID'] = mdm_df['Class'].astype(str) + "_" + mdm_df['Section'].astype(str) + "_" + mdm_df['Roll'].astype(str)

form_df = fetch_sheet_data('form_distribution_log')

expected_columns = [
    'Class', 'Section', 'Roll', 'Student Name', 
    'Date (form generated)', 'Date (receive form)', 
    'Date (returned)', 'Return Status',
    'WhatsApp Added', 'WhatsApp Group',
    'Mobile Updated', 'Old Mobile Number'
]

# Universal completed statuses list
IN_GROUP_STATUSES = ['Yes', 'Added via Link', 'Added Directly']
NO_WA_STATUSES = ['No Smartphone']
RESOLVED_STATUSES = IN_GROUP_STATUSES + NO_WA_STATUSES

if form_df.empty:
    form_df = pd.DataFrame(columns=expected_columns + ['UID'])
else:
    for col in expected_columns:
        if col not in form_df.columns:
            if col == 'Return Status' or col == 'Date (returned)': form_df[col] = "Pending"
            elif col in ['WhatsApp Added', 'Mobile Updated']: form_df[col] = "Not Started"
            elif col in ['WhatsApp Group', 'Old Mobile Number']: form_df[col] = ""
            else: form_df[col] = ""
    form_df['UID'] = form_df['Class'].astype(str) + "_" + form_df['Section'].astype(str) + "_" + form_df['Roll'].astype(str)

# --- 6. UI TABS ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🖨️ 1. Generate", 
    "🤝 2. Distribute", 
    "📥 3. Returns & WA", 
    "💬 4. WhatsApp Report", 
    "📊 5. Master Log", 
    "📈 6. Summary"
])

# ==========================================
# TAB 1: GENERATE PDF & LOG
# ==========================================
with tab1:
    st.subheader("Step 1: Generate PDFs & Save to Database")
    if students_df.empty:
        st.warning("No student data found.")
    else:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            classes = sorted(students_df['Class'].dropna().unique())
            sel_class = st.selectbox("Select Class", classes, key="t1_c")
        with col2:
            sections = sorted(students_df[students_df['Class'] == sel_class]['Section'].unique())
            sel_sec = st.selectbox("Select Section", sections, key="t1_s")
        with col3:
            gen_date_obj = st.date_input("Date to log on Database", now.date())
            gen_date_str = gen_date_obj.strftime("%d-%m-%Y")
            
        filtered_students = students_df[(students_df['Class'] == sel_class) & (students_df['Section'] == sel_sec)].copy()
        
        existing_uids = form_df['UID'].tolist() if not form_df.empty else []
        
        unprinted_df = filtered_students[~filtered_students['UID'].isin(existing_uids)].copy()
        printed_df = filtered_students[filtered_students['UID'].isin(existing_uids)].copy()

        st.divider()
        
        # --- SECTION 1: NEW FORMS ---
        st.markdown("#### 🆕 Section 1: Generate New Forms")
        st.info("These students DO NOT have a form generated in the database yet.")
        
        filter_mode = st.radio("Filter unprinted students:", ["Show All Missing Forms", "Only Show Present Students (via MDM)"], horizontal=True)
        
        if filter_mode == "Only Show Present Students (via MDM)":
            mdm_check_obj = st.date_input("Select MDM Date to Check Presence", now.date(), key="mdm_check_d")
            mdm_check_str = mdm_check_obj.strftime("%d-%m-%Y")
            
            if mdm_df.empty:
                st.warning("No MDM data found in the database.")
                display_unprinted = pd.DataFrame()
            else:
                present_uids = mdm_df[mdm_df['Date'].astype(str) == mdm_check_str]['UID'].tolist()
                display_unprinted = unprinted_df[unprinted_df['UID'].isin(present_uids)]
        else:
            display_unprinted = unprinted_df
            
        if display_unprinted.empty:
            st.success("No students found matching this criteria!")
        else:
            select_all_new = st.checkbox(f"Select All {len(display_unprinted)} Students", key="sa_new")
            if select_all_new:
                selected_new_idx = display_unprinted.index.tolist()
            else:
                selected_new_idx = st.multiselect(
                    "Choose specific students:", 
                    display_unprinted.index, 
                    format_func=lambda i: f"Roll {display_unprinted.loc[i].get('Roll', 'N/A')} - {display_unprinted.loc[i]['Name']}",
                    key="ms_new"
                )
                
            if st.button("📄 Generate New PDFs & Log to Database", type="primary", key="btn_new"):
                if selected_new_idx:
                    with st.spinner("Building PDFs and updating cloud database..."):
                        pdf = BPS_Survey()
                        new_logs = []
                        for i in selected_new_idx:
                            row = display_unprinted.loc[i]
                            pdf.add_page()
                            pdf.draw_single_form(row)
                            
                            new_logs.append({
                                'Class': row['Class'], 
                                'Section': row['Section'], 
                                'Roll': row['Roll'], 
                                'Student Name': row['Name'], 
                                'Date (form generated)': gen_date_str, 
                                'Date (receive form)': 'Pending',
                                'Date (returned)': 'Pending',
                                'Return Status': 'Pending',
                                'WhatsApp Added': 'Not Started',
                                'WhatsApp Group': 'None',
                                'Mobile Updated': 'No',
                                'Old Mobile Number': ''
                            })
                            
                        pdf_bytes = bytes(pdf.output())
                        
                        if new_logs:
                            append_sheet_df('form_distribution_log', pd.DataFrame(new_logs))
                            st.success(f"✅ {len(new_logs)} forms safely logged to the database!")
                            
                        st.download_button(
                            label="⬇️ Download New Survey Forms (PDF)", 
                            data=pdf_bytes, 
                            file_name=f"BPS_NEW_Surveys_{sel_class}_{sel_sec}.pdf",
                            mime="application/pdf",
                            key="dl_new"
                        )
                else:
                    st.error("Please select at least one student.")

        st.divider()

        # --- SECTION 2: RE-PRINT FORMS ---
        st.markdown("#### 🔄 Section 2: Re-Print Existing Forms")
        st.warning("These students ALREADY have forms generated in the database. Generating here will NOT duplicate them.")
        
        if printed_df.empty:
            st.success("No forms have been generated for this class/section yet.")
        else:
            select_all_rep = st.checkbox(f"Select All {len(printed_df)} Students", key="sa_rep")
            if select_all_rep:
                selected_rep_idx = printed_df.index.tolist()
            else:
                selected_rep_idx = st.multiselect(
                    "Choose specific students to re-print:", 
                    printed_df.index, 
                    format_func=lambda i: f"Roll {printed_df.loc[i].get('Roll', 'N/A')} - {printed_df.loc[i]['Name']}",
                    key="ms_rep"
                )
                
            if st.button("🖨️ Re-Print PDFs (No DB Update)", key="btn_rep"):
                if selected_rep_idx:
                    with st.spinner("Building PDFs..."):
                        pdf = BPS_Survey()
                        for i in selected_rep_idx:
                            row = printed_df.loc[i]
                            pdf.add_page()
                            pdf.draw_single_form(row)
                            
                        pdf_bytes = bytes(pdf.output())
                        st.success(f"✅ Successfully prepared {len(selected_rep_idx)} forms for re-print!")
                        
                        st.download_button(
                            label="⬇️ Download Re-Print Survey Forms (PDF)", 
                            data=pdf_bytes, 
                            file_name=f"BPS_REPRINT_Surveys_{sel_class}_{sel_sec}.pdf",
                            mime="application/pdf",
                            key="dl_rep"
                        )
                else:
                    st.error("Please select at least one student to re-print.")

# ==========================================
# TAB 2: MDM AUTO-DISTRIBUTE
# ==========================================
with tab2:
    st.subheader("Step 2: Sync with MDM & Auto-Distribute")
    
    if students_df.empty:
        st.warning("No student data found.")
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
                
                all_class_forms = form_df[
                    (form_df['Class'].astype(str) == str(sel_class_t2)) & 
                    (form_df['Section'].astype(str) == str(sel_sec_t2))
                ]
                all_generated_uids = all_class_forms['UID'].tolist() if not all_class_forms.empty else []
                pending_forms = all_class_forms[all_class_forms['Date (receive form)'] == 'Pending']
                
                ready_to_distribute = pending_forms[pending_forms['UID'].isin(target_mdm_uids)].copy()
                mdm_no_form_uids = [u for u in target_mdm_uids if u not in all_generated_uids]
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
                    
                    if st.button(f"📦 Confirm Distribution & Update Database for {sel_class_t2} - {sel_sec_t2}", type="primary", key="btn_dist"):
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

                st.markdown(f"<div class='alert-box alert-warning'><h4>⚠️ Present but NO FORM ({len(missing_forms)})</h4><p>These students ate MDM today, but no form has been generated for them yet.</p></div>", unsafe_allow_html=True)
                if not missing_forms.empty:
                    st.dataframe(missing_forms[['Class', 'Section', 'Roll', 'Name']], hide_index=True, use_container_width=True)

                st.markdown(f"<div class='alert-box alert-info'><h4>📭 Form Pending but ABSENT ({len(absent_forms)})</h4><p>Forms are printed, but these students did not eat MDM today. Do not distribute.</p></div>", unsafe_allow_html=True)
                if not absent_forms.empty:
                    st.dataframe(absent_forms[['Class', 'Section', 'Roll', 'Student Name']], hide_index=True, use_container_width=True)

# ==========================================
# TAB 3: LOG RETURNED FORMS & WHATSAPP
# ==========================================
with tab3:
    st.subheader("Step 3: Log Returns & Assign WhatsApp Groups")
    
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
        
    if not form_df.empty:
        received_df = form_df[
            (form_df['Date (receive form)'] != 'Pending') & 
            (form_df['Class'].astype(str) == str(sel_class_t3)) & 
            (form_df['Section'].astype(str) == str(sel_sec_t3))
        ]
        
        pending_returns_df = received_df[received_df['Return Status'] == 'Pending'].copy()
        incomplete_returns_df = received_df[received_df['Return Status'] == 'Incomplete'].copy()
        completed_returns_df = received_df[received_df['Return Status'] == 'Complete'].copy()

        st.divider()

        # --- SECTION 3.1: NEW RETURNS ---
        st.markdown("#### 📥 1. Log New Returns (First Time)")
        if pending_returns_df.empty:
            st.info("No pending returns outstanding for this section.")
        else:
            pending_returns_df['Mark Complete'] = False
            pending_returns_df['Mark Incomplete'] = False
            
            edited_new_returns = st.data_editor(
                pending_returns_df[['Mark Complete', 'Mark Incomplete', 'Roll', 'Student Name', 'Date (receive form)']],
                hide_index=True,
                use_container_width=True,
                disabled=['Roll', 'Student Name', 'Date (receive form)']
            )
            
            if st.button("💾 Save New Returns", type="primary", key="btn_new_ret"):
                updated_form_df = form_df.copy()
                changes_made = 0
                
                for idx in edited_new_returns.index:
                    is_complete = edited_new_returns.loc[idx, 'Mark Complete']
                    is_incomplete = edited_new_returns.loc[idx, 'Mark Incomplete']
                    
                    if is_complete or is_incomplete:
                        uid = pending_returns_df.loc[idx, 'UID']
                        mask = updated_form_df['UID'] == uid
                        
                        if is_complete: updated_form_df.loc[mask, 'Return Status'] = 'Complete'
                        elif is_incomplete: updated_form_df.loc[mask, 'Return Status'] = 'Incomplete'
                            
                        updated_form_df.loc[mask, 'Date (returned)'] = ret_date_str
                        changes_made += 1
                        
                if changes_made > 0:
                    updated_form_df = updated_form_df.drop(columns=['UID'], errors='ignore')
                    overwrite_sheet_df('form_distribution_log', updated_form_df)
                    st.success(f"✅ Successfully updated {changes_made} new returns!")
                    st.rerun()
                else: st.warning("No boxes ticked.")

        st.divider()

        # --- SECTION 3.2: FIX INCOMPLETE FORMS ---
        st.markdown("#### ✍️ 2. Fix Incomplete Forms")
        if incomplete_returns_df.empty:
            st.success("There are no incomplete forms waiting to be fixed for this section!")
        else:
            st.warning("These students returned forms previously, but data was missing. Tick the box to mark them fully complete.")
            incomplete_returns_df['Fix & Mark Complete'] = False
            
            edited_fix_returns = st.data_editor(
                incomplete_returns_df[['Fix & Mark Complete', 'Roll', 'Student Name', 'Date (returned)']],
                hide_index=True,
                use_container_width=True,
                disabled=['Roll', 'Student Name', 'Date (returned)']
            )
            
            if st.button("💾 Save Fixed Forms", type="primary", key="btn_fix_ret"):
                updated_form_df = form_df.copy()
                changes_made = 0
                for idx in edited_fix_returns.index:
                    if edited_fix_returns.loc[idx, 'Fix & Mark Complete']:
                        uid = incomplete_returns_df.loc[idx, 'UID']
                        mask = updated_form_df['UID'] == uid
                        updated_form_df.loc[mask, 'Return Status'] = 'Complete'
                        updated_form_df.loc[mask, 'Date (returned)'] = ret_date_str 
                        changes_made += 1
                        
                if changes_made > 0:
                    updated_form_df = updated_form_df.drop(columns=['UID'], errors='ignore')
                    overwrite_sheet_df('form_distribution_log', updated_form_df)
                    st.success(f"✅ Successfully completed {changes_made} forms!")
                    st.rerun()
                else: st.warning("No boxes ticked to fix.")

        st.divider()

        # --- PREPARE DATA FOR SECTIONS 3.3 AND 3.4 ---
        if completed_returns_df.empty:
            st.markdown("#### 💬 3. Pending WhatsApp Assignment")
            st.success("No completed forms available for WhatsApp Assignment yet.")
        else:
            grad_year_map = {
                'CLASS V': '26', 'CLASS IV': '27', 
                'CLASS III': '28', 'CLASS II': '29', 
                'CLASS I': '30', 'CLASS PP': '31', 'CLASS LPP': '32'
            }

            all_wa_df = pd.merge(completed_returns_df, students_df[['UID', 'Father', 'Mobile']], on='UID', how='left')
            all_wa_df['Grad Year'] = all_wa_df['Class'].map(grad_year_map).fillna('XX')
            all_wa_df['Father'] = all_wa_df['Father'].fillna('Guardian')
            all_wa_df['Contact Name (Copy)'] = "BPS " + all_wa_df['Grad Year'] + " " + all_wa_df['Student Name'] + " (" + all_wa_df['Father'] + ")"
            
            # --- ROMAN TO NUMBER MAPPING FOR WHATSAPP GROUPS ---
            class_to_number_map = {
                'CLASS LPP': 'CLASS LPP',
                'CLASS PP': 'CLASS PP',
                'CLASS I': 'CLASS 1',
                'CLASS II': 'CLASS 2',
                'CLASS III': 'CLASS 3',
                'CLASS IV': 'CLASS 4',
                'CLASS V': 'CLASS 5'
            }
            mapped_class = all_wa_df['Class'].map(class_to_number_map).fillna(all_wa_df['Class'])
            all_wa_df['Suggested Group'] = "BPS " + mapped_class.astype(str) + " " + all_wa_df['Section'].astype(str)
            
            # Map legacy 'No' and empty fields to 'Not Started'
            all_wa_df['WhatsApp Status'] = all_wa_df['WhatsApp Added'].replace({'No': 'Not Started', '': 'Not Started'})
            
            # ---> FORCE OVERRIDE FIX: Always use the new Arabic numeral generated name!
            all_wa_df['Group Name'] = all_wa_df['Suggested Group']
            
            all_wa_df['Mobile'] = all_wa_df['Mobile'].fillna("").astype(str).str.replace('.0', '', regex=False)

            # Split into Pending and Saved lists based on new granular statuses
            pending_wa_df = all_wa_df[~all_wa_df['WhatsApp Status'].isin(RESOLVED_STATUSES)].copy()
            saved_wa_df = all_wa_df[all_wa_df['WhatsApp Status'].isin(RESOLVED_STATUSES)].copy()

            # --- SECTION 3.3: PENDING WHATSAPP SYNC ---
            st.markdown("#### 💬 3. Pending WhatsApp Assignment")
            if pending_wa_df.empty:
                st.success("All completed returns have been processed and moved out of the pending queue!")
            else:
                st.info("💡 **Instructions:** Select the exact status from the dropdown. Once you select a RESOLVED status ('Added via Link', 'Added Directly', or 'No Smartphone') and click Save, they will move to Section 4.")
                
                # Granular Status Dropdown Options
                status_options = ["Not Started", "Contact Saved", "Invitation Sent", "Added via Link", "Added Directly", "No Smartphone"]
                
                edited_wa = st.data_editor(
                    pending_wa_df[['WhatsApp Status', 'Contact Name (Copy)', 'Mobile', 'Group Name']],
                    column_config={
                        "WhatsApp Status": st.column_config.SelectboxColumn(
                            "WhatsApp Status",
                            help="Select the current sync status",
                            options=status_options,
                            required=True,
                        )
                    },
                    hide_index=True,
                    use_container_width=True,
                    disabled=['Contact Name (Copy)', 'Group Name'] 
                )

                # --- EXPORT BUTTONS FOR PENDING CONTACTS (Uses the live edited table!) ---
                st.markdown("##### 📲 Download Pending Contacts (No Duplicates)")
                col_vcf, col_csv = st.columns(2)
                
                vcard_data = ""
                for _, row in edited_wa.iterrows():
                    c_name = row['Contact Name (Copy)']
                    c_phone = str(row['Mobile']).strip()
                    if c_phone and c_phone != "N/A" and c_phone != "nan":
                        vcard_data += f"BEGIN:VCARD\nVERSION:3.0\nFN:{c_name}\nTEL:{c_phone}\nEND:VCARD\n"
                
                with col_vcf:
                    if vcard_data:
                        st.download_button(
                            label="📥 Download Pending Mobile Contacts (.vcf)",
                            data=vcard_data.encode('utf-8'),
                            file_name=f"BPS_NEW_Contacts_{sel_class_t3}_{sel_sec_t3}.vcf",
                            mime="text/vcard",
                            key="vcf_pending"
                        )
                
                with col_csv:
                    valid_contacts_df = edited_wa[edited_wa['Mobile'].str.strip() != ""]
                    valid_contacts_df = valid_contacts_df[valid_contacts_df['Mobile'].str.strip() != "nan"]
                    valid_contacts_df = valid_contacts_df[valid_contacts_df['Mobile'].str.strip() != "N/A"]
                    
                    if not valid_contacts_df.empty:
                        google_csv_df = pd.DataFrame({
                            'Name': valid_contacts_df['Contact Name (Copy)'],
                            'Group Membership': valid_contacts_df['Group Name'],
                            'Phone 1 - Type': 'Mobile',
                            'Phone 1 - Value': valid_contacts_df['Mobile']
                        })
                        
                        st.download_button(
                            label="📥 Download Pending Google Contacts (.csv)",
                            data=google_csv_df.to_csv(index=False).encode('utf-8'),
                            file_name=f"Google_BPS_NEW_Contacts_{sel_class_t3}_{sel_sec_t3}.csv",
                            mime="text/csv",
                            key="csv_pending"
                        )

                # --- SAVE BUTTON ---
                if st.button("💾 Save WhatsApp Status Updates", type="primary", key="btn_wa_sync"):
                    updated_form_df = form_df.copy()
                    updated_students_df = students_df.copy()
                    changes_made = 0
                    mobile_changes = 0
                    
                    for idx in edited_wa.index:
                        new_status = edited_wa.loc[idx, 'WhatsApp Status']
                        group_name = edited_wa.loc[idx, 'Group Name']
                        new_mobile = edited_wa.loc[idx, 'Mobile']
                        uid = pending_wa_df.loc[idx, 'UID']
                        
                        old_status = pending_wa_df.loc[idx, 'WhatsApp Status']
                        old_group = pending_wa_df.loc[idx, 'WhatsApp Group']
                        old_mobile = str(pending_wa_df.loc[idx, 'Mobile']).replace('.0', '')
                        
                        # Set Group to None if No Smartphone
                        if new_status == 'No Smartphone':
                            group_name = 'None'

                        if old_status != new_status or old_group != group_name:
                            mask = updated_form_df['UID'] == uid
                            updated_form_df.loc[mask, 'WhatsApp Added'] = new_status
                            updated_form_df.loc[mask, 'WhatsApp Group'] = group_name if new_status != 'Not Started' else 'None'
                            changes_made += 1
                            
                        # Write to Google Sheets for students & back up old number
                        if str(old_mobile) != str(new_mobile):
                            s_mask = updated_students_df['UID'] == uid
                            updated_students_df.loc[s_mask, 'Mobile'] = new_mobile
                            
                            f_mask = updated_form_df['UID'] == uid
                            updated_form_df.loc[f_mask, 'Mobile Updated'] = 'Yes'
                            updated_form_df.loc[f_mask, 'Old Mobile Number'] = old_mobile
                            mobile_changes += 1
                            
                    if changes_made > 0 or mobile_changes > 0:
                        updated_form_df = updated_form_df.drop(columns=['UID'], errors='ignore')
                        overwrite_sheet_df('form_distribution_log', updated_form_df)
                        
                    if mobile_changes > 0:
                        updated_students_df = updated_students_df.drop(columns=['UID'], errors='ignore')
                        overwrite_sheet_df('students_master', updated_students_df) 
                        
                    if changes_made > 0 or mobile_changes > 0:
                        st.success(f"✅ Successfully updated {changes_made} WhatsApp statuses and {mobile_changes} mobile numbers!")
                        st.rerun()
                    else:
                        st.warning("No changes detected.")

            st.divider()

            # --- SECTION 3.4: PROCESSED & RESOLVED ---
            st.markdown("#### ✅ 4. Processed & Resolved (In Group or No Smartphone)")
            if saved_wa_df.empty:
                st.info("No students have been fully processed for this section yet.")
            else:
                st.dataframe(
                    saved_wa_df[['Roll', 'Student Name', 'Contact Name (Copy)', 'Mobile', 'WhatsApp Status', 'Group Name']],
                    hide_index=True,
                    use_container_width=True
                )
                
                with st.expander("📥 Need a Backup? Download ALL Saved Contacts for this class"):
                    col_vcf_saved, col_csv_saved = st.columns(2)
                    
                    vcard_data_saved = ""
                    for _, row in saved_wa_df.iterrows():
                        # Only export actual groups, skip No Smartphone
                        if row['WhatsApp Status'] != 'No Smartphone':
                            c_name = row['Contact Name (Copy)']
                            c_phone = str(row['Mobile']).strip()
                            if c_phone and c_phone != "N/A" and c_phone != "nan":
                                vcard_data_saved += f"BEGIN:VCARD\nVERSION:3.0\nFN:{c_name}\nTEL:{c_phone}\nEND:VCARD\n"
                    
                    with col_vcf_saved:
                        if vcard_data_saved:
                            st.download_button(
                                label="📥 Download FULL Mobile Contacts (.vcf)",
                                data=vcard_data_saved.encode('utf-8'),
                                file_name=f"BPS_ALL_Contacts_{sel_class_t3}_{sel_sec_t3}.vcf",
                                mime="text/vcard",
                                key="vcf_saved"
                            )
                    
                    with col_csv_saved:
                        valid_saved_df = saved_wa_df[saved_wa_df['Mobile'].str.strip() != ""]
                        valid_saved_df = valid_saved_df[valid_saved_df['Mobile'].str.strip() != "nan"]
                        valid_saved_df = valid_saved_df[valid_saved_df['Mobile'].str.strip() != "N/A"]
                        valid_saved_df = valid_saved_df[valid_saved_df['WhatsApp Status'] != 'No Smartphone']
                        
                        if not valid_saved_df.empty:
                            google_csv_saved = pd.DataFrame({
                                'Name': valid_saved_df['Contact Name (Copy)'],
                                'Group Membership': valid_saved_df['Group Name'],
                                'Phone 1 - Type': 'Mobile',
                                'Phone 1 - Value': valid_saved_df['Mobile']
                            })
                            
                            st.download_button(
                                label="📥 Download FULL Google Contacts (.csv)",
                                data=google_csv_saved.to_csv(index=False).encode('utf-8'),
                                file_name=f"Google_BPS_ALL_Contacts_{sel_class_t3}_{sel_sec_t3}.csv",
                                mime="text/csv",
                                key="csv_saved"
                            )

# ==========================================
# TAB 4: WHATSAPP REPORT (SMART STATUS)
# ==========================================
with tab4:
    st.subheader("💬 WhatsApp Group Status Report")
    
    if students_df.empty:
        st.warning("No student data found.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            wa_classes = sorted(students_df['Class'].dropna().unique())
            wa_sel_class = st.selectbox("Select Class", wa_classes, key="wa_c")
        with col2:
            wa_sections = sorted(students_df[students_df['Class'] == wa_sel_class]['Section'].unique())
            wa_sel_sec = st.selectbox("Select Section", wa_sections, key="wa_s")

        class_students = students_df[(students_df['Class'] == wa_sel_class) & (students_df['Section'] == wa_sel_sec)].copy()
        
        if not form_df.empty:
            class_forms = form_df[(form_df['Class'] == wa_sel_class) & (form_df['Section'] == wa_sel_sec)].copy()
        else:
            class_forms = pd.DataFrame(columns=expected_columns)
        
        wa_merged = pd.merge(class_students, class_forms, on='UID', how='left', suffixes=('_stu', '_form'))
        
        wa_merged['WhatsApp Added'] = wa_merged['WhatsApp Added'].fillna('Not Started')
        wa_merged['Date (receive form)'] = wa_merged['Date (receive form)'].fillna('Not Generated')
        wa_merged['Return Status'] = wa_merged['Return Status'].fillna('N/A')
        wa_merged['Mobile Updated'] = wa_merged['Mobile Updated'].fillna('No')
        wa_merged['Old Mobile Number'] = wa_merged['Old Mobile Number'].fillna('')
        
        st.divider()
        
        # --- Part 1: In WhatsApp Group ---
        st.markdown("#### ✅ Part 1: Members in WhatsApp Group")
        part1_df = wa_merged[wa_merged['WhatsApp Added'].isin(IN_GROUP_STATUSES)].copy()
        if part1_df.empty:
            st.info("No students from this section have been added to the WhatsApp group yet.")
        else:
            part1_df['Number Status'] = part1_df['Mobile Updated'].apply(lambda x: '🔄 Changed' if x == 'Yes' else '✅ Unchanged')
            part1_df['Method Added'] = part1_df['WhatsApp Added'].replace({'Yes': 'Added Directly'})
            part1_df['Old Mobile'] = part1_df.apply(lambda r: r['Old Mobile Number'] if r['Mobile Updated'] == 'Yes' else '-', axis=1)
            part1_df['Current Mobile'] = part1_df['Mobile']
            
            display_p1 = part1_df[['Roll_stu', 'Name', 'Method Added', 'Old Mobile', 'Current Mobile', 'Number Status']].rename(columns={'Roll_stu': 'Roll'})
            
            def highlight_changed_number(row):
                if row['Number Status'] == '🔄 Changed':
                    return [''] * 4 + ['background-color: #fff3cd; color: #856404; font-weight: bold;'] + ['']
                return [''] * 6

            st.dataframe(
                display_p1.style.apply(highlight_changed_number, axis=1), 
                hide_index=True, 
                use_container_width=True
            )
            
        st.divider()
        
        # --- Part 2: Took form, NOT in group (Pending & In Progress) ---
        st.markdown("#### ⚠️ Part 2: Form Distributed but NOT in Group")
        part2_df = wa_merged[(~wa_merged['WhatsApp Added'].isin(RESOLVED_STATUSES)) & (~wa_merged['Date (receive form)'].isin(['Pending', 'Not Generated']))].copy()
        
        if part2_df.empty:
            st.success("All students who received a form are either added to the group, marked 'No Smartphone', or haven't received one yet.")
        else:
            def determine_reason(row):
                if row['Return Status'] == 'Incomplete':
                    return "Form Incomplete"
                elif row['Return Status'] == 'Pending':
                    return "Pending Return"
                elif row['WhatsApp Added'] in ['Contact Saved', 'Invitation Sent']:
                    return f"⏳ In Progress: {row['WhatsApp Added']}"
                else:
                    return "Form Complete but not started"

            part2_df['Reason'] = part2_df.apply(determine_reason, axis=1)
            
            display_p2 = part2_df[['Roll_stu', 'Name', 'Date (receive form)', 'Reason']].rename(columns={'Roll_stu': 'Roll', 'Date (receive form)': 'Distributed On'})
            
            def highlight_ready_wa(row):
                if "In Progress" in row['Reason'] or row['Reason'] == "Form Complete but not started":
                    return ['background-color: #d4edda; color: #155724; font-weight: bold;'] * len(row)
                return [''] * len(row)

            st.dataframe(
                display_p2.style.apply(highlight_ready_wa, axis=1), 
                hide_index=True, 
                use_container_width=True
            )

        st.divider()
        
        # --- Part 3: Form Printed (On Desk) ---
        st.markdown("#### 📭 Part 3: Form Printed (On Desk) - Not in Group")
        part3_df = wa_merged[wa_merged['Date (receive form)'] == 'Pending'].copy()
        
        if part3_df.empty:
            st.success("No forms are currently sitting on the desk waiting to be distributed!")
        else:
            st.dataframe(
                part3_df[['Roll_stu', 'Name', 'Father']].rename(columns={'Roll_stu': 'Roll'}), 
                hide_index=True, 
                use_container_width=True
            )

        st.divider()

        # --- Part 4: Form Not Generated ---
        st.markdown("#### ❌ Part 4: Form Not Generated - Not in Group")
        part4_df = wa_merged[wa_merged['Date (receive form)'] == 'Not Generated'].copy()
        
        if part4_df.empty:
            st.success("All students in this section have had their forms generated!")
        else:
            st.info("Check if these students were present on a specific date to see why forms aren't generated.")
            col_d, _ = st.columns([1, 2])
            with col_d:
                p4_date_obj = st.date_input("Check presence on MDM Date:", now.date(), key="p4_date")
                p4_date_str = p4_date_obj.strftime("%d-%m-%Y")
                
            present_uids = []
            if not mdm_df.empty:
                present_uids = mdm_df[mdm_df['Date'].astype(str) == p4_date_str]['UID'].tolist()
                
            part4_df['Reason'] = part4_df['UID'].apply(
                lambda uid: "Came to school but not generated" if uid in present_uids else "Not came to school"
            )
            
            display_p4 = part4_df[['Roll_stu', 'Name', 'Father', 'Reason']].rename(columns={'Roll_stu': 'Roll'})
            
            def highlight_urgent(row):
                if row['Reason'] == "Came to school but not generated":
                    return ['background-color: #f8d7da; color: #721c24; font-weight: bold;'] * len(row)
                return [''] * len(row)

            st.dataframe(
                display_p4.style.apply(highlight_urgent, axis=1), 
                hide_index=True, 
                use_container_width=True
            )

        st.divider()

        # --- Part 5: No Smartphone ---
        st.markdown("#### 📵 Part 5: No Smartphone (Cannot Join)")
        part5_df = wa_merged[wa_merged['WhatsApp Added'].isin(NO_WA_STATUSES)].copy()
        
        if part5_df.empty:
            st.success("No families in this section have reported lacking a smartphone.")
        else:
            st.warning("These students require physical paper notices instead of WhatsApp messages.")
            st.dataframe(
                part5_df[['Roll_stu', 'Name', 'Father', 'Mobile']].rename(columns={'Roll_stu': 'Roll', 'Mobile': 'Contact Number'}), 
                hide_index=True, 
                use_container_width=True
            )

# ==========================================
# TAB 5: MASTER LOG (EDITABLE)
# ==========================================
with tab5:
    st.subheader("Database View & Corrections")
    if not form_df.empty:
        st.info("💡 **Made a mistake?** Edit any cell directly in the table below (like changing a status back to 'Pending') and click Save.")
        
        display_df = form_df.drop(columns=['UID'], errors='ignore')
        
        edited_master_df = st.data_editor(
            display_df, 
            num_rows="dynamic",
            use_container_width=True,
            key="master_editor"
        )
        
        col_save, col_csv, col_clear = st.columns([2, 1, 1])
        
        with col_save:
            if st.button("💾 Save Database Corrections", type="primary"):
                edited_master_df['UID'] = edited_master_df['Class'].astype(str) + "_" + edited_master_df['Section'].astype(str) + "_" + edited_master_df['Roll'].astype(str)
                overwrite_sheet_df('form_distribution_log', edited_master_df)
                st.success("✅ Corrections saved to the cloud database successfully!")
                st.rerun()

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
# TAB 6: SUMMARY & PROGRESS 
# ==========================================
with tab6:
    st.subheader("📈 Class-Wise Distribution & Return Summary")
    
    if students_df.empty:
        st.warning("No student data found to generate a summary.")
    else:
        summary_df = students_df.groupby(['Class', 'Section']).size().reset_index(name='Total Students')
        
        if not form_df.empty:
            gen_counts = form_df.groupby(['Class', 'Section']).size().reset_index(name='Forms Generated')
            dist_df = form_df[form_df['Date (receive form)'] != 'Pending']
            dist_counts = dist_df.groupby(['Class', 'Section']).size().reset_index(name='Distributed')
            comp_df = form_df[form_df['Return Status'] == 'Complete']
            comp_counts = comp_df.groupby(['Class', 'Section']).size().reset_index(name='Returned (Complete)')
            incomp_df = form_df[form_df['Return Status'] == 'Incomplete']
            incomp_counts = incomp_df.groupby(['Class', 'Section']).size().reset_index(name='Returned (Incomplete)')
            
            # WhatsApp Metrics
            wa_df = form_df[form_df['WhatsApp Added'].isin(IN_GROUP_STATUSES)]
            wa_counts = wa_df.groupby(['Class', 'Section']).size().reset_index(name='WhatsApp Synced')

            # Link Sent Metrics
            link_df = form_df[form_df['WhatsApp Added'] == 'Invitation Sent']
            link_counts = link_df.groupby(['Class', 'Section']).size().reset_index(name='Link Sent')

            nowa_df = form_df[form_df['WhatsApp Added'].isin(NO_WA_STATUSES)]
            nowa_counts = nowa_df.groupby(['Class', 'Section']).size().reset_index(name='No Smartphone')

            mob_up_df = form_df[form_df['Mobile Updated'] == 'Yes']
            mob_up_counts = mob_up_df.groupby(['Class', 'Section']).size().reset_index(name='Mobile Numbers Changed')

            summary_df = pd.merge(summary_df, gen_counts, on=['Class', 'Section'], how='left').fillna(0)
            summary_df = pd.merge(summary_df, dist_counts, on=['Class', 'Section'], how='left').fillna(0)
            summary_df = pd.merge(summary_df, comp_counts, on=['Class', 'Section'], how='left').fillna(0)
            summary_df = pd.merge(summary_df, incomp_counts, on=['Class', 'Section'], how='left').fillna(0)
            summary_df = pd.merge(summary_df, wa_counts, on=['Class', 'Section'], how='left').fillna(0)
            summary_df = pd.merge(summary_df, link_counts, on=['Class', 'Section'], how='left').fillna(0)
            summary_df = pd.merge(summary_df, nowa_counts, on=['Class', 'Section'], how='left').fillna(0)
            summary_df = pd.merge(summary_df, mob_up_counts, on=['Class', 'Section'], how='left').fillna(0)
            
            summary_df['Outstanding (With Guardian)'] = summary_df['Distributed'] - (summary_df['Returned (Complete)'] + summary_df['Returned (Incomplete)'])
            summary_df['Pending Desk Stack'] = summary_df['Forms Generated'] - summary_df['Distributed']
            summary_df['Not Generated Yet'] = summary_df['Total Students'] - summary_df['Forms Generated']
            
            cols_to_int = ['Total Students', 'Forms Generated', 'Distributed', 'Returned (Complete)', 'Returned (Incomplete)', 'WhatsApp Synced', 'Link Sent', 'No Smartphone', 'Mobile Numbers Changed', 'Outstanding (With Guardian)', 'Pending Desk Stack', 'Not Generated Yet']
            for col in cols_to_int:
                summary_df[col] = summary_df[col].astype(int)
        else:
            for col in ['Forms Generated', 'Distributed', 'Returned (Complete)', 'Returned (Incomplete)', 'WhatsApp Synced', 'Link Sent', 'No Smartphone', 'Mobile Numbers Changed', 'Outstanding (With Guardian)', 'Pending Desk Stack']:
                summary_df[col] = 0
            summary_df['Not Generated Yet'] = summary_df['Total Students']

        custom_dict = {
            'CLASS LPP': -1, 'LPP': -1,
            'CLASS PP': 0, 'PP': 0,
            'CLASS I': 1, 'I': 1,
            'CLASS II': 2, 'II': 2,
            'CLASS III': 3, 'III': 3,
            'CLASS IV': 4, 'IV': 4,
            'CLASS V': 5, 'V': 5
        }
        
        summary_df['Sort_Order'] = summary_df['Class'].map(custom_dict).fillna(99)
        summary_df = summary_df.sort_values(by=['Sort_Order', 'Section']).drop(columns=['Sort_Order'])

        total_row = pd.DataFrame([{
            'Class': 'TOTAL',
            'Section': '',
            'Total Students': summary_df['Total Students'].sum(),
            'Forms Generated': summary_df['Forms Generated'].sum(),
            'Distributed': summary_df['Distributed'].sum(),
            'Returned (Complete)': summary_df['Returned (Complete)'].sum(),
            'Returned (Incomplete)': summary_df['Returned (Incomplete)'].sum(),
            'WhatsApp Synced': summary_df['WhatsApp Synced'].sum(),
            'Link Sent': summary_df['Link Sent'].sum(),
            'No Smartphone': summary_df['No Smartphone'].sum(),
            'Mobile Numbers Changed': summary_df['Mobile Numbers Changed'].sum(),
            'Outstanding (With Guardian)': summary_df['Outstanding (With Guardian)'].sum(),
            'Pending Desk Stack': summary_df['Pending Desk Stack'].sum(),
            'Not Generated Yet': summary_df['Not Generated Yet'].sum()
        }])
        
        summary_df = pd.concat([summary_df, total_row], ignore_index=True)

        st.markdown("##### Overall School Progress")
        m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
        m1.metric("Total Students", summary_df.loc[summary_df['Class'] == 'TOTAL', 'Total Students'].values[0])
        m2.metric("Forms Generated", summary_df.loc[summary_df['Class'] == 'TOTAL', 'Forms Generated'].values[0])
        m3.metric("Forms Distributed", summary_df.loc[summary_df['Class'] == 'TOTAL', 'Distributed'].values[0])
        m4.metric("📱 WA Synced", summary_df.loc[summary_df['Class'] == 'TOTAL', 'WhatsApp Synced'].values[0])
        m5.metric("🔗 Invite Sent", summary_df.loc[summary_df['Class'] == 'TOTAL', 'Link Sent'].values[0])
        m6.metric("📵 No Smartphone", summary_df.loc[summary_df['Class'] == 'TOTAL', 'No Smartphone'].values[0])
        m7.metric("🔄 Nos Changed", summary_df.loc[summary_df['Class'] == 'TOTAL', 'Mobile Numbers Changed'].values[0])

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
