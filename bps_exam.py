import streamlit as st
import pandas as pd
import re
import uuid
from datetime import datetime
import gspread
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound
from google.oauth2.service_account import Credentials

# ==========================================
# 1. AUTHENTICATION & SECURITY
# ==========================================
if 'authenticated' not in st.session_state or not st.session_state.authenticated:
    st.warning("🔒 Unauthorized Access. Please log in through the main portal.")
    st.stop()

TEACHER_INITIALS = {
    "SUKHAMAY KISKU": "SK", "TAPASI RANA": "TR", "SUJATA BISWAS ROTHA": "SBR", 
    "ROHINI SINGH": "RS", "UDAY NARAYAN JANA": "UNJ", "BIMAL KUMAR PATRA": "BKP", 
    "SUSMITA PAUL": "SP", "TAPAN KUMAR MANDAL": "TKM", "MANJUMA KHATUN": "MK"
}
INV_TEACHER_INITIALS = {v: k for k, v in TEACHER_INITIALS.items()}
TEACHER_LIST = list(TEACHER_INITIALS.keys())

CLASS_OPTIONS = ["CLASS PP", "CLASS I", "CLASS II", "CLASS III", "CLASS IV", "CLASS V"]
SECTIONS = ["A", "B", "C"]
SUBJECT_OPTIONS = [
    "বাংলা", 
    "ইংরেজি", 
    "গণিত", 
    "পরিবেশ", 
    "Health & Physical Education", 
    "Art & Work Education"
]

def inject_security_css(user_name):
    wm = f"{user_name} - EXAM SECURE"
    st.markdown(f"""<style>
        .watermark {{ position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; pointer-events: none; z-index: 9999; background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" viewBox="0 0 300 300"><text x="50" y="150" fill="rgba(200, 200, 200, 0.15)" font-size="20" transform="rotate(-45 150 150)" font-family="Arial, sans-serif">{wm}</text></svg>'); background-repeat: repeat; }}
        .stButton>button {{ border-radius: 8px; font-weight: bold; }}
        .header-card {{ background-color: #f8f9fa; padding: 15px; border-radius: 10px; border-left: 5px solid #6f42c1; margin-bottom: 15px; }}
    </style><div class="watermark"></div>""", unsafe_allow_html=True)

inject_security_css(st.session_state.user_name)

# ==========================================
# 2. GOOGLE SHEETS CONNECTORS
# ==========================================
@st.cache_resource
def get_google_credentials():
    return Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.readonly"]
    )

@st.cache_resource
def init_db_sheet():
    try: return gspread.authorize(get_google_credentials()).open("BPS_Database")
    except Exception: st.error("⚠️ BPS_Database not found!"); st.stop()

@st.cache_resource
def init_exam_sheet():
    try: return gspread.authorize(get_google_credentials()).open("BPS EXAM")
    except SpreadsheetNotFound: 
        st.error("🚨 **Critical Error:** Could not find a Google Sheet named `BPS EXAM`.")
        st.stop()

@st.cache_resource
def init_routine_sheet():
    try: return gspread.authorize(get_google_credentials()).open("bps_routine")
    except Exception: return None

def ensure_worksheet(sh, title, headers):
    try: ws = sh.worksheet(title)
    except WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=1000, cols=20)
        ws.append_row(headers)
    return ws

def refresh_exam_data():
    fetch_exam_schedules.clear()
    fetch_exam_marks.clear()
    fetch_routine_data.clear()
    init_subject_map.clear()
    fetch_teacher_status.clear()

@st.cache_data(ttl=300)
def fetch_mdm_log():
    try: return pd.DataFrame(init_db_sheet().worksheet("mdm_log").get_all_records()).astype(str)
    except Exception: return pd.DataFrame()

@st.cache_data(ttl=300)
def fetch_routine_data():
    try:
        r_sh = init_routine_sheet()
        if r_sh:
            df = pd.DataFrame(r_sh.sheet1.get_all_records()).astype(str)
            df.columns = [str(c).strip() for c in df.columns]
            return df
    except Exception: pass
    return pd.DataFrame()

