import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from PIL import Image
import os
import streamlit.components.v1 as components 
import plotly.express as px
import re # Added for parsing allotted Class/Section

# ==========================================
# 1. SETUP & CONFIGURATION
# ==========================================
st.set_page_config(page_title="BPS Supply Distribution", page_icon="🏫", layout="wide")

# Actual Staff Database 
USERS = {
    "admin": {"name": "SUKHAMAY KISKU", "role": "admin", "password": "bpsAPP@2026"}, 
    "tr": {"name": "TAPASI RANA", "role": "teacher", "password": "tr26"}, 
    "sbr": {"name": "SUJATA BISWAS ROTHA", "role": "teacher", "password": "sbr26"}, 
    "rs": {"name": "ROHINI SINGH", "role": "teacher", "password": "rs26"}, 
    "unj": {"name": "UDAY NARAYAN JANA", "role": "teacher", "password": "unj26"}, 
    "bkp": {"name": "BIMAL KUMAR PATRA", "role": "teacher", "password": "bkp26"}, 
    "sp": {"name": "SUSMITA PAUL", "role": "teacher", "password": "sp26"}, 
    "tkm": {"name": "TAPAN KUMAR MANDAL", "role": "teacher", "password": "tkm26"}, 
    "mk": {"name": "MANJUMA KHATUN", "role": "teacher", "password": "mk26"}
}

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = ""
if 'current_role' not in st.session_state:
    st.session_state.current_role = ""
if 'play_beep' not in st.session_state:
    st.session_state.play_beep = False

# ==========================================
# 2. GOOGLE SHEETS CONNECTION & DATA LOADING
# ==========================================
@st.cache_resource
def get_gspread_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(credentials)

gc = get_gspread_client()

@st.cache_data(ttl=600)
def load_gsheet_data(sheet_name, tab_name):
    """Generic function to load a specific tab from a specific Google Sheet"""
    try:
        ws = gc.open(sheet_name).worksheet(tab_name)
        return pd.DataFrame(ws.get_all_records())
    except Exception as e:
        st.error(f"Error loading {tab_name} from {sheet_name}: {e}")
        return pd.DataFrame()

def get_inventory_items(only_active=True):
    """Fetches items. If only_active is True, hides items marked as 'Hidden'."""
    df_settings = load_gsheet_data("BPS_Distribution_Log", "settings")
    if df_settings.empty or 'Active_Items' not in df_settings.columns:
        return ["Books", "Uniform", "Bag"]

    valid_items = []
    for index, row in df_settings.iterrows():
        # Safely convert headers to lowercase to avoid exact match errors
        safe_row = {str(k).strip().lower(): v for k, v in row.items()}
        
        item = str(safe_row.get('active_items', '')).strip()
        status = str(safe_row.get('status', 'Active')).strip() 
        
        if item and item.lower() != 'nan':
            if only_active and status.lower() == 'hidden':
                continue
            valid_items.append(item)
            
    return valid_items

# ==========================================
# 3. LOGIN SCREEN
# ==========================================
if not st.session_state.logged_in:
    _, col_login, _ = st.columns([1, 2, 1])
    
    with col_login:
        col1, col2 = st.columns([1, 4])
        with col1:
            if os.path.exists("logo.png"):
                st.image(Image.open("logo.png"), width=80)
            else:
                st.write("🏫")
        with col2:
            st.title("Bhagyabantapur Primary School")
            st.subheader("Staff Login")

        st.info("""
        **Welcome to the Digital Supply Distribution Portal!**
        
        **Purpose:** Streamline the distribution of school supplies directly to students present today.
        
        **Key Features:**
        * 📦 **Admin Controls:** Headmaster manages stock and active distribution items.
        * 🔗 **Live MDM Sync:** Only displays students marked 'Present' in the BPS Digital App today.
        * 📊 **Live Dashboard:** Track inventory and distribution trends in real-time.
        """)
        st.markdown("<br>", unsafe_allow_html=True)

        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit_button = st.form_submit_button("Log In")

            if submit_button:
                if username in USERS and USERS[username]["password"] == password:
                    st.session_state.logged_in = True
                    st.session_state.current_user = USERS[username]["name"]
                    st.session_state.current_role = USERS[username]["role"]
                    st.success("Logged in successfully!")
                    st.rerun()
                else:
                    st.error("Invalid Username or Password")
                    
        st.markdown("<br><br><p style='text-align: center; color: gray; font-size: 14px;'>Developed by Sukhamay Kisku (H.M.)</p>", unsafe_allow_html=True)
    st.stop()

