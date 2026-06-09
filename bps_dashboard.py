import streamlit as st

# Clean styling for tall, easy-to-tap buttons
st.markdown("""
<style>
    div[data-testid="stButton"] button {
        height: 70px;
        font-size: 16px;
        font-weight: bold;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

st.title("🏫 BPS Digital System")
st.write("---")

# ROW 1
r1_col1, r1_col2, r1_col3 = st.columns(3)
with r1_col1:
    if st.button("📝 Admission Hub", use_container_width=True): st.switch_page("admission_hub.py")
with r1_col2:
    if st.button("🎓 Student Profiles", use_container_width=True): st.switch_page("student_profile.py")
with r1_col3:
    if st.button("🪪 ID Card Generator", use_container_width=True): st.switch_page("id_card_app.py")

# ROW 2
r2_col1, r2_col2, r2_col3 = st.columns(3)
with r2_col1:
    if st.button("📊 School Data", use_container_width=True): st.switch_page("school_data.py")
with r2_col2:
    if st.button("💰 Exam & Fees", use_container_width=True): st.switch_page("sch_exam_fees.py")
with r2_col3:
    if st.button("📚 Library Manager", use_container_width=True): st.switch_page("library_app.py")

# ROW 3
r3_col1, r3_col2, r3_col3 = st.columns(3)
with r3_col1:
    if st.button("🗓️ Leave Management", use_container_width=True): st.switch_page("leave_app.py")
with r3_col2:
    if st.button("🎒 Distributions", use_container_width=True): st.switch_page("bps_distribution.py")
with r3_col3:
    if st.button("📑 Returns", use_container_width=True): st.switch_page("bps_returns.py")

# ROW 4
r4_col1, r4_col2, r4_col3 = st.columns(3)
with r4_col1:
    if st.button("📋 Form Manager", use_container_width=True): st.switch_page("form_manager.py")
with r4_col2:
    if st.button("🔐 Staff Portal", use_container_width=True): st.switch_page("bps_digital_sk.py")
with r4_col3:
    if st.button("🥦 Grocery Manager", use_container_width=True): st.switch_page("bps_grocery_ad.py")
