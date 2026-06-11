# ==========================================
# TAB 1: APPLY FOR LEAVE
# ==========================================
with tab1:
    st.subheader("Create a New Leave Application")
    col1, col2 = st.columns(2)
    
    with col1:
        applicant_name = st.selectbox("Select Teacher Name", TEACHER_LIST)
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

    # Because this is no longer trapped in a form, this will calculate in real-time!
    calculated_days = (end_date - start_date).days + 1
    
    if calculated_days < 1:
        st.error("⚠️ 'To Date' cannot be before 'From Date'.")
        calculated_days = 0
    else:
        st.info(f"📅 Total Leave Duration: {calculated_days} days")

    # Changed from st.form_submit_button to st.button
    submitted_leave = st.button("Generate Leave Application & Log to DB", type="primary")

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
