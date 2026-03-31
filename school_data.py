import streamlit as st
import pandas as pd
import base64
import re
import os
import gspread
from gspread.exceptions import WorksheetNotFound, APIError
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import AuthorizedSession
import datetime
from fpdf import FPDF

# --- 1. SECURE GOOGLE CONNECTION ---
@st.cache_resource
def get_google_credentials():
    skey = dict(st.secrets["gcp_service_account"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.readonly"]
    return Credentials.from_service_account_info(skey, scopes=scopes)

@st.cache_resource
def init_gsheets():
    creds = get_google_credentials()
    gc = gspread.authorize(creds)
    return gc.open("BPS_Database")

@st.cache_resource
def get_drive_session():
    creds = get_google_credentials()
    return AuthorizedSession(creds)

sh = init_gsheets()

# --- 2. DATABASE HELPER FUNCTIONS ---
@st.cache_data(ttl=5) 
def fetch_sheet_data(sheet_name):
    try:
        ws = sh.worksheet(sheet_name)
        df = pd.DataFrame(ws.get_all_records())
        df = df.replace({'TRUE': True, 'FALSE': False, 'True': True, 'False': False}).infer_objects(copy=False)
        return df
    except:
        return pd.DataFrame()

def clear_sheet_cache():
    fetch_sheet_data.clear()

def append_sheet_df(sheet_name, df):
    if df.empty: return
    try: 
        ws = sh.worksheet(sheet_name)
    except WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=20)
        ws.append_row(list(df.columns))
    
    df = df.fillna("").astype(str)
    ws.append_rows(df.values.tolist())
    clear_sheet_cache()

# --- 3. SECURE IMAGE FETCHING ---
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_secure_image_bytes(file_id):
    try:
        authed_session = get_drive_session()
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
        response = authed_session.get(url)
        if response.status_code == 200: return response.content
        return None
    except Exception: return None

def get_secure_photo_uri(url):
    fallback_image = "https://www.w3schools.com/howto/img_avatar.png"
    if pd.isna(url) or url == "" or not isinstance(url, str): return fallback_image

    file_id = None
    match = re.search(r"(?:id=|/d/)([\w-]+)", url)
    if match: file_id = match.group(1)

    if file_id:
        image_bytes = fetch_secure_image_bytes(file_id)
        if image_bytes:
            b64_str = base64.b64encode(image_bytes).decode()
            return f"data:image/jpeg;base64,{b64_str}"
            
    return url if url.startswith("http") else fallback_image

# --- START NEW APP UI BELOW ---

st.set_page_config(page_title="BPS Data Hub", page_icon="🏫")

st.title("🏫 BPS Data Hub")

# Strict Mobile Responsiveness CSS for Flexbox
st.markdown("""
<style>
@media (max-width: 768px) {
    [data-testid="stHorizontalBlock"] {
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        overflow-x: hidden !important;
    }
    /* Lock the photo column to a fixed width and allow text to fill the rest */
    [data-testid="column"]:nth-of-type(1) {
        flex: 0 0 65px !important;
        width: 65px !important;
    }
    [data-testid="column"]:nth-of-type(2) {
        flex: 1 1 0% !important;
        width: auto !important;
    }
}
</style>
""", unsafe_allow_html=True)

# 1. Fetch Data with API Rate Limit Safety
with st.spinner("Syncing with BPS Database..."):
    try:
        df_students = fetch_sheet_data("students_master")
        df_teachers = fetch_sheet_data("TEACHERS_DETAIL")
    except APIError:
        st.error("Google Sheets API Quota Exceeded. Please try again later.")
        st.stop()
    except Exception as e:
        st.error(f"Error connecting to database: {e}")
        st.stop()

if df_students.empty and df_teachers.empty:
    st.warning("No data found in BPS_Database.")
    st.stop()

# Create Tabs for Navigation
tab_bday, tab_summary, tab_enrolment, tab_search = st.tabs(["🎂 Birthdays", "📊 Summary", "📈 Enrolment", "🔍 Search"])

# ==========================================
# TAB 1: BIRTHDAY MANAGER
# ==========================================
with tab_bday:
    records = []

    if not df_students.empty:
        for idx, row in df_students.iterrows():
            dob_str = str(row.get('DOB', '')).strip()
            name = str(row.get('Name', '')).strip()
            cls = str(row.get('Class', '')).strip().upper()
            sec = str(row.get('Section', '')).strip().upper()
            
            if cls in ["CLASS PP", "CLASS LPP"]:
                cls = "CLASS PP & LPP"
                
            if dob_str and name and dob_str != "nan":
                try:
                    dt = pd.to_datetime(dob_str, errors='coerce')
                    if pd.notna(dt):
                        records.append({
                            'Name': name,
                            'Category': f"{cls} - Section {sec}" if sec else cls,
                            'Role': 'Student',
                            'Month_Num': dt.month,
                            'Month_Name': dt.strftime('%B'),
                            'Day': dt.day,
                            'DOB_Formatted': dt.strftime('%d-%b-%Y')
                        })
                except Exception:
                    pass

    if not df_teachers.empty:
        for idx, row in df_teachers.iterrows():
            dob_str = str(row.get('DOB', '')).strip()
            name = str(row.get('Name', '')).strip()
            designation = str(row.get('Designation', 'Staff')).strip()
            
            if dob_str and name and dob_str != "nan":
                try:
                    dt = pd.to_datetime(dob_str, dayfirst=True, errors='coerce')
                    if pd.notna(dt):
                        records.append({
                            'Name': f"{name} ({designation})",
                            'Category': "Staff & Teachers", 
                            'Role': 'Teacher',
                            'Month_Num': dt.month,
                            'Month_Name': dt.strftime('%B'),
                            'Day': dt.day,
                            'DOB_Formatted': dt.strftime('%d-%b-%Y')
                        })
                except Exception:
                    pass

    df_bday = pd.DataFrame(records)

    if df_bday.empty:
        st.info("No valid dates of birth found in the database.")
    else:
        st.markdown("### Filter Options")
        months = ["All Months"] + [datetime.date(2000, m, 1).strftime('%B') for m in range(1, 13)]
        selected_month = st.selectbox("Select Month to Display", months)

        current_year = datetime.date.today().year
        if selected_month != "All Months":
            filtered_df = df_bday[df_bday['Month_Name'] == selected_month].copy()
            display_title = f"{selected_month} {current_year}"
        else:
            filtered_df = df_bday.copy()
            display_title = f"All Months {current_year}"

        filtered_df = filtered_df.sort_values(by=['Month_Num', 'Day'])

        all_categories = sorted(filtered_df['Category'].unique())
        pp_categories = [cat for cat in all_categories if "CLASS PP & LPP" in cat]
        other_categories = [cat for cat in all_categories if cat not in pp_categories]
        final_category_order = pp_categories + other_categories

        def generate_birthday_pdf(dataframe, month_title, category_order):
            pdf = FPDF()
            pdf.add_page()
            
            if os.path.exists("logo.png"):
                pdf.image("logo.png", x=12, y=8, w=18)
            
            pdf.set_font("helvetica", "B", 16)
            pdf.set_y(10)
            pdf.cell(0, 8, f"Bhagyabantapur Primary School", new_x="LMARGIN", new_y="NEXT", align="C")
            
            pdf.set_font("helvetica", "B", 12)
            pdf.cell(0, 8, f"Birthday Roster: {month_title}", new_x="LMARGIN", new_y="NEXT", align="C")
            pdf.ln(8) 
            
            overall_sl = 1 
            
            for cat in category_order:
                group = dataframe[dataframe['Category'] == cat]
                if group.empty: continue
                
                display_cat = cat
                if cat == "Staff & Teachers":
                    display_cat = "Teachers" if len(group) > 1 else "Teacher"
                    
                pdf.set_font("helvetica", "B", 12)
                pdf.set_text_color(41, 128, 185) 
                pdf.cell(0, 8, f"[{display_cat}]", new_x="LMARGIN", new_y="NEXT")
                
                pdf.set_font("helvetica", "", 10)
                pdf.set_text_color(0, 0, 0)
                
                for _, row in group.iterrows():
                    bday_text = f" {overall_sl:02d}. {row['Name']} (DOB: {row['DOB_Formatted']})"
                    pdf.cell(0, 6, bday_text, new_x="LMARGIN", new_y="NEXT")
                    overall_sl += 1 
                pdf.ln(4)
                
            return bytes(pdf.output())

        if filtered_df.empty:
            st.info(f"No birthdays recorded in {selected_month}.")
        else:
            pdf_bytes = generate_birthday_pdf(filtered_df, display_title, final_category_order)
            
            col_dl, col_space = st.columns([1, 2])
            with col_dl:
                st.download_button(
                    label="📄 Export to PDF",
                    data=pdf_bytes,
                    file_name=f"BPS_Birthdays_{display_title.replace(' ', '_')}.pdf",
                    mime="application/pdf"
                )
            
            st.divider()
            st.markdown(f"### Birthday Roster: {display_title}")
            
            overall_sl_ui = 1 
            for cat in final_category_order:
                group = filtered_df[filtered_df['Category'] == cat]
                if group.empty: continue
                
                display_cat = cat
                if cat == "Staff & Teachers":
                    display_cat = "Teachers" if len(group) > 1 else "Teacher"
                    
                st.markdown(f"#### 🏷️ {display_cat}")
                
                for _, row in group.iterrows():
                    st.markdown(f"**{overall_sl_ui:02d}.** {row['Name']} *(DOB: {row['DOB_Formatted']})*")
                    overall_sl_ui += 1 
                    
                st.write("") 

# ==========================================
# TAB 2: STUDENT SUMMARY
# ==========================================
with tab_summary:
    st.markdown("<h3 style='text-align: center; color: #2980b9;'>Bhagyabantapur Primary School</h3>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center;'>📊 Student Strength Summary</h4>", unsafe_allow_html=True)
    st.divider()

    if not df_students.empty:
        df_students['Clean_Class'] = df_students['Class'].astype(str).str.strip().str.upper()
        class_counts = df_students['Clean_Class'].value_counts().to_dict()

        target_classes = [
            "CLASS LPP", "CLASS PP", "CLASS I", 
            "CLASS II", "CLASS III", "CLASS IV", "CLASS V"
        ]

        summary_lines = []
        summary_lines.append("Bhagyabantapur Primary School")
        summary_lines.append("Student Summary")
        summary_lines.append("-" * 30)

        total_students = 0
        cols = st.columns(3)
        col_idx = 0
        
        for cls in target_classes:
            count = class_counts.get(cls, 0)
            total_students += count
            summary_lines.append(f"{cls}: {count}")
            
            with cols[col_idx % 3]:
                st.metric(label=cls, value=count)
            col_idx += 1

        summary_lines.append("-" * 30)
        summary_lines.append(f"TOTAL: {total_students}")
        
        st.divider()
        st.markdown(f"### **Total Students: {total_students}**")
        
        st.info("💡 **Tip:** Hover over the text box below and click the **Copy icon** in the top right corner to easily copy this data.")
        copy_string = "\n".join(summary_lines)
        st.code(copy_string, language="text")

    else:
        st.warning("No student records found to generate a summary.")

# ==========================================
# TAB 3: ENROLMENT DATA (Social Category)
# ==========================================
with tab_enrolment:
    st.markdown("<h3 style='text-align: center; color: #2980b9;'>Annual Data Enrolment (Social Category wise)</h3>", unsafe_allow_html=True)
    st.divider()

    if not df_students.empty:
        # Prepare clean dataframe for accurate cross-tabulation
        df_clean = df_students.copy()
        df_clean['Class'] = df_clean.get('Class', '').astype(str).str.strip().str.upper()
        df_clean['Gender'] = df_clean.get('Gender', '').astype(str).str.strip().str.upper()
        df_clean['Social Category'] = df_clean.get('Social Category', '').astype(str).str.strip().str.upper()

        def get_level(c):
            if c in ['CLASS PP', 'CLASS LPP']: return 'Bal Vatika'
            if c in ['CLASS I', 'CLASS II', 'CLASS III', 'CLASS IV', 'CLASS V']: return 'Primary'
            return 'Other'

        def get_gender(g):
            if 'BOY' in g or 'M' in g: return 'Boys'
            if 'GIRL' in g or 'F' in g: return 'Girls'
            return 'Unknown'

        def get_soc(c):
            if 'SC' in c: return 'SC'
            if 'ST' in c: return 'ST'
            if 'OBC' in c: return 'OBC'
            if 'GEN' in c: return 'General'
            return 'General' 

        df_clean['Level'] = df_clean['Class'].apply(get_level)
        df_clean['Gen'] = df_clean['Gender'].apply(get_gender)
        df_clean['Soc_Cat'] = df_clean['Social Category'].apply(get_soc)

        categories = ['SC', 'ST', 'OBC', 'General']
        
        def count_stu(lvl, gen, cat):
            return len(df_clean[(df_clean['Level'] == lvl) & (df_clean['Gen'] == gen) & (df_clean['Soc_Cat'] == cat)])

        # Constructing HTML string flat without leading spaces to prevent markdown code block trigger
        html = '<div style="overflow-x:auto;">'
        html += '<table style="width:100%; border-collapse: collapse; text-align: center; font-family: sans-serif; border: 1px solid #ddd; margin-bottom: 20px;">'
        html += '<tr style="background-color: #2980b9; color: white;">'
        html += '<th colspan="2" style="padding: 10px; border: 1px solid #ddd;">Class Level &nbsp;⬇️ &nbsp;|&nbsp; Social Category &nbsp;➡️</th>'
        html += '<th style="padding: 10px; border: 1px solid #ddd;">SC</th>'
        html += '<th style="padding: 10px; border: 1px solid #ddd;">ST</th>'
        html += '<th style="padding: 10px; border: 1px solid #ddd;">OBC</th>'
        html += '<th style="padding: 10px; border: 1px solid #ddd;">General</th>'
        html += '<th style="padding: 10px; border: 1px solid #ddd; background-color: #1a5276;">Total</th>'
        html += '</tr>'
        
        levels_config = [
            ('Bal Vatika', 'Bal Vatika<br><span style="font-size:12px; color:gray;">(Class PP & LPP)</span>'), 
            ('Primary', 'Primary<br><span style="font-size:12px; color:gray;">(Class I - V)</span>')
        ]
        
        for lvl_key, lvl_label in levels_config:
            # Boys Row
            html += '<tr>'
            html += f'<td rowspan="3" style="font-weight: bold; vertical-align: middle; background-color: #f4f6f7; border: 1px solid #ddd; padding: 8px;">{lvl_label}</td>'
            html += '<td style="text-align: left; padding: 8px; border: 1px solid #ddd;">Boys</td>'
            b_tot = 0
            for cat in categories:
                c = count_stu(lvl_key, 'Boys', cat)
                b_tot += c
                html += f'<td style="padding: 8px; border: 1px solid #ddd;">{c}</td>'
            html += f'<td style="padding: 8px; border: 1px solid #ddd; font-weight:bold; background-color: #eaeded;">{b_tot}</td></tr>'
            
            # Girls Row
            html += '<tr>'
            html += '<td style="text-align: left; padding: 8px; border: 1px solid #ddd;">Girls</td>'
            g_tot = 0
            for cat in categories:
                c = count_stu(lvl_key, 'Girls', cat)
                g_tot += c
                html += f'<td style="padding: 8px; border: 1px solid #ddd;">{c}</td>'
            html += f'<td style="padding: 8px; border: 1px solid #ddd; font-weight:bold; background-color: #eaeded;">{g_tot}</td></tr>'
            
            # Total Row
            html += '<tr style="font-weight: bold; background-color: #e8f8f5;">'
            html += '<td style="text-align: left; padding: 8px; border: 1px solid #ddd;">Total</td>'
            t_tot = 0
            for cat in categories:
                c = count_stu(lvl_key, 'Boys', cat) + count_stu(lvl_key, 'Girls', cat)
                t_tot += c
                html += f'<td style="padding: 8px; border: 1px solid #ddd;">{c}</td>'
            html += f'<td style="padding: 8px; border: 1px solid #ddd; font-weight:bold; background-color: #d1f2eb; color: #0e6251;">{t_tot}</td></tr>'

        html += '</table></div>'
        
        st.markdown(html, unsafe_allow_html=True)
    else:
        st.warning("No student records found to generate enrolment data.")

# ==========================================
# TAB 4: STUDENT SEARCH
# ==========================================
with tab_search:
    st.markdown("### 🔍 Search Student Directory")
    search_query = st.text_input("Enter Mobile Number (Primary or Secondary)", placeholder="e.g. 9876543210").strip()
    
    if search_query:
        if df_students.empty:
            st.error("Student database is empty.")
        else:
            df_search = df_students.copy()
            df_search['Mobile_Clean'] = df_search.get('Mobile', '').astype(str).str.replace('.0', '', regex=False).str.strip()
            df_search['Sec_Mobile_Clean'] = df_search.get('Secondary Mobile', '').astype(str).str.replace('.0', '', regex=False).str.strip()
            
            matches = df_search[(df_search['Mobile_Clean'] == search_query) | (df_search['Sec_Mobile_Clean'] == search_query)]
            
            if matches.empty:
                st.warning(f"No student found linked to the number: {search_query}")
            else:
                st.success(f"Found {len(matches)} matching student(s)!")
                st.write("")
                
                for _, row in matches.iterrows():
                    photo_url = str(row.get('Photo_URL', '')).strip()
                    if photo_url == 'nan' or not photo_url:
                        photo_url = str(row.get('Thumb_URL', '')).strip()
                        
                    img_uri = get_secure_photo_uri(photo_url)
                    
                    c1, c2 = st.columns(2)
                    
                    with c1:
                        st.markdown(f"""
                            <img src="{img_uri}" style="width:55px; height:55px; border-radius:50%; object-fit:cover; border:2px solid #2980b9;">
                        """, unsafe_allow_html=True)
                    
                    with c2:
                        st.markdown(f"**{row.get('Name', 'Unknown')}**")
                        st.markdown(f"<span style='color:gray; font-size:14px;'>{row.get('Class', '')} | Sec: {row.get('Section', '')} | Roll: {row.get('Roll', '')}</span>", unsafe_allow_html=True)
                    
                    with st.container(border=True):
                        st.write(f"🧑‍🏫 **Parents:** {row.get('Father', 'N/A')} & {row.get('Mother', 'N/A')}")
                        st.write(f"🎂 **DOB:** {row.get('DOB', 'N/A')}")
                        st.write(f"🩸 **Blood Group:** {row.get('BloodGroup', 'N/A')}")
                        st.write(f"📞 **Primary:** {row.get('Mobile_Clean', 'N/A')} | **Alt:** {row.get('Sec_Mobile_Clean', 'N/A')}")
                        st.write(f"🆔 **Student Code:** {row.get('Student Code', 'N/A')}")
                        st.write(f"📅 **Admission Date:** {row.get('Admission Date', 'N/A')}")
                    
                    st.divider()