def detect_teacher_from_routine(routine_df, class_name, section_name, subject_name):
    if routine_df.empty or 'Class' not in routine_df.columns or 'Subject' not in routine_df.columns:
        return TEACHER_LIST[0]
    
    aliases = {
        "বাংলা": ["বাংলা", "bengali", "bangla", "সহজপাঠ"],
        "ইংরেজি": ["ইংরেজি", "english", "ingreji", "wings"],
        "গণিত": ["গণিত", "math", "mathematics"],
        "পরিবেশ": ["পরিবেশ", "evs", "environment", "poribesh", "জগৎ বাড়ি"],
        "Health & Physical Education": ["স্বাস্থ্য", "খেলা", "health", "physical", "hpe", "pe", "swasthya"],
        "Art & Work Education": ["ড্রয়িং", "নাচ", "গান", "নাটক", "আবৃত্তি", "art", "work", "craft", "কম্পিউটার", "জি. কে"]
    }
    
    target_keywords = aliases.get(subject_name, [subject_name.lower()])
    filtered = routine_df[routine_df['Class'].astype(str).str.strip().str.upper() == class_name.upper()]
    if 'Section' in filtered.columns and not filtered.empty:
        sec_match = filtered[filtered['Section'].astype(str).str.strip().str.upper() == section_name.upper()]
        if not sec_match.empty: filtered = sec_match
            
    for _, row in filtered.iterrows():
        rout_sub = str(row.get('Subject', '')).strip().lower()
        if any(kw.lower() in rout_sub for kw in target_keywords):
            teacher_code = str(row.get('Teacher', '')).strip()
            teacher_code = re.sub(r"\s*\(Sub\)", "", teacher_code, flags=re.IGNORECASE).strip()
            full_name = INV_TEACHER_INITIALS.get(teacher_code, teacher_code)
            if full_name in TEACHER_LIST: return full_name
                
    return "TAPASI RANA"

# ==========================================
# 3. MASTER SUBJECT MAPPING & STATUS TRACKING
# ==========================================
@st.cache_data(ttl=300)
def fetch_teacher_status():
    sh = init_exam_sheet()
    ws = ensure_worksheet(sh, "teacher_exam_status", ["Teacher", "Status", "Timestamp"])
    return pd.DataFrame(ws.get_all_records()).astype(str)

def update_teacher_status(teacher_name, status):
    df = fetch_teacher_status()
    now_str = datetime.now().strftime("%Y-%m-%d %I:%M %p")
    
    if not df.empty and teacher_name in df['Teacher'].values:
        df.loc[df['Teacher'] == teacher_name, 'Status'] = status
        df.loc[df['Teacher'] == teacher_name, 'Timestamp'] = now_str
    else:
        new_row = pd.DataFrame([{"Teacher": teacher_name, "Status": status, "Timestamp": now_str}])
        df = pd.concat([df, new_row], ignore_index=True)
        
    overwrite_sheet(init_exam_sheet(), "teacher_exam_status", df, ["Teacher", "Status", "Timestamp"])
    fetch_teacher_status.clear()

@st.cache_data(ttl=300)
def init_subject_map():
    sh = init_exam_sheet()
    try:
        ws = sh.worksheet("exam_subject_map")
        records = ws.get_all_records()
    except WorksheetNotFound:
        ws = sh.add_worksheet(title="exam_subject_map", rows=1000, cols=10)
        ws.append_row(["Map_ID", "Class", "Section", "Subject", "Teacher", "Modified_By", "Timestamp"])
        records = []
        
    if not records:
        routine_df = fetch_routine_data()
        classes = [("CLASS PP", "A"), ("CLASS I", "A"), ("CLASS II", "A"), ("CLASS III", "A"), ("CLASS IV", "A"), ("CLASS IV", "B"), ("CLASS V", "A")]
        new_records = []
        for c, s in classes:
            for sub in SUBJECT_OPTIONS:
                teacher = detect_teacher_from_routine(routine_df, c, s, sub)
                new_records.append({
                    "Map_ID": uuid.uuid4().hex,
                    "Class": c,
                    "Section": s,
                    "Subject": sub,
                    "Teacher": teacher,
                    "Modified_By": "Auto-Generated",
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %I:%M %p")
                })
        df = pd.DataFrame(new_records)
        ws.update([df.columns.values.tolist()] + df.values.tolist())
        return df
        
    return pd.DataFrame(records).astype(str)

