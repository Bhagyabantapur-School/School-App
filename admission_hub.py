import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- 1. CONFIG & SECURITY ---
st.set_page_config(page_title="BPS Admission Hub", layout="wide")

st.markdown(f"""
    <style>
    .stApp {{ background-color: #f0f2f6; }}
    [data-testid="stAppViewContainer"]::before {{
        content: "BPS ADMISSION - CONFIDENTIAL";
        position: fixed; top: 50%; left: 50%;
        transform: translate(-50%, -50%) rotate(-45deg);
        font-size: 60px; color: rgba(0,0,0,0.03);
        pointer-events: none; z-index: 1000;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATABASE CONNECTION ---
@st.cache_resource
def get_gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    return client

def load_data():
    client = get_gspread_client()
    sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID_HERE/edit").worksheet("students_master") # Remember to put your URL here if you used the conflict fix!
    
    records = sheet.get_all_records()
    df = pd.DataFrame(records)
    
    if 'Student Code' in df.columns:
        df['Student Code'] = df['Student Code'].astype(str).str.zfill(14)
        
    if 'Roll' in df.columns:
        df['Roll'] = pd.to_numeric(df['Roll'], errors='coerce').fillna(0).astype(int)
        
    return df

if 'df' not in st.session_state:
    with st.spinner("Connecting to BPS Database..."):
        try:
            st.session_state.df = load_data()
        except Exception as e:
            st.error(f"Failed to connect to BPS_Database: {e}")
            st.stop()

# --- 3. SIDEBAR NAVIGATION ---
st.sidebar.title("🏫 BPS Admission Hub")

if st.sidebar.button("🔄 Sync Live Database"):
    with st.spinner("Fetching latest data..."):
        st.session_state.df = load_data()
    st.sidebar.success("Data synced successfully!")

menu = st.sidebar.radio("Navigate", ["Data Analytics", "New Admission", "Student Transfer", "System Settings"])

# --- 4. DATA ANALYTICS TAB ---
if menu == "Data Analytics":
    st.title("📊 Student Population Analytics")
    df = st.session_state.df
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Students", len(df))
    col2.metric("Boys", len(df[df['Gender'].str.upper() == 'BOYS']))
    col3.metric("Girls", len(df[df['Gender'].str.upper() == 'GIRLS']))

    st.subheader("Enrollment by Class")
    class_order = ['CLASS LPP', 'CLASS PP', 'CLASS I', 'CLASS II', 'CLASS III', 'CLASS IV', 'CLASS V']
    
    fig = px.histogram(df, x="Class", color="Gender", barmode='group', 
                       category_orders={"Class": class_order},
                       color_discrete_map={'BOYS': '#1f77b4', 'GIRLS': '#e377c2'},
                       text_auto=True)
    st.plotly_chart(fig, use_container_width=True)

# --- 5. NEW ADMISSION (ADD STUDENT) ---
elif menu == "New Admission":
    st.title("📝 New Student Admission")
    
    with st.form("admission_form", clear_on_submit=True):
        st.subheader("Student Details")
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Student Name").upper()
            gender = st.selectbox("Gender", ["BOYS", "GIRLS"])
            cls = st.selectbox("Class", ["CLASS LPP", "CLASS PP", "CLASS I", "CLASS II", "CLASS III", "CLASS IV", "CLASS V"])
            sec = st.selectbox("Section", ["A", "B", "C"])
            roll = st.number_input("Roll Number", min_value=1, step=1)
            # NEW: Admission Date field
            admission_date = st.date_input("Admission Date", datetime.today())
            
        with col2:
            father = st.text_input("Father's Name").upper()
            mother = st.text_input("Mother's Name").upper()
            dob = st.date_input("Date of Birth", min_value=datetime(2010, 1, 1), max_value=datetime.today())
            mobile = st.text_input("Mobile Number")
            blood = st.selectbox("Blood Group", ["", "A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"])

        submitted = st.form_submit_button("Confirm Admission")
        
        if submitted:
            if name and mobile:
                new_sl = len(st.session_state.df) + 1
                student_code = f"BPS{datetime.now().year}{roll:03d}".zfill(14) 
                
                # UPDATED: Now includes Admission Date at the very end (18th column)
                row_to_append = [
                    new_sl, name, gender, cls, sec, roll, father, mother, 
                    dob.strftime("%Y-%m-%d"), blood, mobile, student_code,
                    "GENERAL", "", "", "", "", admission_date.strftime("%Y-%m-%d")
                ]
                
                with st.spinner("Saving to BPS_Database..."):
                    try:
                        client = get_gspread_client()
                        # Use your URL here if you applied the conflict fix earlier!
                        sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID_HERE/edit").worksheet("students_master")
                        sheet.append_row(row_to_append)
                        st.success(f"✅ Successfully admitted {name} to {cls} {sec}!")
                        
                        st.session_state.df = load_data() 
                    except Exception as e:
                        st.error(f"Failed to save student: {e}")
            else:
                st.error("⚠️ Please fill in at least the Student Name and Mobile Number.")

# --- 6. STUDENT TRANSFER (TRANSFER OUT) ---
elif menu == "Student Transfer":
    st.title("📤 Transfer Out Student")
    st.write("Remove a student from the active roster and archive them in the Transfer History log.")
    
    df = st.session_state.df
    
    col1, col2 = st.columns(2)
    with col1:
        transfer_class = st.selectbox("Filter by Class", sorted(df['Class'].unique()))
        filtered_df = df[df['Class'] == transfer_class]
    
    with col2:
        student_display_list = filtered_df['Student Code'].astype(str) + " - " + filtered_df['Name']
        selected_student_str = st.selectbox("Select Student to Transfer", student_display_list)
    
    st.divider()
    
    if selected_student_str:
        target_code = selected_student_str.split(" - ")[0]
        student_data = filtered_df[filtered_df['Student Code'].astype(str) == target_code].iloc[0]
        
        st.subheader("Confirm Student Details")
        st.write(f"**Name:** {student_data['Name']} | **Father:** {student_data['Father']} | **Roll:** {student_data['Roll']} | **Code:** {target_code}")
        
        t_col1, t_col2 = st.columns(2)
        with t_col1:
            transfer_reason = st.selectbox(
                "Reason for Transfer", 
                ["Passed Out", "Change School", "Change Residence", "Other"]
            )
        with t_col2:
            transfer_date = st.date_input("Transfer Date", datetime.today())
            
        st.warning("⚠️ This action will remove the student from the live system and move them to the history tab.")
        
        if st.button("Confirm Transfer Out", type="primary"):
            with st.spinner("Processing Transfer..."):
                try:
                    client = get_gspread_client()
                    # Use your URL here if you applied the conflict fix earlier!
                    db = client.open_by_url("https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID_HERE/edit")
                    master_sheet = db.worksheet("students_master")
                    
                    try:
                        history_sheet = db.worksheet("transfer_history")
                    except gspread.exceptions.WorksheetNotFound:
                        history_sheet = db.add_worksheet(title="transfer_history", rows="1000", cols="20")
                        headers = master_sheet.row_values(1)
                        headers.extend(["Transfer Date", "Transfer Reason"])
                        history_sheet.append_row(headers)
                    
                    cell = master_sheet.find(target_code)
                    
                    if cell:
                        row_num = cell.row
                        
                        row_data = master_sheet.row_values(row_num)
                        
                        # UPDATED: We now pad up to 18 columns to account for the new Admission Date
                        while len(row_data) < 18:
                            row_data.append("")
                            
                        row_data.extend([transfer_date.strftime("%Y-%m-%d"), transfer_reason])
                        
                        history_sheet.append_row(row_data)
                        master_sheet.delete_rows(row_num)
                        
                        st.success(f"✅ Successfully transferred out {student_data['Name']}!")
                        
                        st.session_state.df = load_data()
                        st.rerun() 
                    else:
                        st.error("❌ Could not locate the student code in the live database. Try clicking 'Sync Live Database' in the sidebar first.")
                except Exception as e:
                    st.error(f"Transfer failed: {e}")

# --- 7. SYSTEM SETTINGS ---
elif menu == "System Settings":
    st.title("⚙️ System Settings & Data Explorer")
    st.subheader("Class Configuration")
    st.info("**CLASS LPP (Lower Pre Primary) Section A** is currently active and available in the Admission portal.")
    st.divider()
    
    st.subheader("Raw Master Data Explorer")
    selected_class = st.multiselect("Filter by Class", options=st.session_state.df['Class'].unique(), default=st.session_state.df['Class'].unique())
    filtered_df = st.session_state.df[st.session_state.df['Class'].isin(selected_class)]
    
    st.dataframe(filtered_df, use_container_width=True)
