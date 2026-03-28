import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="BPS Exam Fee Collector", layout="centered")

st.title("💰 BPS Exam Fee Collection")
st.markdown("Record examination fees for students at Bhagyabantapur Primary School.")

# --- CONNECTIONS ---
# Connection to the main BPS Database
conn_bps = st.connection("gsheets", type=GSheetsConnection)

# Connection to the Exam Fees Log Sheet
# Ensure you have a second entry in your secrets for this specific sheet URL
conn_fees = st.connection("exam_fees", type=GSheetsConnection)

# --- DATA LOADING ---
@st.cache_data(ttl=600)
def load_data():
    students = conn_bps.read(worksheet="students_master")
    teachers = conn_bps.read(worksheet="TEACHERS_DETAIL")
    return students, teachers

df_students, df_teachers = load_data()

# --- FORM UI ---
with st.form("fee_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    
    with col1:
        selected_class = st.selectbox("Select Class", options=sorted(df_students['Class'].unique()))
        
    with col2:
        sections = df_students[df_students['Class'] == selected_class]['Section'].unique()
        selected_section = st.selectbox("Select Section", options=sections)

    # Filter students based on Class and Section
    filtered_students = df_students[
        (df_students['Class'] == selected_class) & 
        (df_students['Section'] == selected_section)
    ]
    
    student_names = filtered_students['Name'].tolist()
    selected_student = st.selectbox("Select Student", options=student_names)
    
    # Get specific details for the log
    student_info = filtered_students[filtered_students['Name'] == selected_student].iloc[0]
    
    amount = st.number_input("Payment Amount (₹)", min_value=0, step=5)
    
    payer_type = st.radio("Received From:", ["Student", "Guardian", "Teacher"], horizontal=True)
    
    received_by_teacher = None
    if payer_type == "Teacher":
        received_by_teacher = st.selectbox("Which Teacher?", options=df_teachers['Name'].unique())

    submit_button = st.form_submit_button("Record Payment")

# --- DATA SUBMISSION ---
if submit_button:
    new_entry = pd.DataFrame([{
        "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Student_Code": student_info['Student Code'],
        "Name": selected_student,
        "Class": selected_class,
        "Section": selected_section,
        "Roll": student_info['Roll'],
        "Amount": amount,
        "Payer_Type": payer_type,
        "Teacher_Involved": received_by_teacher if payer_type == "Teacher" else "N/A"
    }])
    
    # Append to the SCH_Exam_Fees sheet
    existing_fees = conn_fees.read(worksheet="Sheet1") # Adjust worksheet name if needed
    updated_fees = pd.concat([existing_fees, new_entry], ignore_index=True)
    
    conn_fees.update(worksheet="Sheet1", data=updated_fees)
    
    st.success(f"Successfully recorded ₹{amount} for {selected_student}!")
    st.balloons()