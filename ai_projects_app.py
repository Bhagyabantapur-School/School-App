with st.expander("🤖 Log AI Generation & Projects", expanded=False):
    # Fetch known AI platforms dynamically from CONFIG
    ai_opts = get_list("AI_Platforms")
    if not ai_opts:
        ai_opts = ["Direct Client", "Upwork", "Fiverr", "Gumroad", "-- Type New --"]
    elif "-- Type New --" not in ai_opts:
        ai_opts.append("-- Type New --")
        
    ai_platform_sel = st.selectbox("Platform / Source", ai_opts, key="ai_plat_sel")
    if ai_platform_sel == "-- Type New --":
        ai_platform = st.text_input("Type New Platform Name", key="ai_new_plat")
    else:
        ai_platform = ai_platform_sel

    ai_project = st.text_input("Project or Task Name (e.g., 'Streamlit App Build')")
    
    ai_c1, ai_c2, ai_c3 = st.columns([1.5, 1, 1.5])
    with ai_c1:
        ai_date = st.date_input("Date Logged", value=st.session_state.locked_date, key="ai_date")
    with ai_c2:
        ai_hours = st.number_input("Hours Spent", min_value=0.0, step=0.5, key="ai_hrs")
    with ai_c3:
        ai_revenue = st.number_input("Estimated Revenue (₹)", min_value=0.0, step=100.0, key="ai_rev")
        
    ai_status = st.selectbox("Payment Status", ["Pending / Unbilled", "Invoice Sent", "✅ Paid"], key="ai_status")

    if st.button("💾 Save AI Income Log", use_container_width=True, type="primary"):
        if ai_platform and ai_project:
            try:
                date_str = ai_date.strftime("%d-%m-%Y")
                
                # Safely get or create the worksheet
                try:
                    ai_ws = sh.worksheet("AI_INCOME_LOG")
                except gspread.exceptions.WorksheetNotFound:
                    ai_ws = sh.add_worksheet(title="AI_INCOME_LOG", rows="100", cols="6")
                    ai_ws.append_row(["Date", "Platform", "Project_Name", "Hours_Spent", "Estimated_Revenue", "Status"])
                
                ai_ws.append_row([
                    date_str, ai_platform, ai_project, ai_hours, ai_revenue, ai_status
                ])
                
                st.success(f"✅ Logged AI project: {ai_project}!")
                if ai_status == "✅ Paid":
                    st.info("Remember to log this cleared payment in your main Manual Financial Record!")
            except Exception as e:
                st.error(f"Error saving to Google Sheets: {e}")
        else:
            st.warning("⚠️ Please provide both the Platform and the Project Name.")
