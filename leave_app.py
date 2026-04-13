import streamlit as st
from datetime import date

# Set page configuration
st.set_page_config(page_title="Leave Application Generator", layout="centered")

st.title("📝 Leave Application Generator")
st.markdown("Generate a formal leave application for **Purba Medinipur DPSC**.")
st.divider()

# Application Form
with st.form("leave_form"):
    col1, col2 = st.columns(2)
    
    with col1:
        applicant_name = st.text_input("Applicant Name", placeholder="e.g., Sukhamay Kisku")
        designation = st.selectbox("Designation", ["A.T", "H.T"])
        leave_type = st.selectbox("Type of Leave", ["Casual Leave", "Medical Leave", "Commuted Leave"])
        num_days = st.number_input("Number of Days", min_value=1, step=1)
        
    with col2:
        start_date = st.date_input("From Date")
        end_date = st.date_input("To Date")
        reason_type = st.selectbox("Reason", ["Personal Affairs", "Medical Affairs", "Other"])
        
        # Allow custom reason if "Other" is selected
        if reason_type == "Other":
            reason = st.text_input("Specify Reason", placeholder="Enter specific reason...")
        else:
            reason = reason_type
            
        app_date = st.date_input("Date of Application", default=date.today())

    # Submit button
    submitted = st.form_submit_button("Generate Letter", type="primary")

# Generate and Display Letter
if submitted:
    if not applicant_name.strip():
        st.error("⚠️ Please enter the Applicant Name to generate the letter.")
    else:
        # Format dates to standard DD-MM-YYYY
        start_str = start_date.strftime("%d-%m-%Y")
        end_str = end_date.strftime("%d-%m-%Y")
        app_str = app_date.strftime("%d-%m-%Y")
        
        # Construct the letter using an f-string
        letter = f"""To,
The Chairman,
Purba Medinipur District Primary School Council,
P.O. Tamluk, Dist - Purba Medinipur

Through The Proper Channel.

Subject: Prayer for {leave_type} for {num_days} days.

Respected Sir/Ma'am,

Most respectfully I beg to state that I am {applicant_name}, {designation} of Khanjanchak Dhananjoy Primary School. P.O- Khanjanchak under Haldia Circle.

I could not attend school on & from {start_str} to {end_str} on account of my {reason}.

I request you to grant my {leave_type} for those days and consider my prayer to sanction leave and oblige.

Expecting your kind-hearted co-operation.

Thanking you.

Place: Khanjanchak
Date: {app_str}

Yours Faithfully,

{applicant_name}
{designation} of Khanjanchak Dhananjoy Pry. School
P.O- Khanjanchak, Haldia Circle
"""
        
        st.success("✅ Letter generated successfully!")
        
        # Display inside a text area for easy review and copying
        st.text_area("Generated Leave Application", value=letter, height=450)
        
        # Provide a quick download button
        st.download_button(
            label="📥 Download as Text File",
            data=letter,
            file_name=f"Leave_Application_{applicant_name.replace(' ', '_')}.txt",
            mime="text/plain"
        )
