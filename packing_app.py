import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# SETUP & CONNECTION
# ==========================================
st.set_page_config(page_title="Packing Tracker", page_icon="🎒", layout="centered")

# --- BACK BUTTON (STRICTLY REQUIRED) ---
if st.button("⬅️ Back to Hub", type="secondary"):
    st.switch_page("routine_app.py")
st.write("---") 
# ---------------------------------------

def get_ist_now():
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)

@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    return client.open("sk_money_location")

try:
    sh = init_connection()
except Exception as e:
    st.error(f"Could not connect to Google Sheets. Error: {e}")
    st.stop()

# --- CACHING FOR DESTINATION MEMORY ---
@st.cache_data(ttl=60)
def load_packing_data():
    try: 
        return pd.DataFrame(sh.worksheet("Packing").get_all_records())
    except: 
        return pd.DataFrame()

# ==========================================
# APP DATA & STATE
# ==========================================
BASE_ITEMS = {
    "📱 Smart Devices": [
        "📱 Mi 11x", 
        "⌚ Amazfit GTS 2 Mini", 
        "🎧 Sony WF-C700N",
        "📱 Redmi Pad SE 4G", 
        "📱 Lenovo Tab 4 10 Plus"
    ],
    "🔌 Power & Cables": [
        "🔌 Mi 11x Charger + Cable", 
        "🔋 Amazfit GTS 2 Mini Charger",
        "🔌 Secondary charger + Cable", 
        "🧱 Mi Powerbank 10000w + Mini Cable",
        "🔌 Toothbrush Charger",
        "🔌 Power Extension Board",
        "🔦 Rechargeable Mini Light"
    ],
    "🪥 Toiletries & Misc": [
        "🪥 Philips Sonicare Toothbrush", 
        "🧴 Babul Toothpaste", 
        "🥢 Tooth pic",
        "👓 Spectacles Glasses",
        "🧳 Spectacles Glasses Case",
        "🕶️ Sunglasses",
        "🧻 Wipes"
    ]
}

if 'custom_items' not in st.session_state:
    st.session_state.custom_items = []

# ==========================================
# MULTI-LEG LOGIC
# ==========================================
df_packing = load_packing_data()
past_visits = []
last_trip_items = []
is_transit_mode = False
last_destination = ""

if not df_packing.empty and 'Visit' in df_packing.columns and 'Items' in df_packing.columns:
    past_visits = sorted(list(dict.fromkeys([str(v).strip() for v in df_packing['Visit'].dropna() if str(v).strip() != ""])))
    
    # Check the very last log entry to determine our "Mode"
    last_row = df_packing.iloc[-1]
    last_destination = str(last_row.get('Visit', '')).strip().upper()
    
    # If the last logged visit was NOT 'HOME', we are in transit/returning
    if last_destination and last_destination != "HOME":
        is_transit_mode = True
        items_string = str(last_row.get('Items', ''))
        last_trip_items = [i.strip() for i in items_string.split(',') if i.strip()]

# ==========================================
# MAIN APP UI
# ==========================================
st.title("🎒 Smart Packing Checklist")

if is_transit_mode:
    st.warning(f"🔄 **Transit Mode:** You are currently logged at **{last_destination}**.")
    st.write("Check off the items you brought with you to ensure you don't leave anything behind before heading to your next stop (or Home).")
else:
    st.success("🏠 **Departure Mode:** You are currently at **HOME**.")
    st.write("Select the items you are packing for your upcoming trip.")

# --- SMART DESTINATION DROPDOWN ---
visit_opts = past_visits + ["-- Add New Destination --"]

# If in transit mode, make "HOME" the default suggestion to return
if is_transit_mode:
    if "HOME" not in past_visits: visit_opts.insert(0, "HOME")
    default_idx = visit_opts.index("HOME")
else:
    default_idx = 0

selected_visit = st.selectbox("📍 Next Destination / Purpose", visit_opts, index=default_idx)

if selected_visit == "-- Add New Destination --":
    visit_name = st.text_input("Type New Destination Name", placeholder="e.g., Digha Trip, Village Visit...")
else:
    visit_name = selected_visit

st.divider()
st.subheader("✅ Checklist")

checked_items = []

if is_transit_mode and last_trip_items:
    # --- TRANSIT MODE CHECKLIST ---
    st.info(f"📋 Showing the {len(last_trip_items)} items you brought from your last trip.")
    transit_cols = st.columns(3)
    
    for idx, item in enumerate(last_trip_items):
        with transit_cols[idx % 3]:
            # Default to unchecked so you have to manually verify each item
            if st.checkbox(item, key=f"transit_{item}"):
                checked_items.append(item)
                
    missing_items = len(last_trip_items) - len(checked_items)
    if missing_items > 0:
        st.error(f"⚠️ **Wait!** You have {missing_items} items still unchecked.")
    else:
        st.success("🎉 All items accounted for!")

else:
    # --- DEPARTURE MODE CHECKLIST (From Home) ---
    cols = st.columns(3)
    for idx, (category, items) in enumerate(BASE_ITEMS.items()):
        with cols[idx]:
            st.markdown(f"**{category}**")
            for item in items:
                if st.checkbox(item, key=item):
                    checked_items.append(item)

    if st.session_state.custom_items:
        st.markdown("---")
        st.markdown("**➕ Added Custom Items**")
        custom_cols = st.columns(3)
        for idx, item in enumerate(st.session_state.custom_items):
            with custom_cols[idx % 3]:
                if st.checkbox(item, key=item):
                    checked_items.append(item)

    # Allow adding new items only when packing from home
    st.markdown("---")
    with st.expander("📝 Add Extra Item to Checklist"):
        c1, c2 = st.columns([3, 1])
        with c1:
            new_item_input = st.text_input("Item Name (Add an emoji!)", key="new_item_val", label_visibility="collapsed", placeholder="e.g., ☂️ Umbrella")
        with c2:
            if st.button("Add Item", use_container_width=True):
                if new_item_input and new_item_input not in st.session_state.custom_items:
                    st.session_state.custom_items.append(new_item_input)
                    st.session_state[new_item_input] = True 
                    st.rerun()

st.divider()

# ==========================================
# SAVE LOGIC
# ==========================================
if st.button("💾 Save Packing Log to Google Sheets", type="primary", use_container_width=True):
    if not visit_name or visit_name.strip() == "":
        st.error("⚠️ Please enter or select your Visit Destination at the top!")
    elif not checked_items:
        st.warning("⚠️ You haven't checked any items to pack!")
    elif is_transit_mode and len(checked_items) < len(last_trip_items):
        st.error(f"🚨 **STOP!** You brought {len(last_trip_items)} items, but only checked off {len(checked_items)}. Find your missing items before saving!")
    else:
        try:
            try:
                ws = sh.worksheet("Packing")
            except gspread.exceptions.WorksheetNotFound:
                ws = sh.add_worksheet(title="Packing", rows="100", cols="4")
                ws.append_row(["Date", "Time", "Items", "Visit"])

            now = get_ist_now()
            date_str = now.strftime("%d-%m-%Y")
            time_str = now.strftime("%H:%M")
            items_str = ", ".join(checked_items) 
            
            ws.append_row([date_str, time_str, items_str, visit_name.strip().upper()])
            
            load_packing_data.clear()
            
            st.success(f"🎒 Success! Logged {len(checked_items)} items for '{visit_name.upper()}'.")
            st.info(f"**Packed:** {items_str}")
            st.balloons()
            
        except Exception as e:
            st.error(f"Failed to save to Google Sheets: {e}")