def save_subject_map(edited_df, original_df, user_name):
    now_str = datetime.now().strftime("%Y-%m-%d %I:%M %p")
    final_records = []
    
    for _, row in edited_df.iterrows():
        row_dict = row.to_dict()
        map_id = str(row_dict.get('Map_ID', ''))
        
        if not map_id or map_id == 'nan' or map_id == 'None' or map_id == '':
            row_dict['Map_ID'] = uuid.uuid4().hex
            row_dict['Modified_By'] = user_name
            row_dict['Timestamp'] = now_str
        else:
            orig_match = original_df[original_df['Map_ID'] == map_id]
            if not orig_match.empty:
                orig = orig_match.iloc[0]
                if (str(row_dict.get('Class')) != str(orig.get('Class')) or 
                    str(row_dict.get('Section')) != str(orig.get('Section')) or 
                    str(row_dict.get('Subject')) != str(orig.get('Subject')) or 
                    str(row_dict.get('Teacher')) != str(orig.get('Teacher'))):
                    row_dict['Modified_By'] = user_name
                    row_dict['Timestamp'] = now_str
            else:
                row_dict['Modified_By'] = user_name
                row_dict['Timestamp'] = now_str
                
        final_records.append(row_dict)
        
    final_df = pd.DataFrame(final_records)
    overwrite_sheet(init_exam_sheet(), "exam_subject_map", final_df, ["Map_ID", "Class", "Section", "Subject", "Teacher", "Modified_By", "Timestamp"])
    refresh_exam_data()

def get_auto_teacher(cls_name, sec_name, sub_name):
    map_df = init_subject_map()
    match = map_df[(map_df['Class'] == cls_name) & (map_df['Section'] == sec_name) & (map_df['Subject'] == sub_name)]
    if not match.empty:
        return match.iloc[0]['Teacher']
    routine_df = fetch_routine_data()
    return detect_teacher_from_routine(routine_df, cls_name, sec_name, sub_name)

# ==========================================
# 4. EXAM SCHEDULES & MARKS ENGINES
# ==========================================
@st.cache_data(ttl=300)
def fetch_exam_schedules():
    sh = init_exam_sheet()
    ws = ensure_worksheet(sh, "schedules", ["Exam_ID", "Date", "Class", "Section", "Subject", "Teacher"])
    return pd.DataFrame(ws.get_all_records()).astype(str)

@st.cache_data(ttl=300)
def fetch_exam_marks():
    sh = init_exam_sheet()
    ws = ensure_worksheet(sh, "marks", ["Exam_ID", "Date", "Class", "Section", "Subject", "Roll", "Name", "Marks_Obtained"])
    return pd.DataFrame(ws.get_all_records()).astype(str)

def overwrite_sheet(sh, sheet_name, df, headers):
    ws = ensure_worksheet(sh, sheet_name, headers)
    ws.clear()
    if not df.empty:
        ws.update([df.columns.values.tolist()] + df.fillna("").values.tolist())
    else:
        ws.append_row(headers)
    refresh_exam_data()

# ==========================================
# 5. MAIN APPLICATION UI
# ==========================================
st.markdown("<h2>📝 BPS Examination Manager</h2>", unsafe_allow_html=True)
st.sidebar.button("🔄 Sync Exam Data", on_click=refresh_exam_data, use_container_width=True)

