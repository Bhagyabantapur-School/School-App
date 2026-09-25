import streamlit as st
import pandas as pd

# Mock database for demonstration purposes
MOCK_DB = {
    "admin_01": {"password": "adminpassword", "role": "admin", "name": "System Admin"},
    "user_01": {"password": "userpassword", "role": "standard", "name": "Regular User"}
}

# ==========================================
# 1. STATE INITIALIZATION
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "role" not in st.session_state:
    st.session_state.role = None

# ==========================================
# 2. THE 'AUTO-LOGIN' CHECK (Survives Refreshes)
# ==========================================
if not st.session_state.logged_in:
    if "user" in st.query_params:
        url_user = st.query_params["user"]
        # Validate the user from the URL against the database
        if url_user in MOCK_DB:
            st.session_state.logged_in = True
            st.session_state.user_id = url_user
            st.session_state.role = MOCK_DB[url_user]["role"]

# ==========================================
# 4. THE LOGOUT PROCESS (Race-Condition Free)
# ==========================================
def process_logout():
    # Instantly clear the URL parameters first
    st.query_params.clear()
    
    # Wipe the session state variables
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.role = None
    
    # Trigger a clean rerun back to the login screen
    st.rerun()

# ==========================================
# 3. THE LOGIN PROCESS
# ==========================================
def login_screen():
    st.title("System Login")
    
    with st.form("login_form"):
        user_input = st.text_input("User ID")
        pass_input = st.text_input("Password", type="password")
        submit_btn = st.form_submit_button("Authenticate")
        
        if submit_btn:
            if user_input in MOCK_DB and MOCK_DB[user_input]["password"] == pass_input:
                # Update session state upon successful authentication
                st.session_state.logged_in = True
                st.session_state.user_id = user_input
                st.session_state.role = MOCK_DB[user_input]["role"]
                
                # Push the User ID to the URL to enable session survival on refresh
                st.query_params["user"] = user_input
                
                st.rerun()
            else:
                st.error("Invalid User ID or Password.")

# ==========================================
# 5. ROLE-BASED ROUTING (Dashboards)
# ==========================================
def admin_dashboard():
    st.title(f"Admin Dashboard - Welcome {MOCK_DB[st.session_state.user_id]['name']}")
    st.success("You have full access to system configurations.")
    
    # Admin specific components go here
    st.metric("Total System Users", len(MOCK_DB))
    
    if st.button("Logout", key="admin_logout", type="primary"):
        process_logout()

def standard_dashboard():
    st.title(f"User Dashboard - Welcome {MOCK_DB[st.session_state.user_id]['name']}")
    st.info("You have standard access.")
    
    # User specific components go here
    st.write("Your personal workspace loads here.")
    
    if st.button("Logout", key="user_logout"):
        process_logout()

# --- Main App Routing Execution ---
if not st.session_state.logged_in:
    login_screen()
else:
    # Route to the appropriate dashboard based on the user's role
    if st.session_state.role == "admin":
        admin_dashboard()
    elif st.session_state.role == "standard":
        standard_dashboard()
    else:
        st.error("Unrecognized role assigned to user.")
        if st.button("Return to Login"):
            process_logout()
