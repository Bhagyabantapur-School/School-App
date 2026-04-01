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
        df_attendance = fetch_sheet_data("student_attendance_master")
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
# TAB 3: ENROLMENT DATA & ROLL STRENGTH
# ==========================================
with tab_enrolment:
    
    if not df_students.empty:
        # Pre-process valid dataframe for both sections (Strict Rule: Exclude blank genders)
        df_valid = df_students.copy()
        df_valid['Gender'] = df_valid.get('Gender', '').astype(str).str.strip().str.upper()
        df_valid = df_valid[df_valid['Gender'] != ''] 
        df_valid['Clean_Class'] = df_valid.get('Class', '').astype(str).str.strip().str.upper()

        def get_demo_gender(g):
            if 'BOY' in g or 'M' in g: return 'Male'
            if 'GIRL' in g or 'F' in g: return 'Female'
            return 'Unknown'
            
        df_valid['Demo_Gender'] = df_valid['Gender'].apply(get_demo_gender)

        # ---------------------------------------------------------
        # SECTION 1: Annual Data Enrolment Table
        # ---------------------------------------------------------
        st.markdown("<h3 style='text-align: center; color: #2980b9;'>Annual Data Enrolment (Social Category wise)</h3>", unsafe_allow_html=True)
        st.write("")

        def get_level(c):
            if c in ['CLASS PP', 'CLASS LPP']: return 'Bal Vatika'
            if c in ['CLASS I', 'CLASS II', 'CLASS III', 'CLASS IV', 'CLASS V']: return 'Primary'
            return 'Other'

        def get_soc(c):
            if 'SC' in c: return 'SC'
            if 'ST' in c: return 'ST'
            if 'OBC' in c: return 'OBC'
            if 'GEN' in c: return 'General'
            return 'General' 

        df_valid['Level'] = df_valid['Clean_Class'].apply(get_level)
        df_valid['Soc_Cat'] = df_valid['Social Category'].astype(str).str.strip().str.upper().apply(get_soc)

        categories_annual = ['SC', 'ST', 'OBC', 'General']
        
        def count_stu_annual(lvl, gen, cat):
            return len(df_valid[(df_valid['Level'] == lvl) & (df_valid['Demo_Gender'] == gen) & (df_valid['Soc_Cat'] == cat)])

        html_annual = '<div style="overflow-x:auto;">'
        html_annual += '<table style="width:100%; border-collapse: collapse; text-align: center; font-family: sans-serif; border: 1px solid #ddd; margin-bottom: 20px;">'
        
        # Header Row 1
        html_annual += '<tr style="background-color: #2980b9; color: white;">'
        html_annual += '<th rowspan="2" style="padding: 10px; border: 1px solid #ddd; vertical-align: middle;">Social Category</th>'
        html_annual += '<th colspan="3" style="padding: 10px; border: 1px solid #ddd;">Bal Vatika<br><span style="font-size:12px; color:#e0f7fa;">(Class PP & LPP)</span></th>'
        html_annual += '<th colspan="3" style="padding: 10px; border: 1px solid #ddd;">Primary<br><span style="font-size:12px; color:#e0f7fa;">(Class I - V)</span></th>'
        html_annual += '</tr>'
        
        # Header Row 2
        html_annual += '<tr style="background-color: #1a5276; color: white;">'
        html_annual += '<th style="padding: 8px; border: 1px solid #ddd;">Boys</th>'
        html_annual += '<th style="padding: 8px; border: 1px solid #ddd;">Girls</th>'
        html_annual += '<th style="padding: 8px; border: 1px solid #ddd;">Total</th>'
        html_annual += '<th style="padding: 8px; border: 1px solid #ddd;">Boys</th>'
        html_annual += '<th style="padding: 8px; border: 1px solid #ddd;">Girls</th>'
        html_annual += '<th style="padding: 8px; border: 1px solid #ddd;">Total</th>'
        html_annual += '</tr>'
        
        totals = {'bv_b': 0, 'bv_g': 0, 'bv_t': 0, 'p_b': 0, 'p_g': 0, 'p_t': 0}
        
        for cat in categories_annual:
            bv_b = count_stu_annual('Bal Vatika', 'Male', cat)
            bv_g = count_stu_annual('Bal Vatika', 'Female', cat)
            bv_t = bv_b + bv_g
            
            p_b = count_stu_annual('Primary', 'Male', cat)
            p_g = count_stu_annual('Primary', 'Female', cat)
            p_t = p_b + p_g
            
            totals['bv_b'] += bv_b
            totals['bv_g'] += bv_g
            totals['bv_t'] += bv_t
            totals['p_b'] += p_b
            totals['p_g'] += p_g
            totals['p_t'] += p_t
            
            html_annual += '<tr>'
            html_annual += f'<td style="font-weight: bold; text-align: left; padding: 8px; border: 1px solid #ddd; background-color: #f4f6f7;">{cat}</td>'
            html_annual += f'<td style="padding: 8px; border: 1px solid #ddd;">{bv_b}</td>'
            html_annual += f'<td style="padding: 8px; border: 1px solid #ddd;">{bv_g}</td>'
            html_annual += f'<td style="padding: 8px; border: 1px solid #ddd; font-weight:bold; background-color: #eaeded;">{bv_t}</td>'
            html_annual += f'<td style="padding: 8px; border: 1px solid #ddd;">{p_b}</td>'
            html_annual += f'<td style="padding: 8px; border: 1px solid #ddd;">{p_g}</td>'
            html_annual += f'<td style="padding: 8px; border: 1px solid #ddd; font-weight:bold; background-color: #eaeded;">{p_t}</td>'
            html_annual += '</tr>'
            
        # Bottom Total Row
        html_annual += '<tr style="font-weight: bold; background-color: #d1f2eb; color: #0e6251;">'
        html_annual += '<td style="text-align: left; padding: 8px; border: 1px solid #ddd;">Total</td>'
        html_annual += f'<td style="padding: 8px; border: 1px solid #ddd;">{totals["bv_b"]}</td>'
        html_annual += f'<td style="padding: 8px; border: 1px solid #ddd;">{totals["bv_g"]}</td>'
        html_annual += f'<td style="padding: 8px; border: 1px solid #ddd; background-color: #a3e4d7;">{totals["bv_t"]}</td>'
        html_annual += f'<td style="padding: 8px; border: 1px solid #ddd;">{totals["p_b"]}</td>'
        html_annual += f'<td style="padding: 8px; border: 1px solid #ddd;">{totals["p_g"]}</td>'
        html_annual += f'<td style="padding: 8px; border: 1px solid #ddd; background-color: #a3e4d7;">{totals["p_t"]}</td>'
        html_annual += '</tr>'

        html_annual += '</table></div>'
        
        st.markdown(html_annual, unsafe_allow_html=True)

        st.divider()

        # ---------------------------------------------------------
        # SECTION 2: Roll Strength (Enrolment Details)
        # ---------------------------------------------------------
        st.markdown("<h3 style='text-align: center; color: #2980b9;'>Roll Strength (Enrolment Details)</h3>", unsafe_allow_html=True)
        st.write("")

        # Helper function to generate 4-digit boxed numbers [0][0][0][0]
        def render_boxed_number(num):
            num_str = f"{int(num):04d}"
            boxes = "".join([f'<span style="display: flex; justify-content: center; align-items: center; width: 24px; height: 32px; border: 2px solid #7f8c8d; background-color: #fff; color: #2c3e50; border-radius: 4px; font-weight: bold; font-family: monospace; font-size: 18px;">{digit}</span>' for digit in num_str])
            return f'<div style="display: flex; justify-content: center; gap: 4px; margin-top: 5px;">{boxes}</div>'

        # --- Data Type 1: Class-wise Dashboard ---
        st.markdown("#### 📌 Class-wise Dashboard")
        
        def map_class_dashboard(c):
            if c in ['CLASS PP', 'CLASS LPP']: return 'Pre Primary'
            if c == 'CLASS I': return 'Class - I'
            if c == 'CLASS II': return 'Class - II'
            if c == 'CLASS III': return 'Class - III'
            if c == 'CLASS IV': return 'Class - IV'
            if c == 'CLASS V': return 'Class - V'
            return None
            
        df_valid['Mapped_Class'] = df_valid['Clean_Class'].apply(map_class_dashboard)
        dash_class_counts = df_valid['Mapped_Class'].value_counts().to_dict()
        dash_order = ['Pre Primary', 'Class - I', 'Class - II', 'Class - III', 'Class - IV', 'Class - V']

        # Row 1
        cols_r1 = st.columns(3)
        for idx, cls_name in enumerate(dash_order[:3]):
            with cols_r1[idx]:
                count = dash_class_counts.get(cls_name, 0)
                st.markdown(f"<div style='text-align:center; padding: 10px; border: 1px solid #ddd; border-radius: 8px; margin-bottom: 10px; background-color: #f4f6f7;'><span style='color:#34495e; font-weight:bold;'>{cls_name}</span><br>{render_boxed_number(count)}</div>", unsafe_allow_html=True)
        
        # Row 2
        cols_r2 = st.columns(3)
        for idx, cls_name in enumerate(dash_order[3:]):
            with cols_r2[idx]:
                count = dash_class_counts.get(cls_name, 0)
                st.markdown(f"<div style='text-align:center; padding: 10px; border: 1px solid #ddd; border-radius: 8px; margin-bottom: 10px; background-color: #f4f6f7;'><span style='color:#34495e; font-weight:bold;'>{cls_name}</span><br>{render_boxed_number(count)}</div>", unsafe_allow_html=True)

        # Row 3 (Total Box)
        st.write("")
        total_valid_students = len(df_valid)
        col_t1, col_t2, col_t3 = st.columns(3)
        with col_t2:
            st.markdown(f"<div style='text-align:center; padding: 10px; border: 2px solid #2980b9; border-radius: 8px; margin-bottom: 10px; background-color: #ebf5fb;'><span style='color:#2980b9; font-weight:bold; font-size: 16px;'>TOTAL STRENGTH</span><br>{render_boxed_number(total_valid_students)}</div>", unsafe_allow_html=True)

        st.write("")

        # --- Data Type 2: Demographic Matrix ---
        st.markdown("#### 📌 Demographic Details")
            
        def get_demo_category(row):
            soc = str(row.get('Social Category', '')).strip().upper()
            rel = str(row.get('Religion', '')).strip().upper()
            
            # Prioritize standard Social Categories
            if 'SC' in soc: return 'SC'
            if 'ST' in soc: return 'ST'
            if 'OBC' in soc: return 'OBC'
            
            # If Religion is Muslim -> Minority
            if 'MUSLIM' in rel or 'ISLAM' in rel: return 'Minority'
            
            # Everything else falls to Others
            return 'Others'

        df_valid['Demo_Category'] = df_valid.apply(get_demo_category, axis=1)

        demo_cats = ['SC', 'ST', 'OBC', 'Minority', 'Others']
        demo_genders = ['Male', 'Female']

        def count_demo(g, c):
            return len(df_valid[(df_valid['Demo_Gender'] == g) & (df_valid['Demo_Category'] == c)])

        html_demo = '<div style="overflow-x:auto;">'
        html_demo += '<table style="width:100%; border-collapse: collapse; text-align: center; font-family: sans-serif; border: 1px solid #ddd; margin-bottom: 20px;">'
        
        # Headers (including Total column)
        html_demo += '<tr style="background-color: #2c3e50; color: white;">'
        html_demo += '<th style="padding: 12px; border: 1px solid #ddd;">Gender &nbsp;⬇️ &nbsp;|&nbsp; Category &nbsp;➡️</th>'
        for c in demo_cats:
            html_demo += f'<th style="padding: 12px; border: 1px solid #ddd;">{c}</th>'
        html_demo += '<th style="padding: 12px; border: 1px solid #ddd; background-color: #1a5276;">Total</th>'
        html_demo += '</tr>'
        
        # Rows (Tracking column totals)
        col_totals = {c: 0 for c in demo_cats}
        for g in demo_genders:
            html_demo += '<tr>'
            html_demo += f'<td style="font-weight: bold; text-align: left; padding: 12px; border: 1px solid #ddd; background-color: #f4f6f7; vertical-align: middle;">{g}</td>'
            row_total = 0
            for c in demo_cats:
                count = count_demo(g, c)
                row_total += count
                col_totals[c] += count
                html_demo += f'<td style="padding: 12px; border: 1px solid #ddd; vertical-align: middle;">{render_boxed_number(count)}</td>'
            
            # Row Total Column
            html_demo += f'<td style="padding: 12px; border: 1px solid #ddd; vertical-align: middle; background-color: #eaeded;">{render_boxed_number(row_total)}</td>'
            html_demo += '</tr>'
            
        # Bottom Total Row
        html_demo += '<tr style="background-color: #d1f2eb;">'
        html_demo += '<td style="font-weight: bold; text-align: left; padding: 12px; border: 1px solid #ddd; color: #0e6251; vertical-align: middle;">Total</td>'
        
        grand_total = 0
        for c in demo_cats:
            count = col_totals[c]
            grand_total += count
            html_demo += f'<td style="padding: 12px; border: 1px solid #ddd; vertical-align: middle;">{render_boxed_number(count)}</td>'
            
        # Grand Total Box
        html_demo += f'<td style="padding: 12px; border: 1px solid #ddd; vertical-align: middle; background-color: #a3e4d7;">{render_boxed_number(grand_total)}</td>'
        html_demo += '</tr>'
            
        html_demo += '</table></div>'
        st.markdown(html_demo, unsafe_allow_html=True)

        st.divider()

        # ---------------------------------------------------------
        # SECTION 3: ছাত্রছাত্রীর বিবরণী (Bengali Details Table)
        # ---------------------------------------------------------
        st.markdown("<h3 style='text-align: center; color: #2980b9;'>ছাত্রছাত্রীর বিবরণী</h3>", unsafe_allow_html=True)
        st.write("")

        def calc_avg_attendance(cls_list):
            if df_attendance.empty: return 0
            
            df_att_clean = df_attendance.copy()
            df_att_clean['Clean_Class'] = df_att_clean.get('Class', '').astype(str).str.strip().str.upper()
            
            mask = df_att_clean['Clean_Class'].isin(cls_list)
            df_filtered = df_att_clean[mask]
            
            if df_filtered.empty: return 0
            
            working_days = df_filtered['Date'].nunique()
            if working_days == 0: return 0
            
            total_present = df_filtered[df_filtered['Status'] == True].shape[0]
            return round(total_present / working_days)

        def count_bengali(cls_list, gender, cat=None, bpl=False):
            mask = df_valid['Clean_Class'].isin(cls_list) & (df_valid['Demo_Gender'] == gender)
            
            if bpl:
                bpl_col = None
                for c in df_valid.columns:
                    if 'BPL' in str(c).upper():
                        bpl_col = c
                        break
                if bpl_col:
                    mask = mask & df_valid[bpl_col].astype(str).str.strip().str.upper().isin(['YES', 'Y', 'TRUE'])
                else:
                    return 0

            if cat == 'GENERAL':
                mask = mask & df_valid['Social Category'].astype(str).str.strip().str.upper().str.contains('GEN')
            elif cat == 'SC':
                mask = mask & (df_valid['Social Category'].astype(str).str.strip().str.upper() == 'SC')
            elif cat == 'OBC':
                mask = mask & df_valid['Social Category'].astype(str).str.strip().str.upper().str.contains('OBC')
            elif cat == 'MINORITY':
                mask = mask & df_valid['Religion'].astype(str).str.strip().str.upper().isin(['MUSLIM', 'ISLAM', 'CHRISTIAN'])
                
            return len(df_valid[mask])

        bengali_rows = [
            ('শিশু শ্রেণি', ['CLASS PP', 'CLASS LPP']),
            ('১ ম', ['CLASS I']),
            ('২ য়', ['CLASS II']),
            ('৩ য়', ['CLASS III']),
            ('৪ র্থ', ['CLASS IV']),
            ('৫ ম', ['CLASS V'])
        ]

        html_bng = '<div style="overflow-x:auto;">'
        html_bng += '<table style="width:100%; border-collapse: collapse; text-align: center; font-family: sans-serif; border: 1px solid #ddd; margin-bottom: 20px;">'
        
        # Headers Row 1
        html_bng += '<tr style="background-color: #2980b9; color: white;">'
        html_bng += '<th rowspan="2" style="padding: 10px; border: 1px solid #ddd; vertical-align: middle;">শ্রেণী</th>'
        html_bng += '<th colspan="3" style="padding: 10px; border: 1px solid #ddd;">মোট ছাত্র ছাত্রী</th>'
        html_bng += '<th rowspan="2" style="padding: 10px; border: 1px solid #ddd; vertical-align: middle;">গড় উপস্থিত</th>'
        html_bng += '<th colspan="2" style="padding: 10px; border: 1px solid #ddd;">সাধারণ</th>'
        html_bng += '<th colspan="2" style="padding: 10px; border: 1px solid #ddd;">B.P.L</th>'
        html_bng += '<th colspan="2" style="padding: 10px; border: 1px solid #ddd;">তপশিলী জাতি</th>'
        html_bng += '<th colspan="2" style="padding: 10px; border: 1px solid #ddd;">ও বি সি</th>'
        html_bng += '<th colspan="2" style="padding: 10px; border: 1px solid #ddd;">সংখ্যা লঘু</th>'
        html_bng += '</tr>'
        
        # Headers Row 2
        html_bng += '<tr style="background-color: #1a5276; color: white;">'
        html_bng += '<th style="padding: 8px; border: 1px solid #ddd;">ছাত্র</th>'
        html_bng += '<th style="padding: 8px; border: 1px solid #ddd;">ছাত্রী</th>'
        html_bng += '<th style="padding: 8px; border: 1px solid #ddd;">মোট</th>'
        
        for _ in range(5):
            html_bng += '<th style="padding: 8px; border: 1px solid #ddd;">ছাত্র</th>'
            html_bng += '<th style="padding: 8px; border: 1px solid #ddd;">ছাত্রী</th>'
        html_bng += '</tr>'
        
        # Initialize Grand Totals
        gt = {
            'tot_b': 0, 'tot_g': 0, 'tot_t': 0, 'att': 0,
            'gen_b': 0, 'gen_g': 0, 'bpl_b': 0, 'bpl_g': 0,
            'sc_b': 0, 'sc_g': 0, 'obc_b': 0, 'obc_g': 0,
            'min_b': 0, 'min_g': 0
        }
        
        for r_name, r_classes in bengali_rows:
            html_bng += '<tr>'
            html_bng += f'<td style="font-weight: bold; text-align: left; padding: 8px; border: 1px solid #ddd; background-color: #f4f6f7;">{r_name}</td>'
            
            # Totals
            b = count_bengali(r_classes, 'Male')
            g = count_bengali(r_classes, 'Female')
            t = b + g
            att = calc_avg_attendance(r_classes)
            
            gt['tot_b'] += b; gt['tot_g'] += g; gt['tot_t'] += t; gt['att'] += att
            
            html_bng += f'<td style="padding: 8px; border: 1px solid #ddd;">{b}</td>'
            html_bng += f'<td style="padding: 8px; border: 1px solid #ddd;">{g}</td>'
            html_bng += f'<td style="padding: 8px; border: 1px solid #ddd; font-weight:bold; background-color: #eaeded;">{t}</td>'
            html_bng += f'<td style="padding: 8px; border: 1px solid #ddd; color: #2980b9; font-weight:bold;">{att}</td>'
            
            # General
            gen_b = count_bengali(r_classes, 'Male', cat='GENERAL')
            gen_g = count_bengali(r_classes, 'Female', cat='GENERAL')
            gt['gen_b'] += gen_b; gt['gen_g'] += gen_g
            html_bng += f'<td style="padding: 8px; border: 1px solid #ddd;">{gen_b}</td><td style="padding: 8px; border: 1px solid #ddd;">{gen_g}</td>'
            
            # BPL
            bpl_b = count_bengali(r_classes, 'Male', bpl=True)
            bpl_g = count_bengali(r_classes, 'Female', bpl=True)
            gt['bpl_b'] += bpl_b; gt['bpl_g'] += bpl_g
            html_bng += f'<td style="padding: 8px; border: 1px solid #ddd;">{bpl_b}</td><td style="padding: 8px; border: 1px solid #ddd;">{bpl_g}</td>'
            
            # SC
            sc_b = count_bengali(r_classes, 'Male', cat='SC')
            sc_g = count_bengali(r_classes, 'Female', cat='SC')
            gt['sc_b'] += sc_b; gt['sc_g'] += sc_g
            html_bng += f'<td style="padding: 8px; border: 1px solid #ddd;">{sc_b}</td><td style="padding: 8px; border: 1px solid #ddd;">{sc_g}</td>'
            
            # OBC
            obc_b = count_bengali(r_classes, 'Male', cat='OBC')
            obc_g = count_bengali(r_classes, 'Female', cat='OBC')
            gt['obc_b'] += obc_b; gt['obc_g'] += obc_g
            html_bng += f'<td style="padding: 8px; border: 1px solid #ddd;">{obc_b}</td><td style="padding: 8px; border: 1px solid #ddd;">{obc_g}</td>'
            
            # Minority
            min_b = count_bengali(r_classes, 'Male', cat='MINORITY')
            min_g = count_bengali(r_classes, 'Female', cat='MINORITY')
            gt['min_b'] += min_b; gt['min_g'] += min_g
            html_bng += f'<td style="padding: 8px; border: 1px solid #ddd;">{min_b}</td><td style="padding: 8px; border: 1px solid #ddd;">{min_g}</td>'
            
            html_bng += '</tr>'
            
        # Final Total Row
        html_bng += '<tr style="background-color: #d1f2eb; font-weight: bold; color: #0e6251;">'
        html_bng += '<td style="text-align: left; padding: 8px; border: 1px solid #ddd;">মোট</td>'
        
        html_bng += f'<td style="padding: 8px; border: 1px solid #ddd;">{gt["tot_b"]}</td>'
        html_bng += f'<td style="padding: 8px; border: 1px solid #ddd;">{gt["tot_g"]}</td>'
        html_bng += f'<td style="padding: 8px; border: 1px solid #ddd; background-color: #a3e4d7;">{gt["tot_t"]}</td>'
        html_bng += f'<td style="padding: 8px; border: 1px solid #ddd;">{gt["att"]}</td>'
        
        html_bng += f'<td style="padding: 8px; border: 1px solid #ddd;">{gt["gen_b"]}</td><td style="padding: 8px; border: 1px solid #ddd;">{gt["gen_g"]}</td>'
        html_bng += f'<td style="padding: 8px; border: 1px solid #ddd;">{gt["bpl_b"]}</td><td style="padding: 8px; border: 1px solid #ddd;">{gt["bpl_g"]}</td>'
        html_bng += f'<td style="padding: 8px; border: 1px solid #ddd;">{gt["sc_b"]}</td><td style="padding: 8px; border: 1px solid #ddd;">{gt["sc_g"]}</td>'
        html_bng += f'<td style="padding: 8px; border: 1px solid #ddd;">{gt["obc_b"]}</td><td style="padding: 8px; border: 1px solid #ddd;">{gt["obc_g"]}</td>'
        html_bng += f'<td style="padding: 8px; border: 1px solid #ddd;">{gt["min_b"]}</td><td style="padding: 8px; border: 1px solid #ddd;">{gt["min_g"]}</td>'
        
        html_bng += '</tr>'
        html_bng += '</table></div>'
        
        st.markdown(html_bng, unsafe_allow_html=True)

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
