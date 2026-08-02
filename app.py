# ==========================================
# 8. HOME PORTAL & NAVIGATION LOGIC
# ==========================================

# 1. Define all application pages
app_page = st.Page("bps_digital.py", title="BPS Digital App", icon="🏫")
fees_page = st.Page("sch_exam_fees.py", title="Exam Fees", icon="💰")
udise_page = st.Page("UDISE+.py", title="UDISE+ Progression", icon="🎓")
gas_page = st.Page("bps_gas_tracker.py", title="Gas Tracker", icon="🛢️")
exam_page = st.Page("bps_exam.py", title="BPS Exams", icon="📝")
assembly_page = st.Page("bps_assembly.py", title="Assembly Planner", icon="🎙️")  # <-- New Assembly App

def home_page_ui():
    st.markdown(f"<h3 style='margin-bottom: 5px;'>👋 Welcome, {st.session_state.user_name}</h3>", unsafe_allow_html=True)
    
    if st.session_state.user_role in ["teacher", "admin"]:
        render_tracker()
        
    st.markdown("#### 🚀 Select Application")
    
    # Primary Applications (Visible to both Admin & Teachers)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🏫 BPS Digital App", type="primary", use_container_width=True):
            st.switch_page(app_page)
    with col2:
        if st.button("📝 BPS Exams", type="primary", use_container_width=True):
            st.switch_page(exam_page)
            
    # Secondary Applications (Visible to both Admin & Teachers)
    col3, col4 = st.columns(2)
    with col3:
        if st.button("💰 Funds & Fees", type="secondary", use_container_width=True):
            st.switch_page(fees_page)
            
    # ========================================================
    # ADMIN-ONLY APPLICATION GATEWAY (Head Teacher Exclusives)
    # ========================================================
    if st.session_state.user_role == "admin":
        with col4:
            if st.button("🎙️ Assembly Planner", type="secondary", use_container_width=True):  # <-- Assembly Button
                st.switch_page(assembly_page)
                
        col5, col6 = st.columns(2)
        with col5:
            if st.button("🎓 UDISE+ Progression", type="secondary", use_container_width=True):
                st.switch_page(udise_page)
        with col6:
            if st.button("🛢️ Gas Tracker", type="secondary", use_container_width=True):
                st.switch_page(gas_page)

home_page = st.Page(home_page_ui, title="Home Portal", icon="🏠", default=True)

# 2. Build Sidebar Navigation based on User Role
nav_pages = {
    "Portal": [home_page],
    "Applications": [app_page, exam_page, fees_page]
}

# 3. Add Admin-Only pages to the Sidebar Navigation
if st.session_state.user_role == "admin":
    nav_pages["Applications"].append(assembly_page)  # <-- Added to Admin Sidebar
    nav_pages["Applications"].append(udise_page)
    nav_pages["Applications"].append(gas_page)

pg = st.navigation(nav_pages)
pg.run()
