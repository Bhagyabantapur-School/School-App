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

# ROW 1
r1_col1, r1_col2, r1_col3 = st.columns(3)
with r1_col1:
    if st.button("📍 Money & Location", use_container_width=True): st.switch_page("money_location.py")
with r1_col2:
    if st.button("💳 Money Utilities", use_container_width=True): st.switch_page("money_utilities.py")
with r1_col3:
    if st.button("💪 Strong Tracker", use_container_width=True): st.switch_page("strong.py")

# ROW 2
r2_col1, r2_col2, r2_col3 = st.columns(3)
with r2_col1:
    if st.button("🚀 Project App", use_container_width=True): st.switch_page("project_app.py")
with r2_col2:
    if st.button("🗳️ Election Duty", use_container_width=True): st.switch_page("election_duty.py")
with r2_col3:
    if st.button("📆 Monthly Tracker", use_container_width=True): st.switch_page("monthly_app.py")

# ROW 3
r3_col1, r3_col2, r3_col3 = st.columns(3)
with r3_col1:
    if st.button("💵 Money Tracker", use_container_width=True): st.switch_page("money_tracker.py")
with r3_col2:
    if st.button("❤️ Health Hub", use_container_width=True): st.switch_page("health_app.py")
with r3_col3:
    if st.button("💾 Backup Tracker", use_container_width=True): st.switch_page("backup_tracker_app.py")

# ROW 4
r4_col1, r4_col2, r4_col3 = st.columns(3)
with r4_col1:
    if st.button("⏱️ Daily Routine", use_container_width=True): st.switch_page("routine_app.py")
with r4_col2:
    if st.button("🔍 Routine Audit", use_container_width=True): st.switch_page("routine_audit.py")
with r4_col3:
    if st.button("✏️ Routine Editor", use_container_width=True): st.switch_page("routine_editor.py")

# ROW 5
r5_col1, r5_col2, r5_col3 = st.columns(3)
with r5_col1:
    if st.button("📦 MDM Returns", use_container_width=True): st.switch_page("mdm_return_log.py")
with r5_col2:
    if st.button("🎬 Video Manager", use_container_width=True): st.switch_page("bps_ytfb_videos.py")
with r5_col3:
    if st.button("🏷️ Trace Inventory", use_container_width=True): st.switch_page("trace.py")

# ROW 6
r6_col1, r6_col2, r6_col3 = st.columns(3)
with r6_col1:
    if st.button("💧 Sleep & Water", use_container_width=True): st.switch_page("sleep_water_app.py")
with r6_col2:
    if st.button("📦 Product Inventory", use_container_width=True): st.switch_page("product_inventory.py")
with r6_col3:
    if st.button("🎒 Packing Tracker", use_container_width=True): st.switch_page("packing_app.py")
