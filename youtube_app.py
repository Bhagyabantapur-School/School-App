with st.expander("▶️ Log YouTube Stats & Revenue", expanded=True):
    # Fetch your 5 channels dynamically from CONFIG
    channel_opts = get_list("YouTube_Channels") 
    yt_channel = st.selectbox("Select Channel", channel_opts)
    
    yt_c1, yt_c2 = st.columns(2)
    with yt_c1:
        yt_date = st.date_input("Analytics Date", value=st.session_state.locked_date)
        yt_views = st.number_input("Views", min_value=0, step=100)
        yt_subs = st.number_input("Subscribers Gained", min_value=0, step=1)
    
    with yt_c2:
        yt_title = st.text_input("Video Title (Optional - for specific tracking)")
        yt_hours = st.number_input("Watch Hours", min_value=0.0, step=1.0)
        yt_revenue = st.number_input("Estimated Revenue", min_value=0.0, step=0.5)

    if st.button("💾 Save YouTube Log", use_container_width=True, type="primary"):
        if yt_channel:
            try:
                date_str = yt_date.strftime("%d-%m-%Y")
                
                # Check if worksheet exists, if not, create it safely
                try:
                    yt_ws = sh.worksheet("YOUTUBE_LOG")
                except gspread.exceptions.WorksheetNotFound:
                    yt_ws = sh.add_worksheet(title="YOUTUBE_LOG", rows="100", cols="7")
                    yt_ws.append_row(["Date", "Channel_Name", "Video_Title", "Views", "Watch_Hours", "Subscribers_Gained", "Estimated_Revenue"])
                
                yt_ws.append_row([
                    date_str, yt_channel, yt_title, yt_views, yt_hours, yt_subs, yt_revenue
                ])
                
                st.success(f"✅ Logged stats for {yt_channel}!")
                st.balloons()
            except Exception as e:
                st.error(f"Error saving to Google Sheets: {e}")
        else:
            st.warning("⚠️ Please select a channel first.")
