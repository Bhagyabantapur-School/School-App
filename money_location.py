import streamlit as st
import pandas as pd
from datetime import datetime

# ==========================================
# PAGE CONFIGURATION
# ==========================================
st.set_page_config(page_title="Money & Location Tracker", layout="centered")

# ==========================================
# GOOGLE SHEETS HELPER FUNCTIONS
# (Replace with your actual GSheets connection methods)
# ==========================================
@st.cache_data(ttl=5)
def get_config_data():
    # Replace with your actual method to fetch the "CONFIG" tab
    # Expected columns: ['Area', 'Specific_Place', 'Remarks', ...]
    pass 

@st.cache_data(ttl=5)
def get_location_data():
    # Replace with your actual method to fetch the location log tab
    pass

def append_to_sheet(sheet_name, row_data):
    # Replace with your actual method to append a row to a specific tab
    pass

# ==========================================
# LOGIC: CHECK ACTIVE JOURNEY FROM SHEET
# ==========================================
def get_current_journey_status(loc_df):
    """Reads the last log from the Google Sheet to determine if a journey is active."""
    if loc_df is None or loc_df.empty:
        return False, "School Route" # Default
    
    last_row = loc_df.iloc[-1]
    last_remark = str(last_row.get('Remark', ''))
    
    # If the last log was a journey start, extract the route
    if last_remark.startswith("Started Route:"):
        # Extracts "Girishmore Route" from "Started Route: Girishmore Route | Mode: Bike..."
        route_name = last_remark.split("Started Route:")[1].split("|")[0].strip()
        return True, route_name
    
    # If the last log was an arrival, the journey is not active
    return False, "School Route"

# ==========================================
# MAIN APP
# ==========================================
def main():
    st.title("Tracker: Location & Money")
    
    # Fetch Data
    config_df = get_config_data()
    loc_df = get_location_data()
    
    # Check current journey status directly from the Google Sheet
    is_journey_active, current_sheet_route = get_current_journey_status(loc_df)

    # Tabs
    tab_location, tab_money = st.tabs(["📍 Location", "💰 Money"])

    # ==========================================
    # LOCATION TAB
    # ==========================================
    with tab_location:
        st.header("Location Tracker")
        
        # Get unique routes from the CONFIG tab's Area column
        if config_df is not None and 'Area' in config_df.columns:
            route_list = config_df['Area'].dropna().unique().tolist()
        else:
            route_list = ["School Route", "Girishmore Route", "Express Route"] # Fallback

        if is_journey_active:
            st.info(f"🚗 **Currently traveling on:** {current_sheet_route}")
            
            # Filter specific places based on the currently active route
            if config_df is not None:
                places = config_df[config_df['Area'] == current_sheet_route]['Specific_Place'].dropna().tolist()
            else:
                places = []
                
            arrived_place = st.selectbox("Where did you arrive?", places)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Log Arrival", use_container_width=True):
                    now = datetime.now()
                    row = [now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), arrived_place, f"Arrived at: {arrived_place}"]
                    append_to_sheet("LOCATION_DATA", row)
                    st.success(f"Logged arrival at {arrived_place}!")
                    st.rerun()
            
            with col2:
                # Custom CSS to make the "Arrived Home Now" button green
                st.markdown("""
                    <style>
                    div.stButton > button:first-child[kind="primary"] {
                        background-color: #4CAF50;
                        color: white;
                        border: none;
                    }
                    </style>""", unsafe_allow_html=True)
                
                if st.button("Arrived Home Now", type="primary", use_container_width=True):
                    now = datetime.now()
                    row = [now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), "Home", "Arrived Home"]
                    append_to_sheet("LOCATION_DATA", row)
                    st.success("Welcome Home!")
                    st.rerun()
                    
        else:
            # No active journey, show start journey options
            st.subheader("Start a New Journey")
            selected_route = st.selectbox("Select Route", route_list)
            travel_mode = st.selectbox("Travel Mode", ["Bike", "Bus", "Walking", "Toto", "Car"])
            companions = st.selectbox("Companions", ["Alone", "Wife", "Subo", "Family", "Colleague"])
            
            if st.button("Start Journey", use_container_width=True):
                now = datetime.now()
                remark = f"Started Route: {selected_route} | Mode: {travel_mode} | With: {companions}"
                row = [now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), "On the way", remark]
                append_to_sheet("LOCATION_DATA", row)
                st.success(f"Started {selected_route}!")
                st.rerun()

    # ==========================================
    # MONEY TAB
    # ==========================================
    with tab_money:
        st.header("Financial Record")
        
        # Quick sync location
        if st.button("🔄 Quick Sync Location"):
            st.toast("Location Synced!")
            
        # Time & Date (Time column added after Date)
        d_col1, d_col2 = st.columns(2)
        with d_col1:
            date_val = st.date_input("Date", datetime.today())
        with d_col2:
            time_val = st.time_input("Time", datetime.now().time())
        
        # IN and OUT side by side (moved up)
        amt_col1, amt_col2 = st.columns(2)
        with amt_col1:
            amount_in = st.number_input("Amount IN (+)", min_value=0.0, step=10.0)
        with amt_col2:
            amount_out = st.number_input("Amount OUT (-)", min_value=0.0, step=10.0)

        # Entity, Category, Sub Cat, Particulars
        col_chk1, col_chk2 = st.columns(2)
        with col_chk1:
            is_pers = st.checkbox("Entity: PERS")
        with col_chk2:
            is_mb = st.checkbox("Account: MB")
            
        entity = "PERS" if is_pers else st.selectbox("Entity", ["", "SCHOOL", "OTHER"])
        account = "MB" if is_mb else st.selectbox("Account", ["", "CASH", "SBI"])
        
        category = st.selectbox("Category", ["", "NEEDS", "FAMILY", "LIFESTYLE", "SCHOOL"])
        sub_cat = st.selectbox("Sub Category", ["", "ME", "SUBO", "MOTHER", "PUJA", "BASO"])
        particulars = st.text_input("Particulars")
        
        # TO/FROM and New Location Column 
        # (Home / Someone's house injects into Location, not TO/FROM)
        loc_col1, loc_col2 = st.columns(2)
        with loc_col1:
            to_from = st.text_input("TO / FROM")
        with loc_col2:
            location_val = st.text_input("Location", help="Enter Home or specific house here")
            
        remark_val = st.text_input("Remark")

        # Incomplete Log Option (Busy time)
        is_incomplete = st.checkbox("Log as Incomplete (for busy time)")

        if st.button("Save Record"):
            # Prepare row for MONEY_DATA tab
            money_row = [
                str(date_val), 
                str(time_val), 
                amount_in, 
                amount_out, 
                entity, 
                account, 
                category, 
                sub_cat, 
                particulars, 
                to_from, 
                location_val, 
                remark_val,
                "Incomplete" if is_incomplete else "Complete"
            ]
            append_to_sheet("MONEY_DATA", money_row)
            st.success("Record Saved!")

if __name__ == "__main__":
    main()
