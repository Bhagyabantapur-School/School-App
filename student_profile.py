import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import AuthorizedSession
import datetime
import pytz

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="BPS Student Profile", page_icon="🎓", layout="wide")

# --- 2. SECURE CREDENTIALS & CONNECTIONS ---
@st.cache_resource
def get_google_credentials():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly"
    ]
    return Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], 
        scopes=scopes
    )

@st.cache_resource
def get_gspread_client():
    creds = get_google_credentials()
    return gspread.authorize(creds)

# --- 3. DATA LOADING & CACHING ---
@st.cache_data(ttl=600)
def load_database_data():
    client = get_gspread_client()
    
    db_main = client.open("BPS_Database") 
    
    try:
        df_master = pd.DataFrame(db_main.worksheet("students_master").get_all_records())
        df_mdm = pd.DataFrame(db_main.worksheet("mdm_log").get_all_records())
        df_attendance = pd.DataFrame(db_main.worksheet("student_attendance_master").get_all_records())
        df_forms = pd.DataFrame(db_main.worksheet("form_distribution_log").get_all_records())
    except gspread.exceptions.WorksheetNotFound as e:
        st.error(f"Could not find worksheet in BPS_Database: {e}.")
        st.stop()
        
    try:
        db_log = client.open("Students Profile")
        log_ws = db_log.sheet1 
        
        headers = log_ws.row_values(1)
        expected_cols = ["Date", "Class", "Section", "Roll", "Name", "Log Type", "Details"]
        
        if len(headers) == 0:
            log_ws.append_row(expected_cols)
            df_logs = pd.DataFrame(columns=expected_cols)
        else:
            records = log_ws.get_all_records()
            if len(records) == 0:
                df_logs = pd.DataFrame(columns=headers)
            else:
                df_logs = pd.DataFrame(records)
            
    except Exception as e:
        st.error(f"Could not connect to 'Students Profile'. Error: {e}")
        df_logs = pd.DataFrame(columns=["Date", "Class", "Section", "Roll", "Name", "Log Type", "Details"])
        
    return df_master, df_mdm, df_attendance, df_forms, df_logs

# --- 4. SECURE IMAGE FETCHER ---
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_secure_image_bytes(file_id):
    try:
        creds = get_google_credentials()
        authed_session = AuthorizedSession(creds)
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
        response = authed_session.get(url)
        
        if response.status_code == 200:
            return response.content
        else:
            return None
    except Exception as e:
        return None

def display_student_photo(url):
    fallback_image = "https://www.w3schools.com/howto/img_avatar.png"
    
    if pd.isna(url) or url == "" or not isinstance(url, str):
        st.image(fallback_image, width=150)
        return

    file_id = None
    if "drive.google.com/file/d/" in url:
        try:
            file_id = url.split("/d/")[1].split("/")[0]
        except IndexError:
            pass

    if file_id:
        image_bytes = fetch_secure_image_bytes(file_id)
        if image_bytes:
            st.image(image_bytes, width=150)
        else:
            st.warning("Secure photo fetch failed.")
            st.image(fallback_image, width=150)
    else:
        try:
            st.image(url, width=150)
        except Exception:
            st.image(fallback_image, width=150)


# Attempt to load data
try:
    df_master, df_mdm, df_attendance, df_forms, df_logs = load_database_data()
except Exception as e:
    st.warning("Please configure your Google Sheets connection and secrets to view live data.")
    st.stop()


# --- SIDEBAR: NAVIGATION ---
st.sidebar.title("BPS Digital Dashboard")
app_mode = st.sidebar.radio("Navigation", ["🎓 Student Profiles", "⚠️ Action Required Tracker"])
st.sidebar.divider()

