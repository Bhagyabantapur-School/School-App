import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import pytz
import plotly.express as px
from fpdf import FPDF # For generating PDF receipts

st.set_page_config(page_title="BPS Exam Fee Collector", layout="wide")

# Set timezone to IST for accurate logging in West Bengal
IST = pytz.timezone('Asia/Kolkata')

st.title("💰 BPS Exam Fee Collection")

# --- CONNECTIONS ---
conn_bps = st.connection("gsheets", type=GSheetsConnection)
conn_fees = st.connection("exam_fees", type=GSheetsConnection)

# --- DATA LOADING ---
@st.cache_data(ttl=600)
def load_data():
    students = conn_bps.read(worksheet="students_master")
    teachers = conn_bps.read(worksheet="TEACHERS_DETAIL")
    fees_log = conn_fees.read(worksheet="Sheet1") # Read existing fees for dashboard
    return students, teachers, fees_log

df_students, df_teachers, df_fees = load_data()

# --- APP LAYOUT (Tabs for Entry and Dashboard) ---
tab1, tab2 = st.tabs(["📝 Collect Fees", "📊 Fee Dashboard"])

with tab1:
    st.subheader("Record New Payment")
    
    # Optional: Placeholder for QR Scanner integration
    # st.info("QR Scanner can be added here to auto-fill student details!")

    with st.form("fee_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            selected_class = st.selectbox("Select Class", options=sorted(df_students['Class'].dropna().unique()))
        with col2:
            sections = df_students[df_students['Class'] == selected_class]['Section'].dropna().unique()
            selected_section = st.selectbox("Select Section", options=sections)
        with col3:
            filtered_students = df_students[
                (df_students['Class'] == selected_class) & 
                (df_students['Section'] == selected_section)
            ]
            student_names = filtered_students['Name'].dropna().tolist()
            selected_student = st.selectbox("Select Student", options=student_names)
        
        col4, col5 = st.columns(2)
        with col4:
            amount = st.number_input("Payment Amount (₹)", min_value=0, step=5)
        with col5:
            payer_type = st.radio("Received From:", ["Student", "Guardian", "Teacher"], horizontal=True)
        
        received_by_teacher = "N/A"
        if payer_type == "Teacher":
            received_by_teacher = st.selectbox("Which Teacher?", options=df_teachers['Name'].dropna().unique())

        submit_button = st.form_submit_button("Record Payment")

    # --- DATA SUBMISSION ---
    if submit_button:
        # Get exact IST time
        current_time_ist = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
        student_info = filtered_students[filtered_students['Name'] == selected_student].iloc[0]
        
        new_entry = pd.DataFrame([{
            "Date": current_time_ist,
            "Student_Code": student_info.get('Student Code', 'N/A'),
            "Name": selected_student,
            "Class": selected_class,
            "Section": selected_section,
            "Roll": student_info.get('Roll', 'N/A'),
            "Amount": amount,
            "Payer_Type": payer_type,
            "Teacher_Involved": received_by_teacher
        }])
        
        # Update Google Sheet
        updated_fees = pd.concat([df_fees, new_entry], ignore_index=True)
        conn_fees.update(worksheet="Sheet1", data=updated_fees)
        
        st.success(f"Successfully recorded ₹{amount} for {selected_student} at {current_time_ist}!")
        
        # --- PDF RECEIPT GENERATION LOGIC ---
        # You can build out the FPDF logic here to create a downloadable receipt
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="Bhagyabantapur Primary School - Fee Receipt", ln=1, align='C')
        pdf.cell(200, 10, txt=f"Student: {selected_student} | Class: {selected_class} | Amount: Rs. {amount}", ln=2, align='L')
        
        # Save to a temporary file and provide a download button
        pdf_output = pdf.output(dest='S').encode('latin-1')
        st.download_button(
            label="📄 Download PDF Receipt",
            data=pdf_output,
            file_name=f"receipt_{selected_student}.pdf",
            mime="application/pdf"
        )

with tab2:
    st.subheader("Collection Dashboard")
    if not df_fees.empty and 'Amount' in df_fees.columns:
        # Clean data slightly for plotting
        df_fees['Amount'] = pd.to_numeric(df_fees['Amount'], errors='coerce').fillna(0)
        
        # Plot total collection per class
        class_totals = df_fees.groupby('Class')['Amount'].sum().reset_index()
        fig = px.bar(class_totals, x='Class', y='Amount', title="Total Fees Collected per Class", text_auto=True)
        st.plotly_chart(fig, use_container_width=True)
        
        st.metric(label="Total Fees Collected Overall", value=f"₹ {df_fees['Amount'].sum()}")
    else:
        st.info("No fee data available yet to display on the dashboard.")
