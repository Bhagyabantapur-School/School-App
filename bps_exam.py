import streamlit as st
import pandas as pd
import re
import uuid
from datetime import datetime
import pytz
import gspread
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import AuthorizedSession
import numpy as np
import base64
import concurrent.futures

# ==========================================
# 1. AUTHENTICATION & SECURITY
# ==========================================
if 'authenticated' not in st.session_state or not st.session_state.authenticated:
    st.warning("🔒 Unauthorized Access. Please log in through the main portal.")
    st.stop()

IST = pytz.timezone('Asia/Kolkata')

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
    wm = str(user_name) + " - EXAM SECURE"
    css = (
        "<style>"
        ".watermark { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; pointer-events: none; z-index: 9999; "
        "background-image: url('data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"300\" height=\"300\" viewBox=\"0 0 300 300\">"
        "<text x=\"50\" y=\"150\" fill=\"rgba(200, 200, 200, 0.15)\" font-size=\"20\" transform=\"rotate(-45 150 150)\" font-family=\"Arial, sans-serif\">" + wm + "</text></svg>'); "
        "background-repeat: repeat; }"
        ".stButton>button { border-radius: 8px; font-weight: bold; }"
        ".header-card { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border-left: 5px solid #6f42c1; margin-bottom: 15px; }"
        ".student-card { background-color: #f8f9fa; border-radius: 12px; padding: 15px; margin-bottom: 15px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.03); }"
        "@media (max-width: 768px) {"
        ".roster-container [data-testid=\"stHorizontalBlock\"] { display: flex !important; flex-direction: row !important; flex-wrap: nowrap !important; gap: 15px; }"
        ".roster-container [data-testid=\"column\"] { width: 50% !important; min-width: 0 !important; flex: 1 1 50% !important; display: block !important; }"
        ".roster-container [data-testid=\"stNumberInputStepUp\"], .roster-container [data-testid=\"stNumberInputStepDown\"] { display: none !important; }"
        ".roster-container input { padding: 0.5rem !important; font-size: 16px !important; }"
        "}"
        "</style><div class=\"watermark\"></div>"
    )
    st.markdown(css, unsafe_allow_html=True)

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
    try: 
        return gspread.authorize(get_google_credentials()).open("BPS_Database")
    except Exception: 
        st.error("⚠️ BPS_Database not found!")
        st.stop()

@st.cache_resource
def init_exam_sheet():
    try: 
        return gspread.authorize(get_google_credentials()).open("BPS EXAM")
    except SpreadsheetNotFound: 
        st.error("🚨 **Critical Error:** Could not find a Google Sheet named `BPS EXAM`.")
        st.stop()

@st.cache_resource
def init_routine_sheet():
    try: 
        return gspread.authorize(get_google_credentials()).open("bps_routine")
    except Exception: 
        return None

@st.cache_resource
def get_drive_session(): 
    return AuthorizedSession(get_google_credentials())

def ensure_worksheet(sh, title, headers):
    try: 
        ws = sh.worksheet(title)
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
    fetch_student_photos.clear()
    
    keys_to_clear = [key for key in st.session_state.keys() if key.startswith("act_") or key.startswith("ext_") or key.startswith("roster_")]
    for key in keys_to_clear:
        del st.session_state[key]

@st.cache_data(ttl=300)
def fetch_mdm_log():
    try: 
        return pd.DataFrame(init_db_sheet().worksheet("mdm_log").get_all_records()).astype(str)
    except Exception: 
        return pd.DataFrame()