# ==========================================
# MODE 1: STUDENT PROFILE VIEWER
# ==========================================
if app_mode == "🎓 Student Profiles":
    st.title("🎓 BPS Student Profile")

    st.sidebar.header("Find Student")
    class_list = sorted(df_master['Class'].astype(str).unique().tolist())
    selected_class = st.sidebar.selectbox("1. Select Class", class_list)

    if selected_class:
        filtered_by_class = df_master[df_master['Class'] == selected_class]
        section_list = sorted(filtered_by_class['Section'].astype(str).unique().tolist())
        selected_section = st.sidebar.selectbox("2. Select Section", section_list)
        
        if selected_section:
            filtered_by_section = filtered_by_class[filtered_by_class['Section'] == selected_section].copy()
            
            filtered_by_section['Roll_Numeric'] = pd.to_numeric(filtered_by_section['Roll'], errors='coerce')
            filtered_by_section = filtered_by_section.sort_values(by='Roll_Numeric')
            
            filtered_by_section['Display_Name'] = filtered_by_section['Name'].astype(str) + " (Roll: " + filtered_by_section['Roll'].astype(str) + ")"
            
            student_list = filtered_by_section['Display_Name'].unique().tolist()
            selected_display_name = st.sidebar.selectbox("3. Select Student", student_list)

            if selected_display_name:
                student_record = filtered_by_section[filtered_by_section['Display_Name'] == selected_display_name]
                
                if not student_record.empty:
                    student = student_record.iloc[0]
                    
                    selected_name = student['Name']
                    selected_roll = student['Roll']
                    
                    # --- PROFILE HEADER ---
                    st.divider()
                    
                    raw_code = str(student.get('Student Code', 'N/A'))
                    if raw_code.lower() not in ['n/a', 'nan', 'none', '']:
                        raw_code = raw_code.replace("'", "").split('.')[0]
                        display_code = raw_code.zfill(14) 
                    else:
                        display_code = "N/A"
                    
                    raw_mobile = str(student.get('Mobile', '')).split('.')[0].strip()
                    has_mobile = raw_mobile.isdigit() and len(raw_mobile) >= 10
                    
                    raw_sec_mobile = str(student.get('Secondary Mobile', '')).split('.')[0].strip()
                    if raw_sec_mobile.lower() in ['nan', 'none', '']:
                        has_sec_mobile = False
                    else:
                        has_sec_mobile = raw_sec_mobile.isdigit() and len(raw_sec_mobile) >= 10
                    
                    head_col1, head_col2 = st.columns([1, 4]) 

                    with head_col1:
                        raw_url = student.get('Photo_URL', '')
                        display_student_photo(raw_url)

                    with head_col2:
                        st.subheader(f"Profile: {student['Name']}")
                        st.write(f"**Class:** {student['Class']} '{student['Section']}' | **Roll No:** {student['Roll']} | **Student Code:** {display_code}")
                        st.caption(f"**Parents:** {student.get('Father', 'N/A')} & {student.get('Mother', 'N/A')}")
                        
                        if has_mobile and has_sec_mobile:
                            btn_col1, btn_col2 = st.columns(2)
                            with btn_col1:
                                st.link_button(f"📞 Primary: {raw_mobile}", f"tel:+91{raw_mobile}", use_container_width=True)
                            with btn_col2:
                                st.link_button(f"📞 Secondary: {raw_sec_mobile}", f"tel:+91{raw_sec_mobile}", use_container_width=True)
                        elif has_mobile:
                            st.link_button(f"📞 Call Guardian ({raw_mobile})", f"tel:+91{raw_mobile}")
                        elif has_sec_mobile:
                            st.link_button(f"📞 Call Guardian ({raw_sec_mobile})", f"tel:+91{raw_sec_mobile}")
                        else:
                            st.error("📞 No valid mobile number on record.")
                    
                    st.divider()
                    
                    # --- MAIN DATA MODULES ---
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.write("### 📅 Master Attendance")
                        student_att = df_attendance[
                            (df_attendance['Class'] == selected_class) & 
                            (df_attendance['Section'] == selected_section) & 
                            (df_attendance['Name'] == selected_name) &
                            (df_attendance['Roll'].astype(str) == str(selected_roll))
                        ]
                        
                        if not student_att.empty:
                            student_att['Status_Bool'] = student_att['Status'].astype(str).str.lower() == 'true'
                            days_present = student_att['Status_Bool'].sum()
                            total_recorded_days = len(student_att)
                            att_percentage = (days_present / total_recorded_days) * 100 if total_recorded_days > 0 else 0
                            
                            st.metric("Total Days Present", f"{days_present} / {total_recorded_days}")
                            st.progress(min(att_percentage / 100, 1.0))
                            st.caption(f"Current Attendance Rate: {att_percentage:.1f}%")
                        else:
                            st.info("No records found.")

                    with col2:
                        st.write("### 🍛 MDM Participation")
                        student_mdm = df_mdm[
                            (df_mdm['Class'] == selected_class) & 
                            (df_mdm['Section'] == selected_section) & 
                            (df_mdm['Name'] == selected_name) &
                            (df_mdm['Roll'].astype(str) == str(selected_roll))
                        ]
                        
                        mdm_days = len(student_mdm)
                        st.metric("Mid-Day Meals Taken", f"{mdm_days} Days")
                        
                        if not student_mdm.empty:
                            st.write("**Recent MDM Activity:**")
                            recent_mdm = student_mdm.tail(5)[['Date', 'Time']].sort_values(by='Date', ascending=False)
                            st.dataframe(recent_mdm, hide_index=True, use_container_width=True)
                        else:
                            st.info("No MDM entries found.")

                    with col3:
                        st.write("### 📋 Admin & Forms")
                        student_forms = df_forms[
                            (df_forms['Class'] == selected_class) & 
                            (df_forms['Section'] == selected_section) & 
                            (df_forms['Student Name'] == selected_name) &
                            (df_forms['Roll'].astype(str) == str(selected_roll))
                        ]
                        
                        if not student_forms.empty:
                            form_data = student_forms.iloc[0]
                            status = form_data.get('Return Status', 'Unknown')
                            if status == 'Complete':
                                st.success(f"**Form:** {status}")
                            else:
                                st.warning(f"**Form:** {status}")
                                
                            wa_status = form_data.get('WhatsApp Added', 'No')
                            if wa_status != 'No':
                                st.info(f"📱 **WhatsApp:** {wa_status}")
                            else:
                                st.error("📱 **WhatsApp:** Not Added")
                        else:
                            st.info("No form records found.")

                    st.divider()

                    # --- ACTIVITY & COMMUNICATION LOG ---
                    st.write("### 📝 Activity & Communication Log")
                    
                    if 'Class' in df_logs.columns and 'Section' in df_logs.columns and 'Name' in df_logs.columns and 'Roll' in df_logs.columns:
                        student_logs = df_logs[
                            (df_logs['Class'] == selected_class) & 
                            (df_logs['Section'] == selected_section) & 
                            (df_logs['Name'] == selected_name) &
                            (df_logs['Roll'].astype(str) == str(selected_roll))
                        ]
                    else:
                        student_logs = pd.DataFrame() 
                    
                    if not student_logs.empty:
                        st.dataframe(student_logs[['Date', 'Log Type', 'Details']], hide_index=True, use_container_width=True)
                    else:
                        st.caption("No previous activities logged for this student.")

                    with st.expander("➕ Add New Log Entry"):
                        with st.form("log_form", clear_on_submit=True):
                            log_type = st.selectbox("Log Type", [
                                "📞 Phone Call Log", 
                                "📱 WhatsApp Group Update", 
                                "🤒 Student Illness", 
                                "⚠️ Discipline/Behavior",
                                "💬 General Note"
                            ])
                            
                            ist = pytz.timezone('Asia/Kolkata')
                            today_str = datetime.datetime.now(ist).strftime("%d.%m.%y")
                            
                            log_date = st.text_input("Date (DD.MM.YY)", today_str)
                            log_notes = st.text_area("Details / Notes", placeholder="Enter the details...")
                            
                            submitted = st.form_submit_button("Save to 'Students Profile'")
                            
                            if submitted:
                                client = get_gspread_client()
                                db_log = client.open("Students Profile")
                                ws = db_log.sheet1
                                
                                if len(ws.row_values(1)) == 0:
                                    ws.append_row(["Date", "Class", "Section", "Roll", "Name", "Log Type", "Details"])
                                
                                ws.append_row([
                                    log_date, selected_class, selected_section, 
                                    selected_roll, selected_name, log_type, log_notes
                                ])
                                
                                st.cache_data.clear()
                                st.success("✅ Log saved successfully!")
                                st.rerun() 


