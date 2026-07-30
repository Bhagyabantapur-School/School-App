import streamlit as st
import pandas as pd
import os
import base64
import re
from datetime import datetime, timezone, timedelta
import gspread
from gspread.exceptions import WorksheetNotFound
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import AuthorizedSession

# ---------------------------------------------------------
# AUTHENTICATION GUARD
# ---------------------------------------------------------
if 'authenticated' not in st.session_state or not st.session_state.authenticated:
    st.warning("🔒 Unauthorized Access. Please log in through the main portal.")
    st.stop()

# ---------------------------------------------------------
# PAGE STYLING & WATERMARK
# ---------------------------------------------------------
def inject_security_css(user_name):
    wm = f"{user_name} - CONFIDENTIAL"
    st.markdown(f"""<style>
        body {{ user-select: none; -webkit-user-select: none; }}
        .watermark {{
            position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
            pointer-events: none; z-index: 9999;
            background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" viewBox="0 0 300 300"><text x="50" y="150" fill="rgba(200, 200, 200, 0.25)" font-size="20" transform="rotate(-45 150 150)" font-family="Arial, sans-serif">{wm}</text></svg>');
            background-repeat: repeat;
        }}
        .block-container {{ padding-top: 1rem; max-width: 850px; overflow-x: hidden; }}
        .stButton>button {{
            width: 100%; border-radius: 10px; height: 3.2em;
            background-color: #007bff; color: white; font-weight: bold; border: none;
        }}
        .header-school-name {{ font-size: 24px; font-weight: 900; color: #007bff; margin: 0; }}
    </style><div class="watermark"></div>""", unsafe_allow_html=True)

inject_security_css(st.session_state.get('user_name', 'Teacher'))

# ---------------------------------------------------------
# GOOGLE SHEETS & DRIVE CONNECTORS
# ---------------------------------------------------------
@st.cache_resource
def get_google_credentials():
    return Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.readonly"]
    )

@st.cache_resource
def init_gsheets():
    try:
        return gspread.authorize(get_google_credentials()).open("BPS_Database")
    except Exception:
        st.error("⚠️ Failed to connect to BPS_Database Google Sheet.")
        st.stop()

@st.cache_resource
def get_drive_session():
    return AuthorizedSession(get_google_credentials())

sh = init_gsheets()

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_secure_image_bytes(file_id):
    try:
        r = get_drive_session().get(f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media")
        return r.content if r.status_code == 200 else None
    except Exception:
        return None

def get_secure_photo_uri(url):
    fallback_avatar = "https://www.w3schools.com/howto/img_avatar.png"
    if pd.isna(url) or url == "" or not isinstance(url, str):
        return fallback_avatar
    match = re.search(r"(?:id=|/d/)([\w-]+)", url)
    if match:
        img_bytes = fetch_secure_image_bytes(match.group(1))
        if img_bytes:
            return f"data:image/jpeg;base64,{base64.b64encode(img_bytes).decode()}"
    return url if url.startswith("http") else fallback_avatar

@st.cache_data(ttl=300)
def fetch_sheet_data(sheet_name):
    try:
        ws = sh.worksheet(sheet_name)
        df = pd.DataFrame(ws.get_all_records())
        return df.replace({'TRUE': True, 'FALSE': False, 'True': True, 'False': False}).infer_objects(copy=False)
    except WorksheetNotFound:
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def clear_sheet_cache():
    fetch_sheet_data.clear()

def save_progression_record(record_dict):
    sheet_name = "udise_progression_2026_27"
    headers = [
        "Student_Key", "Roll", "Name", "Previous_Class_2025_26", "Previous_Section_2025_26",
        "Progression_Status", "Marks_Percent", "Days_Attended",
        "Schooling_Status_2026_27", "Promoted_Class_2026_27", "Promoted_Section_2026_27",
        "Updated_By", "Updated_At"
    ]
    try:
        ws = sh.worksheet(sheet_name)
    except WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=20)
        ws.append_row(headers)

    records = ws.get_all_records()
    df = pd.DataFrame(records) if records else pd.DataFrame(columns=headers)
    
    student_key = str(record_dict["Student_Key"])
    row_values = [str(record_dict.get(h, "")) for h in headers]

    if not df.empty and "Student_Key" in df.columns and (df["Student_Key"].astype(str) == student_key).any():
        row_idx = df.index[df["Student_Key"].astype(str) == student_key].tolist()[0] + 2
        ws.update(range_name=f"A{row_idx}:M{row_idx}", values=[row_values])
    else:
        ws.append_row(row_values)
    
    clear_sheet_cache()

# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------
def render_header():
    if os.path.exists("logo.png"):
        with open("logo.png", "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        st.markdown(f"""
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #e0e0e0; padding-bottom: 15px; margin-bottom: 20px;">
            <img src="data:image/png;base64,{img_b64}" style="max-width: 75px; max-height: 75px; object-fit: contain;">
            <div style="text-align: right;">
                <h2 class="header-school-name" style="line-height: 1.1;">BHAGYABANTAPUR PRIMARY SCHOOL</h2>
                <h4 style="margin: 0; color: #555; font-weight: bold;">UDISE+ Student Progression (2025-26 → 2026-27)</h4>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="border-bottom: 2px solid #e0e0e0; padding-bottom: 15px; margin-bottom: 20px; text-align: center;">
            <h2 class="header-school-name">BHAGYABANTAPUR PRIMARY SCHOOL</h2>
            <h4 style="color: #555; margin: 0;">UDISE+ Student Progression (2025-26 → 2026-27)</h4>
        </div>
        """, unsafe_allow_html=True)

render_header()

# ---------------------------------------------------------
# REVERSE MAPPING LOGIC (Current 2026-27 Class -> Previous 2025-26 Class)
# ---------------------------------------------------------
PREV_CLASS_MAP = {
    "CLASS PP": "New Admission / Anganwadi",
    "CLASS LPP": "New Admission / Anganwadi",
    "CLASS I": "CLASS PP",
    "CLASS II": "CLASS I",
    "CLASS III": "CLASS II",
    "CLASS IV": "CLASS III",
    "CLASS V": "CLASS IV"
}

OUTGOING_LABEL = "CLASS V (2025-26 Outgoing -> Now Class VI)"

# ---------------------------------------------------------
# SIDEBAR REFRESH & INFO
# ---------------------------------------------------------
st.sidebar.markdown("### 🔄 Live Sync")
if st.sidebar.button("🔄 Manual Refresh Data", use_container_width=True):
    clear_sheet_cache()
    st.rerun()

st.sidebar.info("💡 **Note:** Standard classes pull from `students_master`. Use the **Outgoing Class V** mode to record students who transitioned to Class VI.")

# ---------------------------------------------------------
# FETCH CORE DATA
# ---------------------------------------------------------
sm_df = fetch_sheet_data("students_master")
prog_df = fetch_sheet_data("udise_progression_2026_27")

if sm_df.empty:
    st.error("❌ No student data found in `students_master`. Please check your BPS_Database Google Sheet.")
    st.stop()

if "Section" not in sm_df.columns:
    sm_df["Section"] = "A"
if "Thumb_URL" not in sm_df.columns:
    sm_df["Thumb_URL"] = ""

sm_df["Roll"] = sm_df["Roll"].astype(str).str.strip()
sm_df["Name"] = sm_df["Name"].astype(str).str.strip()
sm_df["Class"] = sm_df["Class"].astype(str).str.strip()
sm_df["Section"] = sm_df["Section"].astype(str).str.strip()
sm_df["Student_Key"] = sm_df["Class"] + "_" + sm_df["Section"] + "_" + sm_df["Roll"] + "_" + sm_df["Name"]

completed_keys = set()
if not prog_df.empty and "Student_Key" in prog_df.columns:
    completed_keys = set(prog_df["Student_Key"].astype(str).unique())

# ---------------------------------------------------------
# MAIN UI TABS
# ---------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["🎓 Progression Entry", "📊 Class Status Roster", "📥 Master UDISE+ Report"])

with tab1:
    st.markdown("### Student Progression Selection")
    
    col_cls, col_sec = st.columns(2)
    classes_list = ["Select Class..."] + sorted([c for c in sm_df["Class"].unique() if c]) + [OUTGOING_LABEL]
    selected_class = col_cls.selectbox("Select Class Group", classes_list, key="prog_cls")
    
    # =========================================================
    # SPECIAL MODE: OUTGOING CLASS V (NOW CLASS VI) FROM PORTAL
    # =========================================================
    if selected_class == OUTGOING_LABEL:
        st.info("ℹ️ **Outgoing Class V Mode:** Since these students left for Class VI and are not in `students_master`, enter their Name and Roll Number from your UDISE+ portal below.")
        
        col_in1, col_in2, col_in3 = st.columns([3, 1, 1])
        out_name = col_in1.text_input("Student Name (from UDISE+ Portal)", placeholder="e.g. SUBORNO KISKU").strip().upper()
        out_roll = col_in2.text_input("2025-26 Roll No.", placeholder="e.g. 1").strip()
        out_sec = col_in3.selectbox("2025-26 Section", ["A", "B", "C"], index=0)
        
        if out_name and out_roll:
            out_key = f"OUTGOING_V_{out_sec}_{out_roll}_{out_name}"
            
            st.divider()
            fallback_avatar = "https://www.w3schools.com/howto/img_avatar.png"
            st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 15px; background-color: #f8f9fa; border-left: 5px solid #28a745; padding: 12px; border-radius: 10px; border-right: 1px solid #ddd; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; margin-bottom: 20px;">
                <img src="{fallback_avatar}" style="width: 85px; height: 105px; object-fit: cover; border-radius: 8px; border: 2px solid #28a745; box-shadow: 0px 2px 6px rgba(0,0,0,0.15);">
                <div>
                    <h3 style="margin: 0; color: #28a745; font-weight: 800;">🧑‍🎓 {out_name}</h3>
                    <p style="margin: 4px 0 0 0; font-size: 15px; color: #333;">Roll: <b>{out_roll}</b> | Previous Class (2025-26): <b>CLASS V ({out_sec})</b></p>
                    <p style="margin: 4px 0 0 0; font-size: 14px; color: #007bff; font-weight: bold;">📌 Status: Transitioning to Upper Primary (Class VI in 2026-27)</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            existing = prog_df[prog_df["Student_Key"].astype(str) == out_key] if not prog_df.empty and "Student_Key" in prog_df.columns else pd.DataFrame()
            
            def_status = existing.iloc[0]["Progression_Status"] if not existing.empty else "Promoted / Passed"
            def_marks = str(existing.iloc[0]["Marks_Percent"]) if not existing.empty else ""
            def_days = str(existing.iloc[0]["Days_Attended"]) if not existing.empty else ""
            def_schooling = existing.iloc[0]["Schooling_Status_2026_27"] if not existing.empty else "Left School with TC"
            def_promoted = existing.iloc[0]["Promoted_Class_2026_27"] if not existing.empty else "CLASS VI (Upper Primary / Transitioned)"
            def_promoted_sec = existing.iloc[0]["Promoted_Section_2026_27"] if not existing.empty else "A"
            
            st.markdown("#### 📝 Fill UDISE+ Progression Details")
            
            c1, c2, c3 = st.columns(3)
            prog_status = c1.selectbox(
                "1. Progression Status (for 2025-26)",
                ["Promoted / Passed", "Not Passed (Repeater)", "Promoted Without Exam", "Discontinued Before Exam", "Repeater by Choice"],
                index=["Promoted / Passed", "Not Passed (Repeater)", "Promoted Without Exam", "Discontinued Before Exam", "Repeater by Choice"].index(def_status) if def_status in ["Promoted / Passed", "Not Passed (Repeater)", "Promoted Without Exam", "Discontinued Before Exam", "Repeater by Choice"] else 0,
                key="out_st"
            )
            marks_pct = c2.text_input("2. Marks (%) in 2025-26", value=def_marks, placeholder="e.g. 85%", key="out_mk")
            days_att = c3.text_input("3. No. of Days Attended (2025-26)", value=def_days, placeholder="e.g. 210", key="out_dy")
            
            c4, c5, c6 = st.columns(3)
            schooling_status = c4.selectbox(
                "4. 2026-27 Schooling Status",
                ["Left School with TC", "Left School without TC", "Studying in Same School"],
                index=["Left School with TC", "Left School without TC", "Studying in Same School"].index(def_schooling) if def_schooling in ["Left School with TC", "Left School without TC", "Studying in Same School"] else 0,
                key="out_sc"
            )
            promoted_class_list = ["CLASS VI (Upper Primary / Transitioned)", "CLASS V", "Left School / Other"]
            promoted_cls = c5.selectbox(
                "5. Promoted Class (2026-27)",
                promoted_class_list,
                index=promoted_class_list.index(def_promoted) if def_promoted in promoted_class_list else 0,
                key="out_pc"
            )
            promoted_sec = c6.selectbox("6. Promoted Section", ["A", "B", "C"], index=0, key="out_ps")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            if st.button("✅ Submit Outgoing Class V Progression"):
                utc_now = datetime.now(timezone.utc)
                ist_now = utc_now + timedelta(hours=5, minutes=30)
                
                record_payload = {
                    "Student_Key": out_key,
                    "Roll": out_roll,
                    "Name": out_name,
                    "Previous_Class_2025_26": "CLASS V",
                    "Previous_Section_2025_26": out_sec,
                    "Progression_Status": prog_status,
                    "Marks_Percent": marks_pct,
                    "Days_Attended": days_att,
                    "Schooling_Status_2026_27": schooling_status,
                    "Promoted_Class_2026_27": promoted_cls,
                    "Promoted_Section_2026_27": promoted_sec,
                    "Updated_By": st.session_state.get("user_name", "Admin"),
                    "Updated_At": ist_now.strftime("%d-%m-%Y %I:%M %p")
                }
                
                with st.spinner("Saving outgoing student progression to BPS_Database..."):
                    save_progression_record(record_payload)
                st.success(f"🎉 Progression successfully recorded for outgoing Class V student: **{out_name}**!")
                st.rerun()

    # =========================================================
    # STANDARD MODE: ACTIVE CLASSES IN STUDENTS_MASTER
    # =========================================================
    elif selected_class != "Select Class...":
        sec_list = sorted(sm_df[sm_df["Class"] == selected_class]["Section"].unique())
        selected_section = col_sec.selectbox("Select Section", sec_list if sec_list else ["A"], key="prog_sec")
        
        filtered_students = sm_df[
            (sm_df["Class"] == selected_class) & 
            (sm_df["Section"] == selected_section)
        ].sort_values("Roll", ascending=True)
        
        if filtered_students.empty:
            st.warning("⚠️ No students found in this Class & Section.")
        else:
            student_options = ["Select Student..."] + [
                f"Roll {r['Roll']} - {r['Name']} {'(✅ Done)' if r['Student_Key'] in completed_keys else '(❌ Pending)'}"
                for _, r in filtered_students.iterrows()
            ]
            selected_student_str = st.selectbox("Select Student", student_options, key="prog_student_sel")
            
            if selected_student_str != "Select Student...":
                roll_match = re.search(r"Roll\s+(\S+)\s+-\s+([^(]+)", selected_student_str)
                selected_roll = roll_match.group(1).strip() if roll_match else ""
                
                stu_record = filtered_students[filtered_students["Roll"] == selected_roll].iloc[0]
                stu_key = stu_record["Student_Key"]
                
                thumb_url = stu_record.get("Thumb_URL", "")
                with st.spinner("Loading student thumbnail..."):
                    photo_uri = get_secure_photo_uri(thumb_url)
                
                prev_class_2025_26 = PREV_CLASS_MAP.get(selected_class, "Unknown / Previous Class")
                
                st.divider()
                
                st.markdown(f"""
                <div style="display: flex; align-items: center; gap: 15px; background-color: #f8f9fa; border-left: 5px solid #007bff; padding: 12px; border-radius: 10px; border-right: 1px solid #ddd; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; margin-bottom: 20px;">
                    <img src="{photo_uri}" style="width: 85px; height: 105px; object-fit: cover; border-radius: 8px; border: 2px solid #007bff; box-shadow: 0px 2px 6px rgba(0,0,0,0.15);">
                    <div>
                        <h3 style="margin: 0; color: #007bff; font-weight: 800;">🧑‍🎓 {stu_record['Name']}</h3>
                        <p style="margin: 4px 0 0 0; font-size: 15px; color: #333;">Roll: <b>{stu_record['Roll']}</b> | Current Class (2026-27): <b>{stu_record['Class']} ({stu_record['Section']})</b></p>
                        <p style="margin: 4px 0 0 0; font-size: 14px; color: #28a745; font-weight: bold;">📌 Evaluated For Previous Class (2025-26): {prev_class_2025_26}</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                existing = prog_df[prog_df["Student_Key"].astype(str) == stu_key] if not prog_df.empty and "Student_Key" in prog_df.columns else pd.DataFrame()
                
                def_status = existing.iloc[0]["Progression_Status"] if not existing.empty else "Promoted / Passed"
                def_marks = str(existing.iloc[0]["Marks_Percent"]) if not existing.empty else ""
                def_days = str(existing.iloc[0]["Days_Attended"]) if not existing.empty else ""
                def_schooling = existing.iloc[0]["Schooling_Status_2026_27"] if not existing.empty else "Studying in Same School"
                def_promoted = existing.iloc[0]["Promoted_Class_2026_27"] if not existing.empty else selected_class
                def_promoted_sec = existing.iloc[0]["Promoted_Section_2026_27"] if not existing.empty else selected_section
                
                st.markdown("#### 📝 Fill UDISE+ Progression Details")
                
                c1, c2, c3 = st.columns(3)
                prog_status = c1.selectbox(
                    "1. Progression Status (for 2025-26)",
                    ["Promoted / Passed", "Not Passed (Repeater)", "Promoted Without Exam", "Discontinued Before Exam", "Repeater by Choice"],
                    index=["Promoted / Passed", "Not Passed (Repeater)", "Promoted Without Exam", "Discontinued Before Exam", "Repeater by Choice"].index(def_status) if def_status in ["Promoted / Passed", "Not Passed (Repeater)", "Promoted Without Exam", "Discontinued Before Exam", "Repeater by Choice"] else 0
                )
                marks_pct = c2.text_input("2. Marks (%) in 2025-26", value=def_marks, placeholder="e.g. 82%")
                days_att = c3.text_input("3. No. of Days Attended (2025-26)", value=def_days, placeholder="e.g. 195")
                
                c4, c5, c6 = st.columns(3)
                schooling_status = c4.selectbox(
                    "4. 2026-27 Schooling Status",
                    ["Studying in Same School", "Left School with TC", "Left School without TC"],
                    index=["Studying in Same School", "Left School with TC", "Left School without TC"].index(def_schooling) if def_schooling in ["Studying in Same School", "Left School with TC", "Left School without TC"] else 0
                )
                
                promoted_class_list = ["CLASS PP", "CLASS I", "CLASS II", "CLASS III", "CLASS IV", "CLASS V", "Left School / Outgoing Class V"]
                promoted_cls = c5.selectbox(
                    "5. Promoted Class (2026-27)",
                    promoted_class_list,
                    index=promoted_class_list.index(def_promoted) if def_promoted in promoted_class_list else 0
                )
                
                sec_options = ["A", "B", "C"]
                promoted_sec = c6.selectbox(
                    "6. Promoted Section", 
                    sec_options, 
                    index=sec_options.index(def_promoted_sec) if def_promoted_sec in sec_options else 0
                )
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                if st.button("✅ Submit Student Progression"):
                    utc_now = datetime.now(timezone.utc)
                    ist_now = utc_now + timedelta(hours=5, minutes=30)
                    
                    record_payload = {
                        "Student_Key": stu_key,
                        "Roll": stu_record["Roll"],
                        "Name": stu_record["Name"],
                        "Previous_Class_2025_26": prev_class_2025_26,
                        "Previous_Section_2025_26": selected_section,
                        "Progression_Status": prog_status,
                        "Marks_Percent": marks_pct,
                        "Days_Attended": days_att,
                        "Schooling_Status_2026_27": schooling_status,
                        "Promoted_Class_2026_27": promoted_cls,
                        "Promoted_Section_2026_27": promoted_sec,
                        "Updated_By": st.session_state.get("user_name", "Admin"),
                        "Updated_At": ist_now.strftime("%d-%m-%Y %I:%M %p")
                    }
                    
                    with st.spinner("Saving UDISE+ progression to BPS_Database..."):
                        save_progression_record(record_payload)
                    st.success(f"🎉 Progression successfully updated for **{stu_record['Name']}** (Mapped from 2025-26: **{prev_class_2025_26}**)!")
                    st.rerun()

with tab2:
    st.markdown("### 📊 Class Progression Status Table")
    col_f1, col_f2 = st.columns(2)
    flt_class = col_f1.selectbox("Filter Class Group", ["All"] + sorted([c for c in sm_df["Class"].unique() if c]) + ["CLASS V (2025-26 Outgoing)"], key="flt_cls")
    flt_sec = col_f2.selectbox("Filter Section", ["All", "A", "B"], key="flt_sec")
    
    prog_lookup = {}
    if not prog_df.empty and "Student_Key" in prog_df.columns:
        for _, r in prog_df.iterrows():
            prog_lookup[str(r["Student_Key"])] = r

    roster_rows = []
    
    # 1. Standard Roster from students_master
    if flt_class != "CLASS V (2025-26 Outgoing)":
        view_df = sm_df.copy()
        if flt_class != "All":
            view_df = view_df[view_df["Class"] == flt_class]
        if flt_sec != "All":
            view_df = view_df[view_df["Section"] == flt_sec]
            
        view_df = view_df.sort_values(by=["Class", "Roll"], ascending=True)
        
        for _, stu in view_df.iterrows():
            s_key = stu["Student_Key"]
            prev_class_str = PREV_CLASS_MAP.get(stu["Class"], "Unknown")
            if s_key in prog_lookup:
                p_data = prog_lookup[s_key]
                roster_rows.append({
                    "Roll": stu["Roll"],
                    "Name": stu["Name"],
                    "Prev Class (2025-26)": f"{p_data.get('Previous_Class_2025_26', prev_class_str)}",
                    "Current Class (2026-27)": f"{stu['Class']} - {stu['Section']}",
                    "Status": "✅ Done",
                    "Progression": p_data["Progression_Status"],
                    "Marks (%)": p_data["Marks_Percent"],
                    "Days Att.": p_data["Days_Attended"],
                    "Schooling Status": p_data.get("Schooling_Status_2026_27", "Same School")
                })
            else:
                roster_rows.append({
                    "Roll": stu["Roll"],
                    "Name": stu["Name"],
                    "Prev Class (2025-26)": prev_class_str,
                    "Current Class (2026-27)": f"{stu['Class']} - {stu['Section']}",
                    "Status": "❌ Pending",
                    "Progression": "---",
                    "Marks (%)": "---",
                    "Days Att.": "---",
                    "Schooling Status": "---"
                })
                
    # 2. Outgoing Class V Roster from Saved Database
    if flt_class in ["All", "CLASS V (2025-26 Outgoing)"] and not prog_df.empty and "Previous_Class_2025_26" in prog_df.columns:
        out_df = prog_df[prog_df["Previous_Class_2025_26"] == "CLASS V"]
        if flt_sec != "All":
            out_df = out_df[out_df["Previous_Section_2025_26"] == flt_sec]
            
        for _, r in out_df.iterrows():
            roster_rows.append({
                "Roll": r["Roll"],
                "Name": r["Name"],
                "Prev Class (2025-26)": f"CLASS V - {r.get('Previous_Section_2025_26', 'A')}",
                "Current Class (2026-27)": str(r.get("Promoted_Class_2026_27", "CLASS VI (Upper Primary)")),
                "Status": "✅ Done",
                "Progression": r["Progression_Status"],
                "Marks (%)": r["Marks_Percent"],
                "Days Att.": r["Days_Attended"],
                "Schooling Status": r.get("Schooling_Status_2026_27", "Left School with TC")
            })
            
    roster_display = pd.DataFrame(roster_rows)
    
    def highlight_progression(row):
        if row["Status"] == "✅ Done":
            return ["background-color: #d4edda; color: #155724; font-weight: bold"] * len(row)
        else:
            return ["background-color: #f8d7da; color: #721c24"] * len(row)
            
    if not roster_display.empty:
        st.dataframe(
            roster_display.style.apply(highlight_progression, axis=1),
            hide_index=True,
            use_container_width=True
        )
        completed_cnt = len(roster_display[roster_display["Status"] == "✅ Done"])
        pending_cnt = len(roster_display[roster_display["Status"] == "❌ Pending"])
        
        c_sum1, c_sum2, c_sum3 = st.columns(3)
        c_sum1.metric("Total Roster", len(roster_display))
        c_sum2.metric("✅ Completed", completed_cnt)
        c_sum3.metric("❌ Pending", pending_cnt)
    else:
        st.info("No records to display for this filter.")

with tab3:
    st.markdown("### 📥 Master UDISE+ Cloud Database")
    if prog_df.empty:
        st.info("No progression entries have been recorded yet.")
    else:
        st.dataframe(prog_df, hide_index=True, use_container_width=True)
        csv = prog_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="⬇️ Download UDISE+ Master CSV Report",
            data=csv,
            file_name=f"UDISE_Progression_2026_27_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
