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

st.title("🚀 My Personal Dashboard")
st.write("---")

# ==========================================
# APP DICTIONARY (Categorized Launchpad)
# ==========================================
app_groups = {
    "MONEY": [
        ("Money App", "money_app.py", "💰"), 
        ("Money Utilities", "money_utilities.py", "💳"), 
        ("Money Tracker", "money_tracker.py", "💵"), 
        ("Product Inventory", "product_inventory.py", "📦")
    ],
    "LOCATION": [
        ("Location App", "location_app.py", "📍"), 
        ("Packing Tracker", "packing_app.py", "🎒")
    ],
    "ROUTINE": [
        ("Daily Routine", "routine_app.py", "⏱️"), 
        ("Routine Audit", "routine_audit.py", "🔍"), 
        ("Routine Editor", "routine_editor.py", "✏️"), 
        ("Project App", "project_app.py", "🚀"), 
        ("AI Video Tracker", "ai_video_tracker.py", "🤖"),
        ("Courses", "courses.py", "🎓") # <-- Added here
    ],
    "HEALTH": [
        ("Health Hub", "health_app.py", "❤️"), 
        ("Sleep & Water", "sleep_water_app.py", "💧")
    ],
    "SCH WORK": [
        ("MDM Returns", "mdm_return_log.py", "📦"), 
        ("Video Manager", "bps_ytfb_videos.py", "🎬"), 
        ("Speech Mastery", "speech_prep_app.py", "🎙️")
    ],
    "HOME": [
        ("Trace Inventory", "trace.py", "🏷️"), 
        ("Monthly Tracker", "monthly_app.py", "📆")
    ],
    "HARDWARE": [
        ("Backup Tracker", "backup_tracker_app.py", "💾")
    ],
    "BALANCE": [
        ("Strong Tracker", "strong.py", "💪")
    ],
    "ONES": [
        ("Election Duty", "election_duty.py", "🗳️"), 
        ("App Updater", "app_update.py", "🔄")
    ]
}

# ==========================================
# DYNAMIC GRID GENERATOR
# ==========================================
for group_name, apps in app_groups.items():
    # Group Header
    st.markdown(f"<h4 style='color: #0068c9; margin-top: 10px; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 1px;'>{group_name}</h4>", unsafe_allow_html=True)
    
    # 3-Column Grid Builder
    for i in range(0, len(apps), 3):
        cols = st.columns(3)
        for j in range(3):
            if i + j < len(apps):
                app_name, file_name, icon = apps[i + j]
                with cols[j]:
                    if st.button(f"{icon} {app_name}", key=f"dash_{file_name}", use_container_width=True):
                        st.switch_page(file_name)
            else:
                with cols[j]:
                    st.empty() # Fills empty columns to keep the grid perfectly aligned
                    
    st.markdown("<hr style='margin: 15px 0px; border: 0; border-top: 1px solid #f0f2f6;'>", unsafe_allow_html=True)