# ---------------------------------------------------------
# SECURE PHOTO ENGINE
# ---------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_secure_image_bytes(file_id):
    try:
        r = get_drive_session().get(f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media")
        return r.content if r.status_code == 200 else None
    except Exception: 
        return None

def get_secure_photo_uri(url):
    fb = "https://www.w3schools.com/howto/img_avatar.png"
    if pd.isna(url) or url == "" or not isinstance(url, str): 
        return fb
    match = re.search(r"(?:id=|/d/)([\w-]+)", url)
    if match:
        b = fetch_secure_image_bytes(match.group(1))
        if b: 
            return f"data:image/jpeg;base64,{base64.b64encode(b).decode()}"
    return url if url.startswith("http") else fb

@st.cache_data(ttl=300)
def fetch_student_photos():
    try:
        db = init_db_sheet()
        ws = db.worksheet("students_master")
        data = ws.get_all_values()
        
        if len(data) > 1:
            df = pd.DataFrame(data)
            df.columns = df.iloc[0].astype(str).str.strip()
            df = df[1:].reset_index(drop=True)
            
            if 'Thumb_URL' in df.columns and 'Class' in df.columns and 'Roll' in df.columns:
                if 'Section' not in df.columns:
                    df['Section'] = 'A'
                    
                photo_df = df[['Class', 'Section', 'Roll', 'Thumb_URL']].copy()
                photo_df['Class'] = photo_df['Class'].astype(str).str.strip().str.upper()
                photo_df['Section'] = photo_df['Section'].astype(str).str.strip().str.upper()
                photo_df['Roll'] = photo_df['Roll'].astype(str).str.strip()
                photo_df['Thumb_URL'] = photo_df['Thumb_URL'].astype(str).str.strip()
                return photo_df
    except Exception: 
        pass
    
    return pd.DataFrame(columns=["Class", "Section", "Roll", "Thumb_URL"])

@st.cache_data(ttl=300)
def fetch_routine_data():
    try:
        r_sh = init_routine_sheet()
        if r_sh:
            df = pd.DataFrame(r_sh.sheet1.get_all_records()).astype(str)
            df.columns = [str(c).strip() for c in df.columns]
            return df
    except Exception: 
        pass
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
        if not sec_match.empty: 
            filtered = sec_match
            
    for _, row in filtered.iterrows():
        rout_sub = str(row.get('Subject', '')).strip().lower()
        if any(kw.lower() in rout_sub for kw in target_keywords):
            teacher_code = str(row.get('Teacher', '')).strip()
            teacher_code = re.sub(r"\s*\(Sub\)", "", teacher_code, flags=re.IGNORECASE).strip()
            full_name = INV_TEACHER_INITIALS.get(teacher_code, teacher_code)
            if full_name in TEACHER_LIST: 
                return full_name
                
    return "TAPASI RANA"

# ==========================================
# 3. MASTER SUBJECT MAPPING & STATUS TRACKING
# ==========================================
def sort_display_df(df):
    if df.empty: 
        return df
    temp_df = df.copy()
    temp_df['C_Sort'] = pd.Categorical(temp_df['Class'], categories=CLASS_OPTIONS, ordered=True)
    temp_df['S_Sort'] = pd.Categorical(temp_df['Section'], categories=SECTIONS, ordered=True)
    temp_df['Sub_Sort'] = pd.Categorical(temp_df['Subject'], categories=SUBJECT_OPTIONS, ordered=True)
    temp_df = temp_df.sort_values(['Sub_Sort', 'C_Sort', 'S_Sort']).drop(columns=['C_Sort', 'S_Sort', 'Sub_Sort']).reset_index(drop=True)
    return temp_df

@st.cache_data(ttl=300)
def fetch_teacher_status():
    sh = init_exam_sheet()
    ws = ensure_worksheet(sh, "teacher_exam_status", ["Teacher", "Status", "Timestamp"])
    records = ws.get_all_records()
    if not records: 
        return pd.DataFrame(columns=["Teacher", "Status", "Timestamp"])
    return pd.DataFrame(records).astype(str)

def update_teacher_status(teacher_name, status):
    df = fetch_teacher_status()
    now_str = datetime.now(IST).strftime("%Y-%m-%d %I:%M %p")
    
    if not df.empty and 'Teacher' in df.columns and teacher_name in df['Teacher'].values:
        df.loc[df['Teacher'] == teacher_name, 'Status'] = status
        df.loc[df['Teacher'] == teacher_name, 'Timestamp'] = now_str
    else:
        new_row = pd.DataFrame([{"Teacher": teacher_name, "Status": status, "Timestamp": now_str}])
        if not df.empty:
            df = pd.concat([df, new_row], ignore_index=True)
        else:
            df = new_row
            
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
                search_sub = sub
                if sub in ["Health & Physical Education", "Art & Work Education"]:
                    search_sub = "বাংলা"
                    
                teacher = detect_teacher_from_routine(routine_df, c, s, search_sub)
                
                new_records.append({
                    "Map_ID": uuid.uuid4().hex,
                    "Class": c,
                    "Section": s,
                    "Subject": sub,
                    "Teacher": teacher,
                    "Modified_By": "Auto-Generated",
                    "Timestamp": datetime.now(IST).strftime("%Y-%m-%d %I:%M %p")
                })
        df = pd.DataFrame(new_records)
        ws.update([df.columns.values.tolist()] + df.values.tolist())
        return df
        
    return pd.DataFrame(records).astype(str)

def save_subject_map(edited_df, original_df, user_name, is_partial=False):
    now_str = datetime.now(IST).strftime("%Y-%m-%d %I:%M %p")
    
    if not is_partial:
        final_df = edited_df.copy()
        for i, row in final_df.iterrows():
            map_id = str(row.get('Map_ID', ''))
            if not map_id or map_id == 'nan' or map_id == 'None' or map_id == '':
                final_df.at[i, 'Map_ID'] = uuid.uuid4().hex
                final_df.at[i, 'Modified_By'] = user_name
                final_df.at[i, 'Timestamp'] = now_str
            else:
                orig_match = original_df[original_df['Map_ID'] == map_id]
                if not orig_match.empty:
                    orig = orig_match.iloc[0]
                    if (str(row.get('Class')) != str(orig.get('Class')) or 
                        str(row.get('Section')) != str(orig.get('Section')) or 
                        str(row.get('Subject')) != str(orig.get('Subject')) or 
                        str(row.get('Teacher')) != str(orig.get('Teacher'))):
                        final_df.at[i, 'Modified_By'] = user_name
                        final_df.at[i, 'Timestamp'] = now_str
    else:
        orig_teacher_ids = original_df[original_df['Teacher'] == user_name]['Map_ID'].tolist()
        edited_ids = [str(mid) for mid in edited_df['Map_ID'] if pd.notna(mid) and str(mid).strip() != '' and str(mid) != 'nan']
        deleted_ids = [mid for mid in orig_teacher_ids if mid not in edited_ids]
        
        final_df = original_df[~original_df['Map_ID'].isin(deleted_ids)].copy()
        
        for _, row in edited_df.iterrows():
            row_dict = row.to_dict()
            map_id = str(row_dict.get('Map_ID', ''))
            
            if not map_id or map_id == 'nan' or map_id == 'None' or map_id == '':
                row_dict['Map_ID'] = uuid.uuid4().hex
                row_dict['Modified_By'] = user_name
                row_dict['Timestamp'] = now_str
                row_dict['Teacher'] = user_name 
                final_df = pd.concat([final_df, pd.DataFrame([row_dict])], ignore_index=True)
            else:
                idx = final_df.index[final_df['Map_ID'] == map_id].tolist()
                if idx:
                    idx = idx[0]
                    orig_row = final_df.iloc[idx]
                    if (str(row_dict.get('Class')) != str(orig_row.get('Class')) or 
                        str(row_dict.get('Section')) != str(orig_row.get('Section')) or 
                        str(row_dict.get('Subject')) != str(orig_row.get('Subject')) or 
                        str(row_dict.get('Teacher')) != str(orig_row.get('Teacher'))):
                        row_dict['Modified_By'] = user_name
                        row_dict['Timestamp'] = now_str
                    for col, val in row_dict.items():
                        final_df.at[idx, col] = val
                else:
                    row_dict['Modified_By'] = user_name
                    row_dict['Timestamp'] = now_str
                    final_df = pd.concat([final_df, pd.DataFrame([row_dict])], ignore_index=True)

    overwrite_sheet(init_exam_sheet(), "exam_subject_map", final_df, ["Map_ID", "Class", "Section", "Subject", "Teacher", "Modified_By", "Timestamp"])
    refresh_exam_data()

def get_auto_teacher(cls_name, sec_name, sub_name):
    map_df = init_subject_map()
    match = map_df[(map_df['Class'] == cls_name) & (map_df['Section'] == sec_name) & (map_df['Subject'] == sub_name)]
    if not match.empty:
        return match.iloc[0]['Teacher']
        
    search_sub = sub_name
    if sub_name in ["Health & Physical Education", "Art & Work Education"]:
        search_sub = "বাংলা"
    routine_df = fetch_routine_data()
    return detect_teacher_from_routine(routine_df, cls_name, sec_name, search_sub)

# ==========================================
# 4. EXAM SCHEDULES & MARKS ENGINES
# ==========================================
@st.cache_data(ttl=300)
def fetch_exam_schedules():
    sh = init_exam_sheet()
    ws = ensure_worksheet(sh, "schedules", ["Exam_ID", "Date", "Class", "Section", "Subject", "Teacher", "Full_Marks"])
    records = ws.get_all_records()
    if not records:
        return pd.DataFrame(columns=["Exam_ID", "Date", "Class", "Section", "Subject", "Teacher", "Full_Marks"])
        
    df = pd.DataFrame(records)
    if 'Full_Marks' not in df.columns:
        df['Full_Marks'] = "50"
    return df.astype(str)

@st.cache_data(ttl=300)
def fetch_exam_marks():
    sh = init_exam_sheet()
    ws = ensure_worksheet(sh, "marks", ["Exam_ID", "Date", "Class", "Section", "Subject", "Roll", "Name", "Actual_Marks", "Extra_Marks", "Total_Marks", "Full_Marks", "Percentage", "Graded_By"])
    records = ws.get_all_records()
    
    if not records:
        return pd.DataFrame(columns=["Exam_ID", "Date", "Class", "Section", "Subject", "Roll", "Name", "Actual_Marks", "Extra_Marks", "Total_Marks", "Full_Marks", "Percentage", "Graded_By"])
        
    df = pd.DataFrame(records)
    
    if 'Marks_Obtained' in df.columns and 'Actual_Marks' not in df.columns:
        df['Actual_Marks'] = df['Marks_Obtained']
        df['Extra_Marks'] = 0
        df['Total_Marks'] = df['Marks_Obtained']
        
    if 'Full_Marks' not in df.columns: 
        df['Full_Marks'] = "50"
    if 'Percentage' not in df.columns: 
        df['Percentage'] = ""
    if 'Graded_By' not in df.columns: 
        df['Graded_By'] = ""
        
    return df.astype(str)

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
    tabs = st.tabs(["📚 Master Subject Map", "📅 Schedule New Exams", "📋 View Scheduled Exams", "📈 Mark Entry Progress", "📊 View Student Marks"])
    
    with tabs[0]:
        st.markdown("<div class='header-card'><h4>👨‍🏫 Master Subject Mapping</h4><p style='margin:0; font-size:13px;'>Review all teacher assignments. <b>Rows changed by teachers are highlighted in green.</b></p></div>", unsafe_allow_html=True)
        
        with st.expander("📊 View Teacher Acknowledgement Status", expanded=True):
            status_df = fetch_teacher_status()
            all_teachers = pd.DataFrame({"Teacher": [t for t in TEACHER_LIST if t != "SUKHAMAY KISKU"]})
            
            if not status_df.empty and 'Teacher' in status_df.columns:
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
        subject_map_df = sort_display_df(subject_map_df) 
        
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
            save_subject_map(edited_map_admin, subject_map_df, st.session_state.user_name, is_partial=False)
            st.success("Master Subject Map has been successfully updated!")
            st.rerun()

    with tabs[1]:
        st.markdown("<div class='header-card'><h4>➕ Create Exam Schedule</h4><p style='margin:0; font-size:13px;'>Teachers are auto-detected. Adjust the <b>Full Marks</b> specifically for each class directly in the grid below!</p></div>", unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns([2, 2, 1])
        ex_date = c1.date_input("Exam Date", datetime.now(IST).date()).strftime("%d-%m-%Y")
        ex_sub = c2.selectbox("Select Subject", SUBJECT_OPTIONS)
        default_batch_fm = c3.number_input("Default Batch Marks", min_value=1, value=50, step=1, help="This fills the grid below. You can change them class-wise there.")
        
        c4, c5 = st.columns(2)
        ex_classes = c4.multiselect("Select Class(es)", CLASS_OPTIONS, default=["CLASS III", "CLASS IV"])
        ex_secs = c5.multiselect("Select Section(s)", SECTIONS, default=["A"])
        
        if ex_classes and ex_secs:
            st.markdown("---")
            st.markdown("##### 🔍 Verify Invigilators & Class-Wise Full Marks")
            
            preview_rows = []
            for cls_name in ex_classes:
                for sec_name in ex_secs:
                    auto_teacher = get_auto_teacher(cls_name, sec_name, ex_sub)
                    preview_rows.append({
                        "Date": ex_date,
                        "Class": cls_name,
                        "Section": sec_name,
                        "Subject": ex_sub,
                        "Teacher": auto_teacher,
                        "Full_Marks": default_batch_fm
                    })
            
            preview_df = pd.DataFrame(preview_rows)
            
            edited_schedule_grid = st.data_editor(
                preview_df,
                column_config={
                    "Date": st.column_config.TextColumn("Date", disabled=True),
                    "Class": st.column_config.TextColumn("Class", disabled=True),
                    "Section": st.column_config.TextColumn("Section", disabled=True),
                    "Subject": st.column_config.TextColumn("Subject", disabled=True),
                    "Teacher": st.column_config.SelectboxColumn("Invigilator / Grader", options=TEACHER_LIST, required=True),
                    "Full_Marks": st.column_config.NumberColumn("Full Marks (Edit if needed)", min_value=1, required=True)
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
                        "Teacher": r['Teacher'],
                        "Full_Marks": r['Full_Marks']
                    })
                
                new_df = pd.DataFrame(new_records)
                
                if not schedules.empty:
                    schedules_cleaned = schedules[~schedules['Exam_ID'].isin(new_df['Exam_ID'])]
                    final_schedules = pd.concat([schedules_cleaned, new_df], ignore_index=True)
                else:
                    final_schedules = new_df
                    
                overwrite_sheet(init_exam_sheet(), "schedules", final_schedules, ["Exam_ID", "Date", "Class", "Section", "Subject", "Teacher", "Full_Marks"])
                st.success(f"✅ Successfully scheduled {len(new_records)} exam(s) for {ex_sub} on {ex_date}!")
                st.rerun()
        else:
            st.info("👆 Please select at least one Class and one Section above to preview schedules.")

    with tabs[2]:
        st.subheader("Upcoming & Past Exams")
        schedules = fetch_exam_schedules()
        if not schedules.empty:
            st.dataframe(schedules[['Date', 'Class', 'Section', 'Subject', 'Teacher', 'Full_Marks']], use_container_width=True, hide_index=True)
            
            st.markdown("##### 🗑️ Delete an Exam")
            del_id = st.selectbox("Select Exam to Remove", ["Select..."] + schedules['Exam_ID'].tolist())
            if del_id != "Select...":
                if st.button("Delete Schedule", type="primary"):
                    filtered_df = schedules[schedules['Exam_ID'] != del_id]
                    overwrite_sheet(init_exam_sheet(), "schedules", filtered_df, ["Exam_ID", "Date", "Class", "Section", "Subject", "Teacher", "Full_Marks"])
                    st.success("Deleted!")
                    st.rerun()
        else:
            st.info("No exams scheduled yet.")

    with tabs[3]:
        st.subheader("📈 Mark Entry Progress Dashboard")
        schedules = fetch_exam_schedules()
        mdm = fetch_mdm_log()
        marks = fetch_exam_marks()
        
        if schedules.empty:
            st.info("No exams have been scheduled yet.")
        else:
            progress_data = []
            for _, r in schedules.iterrows():
                e_id = r['Exam_ID']
                e_date = r['Date']
                e_class = r['Class']
                e_sec = r['Section']
                e_sub = r['Subject']
                allotted_t = r['Teacher']
                
                if not mdm.empty:
                    if e_class == "CLASS PP":
                        mdm_present = mdm[(mdm['Date'] == e_date) & (mdm['Class'].isin(["CLASS PP", "CLASS LPP"])) & (mdm['Section'] == e_sec)]
                    else:
                        mdm_present = mdm[(mdm['Date'] == e_date) & (mdm['Class'] == e_class) & (mdm['Section'] == e_sec)]
                    tot_present = len(mdm_present)
                else:
                    tot_present = 0
                    
                entered_count = 0
                graded_by_str = "---"
                if not marks.empty:
                    exam_marks = marks[marks['Exam_ID'] == e_id]
                    entered_count = len(exam_marks[(exam_marks['Actual_Marks'].notna()) & (exam_marks['Actual_Marks'] != "") & (exam_marks['Actual_Marks'] != "nan") & (exam_marks['Actual_Marks'] != "None")])
                    
                    g_list = exam_marks['Graded_By'].unique().tolist()
                    g_list = [t for t in g_list if str(t).strip() not in ["", "nan", "None"]]
                    if g_list:
                        graded_by_str = ", ".join([TEACHER_INITIALS.get(t.strip(), t.strip()) for t in g_list])
                        
                progress_data.append({
                    "Date": e_date,
                    "Class": f"{e_class}-{e_sec}",
                    "Subject": e_sub,
                    "Allotted": TEACHER_INITIALS.get(allotted_t.strip(), allotted_t.strip()),
                    "Graded By": graded_by_str,
                    "Present": tot_present,
                    "Entered": entered_count,
                    "Progress": f"{entered_count} / {tot_present}" if tot_present > 0 else "0 / 0"
                })
                
            prog_df = pd.DataFrame(progress_data)
            st.dataframe(prog_df, use_container_width=True, hide_index=True)

    with tabs[4]:
        st.subheader("📊 View Student Marks")
        schedules = fetch_exam_schedules()
        marks = fetch_exam_marks()
        
        if schedules.empty:
            st.info("No exams scheduled.")
        else:
            exam_opts = {}
            for _, r in schedules.iterrows():
                key_str = f"{r['Date']} | {r['Class']}-{r['Section']} | {r['Subject']}"
                exam_opts[key_str] = r['Exam_ID']
                
            sel_ex = st.selectbox("Select Exam to View", ["Select..."] + list(exam_opts.keys()))
            
            if sel_ex != "Select...":
                e_id = exam_opts[sel_ex]
                if marks.empty:
                    st.warning("No marks recorded in the system yet.")
                else:
                    em = marks[marks['Exam_ID'] == e_id].copy()
                    if em.empty:
                        st.info("No marks entered for this exam yet.")
                    else:
                        em['Numeric_Total'] = pd.to_numeric(em['Total_Marks'], errors='coerce')
                        em['Rank'] = em['Numeric_Total'].rank(method='min', ascending=False, na_option='bottom')
                        em = em.sort_values(by=['Rank'])
                        
                        view_df = em[['Roll', 'Name', 'Actual_Marks', 'Extra_Marks', 'Total_Marks', 'Percentage', 'Rank', 'Graded_By']]
                        st.dataframe(view_df, use_container_width=True, hide_index=True)

# ---------------------------------------------------------
# TEACHER VIEW
# ---------------------------------------------------------
elif st.session_state.user_role == "teacher":
    tabs = st.tabs(["📚 My Subject Mapping", "🎓 Enter Marks"])
    
    with tabs[0]:
        st.markdown(f"<div class='header-card'><h4>📚 Manage Your Subjects</h4><p style='margin:0; font-size:14px;'>You are currently viewing <b>only</b> the subjects assigned to you. You can update Class, Section, or Subject below.</p></div>", unsafe_allow_html=True)
        
        status_df = fetch_teacher_status()
        if not status_df.empty and 'Teacher' in status_df.columns:
            current_status = status_df[status_df['Teacher'] == st.session_state.user_name]['Status'].values
        else:
            current_status = []
            
        if len(current_status) == 0 or current_status[0] not in ["Confirmed ✅", "Edited ✏️", "Viewed 👀"]:
            update_teacher_status(st.session_state.user_name, "Viewed 👀")
            
        subject_map_df = init_subject_map()
        my_map_df = subject_map_df[subject_map_df['Teacher'] == st.session_state.user_name].copy()
        my_map_df = sort_display_df(my_map_df)
        
        if my_map_df.empty:
            st.info("You currently have no subjects assigned in the Master Map. If this is a mistake, you can add them below.")
            
        edited_map_teacher = st.data_editor(
            my_map_df,
            num_rows="dynamic",
            column_config={
                "Map_ID": None,
                "Timestamp": None, 
                "Modified_By": None, 
                "Teacher": st.column_config.SelectboxColumn("Teacher", options=[st.session_state.user_name], disabled=True),
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
                save_subject_map(edited_map_teacher, subject_map_df, st.session_state.user_name, is_partial=True)
                update_teacher_status(st.session_state.user_name, "Edited ✏️")
                st.success("Changes saved! The Head Teacher will review your updates.")
                st.rerun()
            
    with tabs[1]:
        st.markdown("<div class='header-card'><h4>🎓 Grade Entry Portal</h4><p style='margin:0; font-size:14px;'>Select any exam below. Your assigned exams are starred at the top.</p></div>", unsafe_allow_html=True)
        
        schedules = fetch_exam_schedules()
        if schedules.empty:
            st.info("🏖️ No exams are scheduled in the system right now.")
        else:
            exam_display = {}
            for _, r in schedules.iterrows():
                is_mine = r['Teacher'] == st.session_state.user_name
                prefix = "⭐ [Assigned] " if is_mine else "🔹 [Other] "
                key_str = f"{prefix}{r['Date']} | {r['Class']}-{r['Section']} | {r['Subject']}"
                exam_display[key_str] = r['Exam_ID']
                
            sorted_keys = sorted(list(exam_display.keys()), key=lambda x: (not x.startswith("⭐"), x))
            
            selected_exam_str = st.selectbox("Select Exam to Grade", ["Select..."] + sorted_keys)
            
            if selected_exam_str != "Select...":
                exam_id = exam_display[selected_exam_str]
                exam_info = schedules[schedules['Exam_ID'] == exam_id].iloc[0]
                
                e_date = exam_info['Date']
                e_class = exam_info['Class']
                e_sec = exam_info['Section']
                e_sub = exam_info['Subject']
                
                e_fm = 50.0
                try: 
                    if 'Full_Marks' in exam_info and pd.notna(exam_info['Full_Marks']) and str(exam_info['Full_Marks']).strip() != "":
                        e_fm = float(exam_info['Full_Marks'])
                except Exception: 
                    pass
                
                st.markdown("---")
                st.subheader(f"Entering marks for: {e_sub}")
                st.info(f"🎯 **Full Marks:** {int(e_fm)} (Read-Only)")
                
                check_all_marks = fetch_exam_marks()
                if not check_all_marks.empty:
                    existing_for_alert = check_all_marks[check_all_marks['Exam_ID'] == exam_id]
                    if not existing_for_alert.empty:
                        prev_graders = [str(g).strip() for g in existing_for_alert['Graded_By'].unique() if str(g).strip() not in ["", "nan", "None"]]
                        if prev_graders:
                            if st.session_state.user_name not in prev_graders:
                                warning_names = ", ".join(prev_graders)
                                st.warning(f"🚨 **WARNING:** Marks for this exam have already been entered by **{warning_names}**. Any changes you save will OVERWRITE their data!")
                            else:
                                st.info("✏️ You have previously entered marks for this exam. You can edit them below.")
                
                mdm = fetch_mdm_log()
                if not mdm.empty:
                    if e_class == "CLASS PP":
                        mdm_present = mdm[(mdm['Date'] == e_date) & (mdm['Class'].isin(["CLASS PP", "CLASS LPP"])) & (mdm['Section'] == e_sec)]
                    else:
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
                    
                    roster = mdm_present[['Class', 'Section', 'Roll', 'Name']].copy()
                    roster['Class'] = roster['Class'].astype(str).str.strip().str.upper()
                    roster['Section'] = roster['Section'].astype(str).str.strip().str.upper()
                    roster['Roll'] = roster['Roll'].astype(str).str.strip()
                    
                    roster = roster.drop_duplicates(subset=['Class', 'Section', 'Roll']).reset_index(drop=True)
                    
                    photos_df = fetch_student_photos()
                    if not photos_df.empty:
                        photos_df = photos_df.drop_duplicates(subset=['Class', 'Section', 'Roll'])
                        roster = pd.merge(roster, photos_df, on=['Class', 'Section', 'Roll'], how='left')
                    else:
                        roster['Thumb_URL'] = None
                        
                    if 'Thumb_URL' in roster.columns:
                        roster['Thumb_URL'] = roster['Thumb_URL'].replace({"": None, "nan": None, "None": None})
                        
                    if not existing_marks.empty:
                        existing_subset = existing_marks[['Class', 'Section', 'Roll', 'Actual_Marks', 'Extra_Marks', 'Total_Marks', 'Percentage']].drop_duplicates(subset=['Class', 'Section', 'Roll'])
                        existing_subset['Class'] = existing_subset['Class'].astype(str).str.strip().str.upper()
                        existing_subset['Section'] = existing_subset['Section'].astype(str).str.strip().str.upper()
                        existing_subset['Roll'] = existing_subset['Roll'].astype(str).str.strip()
                        roster = pd.merge(roster, existing_subset, on=['Class', 'Section', 'Roll'], how='left')
                    else:
                        roster['Actual_Marks'] = None
                        roster['Extra_Marks'] = 0.0
                        roster['Total_Marks'] = None
                        roster['Percentage'] = None
                        
                    roster['Actual_Marks'] = pd.to_numeric(roster['Actual_Marks'], errors='coerce').astype('float')
                    roster['Extra_Marks'] = pd.to_numeric(roster['Extra_Marks'], errors='coerce').fillna(0.0).astype('float')
                    
                    if 'Thumb_URL' not in roster.columns: 
                        roster['Thumb_URL'] = ""
                        
                    with st.spinner("Loading profiles..."):
                        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as exe:
                            roster['Photo'] = list(exe.map(get_secure_photo_uri, roster['Thumb_URL'].tolist()))

                    live_totals = []
                    for idx, r in roster.iterrows():
                        rk = f"{exam_id}_{r['Roll']}_{idx}"
                        actual_key = f"act_{rk}"
                        extra_key = f"ext_{rk}"
                        
                        if actual_key not in st.session_state:
                            val = r['Actual_Marks']
                            st.session_state[actual_key] = float(val) if pd.notna(val) else None
                        if extra_key not in st.session_state:
                            val = r['Extra_Marks']
                            st.session_state[extra_key] = float(val) if pd.notna(val) else 0.0
                            
                        act_val = st.session_state[actual_key]
                        ext_val = st.session_state[extra_key]
                        
                        if act_val is not None:
                            live_totals.append(act_val + (ext_val if ext_val is not None else 0.0))
                        else:
                            live_totals.append(np.nan)
                            
                    roster['Live_Total'] = live_totals
                    roster['Rank'] = roster['Live_Total'].rank(method='min', ascending=False, na_option='bottom')
                    
                    st.markdown("### Grade Entry Roster")
                    
                    sort_col1, sort_col2 = st.columns([1, 1])
                    with sort_col1:
                        sort_by_rank = st.toggle("🏆 Sort by Rank")
                    with sort_col2:
                        if sort_by_rank:
                            st.caption("⚠️ *Live sorting is ON.*")
                            
                    if sort_by_rank:
                        roster['Numeric_Roll'] = pd.to_numeric(roster['Roll'], errors='coerce')
                        roster = roster.sort_values(by=['Live_Total', 'Numeric_Roll'], ascending=[False, True])
                    else:
                        roster['Numeric_Roll'] = pd.to_numeric(roster['Roll'], errors='coerce')
                        roster = roster.sort_values(by=['Numeric_Roll'])

                    st.markdown('<div class="roster-container">', unsafe_allow_html=True)
                    
                    has_error = False

                    for idx, r in roster.iterrows():
                        rk = f"{exam_id}_{r['Roll']}_{idx}"
                        actual_key = f"act_{rk}"
                        extra_key = f"ext_{rk}"
                        
                        act_val = st.session_state[actual_key]
                        ext_val = st.session_state[extra_key]
                        
                        tot_val = None
                        pct_val = None
                        if act_val is not None:
                            tot_val = act_val + (ext_val if ext_val is not None else 0.0)
                            pct_val = round((tot_val / e_fm) * 100, 1) if e_fm > 0 else 0.0

                        if tot_val is not None and tot_val > e_fm:
                            has_error = True

                        if pd.notna(r['Rank']):
                            rank_html = "<span style='background-color:#ffeb3b; color:#856404; padding:2px 5px; border-radius:4px; font-weight:bold; font-size:11px;'>🏆 #" + str(int(r['Rank'])) + "</span>"
                        else:
                            rank_html = "<span style='background-color:#e9ecef; color:#6c757d; padding:2px 5px; border-radius:4px; font-weight:bold; font-size:11px;'>-</span>"

                        st.markdown("<div class='student-card'>", unsafe_allow_html=True)
                        
                        top_row_html = (
                            "<div style='display:flex; align-items:center; gap:15px; margin-bottom: 12px;'>"
                            "<img src='" + str(r['Photo']) + "' style='width:65px; height:65px; object-fit:cover; border-radius:8px; border: 1px solid #ddd;'>"
                            "<div style='line-height:1.3;'>"
                            "<b style='font-size:16px; color:#222;'>" + str(r['Name']) + "</b><br>"
                            "<span style='font-size:13px; color:#666;'>Roll: " + str(r['Roll']) + " &nbsp;&nbsp; " + rank_html + "</span>"
                            "</div></div>"
                        )
                        st.markdown(top_row_html, unsafe_allow_html=True)
                        
                        col_act, col_ext = st.columns(2)
                        with col_act:
                            st.number_input("Actual Marks", min_value=0.0, key=actual_key)
                        with col_ext:
                            st.number_input("Extra Marks (+)", min_value=0.0, key=extra_key)
                            
                        if tot_val is not None:
                            if tot_val > e_fm:
                                tot_disp = "<span style='color:red;'><b>" + str(tot_val) + "</b> <span style='font-size:11px;'>(Exceeds " + str(int(e_fm)) + "!)</span></span>"
                                pct_disp = "<span style='color:gray;'>-</span>"
                            else:
                                tot_disp = "<b>" + str(tot_val) + "</b>"
                                pct_disp = "<b>" + str(pct_val) + "%</b>"
                        else:
                            tot_disp = "<span style='color:gray;'>-</span>"
                            pct_disp = "<span style='color:gray;'>-</span>"

                        bottom_row_html = (
                            "<div style='display:flex; justify-content: space-between; background:#fff; padding:10px 15px; border-radius:8px; border:1px solid #dee2e6; margin-top:2px;'>"
                            "<div style='font-size:15px; color:#333;'>Total: " + tot_disp + "</div>"
                            "<div style='font-size:15px; color:#28a745;'>%: " + pct_disp + "</div>"
                            "</div>"
                        )
                        st.markdown(bottom_row_html, unsafe_allow_html=True)
                        
                        st.markdown("</div>", unsafe_allow_html=True)

                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    if has_error:
                        st.error("🚨 Cannot save. One or more students have a Total Mark exceeding the Full Mark (" + str(int(e_fm)) + "). Please fix the errors highlighted in red above.")
                    else:
                        if st.button("💾 Save Exam Marks", type="primary"):
                            all_marks = fetch_exam_marks() 
                            new_records = []
                            
                            for idx, r in roster.iterrows():
                                rk = f"{exam_id}_{r['Roll']}_{idx}"
                                act_val = st.session_state.get(f"act_{rk}")
                                ext_val = st.session_state.get(f"ext_{rk}", 0.0)
                                
                                if act_val is not None:
                                    total = act_val + (ext_val if ext_val is not None else 0.0)
                                    pct = round((total / e_fm) * 100, 1) if e_fm > 0 else 0.0
                                    
                                    new_records.append({
                                        "Exam_ID": exam_id,
                                        "Date": e_date,
                                        "Class": e_class,
                                        "Section": e_sec,
                                        "Subject": e_sub,
                                        "Roll": r['Roll'],
                                        "Name": r['Name'],
                                        "Actual_Marks": act_val,
                                        "Extra_Marks": ext_val,
                                        "Total_Marks": total,
                                        "Full_Marks": int(e_fm),
                                        "Percentage": pct,
                                        "Graded_By": st.session_state.user_name
                                    })
                                    
                            new_marks_df = pd.DataFrame(new_records)
                            
                            if not all_marks.empty:
                                all_marks_purged = all_marks[all_marks['Exam_ID'] != exam_id]
                                if 'Marks_Obtained' in all_marks_purged.columns:
                                    all_marks_purged = all_marks_purged.drop(columns=['Marks_Obtained'])
                                final_marks = pd.concat([all_marks_purged, new_marks_df], ignore_index=True)
                            else:
                                final_marks = new_marks_df
                                
                            overwrite_sheet(
                                init_exam_sheet(), 
                                "marks", 
                                final_marks, 
                                ["Exam_ID", "Date", "Class", "Section", "Subject", "Roll", "Name", "Actual_Marks", "Extra_Marks", "Total_Marks", "Full_Marks", "Percentage", "Graded_By"]
                            )
                            
                            st.success(f"🎉 Marks saved successfully for {len(new_records)} students! Totals and Percentages have been locked in.")
                            st.rerun()
        else:
            st.info("No exams have been scheduled in the system yet.")
