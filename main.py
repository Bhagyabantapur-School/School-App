import streamlit as st

# 1. Page Configuration
st.set_page_config(
    page_title="My Personal Hub",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. Custom CSS to float the button inside the card
st.markdown("""
<style>
    /* Pull Streamlit buttons up into the extra padding of the HTML cards */
    div[data-testid="stButton"] {
        margin-top: -70px;
        margin-bottom: 25px;
        padding: 0px 20px;
        position: relative;
        z-index: 10;
    }
    /* Style the button to look semi-transparent so it blends with the card background */
    div[data-testid="stButton"] button {
        background-color: rgba(255, 255, 255, 0.6);
        border: 1px solid rgba(0, 0, 0, 0.1);
        font-weight: bold;
        color: #333;
    }
    div[data-testid="stButton"] button:hover {
        background-color: white;
        border: 1px solid rgba(0, 0, 0, 0.3);
    }
</style>
""", unsafe_allow_html=True)

# 3. Card Generator Function (Updated with text_color and extra bottom padding)
def create_card(icon, title, data_label, data_value, bg_color, border_color, text_color):
    return f"""
    <div style="background-color: {bg_color}; padding: 20px 20px 80px 20px; border-radius: 12px; border-left: 6px solid {border_color}; box-shadow: 2px 2px 8px rgba(0,0,0,0.05);">
        <div style="font-size: 20px; color: #333;"><b>{icon} {title}</b></div>
        <hr style="margin: 12px 0; border: none; border-top: 2px solid rgba(0,0,0,0.1);">
        <div style="font-size: 15px; color: #555;">
            {data_label}<br>
            <span style="font-size: 24px; font-weight: 900; color: {text_color};">{data_value}</span>
        </div>
    </div>
    """

# 4. Define the Dashboard Function
def show_dashboard():
    st.title("🚀 My Personal Dashboard")
    st.markdown("Welcome back! Here is a summary of your systems:")
    st.write("")

    # Grid Layout: 3 columns
    col1, col2, col3 = st.columns(3)

    with col1:
        # Blue Theme
        st.markdown(create_card("📍", "Money & Location", "Latest Log", "Bhagyabantapur", "#E3F2FD", "#1E88E5", "#1565C0"), unsafe_allow_html=True)
        if st.button("Open App", key="btn1", use_container_width=True): st.switch_page(money_location_page)

        # Indigo Theme
        st.markdown(create_card("🗳️", "Election Duty", "Status", "Assigned", "#E8EAF6", "#3949AB", "#283593"), unsafe_allow_html=True)
        if st.button("Open App", key="btn4", use_container_width=True): st.switch_page(election_page)
        
        # Pink Theme
        st.markdown(create_card("❤️", "Health Hub", "Blood Pressure", "120/80", "#FCE4EC", "#D81B60", "#AD1457"), unsafe_allow_html=True)
        if st.button("Open App", key="btn7", use_container_width=True): st.switch_page(health_page)

    with col2:
        # Red Theme
        st.markdown(create_card("💪", "Strong Tracker", "Current Streak", "12 Days", "#FFEBEE", "#E53935", "#C62828"), unsafe_allow_html=True)
        if st.button("Open App", key="btn2", use_container_width=True): st.switch_page(strong_page)

        # Teal Theme
        st.markdown(create_card("📆", "Monthly Tracker", "Current Month", "April 2026", "#E0F2F1", "#00897B", "#00695C"), unsafe_allow_html=True)
        if st.button("Open App", key="btn5", use_container_width=True): st.switch_page(monthly_page)
            
        # Orange Theme
        st.markdown(create_card("💾", "Backup Tracker", "Last Backup", "2 Hours Ago", "#FFF3E0", "#FB8C00", "#EF6C00"), unsafe_allow_html=True)
        if st.button("Open App", key="btn8", use_container_width=True): st.switch_page(backup_page)

    with col3:
        # Purple Theme
        st.markdown(create_card("🚀", "Project App", "Tasks Completed", "85%", "#F3E5F5", "#8E24AA", "#6A1B9A"), unsafe_allow_html=True)
        if st.button("Open App", key="btn3", use_container_width=True): st.switch_page(project_page)

        # Green Theme
        st.markdown(create_card("💵", "Money Tracker", "Wallet Balance", "₹ 4,250", "#E8F5E9", "#43A047", "#2E7D32"), unsafe_allow_html=True)
        if st.button("Open App", key="btn6", use_container_width=True): st.switch_page(money_tracker_page)

# 5. Define all Page Links
dashboard_page = st.Page(show_dashboard, title="Visual Dashboard", icon="🚀", default=True)

money_location_page = st.Page("money_location.py", title="Money & Location", icon="📍")
strong_page = st.Page("strong.py", title="Strong Tracker", icon="💪")
project_page = st.Page("project_app.py", title="Project Tracker", icon="🚀")
election_page = st.Page("election_duty.py", title="Election Duty", icon="🗳️")
monthly_page = st.Page("monthly_app.py", title="Monthly Tracker", icon="📆")
money_tracker_page = st.Page("money_tracker.py", title="Money Tracker", icon="💵")
health_page = st.Page("health_app.py", title="Health Tracker", icon="❤️")
backup_page = st.Page("backup_tracker_app.py", title="Backup Tracker", icon="💾")

# 6. Run Navigation
pg = st.navigation([
    dashboard_page,
    money_location_page, 
    strong_page, 
    project_page, 
    election_page, 
    monthly_page, 
    money_tracker_page,
    health_page,
    backup_page
])

pg.run()
