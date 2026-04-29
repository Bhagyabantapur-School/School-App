import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import date, timedelta, datetime
from fpdf import FPDF
import pandas as pd
import tempfile
import os

# Page Config
st.set_page_config(page_title="Leave App - BPS Digital", layout="wide")

st.title("📝 BPS Leave & Joining Management")
st.markdown("Manage leave applications, generate joining letters, and track statuses.")
st.divider()

# Teacher List
TEACHER_LIST = [
    "SUKHAMAY KISKU", "UDAY NARAYAN JANA", "SUSMITA PAUL", 
    "TAPASI RANA", "BIMAL KUMAR PATRA", "SUJATA BISWAS ROTHA", 
    "TAPAN KUMAR MANDAL", "ROHINI SINGH", "MANJUMA KHATUN"
]

# --- GOOGLE SHEETS AUTHENTICATION ---
@st.cache_resource
def get_gspread_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(credentials)

try:
    client = get_gspread_client()
    doc = client.open("Leaves")
    try:
        sheet = doc.worksheet("Leaves")
    except gspread.exceptions.WorksheetNotFound:
        sheet = doc.sheet1
    
    # Fetch all data to process logs and pending letters
    all_data = sheet.get_all_values()
except Exception as e:
    st.error(f"⚠️ Could not connect to Google Sheets: {e}")
    all_data = []

# --- PDF GENERATION FUNCTIONS ---
def create_leave_pdf(name, desig, l_type, n_days, start, end, rsn, app_dt):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_margins(20, 20, 20)
    pdf.set_font("Arial", size=12)
    
    pdf.cell(0, 6, txt="To,", ln=1)
    pdf.cell(0, 6, txt="The Chairman,", ln=1)
    pdf.cell(0, 6, txt="Purba Medinipur District Primary School Council,", ln=1)
    pdf.cell(0, 6, txt="P.O. Tamluk, Dist - Purba Medinipur", ln=1)
    pdf.ln(6)
    pdf.cell(0, 6, txt="Through The Proper Channel.", ln=1)
    pdf.ln(6)
    
    pdf.set_font("Arial", style='B', size=12)
    pdf.cell(0, 6, txt=f"Subject: Prayer for {l_type} for {n_days} days.", ln=1, align='C')
    pdf.set_font("Arial", size=12)
    pdf.ln(6)
    
    pdf.cell(0, 6, txt="Respected Sir/Madam,", ln=1)
    pdf.ln(4)
    indent = "        "
    
    body1 = (f"{indent}Most respectfully I beg to state that I am {name}, {desig} of "
             f"Bhagyabantapur Primary School, Vill:- Bhagyabantapur, P.O.- Khanjanchak.")
    pdf.multi_cell(0, 6, txt=body1)
    pdf.ln(2)
    body2 = f"{indent}I could not attend school on & from {start} to {end} on account of my {rsn}."
    pdf.multi_cell(0, 6, txt=body2)
    pdf.ln(2)
    body3 = f"{indent}I request you to grant my {l_type} for those days and consider my prayer to sanction leave and oblige."
    pdf.multi_cell(0, 6, txt=body3)
    pdf.ln(6)
    pdf.cell(0, 6, txt=f"{indent}Expecting your kind-hearted co-operation.", ln=1)
    pdf.ln(4)
    pdf.cell(0, 6, txt=f"{indent}Thanking you.", ln=1)
    pdf.ln(15)
    
    y_pos = pdf.get_y()
    pdf.set_xy(20, y_pos)
    pdf.cell(60, 6, txt="Place: Bhagyabantapur")
    pdf.set_xy(20, y_pos + 6)
    pdf.cell(60, 6, txt=f"Date: {app_dt}")
    
    sig_x = 115
    sig_w = 75
    pdf.set_xy(sig_x, y_pos)
    pdf.cell(sig_w, 6, txt="Yours Faithfully,", ln=1, align='C')
    pdf.set_xy(sig_x, y_pos + 25)
    pdf.cell(sig_w, 6, txt=f"{name}", ln=1, align='C')
    pdf.set_x(sig_x)
    pdf.cell(sig_w, 6, txt=f"{desig}", ln=1, align='C')
    pdf.set_x(sig_x)
    pdf.cell(sig_w, 6, txt="Bhagyabantapur Primary School", ln=1, align='C')
    pdf.set_x(sig_x)
    pdf.cell(sig_w, 6, txt="Vill:- Bhagyabantapur, P.O.- Khanjanchak", ln=1, align='C')
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf.output(tmp.name)
        with open(tmp.name, "rb") as f:
            return f.read()

