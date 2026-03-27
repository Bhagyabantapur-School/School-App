# --- SIDEBAR: DEVELOPER CONSOLE ---
st.sidebar.header("🛠️ Developer Tools")

with st.sidebar.expander("📝 Log App Development"):
    with st.form("dev_log_form", clear_on_submit=True):
        st.caption("Record new code updates and features.")
        app_version = st.text_input("Version Number", placeholder="e.g., v1.2")
        app_changes = st.text_area("Release Notes", placeholder="e.g., Added secure photo fetching and direct Call Parent button.")
        
        submitted_dev = st.form_submit_button("Save Update Log")
        
        if submitted_dev and app_changes:
            st.cache_data.clear() # Clears cache to ensure the app is fresh after an update
            
            try:
                client = get_gspread_client()
                db_main = client.open("BPS_Database")
                
                # Check if dev log tab exists, if not, create it
                try:
                    dev_ws = db_main.worksheet("App_Development_Log")
                except gspread.exceptions.WorksheetNotFound:
                    dev_ws = db_main.add_worksheet(title="App_Development_Log", rows="500", cols="5")
                    dev_ws.append_row(["Date", "Time (IST)", "Developer", "Version", "Release Notes"])
                    
                # Get Current Indian Standard Time
                ist = pytz.timezone('Asia/Kolkata')
                now = datetime.datetime.now(ist)
                
                log_date = now.strftime("%d.%m.%y")
                log_time = now.strftime("%I:%M %p")
                
                dev_ws.append_row([log_date, log_time, "Sukhamay Kisku", app_version, app_changes])
                
                st.sidebar.success(f"✅ Version {app_version} logged successfully!")
            except Exception as e:
                st.sidebar.error(f"Failed to save development log: {e}")

st.sidebar.divider()
