# 2. AUTOMATICALLY sync with main "sk_money_location" (SMART MAPPING)
                if finance_type == "Paid" and cost > 0:
                    money_sh = gc.open("sk_money_location")
                    money_ws = money_sh.worksheet("MONEY_DATA")
                    
                    entity = "PERS" if course_type == "Personal" else "WORK"
                    
                    # Read the headers of your MONEY_DATA tab
                    raw_headers = money_ws.row_values(1)
                    
                    # Clean the headers: removes hidden spaces and makes them uppercase for matching
                    clean_headers = [str(h).strip().upper() for h in raw_headers]
                    
                    # Create an empty row matching the exact length of your columns
                    money_row = [""] * len(raw_headers)
                    
                    # Upgraded helper function: checks for variations and ignores hidden spaces
                    def fill_col(possible_names, value):
                        for name in possible_names:
                            clean_name = name.strip().upper()
                            if clean_name in clean_headers:
                                money_row[clean_headers.index(clean_name)] = value
                                return # Stop looking once we find a match
                    
                    fill_col(["DATE"], date_logged)
                    fill_col(["TIME"], time_logged)
                    fill_col(["IN"], "")
                    fill_col(["OUT"], cost)
                    fill_col(["ACCOUNT"], account_sel)
                    fill_col(["FUND"], "Salary")
                    fill_col(["ENTITY"], entity)
                    fill_col(["CATEGORY"], "EDUCATION")
                    fill_col(["SUB CATEGORY", "SUB-CATEGORY", "SUBCATEGORY"], "Course/Workshop")
                    fill_col(["PARTICULARS"], course_name)
                    
                    # This will now catch "TO_FROM", "TO/FROM", or even "TO_FROM " with hidden spaces!
                    fill_col(["TO_FROM", "TO/FROM", "TO / FROM", "TO FROM"], to_from) 
                    
                    fill_col(["REMARK", "REMARKS"], "Auto-logged Course Fee")
                    
                    # Append the perfectly mapped row
                    money_ws.append_row(money_row)
                    clear_money_cache.clear() 
                    
                    st.success(f"✅ Course saved to COURSE_LOG and ₹{cost} synced perfectly to main ledger!")
                else:
                    st.success("✅ Free course details saved to COURSE_LOG successfully!")
