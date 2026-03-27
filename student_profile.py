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
        
        if len(log_ws.row_values(1)) == 0:
            log_ws.append_row(["Date", "Class", "Section", "Roll", "Name", "Log Type", "Details"])
            df_logs = pd.DataFrame(columns=["Date", "Class", "Section", "Roll", "Name", "Log Type", "Details"])
        else:
            df_logs = pd.DataFrame(log_ws.get_all_records())
            
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

# --- 5. MAIN APP LOGIC ---
st.title("🎓 BPS Student Profile Dashboard")

# --- SIDEBAR: DEVELOPER CONSOLE ---
st.sidebar.header("🛠️ Developer Tools")

with st.sidebar.expander("📝 Log App Development"):
    with st.form("dev_log_form", clear_on_submit=True):
        st.caption("Record new code updates and features.")
        app_version = st.text_input("Version Number", placeholder="e.g., v1.2")
        app_changes = st.text_area("Release Notes", placeholder="e.g., Added secure photo fetching and direct Call Parent button.")
        
        submitted_dev = st.form_submit_button("Save Update Log")
        
        if submitted_dev and app_changes:
            st.cache_data.clear() # Clears cache to ensure the app is fresh after an update
            
            try:
                client = get_gspread_client()
                db_main = client.open("BPS_Database")
                
                # Check if dev log tab exists, if not, create it
                try:
                    dev_ws = db_main.worksheet("App_Development_Log")
                except gspread.exceptions.WorksheetNotFound:
                    dev_ws = db_main.add_worksheet(title="App_Development_Log", rows="500", cols="5")
                    dev_ws.append_row(["Date", "Time (IST)", "Developer", "Version", "Release Notes"])
                    
                # Get Current Indian Standard Time
                ist = pytz.timezone('Asia/Kolkata')
                now = datetime.datetime.now(ist)
                
                log_date = now.strftime("%d.%m.%y")
                log_time = now.strftime("%I:%M %p")
                
                dev_ws.append_row([log_date, log_time, "Sukhamay Kisku", app_version, app_changes])
                
                st.sidebar.success(f"✅ Version {app_version} logged successfully!")
            except Exception as e:
                st.sidebar.error(f"Failed to save development log: {e}")

st.sidebar.divider()

# Attempt to load data
try:
    df_master, df_mdm, df_attendance, df_forms, df_logs = load_database_data()
except Exception as e:
    st.warning("Please configure your Google Sheets connection and secrets to view live data.")
    st.stop()

# --- SIDEBAR: EASY SEARCH ---
st.sidebar.header("Find Student")

class_list = sorted(df_master['Class'].astype(str).unique().tolist())
selected_class = st.sidebar.selectbox("1. Select Class", class_list)

if selected_class:
    filtered_by_class = df_master[df_master['Class'] == selected_class]
    section_list = sorted(filtered_by_class['Section'].astype(str).unique().tolist())
    selected_section = st.sidebar.selectbox("2. Select Section", section_list)
    
    if selected_section:
        filtered_by_section = filtered_by_class[filtered_by_class['Section'] == selected_section].copy()
        
        # Sort by Roll Number
        filtered_by_section['Roll_Numeric'] = pd.to_numeric(filtered_by_section['Roll'], errors='coerce')
        filtered_by_section = filtered_by_section.sort_values(by='Roll_Numeric')
        
        # Display Name
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
                
                raw_mobile = str(student.get('Mobile', '')).split('.')[0]
                has_mobile = raw_mobile.isdigit() and len(raw_mobile) >= 10
                
                head_col1, head_col2 = st.columns([1, 4]) 

                with head_col1:
                    raw_url = student.get('Photo_URL', '')
                    display_student_photo(raw_url)

                with head_col2:
                    st.subheader(f"Profile: {student['Name']}")
                    st.write(f"**Class:** {student['Class']} '{student['Section']}' | **Roll No:** {student['Roll']} | **Student Code:** {display_code}")
                    st.caption(f"**Parents:** {student.get('Father', 'N/A')} & {student.get('Mother', 'N/A')}")
                    
                    if has_mobile:
                        st.link_button(f"📞 Call Guardian ({raw_mobile})", f"tel:+91{raw_mobile}")
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
                
                student_logs = df_logs[
                    (df_logs['Class'] == selected_class) & 
                    (df_logs['Section'] == selected_section) & 
                    (df_logs['Name'] == selected_name) &
                    (df_logs['Roll'].astype(str) == str(selected_roll))
                ]
                
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
                                log_date, 
                                selected_class, 
                                selected_section, 
                                selected_roll, 
                                selected_name, 
                                log_type, 
                                log_notes
                            ])
                            
                            st.success("✅ Log saved successfully!")
                            st.rerun()
