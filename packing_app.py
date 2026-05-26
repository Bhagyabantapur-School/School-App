import streamlit as st
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# --- Google Sheets Connection ---
# Make sure your st.secrets["gcp_service_account"] is configured in your Streamlit Cloud deployment
@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    return client

client = init_connection()

@st.cache_data(ttl=600)
def get_sheet():
    # Opens the sk_money_location sheet and selects the Packing tab
    return client.open("sk_money_location").worksheet("Packing")

sheet = get_sheet()

# --- Initialize Default Packing List in Session State ---
if 'packing_items' not in st.session_state:
    st.session_state.packing_items = [
        "📱 Mi 11x", 
        "⌚ Amazfit GTS 2 Mini", 
        "🔌 Mi 11x Charger + Cable", 
        "🔌 Amazfit GTS 2 Mini Charger", 
        "🔌 Secondary charger + Cable", 
        "🔋 Mi Powerbank 10000w + Mini Cable", 
        "🎧 Sony WF-C700N", 
        "📱 Lenovo Tab 4 10 Plus", 
        "📱 Redmi Pad SE 4G", 
        "🪥 Philips Sonicare Toothbrush", 
        "🔌 Toothbrush Charger", 
        "🧴 Babul Toothpaste", 
        "🥢 Toothpick"
    ]

st.title("🧳 Smart Packing Checklist")

# --- Form for Visit Details ---
st.subheader("Trip Details")
visit_location = st.text_input("Visit (Destination/Purpose):", placeholder="e.g., Kolkata for 3 days")

# --- Option to Add New Items ---
with st.expander("➕ Add New Item to Checklist"):
    col1, col2 = st.columns([3, 1])
    with col1:
        new_item = st.text_input("Item name (Include an emoji icon!):", placeholder="e.g., 🕶️ Sunglasses")
    with col2:
        st.write("") # Spacing
        st.write("") # Spacing
        if st.button("Add Item"):
            if new_item and new_item not in st.session_state.packing_items:
                st.session_state.packing_items.append(new_item)
                st.success(f"Added {new_item}!")
                st.rerun()

# --- Checklist ---
st.subheader("Your Items")
st.write("Select the items you are packing:")

# Dictionary to store the checkbox states
packed_status = {}
for item in st.session_state.packing_items:
    packed_status[item] = st.checkbox(item)

# --- Save to Google Sheet ---
if st.button("💾 Save Packing List to Sheet", type="primary"):
    if not visit_location:
        st.error("Please enter a Visit/Destination before saving.")
    else:
        # Filter only the items that were checked
        packed_items_list = [item for item, is_checked in packed_status.items() if is_checked]
        
        if not packed_items_list:
            st.warning("You haven't selected any items to pack!")
        else:
            # Format Data
            now = datetime.now()
            current_date = now.strftime("%Y-%m-%d")
            current_time = now.strftime("%H:%M:%S")
            items_string = ", ".join(packed_items_list)
            
            # Prepare row: Date | Time | Items | Visit
            row_to_insert = [current_date, current_time, items_string, visit_location]
            
            try:
                sheet.append_row(row_to_insert)
                st.success(f"Successfully logged {len(packed_items_list)} items for your visit to '{visit_location}'!")
                st.balloons()
            except Exception as e:
                st.error(f"Failed to update Google Sheet: {e}")
