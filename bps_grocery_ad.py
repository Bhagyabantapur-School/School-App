import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pytz

# Set Timezone for Haldia, West Bengal
IST = pytz.timezone('Asia/Kolkata')

st.set_page_config(page_title="BPS Grocery Manager", page_icon="🥦", layout="centered")

# ==========================================
# SESSION STATE INITIALIZATION
# ==========================================
if 'cart' not in st.session_state: st.session_state.cart = []

# ==========================================
# DATABASE CONNECTION & CACHING
# ==========================================
@st.cache_resource
def get_gspread_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

client = get_gspread_client()

@st.cache_data(ttl=30, show_spinner=False)
def load_sheet_data(worksheet_name):
    try:
        sheet = client.open("BPS_Grocery_DB").worksheet(worksheet_name)
        records = sheet.get_all_records()
        return pd.DataFrame(records) if records else pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading {worksheet_name}: {e}")
        return pd.DataFrame()

def append_to_sheet(worksheet_name, data_dict):
    sheet = client.open("BPS_Grocery_DB").worksheet(worksheet_name)
    headers = sheet.row_values(1)
    row_to_insert = [str(data_dict.get(header, "")) for header in headers]
    sheet.append_row(row_to_insert)
    load_sheet_data.clear()

def bulk_update_sheet(worksheet_name, df):
    sheet = client.open("BPS_Grocery_DB").worksheet(worksheet_name)
    df = df.astype(str) # Convert everything to string to prevent JSON errors
    data = [df.columns.values.tolist()] + df.values.tolist()
    sheet.clear()
    try:
        sheet.update(values=data, range_name="A1")
    except TypeError:
        sheet.update("A1", data) # Fallback for older gspread versions
    load_sheet_data.clear()

st.title("🥦 BPS Grocery & Supply Manager")

# Load data safely
df_inventory = load_sheet_data("Inventory")
df_orders = load_sheet_data("Orders")

# --- NAVIGATION MENU ---
menu_choice = st.selectbox(
    "📌 Main Menu", 
    ["🛒 Log New Order", "📦 Stock & Reminders", "💳 Payments & Dues"]
)
st.markdown("---")

# ==========================================
# PAGE 1: LOG NEW ORDER (WITH CART)
# ==========================================
if menu_choice == "🛒 Log New Order":
    
    col1, col2 = st.columns([1.2, 1])
    
    with col1:
        st.subheader("1. Add Items to Order")
        
        # Add new item expander (Updates dropdown instantly)
        with st.expander("➕ Item not in list? Create New Item"):
            new_name = st.text_input("New Item Name (e.g., Potato, Rice)")
            new_unit = st.selectbox("Unit", ["kg", "grams", "liters", "packets", "pieces", "box"])
            new_alert = st.number_input("Low Stock Alert Level", min_value=0.0, value=2.0)
            if st.button("Save New Item to Master List"):
                if new_name:
                    append_to_sheet("Inventory", {
                        "Item_Name": new_name.title(),
                        "Unit": new_unit,
                        "Current_Stock": 0.0,
                        "Alert_Limit": new_alert
                    })
                    st.success(f"Added {new_name}! It is now available in the dropdown.")
                    st.rerun()

        # Selection Dropdown
        if not df_inventory.empty:
            item_list = df_inventory['Item_Name'].tolist()
            selected_item = st.selectbox("Select Item from List", ["--Select--"] + sorted(item_list))
            
            qty = st.number_input("Quantity Ordered", min_value=0.0, step=0.5)
            
            if st.button("⬇️ Add to Order Basket"):
                if selected_item != "--Select--" and qty > 0:
                    unit = df_inventory[df_inventory['Item_Name'] == selected_item].iloc[0]['Unit']
                    st.session_state.cart.append({"Item_Name": selected_item, "Quantity": qty, "Unit": unit})
                    st.success(f"Added {qty} {unit} of {selected_item} to cart.")
                    st.rerun()
        else:
            st.info("Inventory is empty. Please create a new item above.")

    with col2:
        st.subheader("2. Current Order Basket")
        if len(st.session_state.cart) == 0:
            st.write("Basket is empty.")
        else:
            order_summary = ""
            for i, item in enumerate(st.session_state.cart):
                st.write(f"• **{item['Item_Name']}**: {item['Quantity']} {item['Unit']}")
                order_summary += f"{item['Item_Name']} ({item['Quantity']}{item['Unit']}), "
            
            st.markdown("---")
            total_bill = st.number_input("Total Shop Bill Amount (₹)", min_value=0.0, step=10.0)
            
            if st.button("✅ Save & Log Order", type="primary"):
                now_ist = datetime.now(IST)
                
                # 1. Generate Order ID
                next_id = len(df_orders) + 1 if not df_orders.empty else 1
                order_id = f"ORD-{now_ist.strftime('%Y%m')}-{next_id:03d}"
                
                # 2. Save Order to Database
                append_to_sheet("Orders", {
                    "Order_ID": order_id,
                    "Date": now_ist.strftime("%d-%m-%Y"),
                    "Order_Details": order_summary.strip(", "),
                    "Total_Amount": total_bill,
                    "Payment_Status": "Unpaid"
                })
                
                # 3. Automatically increase Stock in Inventory
                if not df_inventory.empty:
                    temp_inv = df_inventory.copy()
                    for cart_item in st.session_state.cart:
                        idx = temp_inv.index[temp_inv['Item_Name'] == cart_item['Item_Name']].tolist()
                        if idx:
                            curr = float(temp_inv.at[idx[0], 'Current_Stock'])
                            temp_inv.at[idx[0], 'Current_Stock'] = curr + float(cart_item['Quantity'])
                    bulk_update_sheet("Inventory", temp_inv)
                
                st.session_state.cart = [] # Clear the cart
                st.success("Order logged! Stock levels have been automatically updated.")
                st.balloons()
            
            if st.button("Clear Basket"):
                st.session_state.cart = []
                st.rerun()