# ==========================================
# 4. MAIN APPLICATION 
# ==========================================
col1, col2, col3 = st.columns([1, 3, 1])
with col1:
    if os.path.exists("logo.png"):
        st.image(Image.open("logo.png"), width=80)
with col2:
    st.title("BPS Distribution")
with col3:
    st.info(f"👤 **{st.session_state.current_user}**\n\n({st.session_state.current_role.title()})")
    if st.button("Log Out"):
        st.session_state.logged_in = False
        st.session_state.current_user = ""
        st.session_state.current_role = ""
        st.rerun()

st.markdown("---")

with st.spinner("Loading School Database..."):
    df_students = load_gsheet_data("BPS_Database", "students_master")
    df_mdm = load_gsheet_data("BPS_Database", "mdm_log")
    df_logs_db = load_gsheet_data("BPS_Distribution_Log", "Sheet1")
    
    teacher_active_items = get_inventory_items(only_active=True)
    all_master_items = get_inventory_items(only_active=False)

if df_students.empty:
    st.warning("No student data found in students_master.")
    st.stop()

if st.session_state.current_role == "admin":
    tab_entry, tab_summary, tab_receive, tab_dashboard, tab_admin = st.tabs(["Distribute Items", "My Session Summary", "📦 Receive Stock", "📊 Dashboard", "⚙️ Admin Settings"])
else:
    tab_entry, tab_summary = st.tabs(["Distribute Items", "My Session Summary"])

