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
    # Define scopes for Google Sheets and Drive
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    return client

def load_data():
    client = get_gspread_client()
    # Open the database and get the specific sheet
    sheet = client.open("BPS_Database").worksheet("students_master")
    # Fetch all data and convert to Pandas DataFrame
    records = sheet.get_all_records()
    return pd.DataFrame(records)

# Initialize Data in Session State
if 'df' not in st.session_state:
    try:
        st.session_state.df = load_data()
    except Exception as e:
        st.error(f"Failed to connect to BPS_Database: {e}")
        st.stop()

# --- 3. SIDEBAR NAVIGATION ---
st.sidebar.title("🏫 BPS Admission Hub")
menu = st.sidebar.radio("Navigate", ["Data Analytics", "New Admission", "System Settings"])

# --- 4. DATA ANALYTICS TAB ---
if menu == "Data Analytics":
    st.title("📊 Student Population Analytics")
    df = st.session_state.df
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Students", len(df))
    col2.metric("Boys", len(df[df['Gender'].str.upper() == 'BOYS']))
    col3.metric("Girls", len(df[df['Gender'].str.upper() == 'GIRLS']))

    st.subheader("Enrollment by Class")
    
    # Updated to 'CLASS LPP'
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
            
            # Updated to 'CLASS LPP'
            cls = st.selectbox("Class", ["CLASS LPP", "CLASS PP", "CLASS I", "CLASS II", "CLASS III", "CLASS IV", "CLASS V"])
            sec = st.selectbox("Section", ["A", "B", "C"])
            roll = st.number_input("Roll Number", min_value=1, step=1)
            
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
                student_code = f"BPS{datetime.now().year}{roll:03d}"
                
                # Create a list exactly matching the columns in your students_master.csv
                row_to_append = [
                    new_sl, name, gender, cls, sec, roll, father, mother, 
                    dob.strftime("%Y-%m-%d"), blood, mobile, student_code,
                    "GENERAL", "", "", "" 
                ]
                
                with st.spinner("Saving to BPS_Database..."):
                    try:
                        client = get_gspread_client()
                        sheet = client.open("BPS_Database").worksheet("students_master")
                        
                        # Append the list directly to the bottom of the Google Sheet
                        sheet.append_row(row_to_append)
                        
                        st.success(f"✅ Successfully admitted {name} to {cls} {sec}!")
                        
                        # Refresh the cached data
                        st.session_state.df = load_data() 
                    except Exception as e:
                        st.error(f"Failed to save student: {e}")
            else:
                st.error("⚠️ Please fill in at least the Student Name and Mobile Number.")

# --- 6. SYSTEM SETTINGS ---
elif menu == "System Settings":
    st.title("⚙️ System Settings & Data Explorer")
    st.subheader("Class Configuration")
    
    # Updated text description
    st.info("**CLASS LPP (Lower Pre Primary) Section A** is currently active and available in the Admission portal.")
    
    st.divider()
    
    st.subheader("Raw Master Data Explorer")
    selected_class = st.multiselect("Filter by Class", options=st.session_state.df['Class'].unique(), default=st.session_state.df['Class'].unique())
    filtered_df = st.session_state.df[st.session_state.df['Class'].isin(selected_class)]
    
    st.dataframe(filtered_df, use_container_width=True)
