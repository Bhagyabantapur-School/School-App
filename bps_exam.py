import streamlit as st
import pandas as pd
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

# Re-use standard teacher lists and options
TEACHER_INITIALS = {"SUKHAMAY KISKU": "SK", "TAPASI RANA": "TR", "SUJATA BISWAS ROTHA": "SBR", "ROHINI SINGH": "RS", "UDAY NARAYAN JANA": "UNJ", "BIMAL KUMAR PATRA": "BKP", "SUSMITA PAUL": "SP", "TAPAN KUMAR MANDAL": "TKM", "MANJUMA KHATUN": "MK"}
TEACHER_LIST = list(TEACHER_INITIALS.keys())
CLASS_OPTIONS = ["CLASS PP", "CLASS I", "CLASS II", "CLASS III", "CLASS IV", "CLASS V"]
SECTIONS = ["A", "B", "C"]

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
    except: st.error("⚠️ BPS_Database not found!"); st.stop()

@st.cache_resource
def init_exam_sheet():
    try: return gspread.authorize(get_google_credentials()).open("BPS EXAM")
    except SpreadsheetNotFound: 
        st.error("🚨 **Critical Error:** Could not find a Google Sheet named `BPS EXAM`.")
        st.info("Please create a blank Google Sheet named **BPS EXAM** and share it with your service account email.")
        st.stop()

def ensure_worksheet(sh, title, headers):
    try: ws = sh.worksheet(title)
    except WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=1000, cols=20)
        ws.append_row(headers)
    return ws

# Clear caches for live reloads
def refresh_exam_data():
    fetch_exam_schedules.clear()
    fetch_exam_marks.clear()

@st.cache_data(ttl=300)
def fetch_mdm_log():
    try: return pd.DataFrame(init_db_sheet().worksheet("mdm_log").get_all_records()).astype(str)
    except: return pd.DataFrame()

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
# 3. MAIN APPLICATION UI
# ==========================================
st.markdown(f"<h2>📝 BPS Examination Manager</h2>", unsafe_allow_html=True)
st.sidebar.button("🔄 Sync Exam Data", on_click=refresh_exam_data, use_container_width=True)

# ---------------------------------------------------------
# ADMIN VIEW: SCHEDULE EXAMS
# ---------------------------------------------------------
if st.session_state.user_role == "admin":
    tabs = st.tabs(["📅 Schedule New Exam", "📋 View Scheduled Exams"])
    
    with tabs[0]:
        st.markdown("<div class='header-card'><h4>➕ Create Exam Schedule</h4></div>", unsafe_allow_html=True)
        with st.form("schedule_exam_form"):
            c1, c2 = st.columns(2)
            ex_date = c1.date_input("Exam Date", datetime.now()).strftime("%d-%m-%Y")
            ex_class = c2.selectbox("Class", CLASS_OPTIONS)
            
            c3, c4 = st.columns(2)
            ex_sec = c3.selectbox("Section", SECTIONS)
            ex_sub = c4.text_input("Subject (e.g., Bengali, Math, English)", "Mathematics")
            
            ex_teacher = st.selectbox("Assign Invigilator/Grader", TEACHER_LIST)
            
            if st.form_submit_button("Save Exam Schedule", type="primary"):
                exam_id = f"{ex_date}_{ex_class}_{ex_sec}_{ex_sub}".replace(" ", "")
                schedules = fetch_exam_schedules()
                
                # Check if exists to prevent duplicates
                if not schedules.empty and exam_id in schedules['Exam_ID'].values:
                    st.warning("⚠️ This exam is already scheduled!")
                else:
                    new_row = {
                        "Exam_ID": exam_id, "Date": ex_date, "Class": ex_class, 
                        "Section": ex_sec, "Subject": ex_sub.strip(), "Teacher": ex_teacher
                    }
                    new_df = pd.concat([schedules, pd.DataFrame([new_row])], ignore_index=True) if not schedules.empty else pd.DataFrame([new_row])
                    overwrite_sheet(init_exam_sheet(), "schedules", new_df, ["Exam_ID", "Date", "Class", "Section", "Subject", "Teacher"])
                    st.success(f"✅ Scheduled {ex_sub} for {ex_class}-{ex_sec} on {ex_date}!")

    with tabs[1]:
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
# TEACHER VIEW: ENTER MARKS
# ---------------------------------------------------------
elif st.session_state.user_role == "teacher":
    st.markdown("<div class='header-card'><h4>🎓 Grade Entry Portal</h4><p style='margin:0; font-size:14px;'>Only students present in the MDM Log on the exam date will appear here.</p></div>", unsafe_allow_html=True)
    
    schedules = fetch_exam_schedules()
    if not schedules.empty:
        # Filter schedules for the logged-in teacher
        my_exams = schedules[schedules['Teacher'] == st.session_state.user_name]
        
        if my_exams.empty:
            st.info("🏖️ You have no exams assigned for grading.")
        else:
            # Create a readable display mapping for the dropdown
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
                
                # Fetch MDM attendance for that specific date & class
                mdm = fetch_mdm_log()
                if not mdm.empty:
                    mdm_present = mdm[(mdm['Date'] == e_date) & (mdm['Class'] == e_class) & (mdm['Section'] == e_sec)]
                else:
                    mdm_present = pd.DataFrame()
                    
                if mdm_present.empty:
                    st.error(f"🚨 **No Students Found!** The MDM attendance log for **{e_class}-{e_sec}** on **{e_date}** is empty. You must complete MDM entry for this day before you can enter marks.")
                else:
                    st.success(f"✅ Found {len(mdm_present)} students present on {e_date}.")
                    
                    # Fetch existing marks to populate if already partially graded
                    all_marks = fetch_exam_marks()
                    existing_marks = pd.DataFrame()
                    if not all_marks.empty:
                        existing_marks = all_marks[all_marks['Exam_ID'] == exam_id]
                    
                    # Prepare dataframe for Data Editor
                    roster = mdm_present[['Roll', 'Name']].copy()
                    if not existing_marks.empty:
                        roster = pd.merge(roster, existing_marks[['Roll', 'Marks_Obtained']], on='Roll', how='left')
                    else:
                        roster['Marks_Obtained'] = ""
                        
                    # Show Interactive Table
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
                        # Build the new records for this specific exam
                        new_records = []
                        for _, r in edited_marks.iterrows():
                            # Only save if marks were actually entered
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
                        
                        # Purge old marks for this exam ID and merge new ones
                        if not all_marks.empty:
                            all_marks_purged = all_marks[all_marks['Exam_ID'] != exam_id]
                            final_marks = pd.concat([all_marks_purged, new_marks_df], ignore_index=True)
                        else:
                            final_marks = new_marks_df
                            
                        # Save to Sheet
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
