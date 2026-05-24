st.divider()
st.subheader("📋 Pending Items")
df_shop = load_shopping_data()
if not df_shop.empty:
    pending = df_shop[df_shop['Status'] == 'Pending']
    if not pending.empty:
        # --- SMART COLUMN SELECTION ---
        # Only select columns that actually exist in your Google Sheet
        potential_cols = ['Item', 'Shop_Type', 'Note', 'Fund', 'Account']
        found_cols = [c for c in potential_cols if c in pending.columns]
        
        df_display = pending[found_cols].copy()
        
        # Rename 'Note' to 'Sub Category' if it exists for display purposes
        if 'Note' in df_display.columns:
            df_display.rename(columns={'Note': 'Sub Category'}, inplace=True)
            
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.write("You have no pending items!")