def create_joining_pdf(name, desig, l_type, n_days, start, end, rsn, j_date):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_margins(20, 20, 20)
    pdf.set_font("Arial", size=12)
    
    pdf.cell(0, 6, txt="To,", ln=1)
    pdf.cell(0, 6, txt="The Chairman,", ln=1)
    pdf.cell(0, 6, txt="Purba Medinipur District Primary School Council,", ln=1)
    pdf.cell(0, 6, txt="P.O. Tamluk, Dist - Purba Medinipur", ln=1)
    pdf.ln(6)
    pdf.cell(0, 6, txt="Through The Proper Channel.", ln=1)
    pdf.ln(6)
    
    pdf.set_font("Arial", style='B', size=12)
    pdf.cell(0, 6, txt=f"Subject: Joining Report after availing {l_type} for {n_days} days.", ln=1, align='C')
    pdf.set_font("Arial", size=12)
    pdf.ln(6)
    
    pdf.cell(0, 6, txt="Respected Sir/Madam,", ln=1)
    pdf.ln(4)
    indent = "        "
    
    body1 = (f"{indent}With due respect, I beg to state that I am {name}, {desig} of "
             f"Bhagyabantapur Primary School, Vill:- Bhagyabantapur, P.O.- Khanjanchak.")
    pdf.multi_cell(0, 6, txt=body1)
    pdf.ln(2)
    body2 = f"{indent}I was absent from school duties on account of my {rsn}. I availed {l_type} for {n_days} days on & from {start} to {end}."
    pdf.multi_cell(0, 6, txt=body2)
    pdf.ln(2)
    body3 = f"{indent}I am now reporting for my regular duties today, {j_date}, in the forenoon at the scheduled time."
    pdf.multi_cell(0, 6, txt=body3)
    pdf.ln(2)
    body4 = f"{indent}I request you to kindly accept my joining report and oblige."
    pdf.multi_cell(0, 6, txt=body4)
    pdf.ln(6)
    pdf.cell(0, 6, txt=f"{indent}Thanking you.", ln=1)
    pdf.ln(15)
    
    y_pos = pdf.get_y()
    pdf.set_xy(20, y_pos)
    pdf.cell(60, 6, txt="Place: Bhagyabantapur")
    pdf.set_xy(20, y_pos + 6)
    pdf.cell(60, 6, txt=f"Date: {j_date}")
    
    sig_x = 115
    sig_w = 75
    pdf.set_xy(sig_x, y_pos)
    pdf.cell(sig_w, 6, txt="Yours Faithfully,", ln=1, align='C')
    pdf.set_xy(sig_x, y_pos + 25)
    pdf.cell(sig_w, 6, txt=f"{name}", ln=1, align='C')
    pdf.set_x(sig_x)
    pdf.cell(sig_w, 6, txt=f"{desig}", ln=1, align='C')
    pdf.set_x(sig_x)
    pdf.cell(sig_w, 6, txt="Bhagyabantapur Primary School", ln=1, align='C')
    pdf.set_x(sig_x)
    pdf.cell(sig_w, 6, txt="Vill:- Bhagyabantapur, P.O.- Khanjanchak", ln=1, align='C')
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf.output(tmp.name)
        with open(tmp.name, "rb") as f:
            return f.read()

# --- TABS SETUP ---
tab1, tab2, tab3 = st.tabs(["📝 1. Apply for Leave", "🔄 2. Generate Joining Letters", "📊 3. Leave Log & Status"])

# ==========================================
# TAB 1: APPLY FOR LEAVE
# ==========================================
with tab1:
    with st.form("leave_form"):
        st.subheader("Create a New Leave Application")
        col1, col2 = st.columns(2)
        
        with col1:
            applicant_name = st.selectbox("Select Teacher Name", TEACHER_LIST)
            # Removed the Designation dropdown here
            leave_type = st.selectbox("Type of Leave", ["Casual Leave", "Medical Leave", "Commuted Leave"])
            app_date = st.date_input("Date of Leave Application", value=date.today())
            
        with col2:
            start_date = st.date_input("From Date")
            end_date = st.date_input("To Date")
            reason_type = st.selectbox("Reason", ["Personal Affairs", "Medical Affairs", "Other"])
            if reason_type == "Other":
                reason = st.text_input("Specify Reason")
            else:
                reason = reason_type
                
            joining_status = st.radio("Do you need a Joining Letter for this leave?", 
                                      ["Yes, keep it pending", "No, joining letter not required"])

        calculated_days = (end_date - start_date).days + 1
        
        if calculated_days < 1:
            st.error("⚠️ 'To Date' cannot be before 'From Date'.")
            calculated_days = 0
        else:
            st.info(f"📅 Total Leave Duration: {calculated_days} days")

        submitted_leave = st.form_submit_button("Generate Leave Application & Log to DB", type="primary")

    if submitted_leave and calculated_days > 0:
        # --- AUTO-DETECT DESIGNATION ---
        designation = "H.T" if applicant_name == "SUKHAMAY KISKU" else "A.T"
        
        status_val = "Pending" if "Yes" in joining_status else "Not Required"
        
        row_to_insert = [
            app_date.strftime("%d-%m-%Y"), applicant_name, leave_type, calculated_days,
            start_date.strftime("%d-%m-%Y"), end_date.strftime("%d-%m-%Y"), reason,
            designation, status_val
        ]
        
        try:
            sheet.append_row(row_to_insert)
            st.success("📊 Data successfully logged to Google Sheets.")
            
            leave_pdf = create_leave_pdf(applicant_name, designation, leave_type, calculated_days, 
                                         start_date.strftime("%d-%m-%Y"), end_date.strftime("%d-%m-%Y"), 
                                         reason, app_date.strftime("%d-%m-%Y"))
            
            st.download_button(
                label="📄 Download Leave Application PDF",
                data=leave_pdf,
                file_name=f"Leave_App_{applicant_name.replace(' ', '_')}_{app_date.strftime('%d-%m-%Y')}.pdf",
                mime="application/pdf",
                type="primary"
            )
        except Exception as e:
            st.error(f"⚠️ Failed to log to Google Sheets: {e}")

