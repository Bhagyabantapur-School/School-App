with st.expander("📈 Log Stock & Mutual Fund Investments", expanded=False):
    # Fetch known assets dynamically from CONFIG
    asset_opts = get_list("Investment_Assets")
    if not asset_opts:
        # Defaulting to your standard portfolio foundations
        asset_opts = ["Mahindra Manulife Mutual Fund", "UTI Mutual Fund", "Index Fund", "Direct Equity", "-- Type New --"]
    elif "-- Type New --" not in asset_opts:
        asset_opts.append("-- Type New --")
        
    asset_sel = st.selectbox("Asset / Fund Name", asset_opts, key="inv_asset_sel")
    if asset_sel == "-- Type New --":
        asset_name = st.text_input("Type New Asset Name", key="inv_new_asset")
    else:
        asset_name = asset_sel

    inv_c1, inv_c2 = st.columns(2)
    with inv_c1:
        inv_type = st.selectbox("Transaction Type", [
            "Buy (SIP)", 
            "Buy (Lumpsum)", 
            "Sell (Redemption)", 
            "Dividend / Yield Payout"
        ], key="inv_type")
        inv_date = st.date_input("Transaction Date", value=st.session_state.locked_date, key="inv_date")
        
    with inv_c2:
        inv_amount = st.number_input("Total Amount (₹)", min_value=0.0, step=500.0, key="inv_amt")
        inv_units = st.number_input("Units / Qty (Optional)", min_value=0.0, step=0.001, format="%.3f", key="inv_units")

    # Optional: Calculate approximate NAV/Price if both amount and units are provided
    nav_calc = (inv_amount / inv_units) if inv_units > 0 else 0.0
    if nav_calc > 0:
        st.caption(f"🧮 *Calculated NAV/Price: ₹{nav_calc:.2f}*")

    if st.button("💾 Save Investment Log", use_container_width=True, type="primary"):
        if asset_name and inv_amount > 0:
            try:
                date_str = inv_date.strftime("%d-%m-%Y")
                time_str = get_ist_now().strftime("%H:%M")
                
                # 1. Log to the Portfolio Tracker
                try:
                    inv_ws = sh.worksheet("INVESTMENT_LOG")
                except gspread.exceptions.WorksheetNotFound:
                    inv_ws = sh.add_worksheet(title="INVESTMENT_LOG", rows="100", cols="6")
                    inv_ws.append_row(["Date", "Asset_Name", "Transaction_Type", "Amount_INR", "Units_Qty", "NAV_or_Price"])
                
                inv_ws.append_row([
                    date_str, asset_name, inv_type, inv_amount, inv_units, round(nav_calc, 2)
                ])
                
                # 2. AUTOMATICALLY sync with Main MONEY_DATA
                # Because an SIP/Buy is a real cash deduction, and a Sell/Dividend is a real cash deposit.
                money_ws = sh.worksheet("MONEY_DATA")
                
                if "Buy" in inv_type:
                    # Money leaves MB (OUT), goes to ASSETS
                    money_row = [date_str, time_str, "", inv_amount, "MB", "Salary", "ASSETS", "INVESTMENT", "MUTUAL FUND / STOCK", asset_name, "", "", f"Auto-logged {inv_type}"]
                else:
                    # Money enters MB (IN), comes from ASSETS
                    money_row = [date_str, time_str, inv_amount, "", "MB", "", "ASSETS", "INCOME", "MARKET YIELD", asset_name, "", "", f"Auto-logged {inv_type}"]
                
                money_ws.append_row(money_row)
                load_money_data.clear()
                
                st.success(f"✅ Logged {inv_type} for {asset_name} and synced with Main Money Ledger!")
                st.balloons()
            except Exception as e:
                st.error(f"Error saving to Google Sheets: {e}")
        else:
            st.warning("⚠️ Please provide the Asset Name and an Amount greater than zero.")