# --- TEACHER ENTRY TAB ---
with tab_entry:
    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.header("Issue Supplies")
    with col_b:
        if st.button("🔄 Sync Live Data"):
            st.cache_data.clear()
            st.rerun()

    st.info("⚠️ Only showing students who are present in the BPS Digital App today.")

    if not teacher_active_items:
        st.error("No items currently authorized for distribution. Please contact the Admin.")
    else:
        distribution_type = st.selectbox("Select Item Category Being Distributed:", teacher_active_items)
        
        # --- SMART DROPDOWN FILTERING LOGIC ---
        allotted_class = "All"
        allotted_section = "All"
        
        # Scan the item name to see if it was allotted to a specific Class/Section
        match = re.search(r'\((Class [^)]+)\)', distribution_type)
        if match:
            inner_text = match.group(1) 
            parts = inner_text.split(" - Sec ")
            allotted_class = parts[0].replace("Class ", "").strip()
            if len(parts) > 1:
                allotted_section = parts[1].strip()
        # --------------------------------------
        
        col1, col2 = st.columns(2)
        with col1:
            all_classes_in_db = sorted(df_students['Class'].astype(str).unique())
            
            # If the item is locked to a specific class, ONLY show that class
            if allotted_class != "All":
                classes_to_show = [allotted_class] if allotted_class in all_classes_in_db else []
            else:
                classes_to_show = all_classes_in_db
                
            sel_class = st.selectbox("Select Class", classes_to_show)
            
        with col2:
            if sel_class:
                all_sections_in_db = sorted(df_students[df_students['Class'].astype(str) == sel_class]['Section'].astype(str).unique())
                
                # If the item is locked to a specific section, ONLY show that section
                if allotted_section != "All":
                    sections_to_show = [allotted_section] if allotted_section in all_sections_in_db else []
                else:
                    sections_to_show = all_sections_in_db
            else:
                sections_to_show = []
                
            sel_section = st.selectbox("Select Section", sections_to_show)

        st.markdown("---")
        
        if not sel_class or not sel_section:
            st.warning("Please ensure a valid Class and Section are selected.")
        else:
            today_str = datetime.now().strftime("%d-%m-%Y") 
            
            if not df_mdm.empty and 'Date' in df_mdm.columns and 'Name' in df_mdm.columns:
                mdm_today = df_mdm[df_mdm['Date'].astype(str) == today_str]
                present_names_today = mdm_today['Name'].astype(str).str.strip().str.lower().tolist()
                
                class_df = df_students[(df_students['Class'].astype(str) == sel_class) & 
                                       (df_students['Section'].astype(str) == sel_section)]
                
                class_df = class_df[class_df['Name'].astype(str).str.strip().str.lower().isin(present_names_today)]
            else:
                class_df = pd.DataFrame() 
    
            if class_df.empty:
                st.warning(f"No students found logged in the MDM App today for Class {sel_class} - Section {sel_section}.")
            else:
                st.subheader(f"Present Students: Class {sel_class} ({sel_section})")
                
                if 'current_distribution' not in st.session_state:
                    st.session_state.current_distribution = {}
    
                for index, row in class_df.iterrows():
                    student_name = str(row['Name']).strip()
                    
                    already_received = False
                    received_date = ""
                    
                    if not df_logs_db.empty and 'Name' in df_logs_db.columns and 'Item Given' in df_logs_db.columns:
                        past_records = df_logs_db[
                            (df_logs_db['Name'].astype(str).str.strip().str.lower() == student_name.lower()) &
                            (df_logs_db['Item Given'].astype(str).str.strip().str.lower() == distribution_type.strip().lower())
                        ]
                        if not past_records.empty:
                            already_received = True
                            received_date = past_records.iloc[-1]['Date']
    
                    widget_key = f"{sel_class}_{sel_section}_{row['Roll']}_{student_name}"
                    
                    if already_received:
                        st.checkbox(f"Roll {row['Roll']}: {student_name} ✅ (Received on {received_date})", 
                                    value=True, disabled=True, key=f"dis_{widget_key}")
                    else:
                        if widget_key not in st.session_state.current_distribution:
                            st.session_state.current_distribution[widget_key] = False
                            
                        is_checked = st.checkbox(f"Roll {row['Roll']}: {student_name}", key=f"chk_{widget_key}")
                        
                        if is_checked and not st.session_state.current_distribution[widget_key]:
                            st.session_state.play_beep = True
                            
                        st.session_state.current_distribution[widget_key] = is_checked
    
                if st.session_state.play_beep:
                    components.html(
                        """
                        <script>
                        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                        const oscillator = audioCtx.createOscillator();
                        oscillator.type = 'sine';
                        oscillator.frequency.setValueAtTime(800, audioCtx.currentTime); 
                        oscillator.connect(audioCtx.destination);
                        oscillator.start();
                        oscillator.stop(audioCtx.currentTime + 0.1); 
                        </script>
                        """, height=0, width=0
                    )
                    st.session_state.play_beep = False 
    
                st.markdown("<br>", unsafe_allow_html=True)
                
                if st.button(f"Submit {distribution_type} Distribution", type="primary"):
                    with st.spinner("Saving logs to Google Sheets..."):
                        try:
                            log_sheet = gc.open("BPS_Distribution_Log")
                            log_ws = log_sheet.sheet1 
                            
                            now = datetime.now()
                            current_date = now.strftime("%d-%m-%Y") 
                            current_time = now.strftime("%H:%M:%S")
                            teacher = st.session_state.current_user
                            
                            rows_to_append = []
                            
                            for index, row in class_df.iterrows():
                                widget_key = f"{sel_class}_{sel_section}_{row['Roll']}_{row['Name']}"
                                
                                if st.session_state.current_distribution.get(widget_key, False):
                                    log_row = [
                                        current_date, 
                                        current_time, 
                                        teacher,  
                                        sel_class, 
                                        sel_section,
                                        row['Roll'], 
                                        row['Name'], 
                                        distribution_type 
                                    ]
                                    rows_to_append.append(log_row)
                            
                            if rows_to_append:
                                log_ws.append_rows(rows_to_append)
                                st.success(f"Successfully logged {len(rows_to_append)} {distribution_type}(s)!")
                                
                                if 'recent_logs' not in st.session_state:
                                    st.session_state.recent_logs = []
                                st.session_state.recent_logs.extend(rows_to_append)
                                
                                st.session_state.current_distribution.clear()
                                st.cache_data.clear() 
                                st.rerun()
                            else:
                                st.warning("No new students were selected. Nothing was saved.")
                                
                        except Exception as e:
                            st.error(f"Failed to save to Google Sheets: {e}")

