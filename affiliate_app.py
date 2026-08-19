with st.expander("🛒 Log Affiliate Sales & Commissions", expanded=False):
    # Fetch your affiliate programs dynamically from CONFIG
    aff_opts = get_list("Affiliate_Programs")
    if not aff_opts:
        aff_opts = ["Amazon Associates", "Flipkart Affiliate", "Hostinger", "-- Type New --"]
        
    aff_program = st.selectbox("Select Affiliate Program", aff_opts)
    if aff_program == "-- Type New --":
        aff_program = st.text_input("Type New Program Name")

    aff_product = st.text_input("Product or Campaign Promoted (e.g., DJI Mic Mini)")
    
    aff_c1, aff_c2, aff_c3 = st.columns(3)
    with aff_c1:
        aff_date = st.date_input("Date", value=st.session_state.locked_date, key="aff_date")
    with aff_c2:
        aff_clicks = st.number_input("Link Clicks", min_value=0, step=10, key="aff_clicks")
    with aff_c3:
        aff_conversions = st.number_input("Conversions (Sales)", min_value=0, step=1, key="aff_conv")
        
    aff_commission = st.number_input("Estimated Commission Earned (₹)", min_value=0.0, step=50.0, key="aff_comm")

    if st.button("💾 Save Affiliate Log", use_container_width=True, type="primary"):
        if aff_program and aff_product:
            try:
                date_str = aff_date.strftime("%d-%m-%Y")
                
                # Safely get or create the worksheet
                try:
                    aff_ws = sh.worksheet("AFFILIATE_LOG")
                except gspread.exceptions.WorksheetNotFound:
                    aff_ws = sh.add_worksheet(title="AFFILIATE_LOG", rows="100", cols="6")
                    aff_ws.append_row(["Date", "Program", "Product_or_Campaign", "Clicks", "Conversions", "Estimated_Commission"])
                
                aff_ws.append_row([
                    date_str, aff_program, aff_product, aff_clicks, aff_conversions, aff_commission
                ])
                
                st.success(f"✅ Logged {aff_conversions} sales for {aff_program}!")
            except Exception as e:
                st.error(f"Error saving to Google Sheets: {e}")
        else:
            st.warning("⚠️ Please provide both the Program and the Product name.")
