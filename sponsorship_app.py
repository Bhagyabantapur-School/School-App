with st.expander("🤝 Log Sponsorship & Brand Deals", expanded=False):
    # Fetch known sponsors dynamically from CONFIG
    sponsor_opts = get_list("Sponsors")
    if not sponsor_opts:
        sponsor_opts = ["-- Type New --"]
    elif "-- Type New --" not in sponsor_opts:
        sponsor_opts.append("-- Type New --")
        
    sp_brand_sel = st.selectbox("Sponsor / Brand Name", sponsor_opts, key="sp_brand_sel")
    if sp_brand_sel == "-- Type New --":
        sp_brand = st.text_input("Type New Brand Name", key="sp_new_brand")
    else:
        sp_brand = sp_brand_sel

    sp_campaign = st.text_input("Campaign or Video Title (e.g., DJI Mic Mini Integration)")
    
    sp_c1, sp_c2 = st.columns(2)
    with sp_c1:
        sp_type = st.selectbox("Deliverable Type", [
            "Integrated (60-90s)", 
            "Dedicated Video", 
            "YouTube Shorts", 
            "Community Post",
            "Bundle / Multi-Video"
        ])
        sp_status = st.selectbox("Current Status", [
            "Pitching / Outreach",
            "Negotiating",
            "Contract Signed",
            "Content Submitted for Approval",
            "Content Live",
            "Invoice Sent",
            "✅ Paid"
        ])
    
    with sp_c2:
        sp_publish_date = st.date_input("Target Publish Date", value=st.session_state.locked_date, key="sp_pub_date")
        sp_fee = st.number_input("Agreed Fee (₹)", min_value=0.0, step=1000.0, key="sp_fee")

    if st.button("💾 Save / Update Sponsorship Log", use_container_width=True, type="primary"):
        if sp_brand and sp_campaign:
            try:
                today_str = get_ist_now().strftime("%d-%m-%Y")
                publish_str = sp_publish_date.strftime("%d-%m-%Y")
                
                # Safely get or create the worksheet
                try:
                    sp_ws = sh.worksheet("SPONSORSHIP_LOG")
                except gspread.exceptions.WorksheetNotFound:
                    sp_ws = sh.add_worksheet(title="SPONSORSHIP_LOG", rows="100", cols="7")
                    sp_ws.append_row(["Date_Logged", "Brand_Name", "Campaign_or_Video", "Deliverable_Type", "Status", "Target_Publish_Date", "Agreed_Fee"])
                
                sp_ws.append_row([
                    today_str, sp_brand, sp_campaign, sp_type, sp_status, publish_str, sp_fee
                ])
                
                st.success(f"✅ Logged deal with {sp_brand} as '{sp_status}'!")
                if sp_status == "✅ Paid":
                    st.info("Don't forget to log this physical cash flow in your main Manual Financial Record!")
            except Exception as e:
                st.error(f"Error saving to Google Sheets: {e}")
        else:
            st.warning("⚠️ Please provide both the Brand Name and Campaign Title.")