# ==========================================
# TAB 2: GENERATE JOINING LETTERS
# ==========================================
with tab2:
    st.subheader("Generate & Print Joining Letters")
    
    if len(all_data) > 1:
        view_filter = st.radio("Filter Leaves:", ["Show Pending Only", "Show All Leaves (Includes Not Required / Printed)"], horizontal=True)
        
        available_leaves = []
        
        for i, row in enumerate(all_data[1:], start=2): 
            while len(row) < 9:
                row.append("")
                
            status = row[8] if row[8] else "Legacy/Unknown"
            
            if view_filter == "Show Pending Only" and status != "Pending":
                continue
                
            label = f"{row[1]} - {row[2]} ({row[4]} to {row[5]}) | Status: {status}"
            
            available_leaves.append({
                "label": label,
                "row_index": i, "app_date": row[0], "teacher": row[1], "leave_type": row[2],
                "days": row[3], "from_date": row[4], "to_date": row[5], "reason": row[6],
                "designation": row[7] if row[7] else "A.T",
                "current_status": status
            })
        
        if not available_leaves:
            if view_filter == "Show Pending Only":
                st.success("🎉 All caught up! There are no pending joining letters.")
            else:
                st.info("No leave records found.")
        else:
            options = {l["label"]: l for l in available_leaves}
            selected_key = st.selectbox("Select a leave record to generate its Joining Letter:", list(options.keys()))
            selected_leave = options[selected_key]
            
            with st.form("confirm_joining_form"):
                st.write(f"**Confirm Details for {selected_leave['teacher']}**")
                
                try:
                    to_date_obj = datetime.strptime(selected_leave['to_date'], "%d-%m-%Y").date()
                    default_join = to_date_obj + timedelta(days=1)
                except:
                    default_join = date.today()
                    
                j_date = st.date_input("Select the Actual Joining Date", value=default_join)
                
                submit_join = st.form_submit_button("Generate Joining Letter & Mark as Printed", type="primary")
            
            if submit_join:
                join_pdf = create_joining_pdf(
                    selected_leave['teacher'], selected_leave['designation'], selected_leave['leave_type'],
                    selected_leave['days'], selected_leave['from_date'], selected_leave['to_date'],
                    selected_leave['reason'], j_date.strftime("%d-%m-%Y")
                )
                
                try:
                    sheet.update_cell(selected_leave['row_index'], 9, "Printed")
                    st.success(f"✅ Status successfully updated to 'Printed' in the database.")
                    
                    st.download_button(
                        label="📝 Download Joining Letter PDF",
                        data=join_pdf,
                        file_name=f"Joining_Letter_{selected_leave['teacher'].replace(' ', '_')}_{j_date.strftime('%d-%m-%Y')}.pdf",
                        mime="application/pdf",
                        type="primary"
                    )
                    st.info("🔄 Please refresh the page after downloading to update the list views.")
                except Exception as e:
                    st.error(f"⚠️ Failed to update Google Sheet: {e}")
    else:
        st.info("No leave data found in the Google Sheet yet.")

# ==========================================
# TAB 3: LEAVE LOG & STATUS
# ==========================================
with tab3:
    st.subheader("Database Log & Letter Status")
    
    if len(all_data) > 1:
        display_data = []
        for row in all_data[1:]:
            while len(row) < 9:
                row.append("")
            
            if row[8] == "":
                row[8] = "Legacy/Unknown"
                
            display_data.append({
                "App Date": row[0], "Teacher": row[1], "Leave Type": row[2], 
                "Days": row[3], "From": row[4], "To": row[5], "Reason": row[6],
                "Joining Status": row[8]
            })
            
        df = pd.DataFrame(display_data)
        
        def color_status(val):
            color = 'green' if val == 'Printed' else 'orange' if val == 'Pending' else 'gray'
            return f'color: {color}'
        
        st.dataframe(df.style.map(color_status, subset=['Joining Status']), use_container_width=True)
    else:
        st.info("The database is currently empty.")