# ==========================================
# MODE 2: INCOMPLETE DATA TRACKER
# ==========================================
elif app_mode == "⚠️ Action Required Tracker":
    st.title("⚠️ Action Required Tracker")
    st.write("Review students with missing essential information or pending administrative forms.")
    st.divider()
    
    class_list = sorted(df_master['Class'].astype(str).unique().tolist())
    selected_class_tracker = st.selectbox("1. Filter Tracking By Class", class_list)
    
    if selected_class_tracker:
        df_class_filtered = df_master[df_master['Class'] == selected_class_tracker].copy()
        
        # Add a Section Dropdown with an "All Sections" option
        section_list = ["All Sections"] + sorted(df_class_filtered['Section'].astype(str).unique().tolist())
        selected_section_tracker = st.selectbox("2. Filter By Section", section_list)
        
        if selected_section_tracker:
            if selected_section_tracker == "All Sections":
                df_tracker = df_class_filtered.copy()
            else:
                df_tracker = df_class_filtered[df_class_filtered['Section'] == selected_section_tracker].copy()
            
            # Sort properly by Roll numeric value
            df_tracker['Roll_Numeric'] = pd.to_numeric(df_tracker['Roll'], errors='coerce')
            df_tracker = df_tracker.sort_values(by='Roll_Numeric')
            
            incomplete_count = 0
            
            for idx, row in df_tracker.iterrows():
                missing_items = []
                
                # 1. Check Photo
                photo_val = str(row.get('Photo_URL', ''))
                if pd.isna(photo_val) or photo_val.strip() == '' or photo_val.lower() == 'nan':
                    missing_items.append("📷 Missing Photograph")
                    
                # 2. Check Mobile
                mob = str(row.get('Mobile', '')).split('.')[0].strip()
                if not mob.isdigit() or len(mob) < 10:
                    missing_items.append("📞 Missing/Invalid Primary Mobile")
                    
                # 3. Check Student Code
                code = str(row.get('Student Code', '')).replace("'", "").split('.')[0].strip()
                if code.lower() in ['nan', 'none', ''] or len(code) < 13:
                    missing_items.append("🆔 Missing Banglar Shiksha Code")
                    
                # 4. Check Administrative Form Status
                s_form = df_forms[
                    (df_forms['Class'] == row['Class']) & 
                    (df_forms['Section'] == row['Section']) & 
                    (df_forms['Roll'].astype(str) == str(row['Roll']))
                ]
                if not s_form.empty:
                    status = str(s_form.iloc[0].get('Return Status', '')).strip()
                    if status != 'Complete':
                        missing_items.append(f"📋 Form is {status}")
                else:
                    missing_items.append("📋 Distribution Form Record Missing")
                    
                if len(missing_items) > 0:
                    incomplete_count += 1
                    with st.container():
                        t_col1, t_col2, t_col3 = st.columns([1, 2, 2])
                        
                        with t_col1:
                            display_student_photo(photo_val)
                        
                        with t_col2:
                            st.subheader(row['Name'])
                            st.write(f"Class {row['Class']} '{row['Section']}'")
                            st.write(f"Roll No: **{row['Roll']}**")
                        
                        with t_col3:
                            st.write("**Data Missing:**")
                            for item in missing_items:
                                st.error(item)
                                
                    st.divider()
                    
            if incomplete_count == 0:
                st.success(f"✅ Amazing! All student records for the selected group are 100% complete!")
            else:
                section_display = "All Sections" if selected_section_tracker == "All Sections" else f"Section '{selected_section_tracker}'"
                st.info(f"Showing {incomplete_count} students with incomplete records in Class {selected_class_tracker}, {section_display}.")