# ---------------------------------------------------------
# ADMIN VIEW
# ---------------------------------------------------------
if st.session_state.user_role == "admin":
    tabs = st.tabs(["📚 Master Subject Map", "📅 Schedule New Exams", "📋 View Scheduled Exams"])
    
    with tabs[0]:
        st.markdown("<div class='header-card'><h4>👨‍🏫 Master Subject Mapping</h4><p style='margin:0; font-size:13px;'>Review all teacher assignments. <b>Rows changed by teachers are highlighted in green.</b></p></div>", unsafe_allow_html=True)
        
        # --- ADMIN TRACKING DASHBOARD ---
        with st.expander("📊 View Teacher Acknowledgement Status", expanded=True):
            status_df = fetch_teacher_status()
            
            # Create a master list to show all teachers even if they haven't logged in
            all_teachers = pd.DataFrame({"Teacher": [t for t in TEACHER_LIST if t != "SUKHAMAY KISKU"]}) # Excluding Admin
            
            if not status_df.empty:
                merged_status = pd.merge(all_teachers, status_df, on="Teacher", how="left").fillna({"Status": "Pending ⏳", "Timestamp": "Never"})
            else:
                merged_status = all_teachers.copy()
                merged_status["Status"] = "Pending ⏳"
                merged_status["Timestamp"] = "Never"
                
            def highlight_status(val):
                if "Confirmed" in str(val): return 'color: green; font-weight: bold'
                if "Edited" in str(val): return 'color: orange; font-weight: bold'
                if "Viewed" in str(val): return 'color: blue; font-weight: bold'
                return 'color: red'
                
            st.dataframe(
                merged_status.style.map(highlight_status, subset=['Status']), 
                hide_index=True, 
                use_container_width=True
            )
            
        st.divider()

        subject_map_df = init_subject_map()
        
        def highlight_modified(row):
            if row['Modified_By'] != 'Auto-Generated' and str(row['Modified_By']).strip() != '':
                return ['background-color: #d4edda; color: #155724; font-weight:bold'] * len(row)
            return [''] * len(row)
            
        edited_map_admin = st.data_editor(
            subject_map_df.style.apply(highlight_modified, axis=1),
            num_rows="dynamic",
            column_config={
                "Map_ID": None,
                "Timestamp": st.column_config.TextColumn("Last Updated", disabled=True),
                "Modified_By": st.column_config.TextColumn("Changed By", disabled=True),
                "Teacher": st.column_config.SelectboxColumn("Teacher", options=TEACHER_LIST, required=True),
                "Class": st.column_config.SelectboxColumn("Class", options=CLASS_OPTIONS, required=True),
                "Section": st.column_config.SelectboxColumn("Section", options=SECTIONS, required=True),
                "Subject": st.column_config.SelectboxColumn("Subject", options=SUBJECT_OPTIONS, required=True)
            },
            hide_index=True,
            use_container_width=True
        )
        
        if st.button("💾 Save Master Map Changes", type="primary"):
            save_subject_map(edited_map_admin, subject_map_df, st.session_state.user_name)
            st.success("Master Subject Map has been successfully updated!")
            st.rerun()

    with tabs[1]:
        st.markdown("<div class='header-card'><h4>➕ Create Exam Schedule</h4><p style='margin:0; font-size:13px;'>Teachers are automatically detected from the <b>Master Subject Map</b>!</p></div>", unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        ex_date = c1.date_input("Exam Date", datetime.now()).strftime("%d-%m-%Y")
        ex_sub = c2.selectbox("Select Subject", SUBJECT_OPTIONS)
        
        c3, c4 = st.columns(2)
        ex_classes = c3.multiselect("Select Class(es)", CLASS_OPTIONS, default=["CLASS III", "CLASS IV"])
        ex_secs = c4.multiselect("Select Section(s)", SECTIONS, default=["A"])
        
        if ex_classes and ex_secs:
            st.markdown("---")
            st.markdown("##### 🔍 Review Assigned Invigilators")
            
            preview_rows = []
            for cls_name in ex_classes:
                for sec_name in ex_secs:
                    auto_teacher = get_auto_teacher(cls_name, sec_name, ex_sub)
                    preview_rows.append({
                        "Date": ex_date,
                        "Class": cls_name,
                        "Section": sec_name,
                        "Subject": ex_sub,
                        "Teacher": auto_teacher
                    })
            
            preview_df = pd.DataFrame(preview_rows)
            
            edited_schedule_grid = st.data_editor(
                preview_df,
                column_config={
                    "Date": st.column_config.TextColumn("Date", disabled=True),
                    "Class": st.column_config.TextColumn("Class", disabled=True),
                    "Section": st.column_config.TextColumn("Section", disabled=True),
                    "Subject": st.column_config.TextColumn("Subject", disabled=True),
                    "Teacher": st.column_config.SelectboxColumn("Invigilator / Grader", options=TEACHER_LIST, required=True)
                },
                hide_index=True,
                use_container_width=True
            )
            
            if st.button("💾 Confirm & Save All Schedules", type="primary"):
                schedules = fetch_exam_schedules()
                new_records = []
                
                for _, r in edited_schedule_grid.iterrows():
                    exam_id = f"{r['Date']}_{r['Class']}_{r['Section']}_{r['Subject']}".replace(" ", "")
                    new_records.append({
                        "Exam_ID": exam_id,
                        "Date": r['Date'],
                        "Class": r['Class'],
                        "Section": r['Section'],
                        "Subject": r['Subject'],
                        "Teacher": r['Teacher']
                    })
                
                new_df = pd.DataFrame(new_records)
                
                if not schedules.empty:
                    schedules_cleaned = schedules[~schedules['Exam_ID'].isin(new_df['Exam_ID'])]
                    final_schedules = pd.concat([schedules_cleaned, new_df], ignore_index=True)
                else:
                    final_schedules = new_df
                    
                overwrite_sheet(init_exam_sheet(), "schedules", final_schedules, ["Exam_ID", "Date", "Class", "Section", "Subject", "Teacher"])
                st.success(f"✅ Successfully scheduled {len(new_records)} exam(s) for {ex_sub} on {ex_date}!")
                st.rerun()
        else:
            st.info("👆 Please select at least one Class and one Section above to preview schedules.")

    with tabs[2]:
        st.subheader("Upcoming & Past Exams")
        schedules = fetch_exam_schedules()
        if not schedules.empty:
            st.dataframe(schedules[['Date', 'Class', 'Section', 'Subject', 'Teacher']], use_container_width=True, hide_index=True)
            
            st.markdown("##### 🗑️ Delete an Exam")
            del_id = st.selectbox("Select Exam to Remove", ["Select..."] + schedules['Exam_ID'].tolist())
            if del_id != "Select..." and st.button("Delete Schedule", type="primary"):
                filtered_df = schedules[schedules['Exam_ID'] != del_id]
                overwrite_sheet(init_exam_sheet(), "schedules", filtered_df, ["Exam_ID", "Date", "Class", "Section", "Subject", "Teacher"])
                st.success("Deleted!")
                st.rerun()
        else:
            st.info("No exams scheduled yet.")

# ---------------------------------------------------------
# TEACHER VIEW
# ---------------------------------------------------------
elif st.session_state.user_role == "teacher":
    tabs = st.tabs(["📚 My Subject Mapping", "🎓 Enter Marks"])
    
    with tabs[0]:
        st.markdown("<div class='header-card'><h4>📚 Check & Update Exam Subjects</h4><p style='margin:0; font-size:14px;'>Review your assigned exam subjects below. You can update the Class, Section, or Subject if required.</p></div>", unsafe_allow_html=True)
        
        # --- BACKGROUND LOGGING: Log "Viewed" Status if they haven't confirmed/edited recently ---
        status_df = fetch_teacher_status()
        current_status = status_df[status_df['Teacher'] == st.session_state.user_name]['Status'].values
        if len(current_status) == 0 or current_status[0] not in ["Confirmed ✅", "Edited ✏️", "Viewed 👀"]:
            update_teacher_status(st.session_state.user_name, "Viewed 👀")
            
        subject_map_df = init_subject_map()
        
        def highlight_teacher(row):
            if row['Teacher'] == st.session_state.user_name:
                return ['background-color: #e2e3e5; font-weight: bold'] * len(row)
            return [''] * len(row)
            
        edited_map_teacher = st.data_editor(
            subject_map_df.style.apply(highlight_teacher, axis=1),
            num_rows="dynamic",
            column_config={
                "Map_ID": None,
                "Timestamp": st.column_config.TextColumn("Last Updated", disabled=True),
                "Modified_By": st.column_config.TextColumn("Changed By", disabled=True),
                "Teacher": st.column_config.SelectboxColumn("Teacher", options=TEACHER_LIST, required=True),
                "Class": st.column_config.SelectboxColumn("Class", options=CLASS_OPTIONS, required=True),
                "Section": st.column_config.SelectboxColumn("Section", options=SECTIONS, required=True),
                "Subject": st.column_config.SelectboxColumn("Subject", options=SUBJECT_OPTIONS, required=True)
            },
            hide_index=True,
            use_container_width=True
        )
        
        st.write("")
        col_ok, col_save = st.columns(2)
        
        with col_ok:
            if st.button("✅ Confirm All My Subjects are Correct", type="secondary", use_container_width=True):
                update_teacher_status(st.session_state.user_name, "Confirmed ✅")
                st.success("Thank you! Head Sir has been notified that your subjects are correct.")
                st.rerun()
                
        with col_save:
            if st.button("💾 Save My Changes", type="primary", use_container_width=True):
                save_subject_map(edited_map_teacher, subject_map_df, st.session_state.user_name)
                update_teacher_status(st.session_state.user_name, "Edited ✏️")
                st.success("Changes saved! The Head Teacher will review your updates.")
                st.rerun()
            
    with tabs[1]:
        st.markdown("<div class='header-card'><h4>🎓 Grade Entry Portal</h4><p style='margin:0; font-size:14px;'>Only students present in the MDM Log on the exam date will appear here.</p></div>", unsafe_allow_html=True)
        
        schedules = fetch_exam_schedules()
        if not schedules.empty:
            my_exams = schedules[schedules['Teacher'] == st.session_state.user_name]
            
            if my_exams.empty:
                st.info("🏖️ You have no exams assigned for grading.")
            else:
                exam_display = {f"{r['Date']} | {r['Class']}-{r['Section']} | {r['Subject']}": r['Exam_ID'] for _, r in my_exams.iterrows()}
                selected_exam_str = st.selectbox("Select Exam to Grade", ["Select..."] + list(exam_display.keys()))
                
                if selected_exam_str != "Select...":
                    exam_id = exam_display[selected_exam_str]
                    exam_info = my_exams[my_exams['Exam_ID'] == exam_id].iloc[0]
                    
                    e_date = exam_info['Date']
                    e_class = exam_info['Class']
                    e_sec = exam_info['Section']
                    e_sub = exam_info['Subject']
                    
                    st.markdown("---")
                    st.subheader(f"Entering marks for: {e_sub}")
                    
                    mdm = fetch_mdm_log()
                    if not mdm.empty:
                        mdm_present = mdm[(mdm['Date'] == e_date) & (mdm['Class'] == e_class) & (mdm['Section'] == e_sec)]
                    else:
                        mdm_present = pd.DataFrame()
                        
                    if mdm_present.empty:
                        st.error(f"🚨 **No Students Found!** The MDM attendance log for **{e_class}-{e_sec}** on **{e_date}** is empty. You must complete MDM entry for this day before you can enter marks.")
                    else:
                        st.success(f"✅ Found {len(mdm_present)} students present on {e_date}.")
                        
                        all_marks = fetch_exam_marks()
                        existing_marks = pd.DataFrame()
                        if not all_marks.empty:
                            existing_marks = all_marks[all_marks['Exam_ID'] == exam_id]
                        
                        roster = mdm_present[['Roll', 'Name']].copy()
                        if not existing_marks.empty:
                            roster = pd.merge(roster, existing_marks[['Roll', 'Marks_Obtained']], on='Roll', how='left')
                        else:
                            roster['Marks_Obtained'] = ""
                            
                        st.markdown("Fill in the **Marks_Obtained** column below and click Save.")
                        edited_marks = st.data_editor(
                            roster,
                            column_config={
                                "Roll": st.column_config.TextColumn("Roll No.", disabled=True),
                                "Name": st.column_config.TextColumn("Student Name", disabled=True),
                                "Marks_Obtained": st.column_config.TextColumn("Marks", required=True)
                            },
                            hide_index=True,
                            use_container_width=True
                        )
                        
                        if st.button("💾 Save Exam Marks", type="primary"):
                            new_records = []
                            for _, r in edited_marks.iterrows():
                                if pd.notna(r['Marks_Obtained']) and str(r['Marks_Obtained']).strip() != "":
                                    new_records.append({
                                        "Exam_ID": exam_id,
                                        "Date": e_date,
                                        "Class": e_class,
                                        "Section": e_sec,
                                        "Subject": e_sub,
                                        "Roll": r['Roll'],
                                        "Name": r['Name'],
                                        "Marks_Obtained": r['Marks_Obtained']
                                    })
                                    
                            new_marks_df = pd.DataFrame(new_records)
                            
                            if not all_marks.empty:
                                all_marks_purged = all_marks[all_marks['Exam_ID'] != exam_id]
                                final_marks = pd.concat([all_marks_purged, new_marks_df], ignore_index=True)
                            else:
                                final_marks = new_marks_df
                                
                            overwrite_sheet(
                                init_exam_sheet(), 
                                "marks", 
                                final_marks, 
                                ["Exam_ID", "Date", "Class", "Section", "Subject", "Roll", "Name", "Marks_Obtained"]
                            )
                            st.success(f"🎉 Marks saved successfully for {len(new_records)} students!")
                            st.rerun()
        else:
            st.info("No exams have been scheduled in the system yet.")
