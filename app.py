import streamlit as st

# ==========================================
# 1. GLOBAL PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="My Unified Hub",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. USER AUTHENTICATION DICTIONARY
# ==========================================
USERS = {
    "admin": {"name": "SUKHAMAY KISKU", "role": "admin", "password": "bpsAPP@2026"}, 
    "tr": {"name": "TAPASI RANA", "role": "teacher", "password": "tr26"}, 
    "sbr": {"name": "SUJATA BISWAS ROTHA", "role": "teacher", "password": "sbr26"}, 
    "rs": {"name": "ROHINI SINGH", "role": "teacher", "password": "rs26"}, 
    "unj": {"name": "UDAY NARAYAN JANA", "role": "teacher", "password": "unj26"}, 
    "bkp": {"name": "BIMAL KUMAR PATRA", "role": "teacher", "password": "bkp26"}, 
    "sp": {"name": "SUSMITA PAUL", "role": "teacher", "password": "sp26"}, 
    "tkm": {"name": "TAPAN KUMAR MANDAL", "role": "teacher", "password": "tkm26"}, 
    "mk": {"name": "MANJUMA KHATUN", "role": "teacher", "password": "mk26"}
}

# ==========================================
# 3. SESSION STATE INITIALIZATION
# ==========================================
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'user_role' not in st.session_state: st.session_state.user_role = None
if 'user_name' not in st.session_state: st.session_state.user_name = None

# ==========================================
# 4. LOGIN SCREEN (GATEKEEPER)
# ==========================================
if not st.session_state.authenticated:
    # Hide the sidebar completely on the login screen
    st.markdown("<style>[data-testid='stSidebar'] {display: none;}</style>", unsafe_allow_html=True)
    
    st.markdown("<div class='login-box'><h3>🔐 System Login</h3><p>Please enter your Username & Password.</p></div>", unsafe_allow_html=True)
    
    with st.form("login_form"):
        ui = st.text_input("Username").lower().strip() 
        pi = st.text_input("Password", type="password")
        
        if st.form_submit_button("Login"):
            if ui in USERS and pi == USERS[ui]["password"]:
                st.session_state.authenticated = True
                st.session_state.user_role = USERS[ui]["role"]
                st.session_state.user_name = USERS[ui]["name"]
                st.rerun() 
            else: 
                st.error("❌ Incorrect Credentials")
    
    st.stop() # Halts all further script execution until logged in

# ==========================================
# 5. HOME PORTAL & NAVIGATION LOGIC
# ==========================================
# Sidebar Logout & Welcome
st.sidebar.success(f"👋 Welcome, {st.session_state.user_name}")
if st.sidebar.button("Log Out"): 
    st.session_state.authenticated = False 
    st.rerun()
st.sidebar.markdown("---")

# Define pages for navigation
app_page = st.Page("bps_digital.py", title="BPS Digital App", icon="🏫")
fees_page = st.Page("sch_exam_fees.py", title="Exam Fees", icon="💰")
udise_page = st.Page("UDISE+.py", title="UDISE+ Progression", icon="🎓")

# Define the visual interface for the home page (The Buttons)
def home_page_ui():
    st.markdown(f"<h2 style='text-align: center;'>Welcome to the Unified Hub, {st.session_state.user_name}!</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Select an application from the sidebar or click below to launch your primary workspace.</p>", unsafe_allow_html=True)
    
    st.write("") # Spacing
    st.write("")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 Enter BPS Digital App", type="primary", use_container_width=True):
            st.switch_page(app_page)
            
        st.write("") # Spacing between buttons
        
        if st.button("💰 Enter Funds & Fees", type="secondary", use_container_width=True):
            st.switch_page(fees_page)
            
        # Admin-only Home Portal Button
        if st.session_state.user_role == "admin":
            st.write("")
            if st.button("🎓 Enter UDISE+ Progression", type="secondary", use_container_width=True):
                st.switch_page(udise_page)

home_page = st.Page(home_page_ui, title="Home Portal", icon="🏠", default=True)

# Build Navigation Menu dynamically based on User Role
nav_pages = {
    "Portal": [home_page],
    "Applications": [app_page, fees_page]
}

# Only append UDISE+ if logged in as admin
if st.session_state.user_role == "admin":
    nav_pages["Applications"].append(udise_page)

pg = st.navigation(nav_pages)
pg.run()
