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
        # Automatically format username inputs to lowercase and strip spaces
        ui = st.text_input("Username").lower().strip() 
        pi = st.text_input("Password", type="password")
        
        if st.form_submit_button("Login"):
            # Verify credentials against the dictionary
            if ui in USERS and pi == USERS[ui]["password"]:
                st.session_state.authenticated = True
                st.session_state.user_role = USERS[ui]["role"]
                st.session_state.user_name = USERS[ui]["name"]
                st.rerun() 
            else: 
                st.error("❌ Incorrect Credentials")
    
    st.stop() # Halts all further script execution until logged in

# ==========================================
# --- AUTHENTICATED SYSTEM STARTS HERE ---
# ==========================================

# Sidebar Logout & Welcome
st.sidebar.success(f"👋 Welcome, {st.session_state.user_name}")
if st.sidebar.button("Log Out"): 
    st.session_state.authenticated = False 
    st.rerun()
st.sidebar.markdown("---")

# ==========================================
# EXECUTE NAVIGATION MENU
# ==========================================
# Only keep the app.py page
main_app = st.Page("app.py", title="BPS Digital App", icon="🚀", default=True)

pg = st.navigation([main_app])

# RUN NAVIGATION
pg.run()
