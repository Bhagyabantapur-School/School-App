import streamlit as st

# 1. Configure the BPS workspace (Must be the first Streamlit command)
st.set_page_config(
    page_title="BPS Digital", 
    page_icon="🏫", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Initialize the login state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# 3. Create the login validation function
def verify_login():
    # Replace these with your actual username and password logic
    if st.session_state.username == "admin" and st.session_state.password == "bps123":
        st.session_state.logged_in = True
    else:
        st.error("Incorrect username or password.")

# 4. The Gatekeeper: Show login screen OR the main app
if not st.session_state.logged_in:
    # --- LOGIN SCREEN ---
    st.title("🏫 BPS Digital System Login")
    st.text_input("Username", key="username")
    st.text_input("Password", type="password", key="password")
    st.button("Log In", on_click=verify_login)

else:
    # --- FULL SYSTEM NAVIGATION (Only accessible if logged in) ---
    
    # Define pages
    home_page = st.Page("app.py", title="System Dashboard", icon="🏠", default=True)
    admission_page = st.Page("admission_hub.py", title="Admission Hub", icon="📝")
    student_profile_page = st.Page("student_profile.py", title="Student Profiles", icon="🧑‍🎓")
    id_card_page = st.Page("id_card_app.py", title="ID Card Generator", icon="🪪")
    school_data_page = st.Page("school_data.py", title="School Data", icon="📊")
    exam_fees_page = st.Page("sch_exam_fees.py", title="Exam & Fees", icon="💰")
    distribution_page = st.Page("bps_distribution.py", title="Distributions", icon="🎒")
    returns_page = st.Page("bps_returns.py", title="Returns", icon="📑")

    # Group navigation
    pg = st.navigation({
        "System Home": [home_page],
        "Student Management": [admission_page, student_profile_page, id_card_page],
        "Academics & Finance": [school_data_page, exam_fees_page],
        "Operations": [distribution_page, returns_page]
    })

    # Sidebar branding
    st.sidebar.markdown("---")
    st.sidebar.markdown("#### Bhagyabantapur Primary School")
    st.sidebar.caption("BPS Digital Smart School System")
    
    # Optional: Add a logout button to the sidebar
    if st.sidebar.button("Log Out"):
        st.session_state.logged_in = False
        st.rerun()

    # Run the router
    pg.run()
