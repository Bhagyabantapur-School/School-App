import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="BPS Student Profile", page_icon="🎓", layout="wide")

# --- 2. GOOGLE SHEETS CONNECTION ---
@st.cache_resource
def get_gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    # Connects using Streamlit Cloud Secrets
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], 
        scopes=scopes
    )
    return gspread.authorize(creds)

# --- 3. DATA LOADING & CACHING ---
@st.cache_data(ttl=600) # Refreshes every 10 minutes
def load_database_data():
    client = get_gspread_client()
    db = client.open("BPS_Database") 
    
    try:
        # Fetching worksheets based on your actual file names
        df_master = pd.DataFrame(db.worksheet("students_master").get_all_records())
        df_mdm = pd.DataFrame(db.worksheet("mdm_log").get_all_records())
        df_attendance = pd.DataFrame(db.worksheet("student_attendance_master").get_all_records())
        df_forms = pd.DataFrame(db.worksheet("form_distribution_log").get_all_records())
    except gspread.exceptions.WorksheetNotFound as e:
        st.error(f"Could not find worksheet: {e}. Please check your tab names in Google Sheets.")
        st.stop()
        
    return df_master, df_mdm, df_attendance, df_forms

# --- 4. HELPER FUNCTION: GOOGLE DRIVE PHOTOS ---
def get_image_url(url):
    """
    Converts a Google Drive view link into a direct download link for Streamlit.
    """
    if pd.isna(url) or url == "" or not isinstance(url, str):
        # Default placeholder avatar
        return "https://www.w3schools.com/howto/img_avatar.png"
    
    if "drive.google.com/file/d/" in url:
        try:
            file_id = url.split("/d/")[1].split("/")[0]
            return f"https://drive.google.com/uc?export=download&id={file_id}"
        except IndexError:
            return url
    return url

# --- 5. MAIN APP LOGIC ---
st.title("🎓 BPS Student Profile Dashboard")

try:
    df_master, df_mdm, df_attendance, df_forms = load_database_data()
except Exception as e:
    st.warning("Please configure your Google Sheets connection and secrets to view live data.")
    st.stop()

# --- SIDEBAR: EASY SEARCH ---
st.sidebar.header("Find Student")

# Cascading Dropdowns for accurate selection
class_list = sorted(df_master['Class'].astype(str).unique().tolist())
selected_class = st.sidebar.selectbox("1. Select Class", class_list)

if selected_class:
    filtered_by_class = df_master[df_master['Class'] == selected_class]
    section_list = sorted(filtered_by_class['Section'].astype(str).unique().tolist())
    selected_section = st.sidebar.selectbox("2. Select Section", section_list)
    
    if selected_section:
        filtered_by_section = filtered_by_class[filtered_by_class['Section'] == selected_section]
        student_list = sorted(filtered_by_section['Name'].astype(str).unique().tolist())
        selected_name = st.sidebar.selectbox("3. Select Student", student_list)

        if selected_name:
            # Get the specific student's master record
            student_record = filtered_by_section[filtered_by_section['Name'] == selected_name]
            
            if not student_record.empty:
                student = student_record.iloc[0]
                
                # --- PROFILE HEADER ---
                st.divider()
                
                # Format the 14-digit Banglar Shiksha Student Code
                raw_code = str(student.get('Student Code', 'N/A'))
                if raw_code.lower() not in ['n/a', 'nan', 'none', '']:
                    raw_code = raw_code.replace("'", "").split('.')[0] # Clean up decimals/quotes if any
                    display_code = raw_code.zfill(14) 
                else:
                    display_code = "N/A"
                
                # Layout for Photo and Details
                head_col1, head_col2 = st.columns([1, 4]) 

                with head_col1:
                    raw_url = student.get('Photo_URL', '')
                    final_photo_url = get_image_url(raw_url)
                    st.image(final_photo_url, width=150)

                with head_col2:
                    st.subheader(f"Profile: {student['Name']}")
                    st.write(f"**Class:** {student['Class']} '{student['Section']}' | **Roll No:** {student['Roll']} | **Student Code:** {display_code}")
                    st.caption(f"**Parents:** {student.get('Father', 'N/A')} & {student.get('Mother', 'N/A')} | **Mobile:** {student.get('Mobile', 'N/A')}")
                
                st.divider()
                
                # --- MAIN DATA MODULES ---
                col1, col2, col3 = st.columns(3)
                
                # MODULE 1: OVERALL ATTENDANCE
                with col1:
                    st.write("### 📅 Master Attendance")
                    student_att = df_attendance[
                        (df_attendance['Class'] == selected_class) & 
                        (df_attendance['Section'] == selected_section) & 
                        (df_attendance['Name'] == selected_name)
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
                        st.info("No master attendance records found.")

                # MODULE 2: MDM LOG
                with col2:
                    st.write("### 🍛 MDM Participation")
                    student_mdm = df_mdm[
                        (df_mdm['Class'] == selected_class) & 
                        (df_mdm['Section'] == selected_section) & 
                        (df_mdm['Name'] == selected_name)
                    ]
                    
                    mdm_days = len(student_mdm)
                    st.metric("Mid-Day Meals Taken", f"{mdm_days} Days")
                    
                    if not student_mdm.empty:
                        st.write("**Recent MDM Activity:**")
                        recent_mdm = student_mdm.tail(5)[['Date', 'Time']].sort_values(by='Date', ascending=False)
                        st.dataframe(recent_mdm, hide_index=True, use_container_width=True)
                    else:
                        st.info("No MDM entries found.")

                # MODULE 3: ADMINISTRATIVE / FORMS
                with col3:
                    st.write("### 📋 Admin & Forms")
                    student_forms = df_forms[
                        (df_forms['Class'] == selected_class) & 
                        (df_forms['Section'] == selected_section) & 
                        (df_forms['Student Name'] == selected_name)
                    ]
                    
                    if not student_forms.empty:
                        form_data = student_forms.iloc[0]
                        
                        status = form_data.get('Return Status', 'Unknown')
                        if status == 'Complete':
                            st.success(f"**Form Status:** {status}")
                        else:
                            st.warning(f"**Form Status:** {status}")
                            
                        wa_status = form_data.get('WhatsApp Added', 'No')
                        wa_group = form_data.get('WhatsApp Group', 'None')
                        if wa_status != 'No':
                            st.info(f"📱 **WhatsApp:** {wa_status} ({wa_group})")
                        else:
                            st.error("📱 **WhatsApp:** Not Added")
                            
                        st.caption(f"Last updated on Banglar Shiksha: {form_data.get('Banglar Shiksha Updated', 'No')}")
                    else:
                        st.info("No form distribution records found.")