# --- SUMMARY TAB ---
with tab_summary:
    st.header("Your Recent Submissions")
    st.info("This shows the distributions you have logged during this current login session.")
    
    if 'recent_logs' in st.session_state and st.session_state.recent_logs:
        df_logs = pd.DataFrame(st.session_state.recent_logs, columns=['Date', 'Time', 'Teacher', 'Class', 'Section', 'Roll', 'Name', 'Item Given'])
        
        df_display = df_logs.drop(columns=['Teacher'])
        st.dataframe(df_display, hide_index=True)
    else:
        st.write("No distributions logged yet in this session.")

# --- ADMIN ONLY TABS ---
if st.session_state.current_role == "admin":
    
    # 📦 RECEIVE STOCK TAB
    with tab_receive:
        st.header("Receive New Inventory")
        st.write("Log newly arrived stock here. Select an existing item or add a completely new one.")
        
        item_options = all_master_items + ["➕ Add New Item"]
        
        recv_item_selection = st.selectbox("Select Item Received:", item_options)
        
        if recv_item_selection == "➕ Add New Item":
            final_item_base = st.text_input("Type New Item Name (e.g., Geometry Box):")
            
            st.markdown("**Optional: Allot Item to Specific Class/Section**")
            col1, col2 = st.columns(2)
            with col1:
                all_classes = ["All Classes"] + sorted(df_students['Class'].astype(str).unique().tolist())
                allot_class = st.selectbox("Allotted Class:", all_classes)
            with col2:
                if allot_class != "All Classes":
                    avail_sections = ["All Sections"] + sorted(df_students[df_students['Class'].astype(str) == allot_class]['Section'].astype(str).unique().tolist())
                else:
                    avail_sections = ["All Sections"]
                allot_section = st.selectbox("Allotted Section:", avail_sections)
                
            if not final_item_base.strip():
                final_item = ""
            elif allot_class == "All Classes":
                final_item = final_item_base.strip()
            else:
                sec_str = f" - Sec {allot_section}" if allot_section != "All Sections" else ""
                final_item = f"{final_item_base.strip()} (Class {allot_class}{sec_str})"
        else:
            final_item = recv_item_selection
            
        recv_qty = st.number_input("Quantity Received:", min_value=1, step=1, value=50)
        recv_date = st.date_input("Date Received:", datetime.today())
        
        if st.button("Log Received Stock", type="primary"):
            if not final_item or not final_item.strip():
                st.error("Please specify the item name before submitting.")
            else:
                with st.spinner("Updating inventory in Google Sheets..."):
                    try:
                        final_item = final_item.strip()
                        ws_settings = gc.open("BPS_Distribution_Log").worksheet("settings")
                        cell = ws_settings.find(final_item, in_column=1)
                        formatted_date = recv_date.strftime("%d-%m-%Y")
                        
                        if cell:
                            curr_qty_str = ws_settings.cell(cell.row, 3).value
                            try:
                                curr_qty = int(curr_qty_str) if curr_qty_str else 0
                            except ValueError:
                                curr_qty = 0
                            
                            new_qty = curr_qty + recv_qty
                            
                            ws_settings.update_cell(cell.row, 2, formatted_date)
                            ws_settings.update_cell(cell.row, 3, new_qty)
                            st.success(f"Successfully added {recv_qty} to {final_item}! Total received is now {new_qty}.")
                        else:
                            col_a_values = ws_settings.col_values(1)
                            next_row = len(col_a_values) + 1
                            
                            ws_settings.update_cell(next_row, 1, final_item)
                            ws_settings.update_cell(next_row, 2, formatted_date)
                            ws_settings.update_cell(next_row, 3, recv_qty)
                            ws_settings.update_cell(next_row, 4, "Active") 
                            st.success(f"Successfully added NEW item '{final_item}' with a starting quantity of {recv_qty}!")

                        st.cache_data.clear()
                    except Exception as e:
                        st.error(f"Error updating stock: {e}")

    # 📊 DASHBOARD TAB
    with tab_dashboard:
        st.header("Master Inventory Dashboard")
        st.info("Live overview of stock levels and distribution history.")
        
        df_settings = load_gsheet_data("BPS_Distribution_Log", "settings")
        
        if df_settings.empty:
            st.warning("Settings data not found. Cannot generate dashboard.")
        else:
            summary_data = []
            
            for index, row in df_settings.iterrows():
                safe_row = {str(k).strip().lower(): v for k, v in row.items()}
                
                item = str(safe_row.get('active_items', '')).strip()
                if not item or item.lower() == 'nan': 
                    continue
                    
                recv_date = safe_row.get('receive date', 'No Data')
                if pd.isna(recv_date) or str(recv_date).strip() == '':
                    recv_date = 'No Data'
                    
                total_recv_raw = safe_row.get('total received qty', safe_row.get('total received', 0))
                try:
                    total_recv = int(float(total_recv_raw)) if not pd.isna(total_recv_raw) else 0
                except:
                    total_recv = 0
                    
                if not df_logs_db.empty and 'Item Given' in df_logs_db.columns:
                    distributed_df = df_logs_db[df_logs_db['Item Given'].astype(str).str.strip().str.lower() == item.lower()]
                    total_dist = len(distributed_df)
                else:
                    total_dist = 0
                    
                remaining = total_recv - total_dist
                status = str(safe_row.get('status', 'Active')).strip()
                display_status = "👁️ Active" if status.lower() != 'hidden' else "🙈 Hidden"
                
                summary_data.append({
                    "Item": item,
                    "Receive Date": recv_date, 
                    "Total Received": total_recv,
                    "Total Distributed": total_dist,
                    "Remaining Stock": remaining,
                    "App Status": display_status
                })
                
            summary_df = pd.DataFrame(summary_data)
            
            st.subheader("Current Stock Overview")
            st.dataframe(summary_df, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            
            if not summary_df.empty:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Remaining vs Distributed")
                    fig_bar = px.bar(
                        summary_df, 
                        x="Item", 
                        y=["Total Distributed", "Remaining Stock"], 
                        title="Inventory Breakdown by Item",
                        barmode="stack",
                        color_discrete_map={"Total Distributed": "#FF7F0E", "Remaining Stock": "#1F77B4"}
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)
                
                with col2:
                    st.subheader("Distribution Timeline")
                    if not df_logs_db.empty and 'Date' in df_logs_db.columns and 'Item Given' in df_logs_db.columns:
                        dist_trends = df_logs_db.groupby(['Date', 'Item Given']).size().reset_index(name='Items Distributed')
                        
                        dist_trends['Date_Obj'] = pd.to_datetime(dist_trends['Date'], format='%d-%m-%Y', errors='coerce')
                        dist_trends = dist_trends.sort_values(by='Date_Obj')
                        
                        fig_line = px.line(
                            dist_trends, 
                            x="Date", 
                            y="Items Distributed", 
                            color="Item Given", 
                            markers=True,
                            title="Daily Distributions"
                        )
                        st.plotly_chart(fig_line, use_container_width=True)
                    else:
                        st.info("Not enough distribution data to plot a timeline yet.")

    # ⚙️ ADMIN SETTINGS TAB
    with tab_admin:
        st.header("Distribution Configuration")
        st.write("Manage what items are currently visible to teachers in the Distribute Items tab.")
        st.info("💡 Deselecting an item here only hides it from the teachers. It remains safely in your Master Inventory and Dashboard!")
        
        new_active_items = st.multiselect(
            "Select items that teachers are allowed to distribute today:", 
            all_master_items, 
            default=teacher_active_items
        )
        
        if st.button("Save Settings", type="primary"):
            try:
                ws_settings = gc.open("BPS_Distribution_Log").worksheet("settings")
                
                with st.spinner("Updating status in Google Sheets..."):
                    col_a_values = ws_settings.col_values(1)
                    
                    status_updates = []
                    for i, item in enumerate(col_a_values):
                        if i == 0:
                            status_updates.append(["Status"]) 
                        else:
                            if str(item).strip() in new_active_items:
                                status_updates.append(["Active"])
                            else:
                                status_updates.append(["Hidden"])
                    
                    ws_settings.update(values=status_updates, range_name="D1")
                    
                st.success("Settings saved successfully! The app display has been updated.")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Error saving settings: {e}")

# ==========================================
# 5. FOOTER
# ==========================================
st.markdown("<br><br><br>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: gray; font-size: 14px;'>Developed by Sukhamay Kisku (H.M.)</p>", unsafe_allow_html=True)