# ==========================================
# PAGE 2: STOCK & REMINDERS
# ==========================================
elif menu_choice == "📦 Stock & Reminders":
    st.header("Inventory Dashboard")
    
    if not df_inventory.empty:
        # --- LOW STOCK REMINDERS ---
        df_inventory['Current_Stock'] = pd.to_numeric(df_inventory['Current_Stock'], errors='coerce').fillna(0)
        df_inventory['Alert_Limit'] = pd.to_numeric(df_inventory['Alert_Limit'], errors='coerce').fillna(0)
        
        low_stock = df_inventory[df_inventory['Current_Stock'] <= df_inventory['Alert_Limit']]
        
        if not low_stock.empty:
            st.error(f"🚨 **Reminder: You need to order {len(low_stock)} items!**")
            for _, row in low_stock.iterrows():
                st.write(f"⚠️ **{row['Item_Name']}** (Only {row['Current_Stock']} {row['Unit']} left)")
        else:
            st.success("✅ All stock levels are healthy! No reminders.")
            
        st.markdown("---")
        st.subheader("Update Current Stock (Mid-Day Meal Usage)")
        st.write("Edit the 'Current_Stock' numbers directly in the table below and hit Save.")
        
        # Display editable dataframe
        edited_df = st.data_editor(
            df_inventory, 
            hide_index=True, 
            use_container_width=True,
            disabled=["Item_Name", "Unit"] # Prevent accidental renaming here
        )
        
        if st.button("💾 Save Stock Updates", type="primary"):
            with st.spinner("Updating database..."):
                bulk_update_sheet("Inventory", edited_df)
                st.success("Stock updated successfully!")
                st.rerun()
    else:
        st.info("No items in inventory. Add items via the 'Log New Order' page.")

# ==========================================
# PAGE 3: PAYMENTS & DUES
# ==========================================
elif menu_choice == "💳 Payments & Dues":
    st.header("Shop Payment Tracker")
    
    if not df_orders.empty:
        unpaid = df_orders[df_orders['Payment_Status'] == 'Unpaid']
        paid = df_orders[df_orders['Payment_Status'] == 'Paid']
        
        st.subheader("🔴 Pending Dues")
        if not unpaid.empty:
            total_due = pd.to_numeric(unpaid['Total_Amount'], errors='coerce').sum()
            st.warning(f"**Total Outstanding Amount: ₹{total_due}**")
            
            # Show unpaid list and allow marking as paid
            for idx, row in unpaid.iterrows():
                with st.container():
                    st.write(f"**{row['Order_ID']}** | Date: {row['Date']} | Amount: **₹{row['Total_Amount']}**")
                    st.caption(f"Items: {row['Order_Details']}")
                    
                    if st.button(f"Mark as Paid ##{row['Order_ID']}", key=row['Order_ID']):
                        with st.spinner("Logging payment..."):
                            sheet = client.open("BPS_Grocery_DB").worksheet("Orders")
                            # +2 because Google Sheets is 1-indexed and has a header row
                            sheet.update_cell(idx + 2, 5, 'Paid') 
                            load_sheet_data.clear()
                            st.success(f"{row['Order_ID']} marked as Paid!")
                            st.rerun()
                    st.markdown("---")
        else:
            st.success("🎉 All shop bills are paid up to date!")
            
        with st.expander("🟢 View Paid Orders History"):
            st.dataframe(paid, use_container_width=True, hide_index=True)
    else:
        st.info("No orders found in the database.")
