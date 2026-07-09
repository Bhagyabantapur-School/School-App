import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pytz
from datetime import datetime

# --- 1. AUTHENTICATION SETUP ---
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

try:
    credentials = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=scopes,
    )
    client = gspread.authorize(credentials)
except Exception as e:
    st.error(f"Authentication failed. Please check your Streamlit Secrets. Error: {e}")
    st.stop()

# --- 2. CONNECT TO THE SHEET & WORKSHEETS ---
SHEET_NAME = "APP UPDATE" 

try:
    sheet = client.open(SHEET_NAME)
    worksheet_update = sheet.worksheet("Update") 
    worksheet_common = sheet.worksheet("Common")
except Exception as e:
    st.error(f"Failed to connect to sheet or tabs. Details: {e}")
    st.stop()

# --- 3. SMART DATA CACHING (Prevents API Limits) ---
if "update_data" not in st.session_state:
    try:
        st.session_state.update_data = worksheet_update.get_all_values()
    except:
        st.session_state.update_data = []

def get_dropdown_options(column_index):
    if not st.session_state.update_data or len(st.session_state.update_data) <= 1:
        return []
    values = []
    for row in st.session_state.update_data[1:]:
        if len(row) > column_index:
            val = str(row[column_index]).strip()
            if val:
                values.append(val)
    return sorted(list(set(values))) 

def get_last_lines(app_name):
    if not app_name or app_name == "➕ Add New..." or not st.session_state.update_data:
        return 0
    for row in reversed(st.session_state.update_data):
        if len(row) > 7 and str(row[2]).strip() == app_name:
            try:
                return int(row[7])
            except (ValueError, TypeError):
                continue
    return 0

# --- 4. TIMEZONE CONFIGURATION ---
ist = pytz.timezone('Asia/Kolkata')
current_ist = datetime.now(ist)

# --- 5. STREAMLIT USER INTERFACE ---
st.title("BPS Digital - App & Feature Logger")
st.write("Submit new app updates or log reusable common features directly to the Google Sheet.")

tab1, tab2 = st.tabs(["🚀 Log App Update", "🧩 Log Common Feature"])

# ==========================================
# TAB 1: THE APP UPDATE LOGGER (Interactive Mode)
# ==========================================
with tab1:
    st.info("💡 Select an existing option from the dropdowns, or choose '➕ Add New...' to type a new one.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        date_input = st.date_input("Date", value=current_ist.date(), key="d_up")
        time_input = st.time_input("Time", value=current_ist.time(), step=60, key="t_up")
        
        app_sel = st.selectbox("App Name", ["➕ Add New..."] + get_dropdown_options(2))
        app_input = st.text_input("Type New App Name") if app_sel == "➕ Add New..." else app_sel
        
        details_input = st.text_area("Details of Update")
        
        ai_sel = st.selectbox("AI Used", ["➕ Add New..."] + get_dropdown_options(4))
        ai_input = st.text_input("Type New AI") if ai_sel == "➕ Add New..." else ai_sel
        
        ai_answer = st.text_area("AI Answer")
        
    with col2:
        short_sel = st.selectbox("Short Description", ["➕ Add New..."] + get_dropdown_options(6))
        short_input = st.text_input("Type New Short Description") if short_sel == "➕ Add New..." else short_sel
        
        default_lines = get_last_lines(app_input)
        lines_input = st.number_input("Lines of Code", min_value=0, step=1, value=default_lines)
        
        feat_sel = st.selectbox("Features Added", ["➕ Add New..."] + get_dropdown_options(8))
        features_input = st.text_input("Type New Feature") if feat_sel == "➕ Add New..." else feat_sel
        
        chat_sel = st.selectbox("Chat Reference / Link", ["➕ Add New..."] + get_dropdown_options(10))
        chat_input = st.text_input("Type New Chat Reference") if chat_sel == "➕ Add New..." else chat_sel
        
        gs_sel = st.selectbox("Google Sheet (Linked)", ["➕ Add New..."] + get_dropdown_options(11))
        gs_input = st.text_input("Type New Google Sheet Name") if gs_sel == "➕ Add New..." else gs_sel
        
        selected_ai = st.text_area("Selected AI Content (Paste the line here)")

    if st.button("Save Update to Google Sheet", type="primary"):
        row_data_update = [
            str(date_input),
            str(time_input.strftime("%H:%M:%S")),
            app_input,
            details_input,
            ai_input,
            ai_answer,       
            short_input,     
            lines_input,
            features_input,
            selected_ai,     
            chat_input,
            gs_input         
        ]
        
        try:
            worksheet_update.append_row(row_data_update)
            st.session_state.update_data.append(row_data_update) 
            st.success("Successfully logged the update to the 'Update' tab!")
        except Exception as e:
            st.error(f"An error occurred while saving: {e}")

# ==========================================
# TAB 2: THE COMMON FEATURE LOGGER (Standard Form)
# ==========================================
with tab2:
    with st.form("common_form", clear_on_submit=True):
        col3, col4 = st.columns(2)
        
        with col3:
            date_input_common = st.date_input("Date", value=current_ist.date(), key="d_com")
            time_input_common = st.time_input("Time", value=current_ist.time(), step=60, key="t_com") 
            common_feature = st.text_input("Common Feature Name")
            
            # --- NEW FIELD ADDED HERE ---
            ask_for_prompt = st.text_area("Ask for the Prompt (How you asked AI)")
            
        with col4:
            # Moved Prompt over to the right side to balance the layout perfectly 4 and 4
            prompt_input = st.text_area("Prompt (The resulting AI instruction)")
            used_in_app = st.text_input("Used in App (Where it was first used)")
            chat_input_common = st.text_input("Chat Name")
            use_in_other = st.text_area("Use in other app (Add names as you use this in the future)")

        if st.form_submit_button("Save Feature to Google Sheet"):
            # Ensure this perfectly matches your new 8-column layout in Google Sheets
            row_data_common = [
                str(date_input_common),
                str(time_input_common.strftime("%H:%M:%S")),
                common_feature,
                ask_for_prompt,  # Inserted in the 4th column
                prompt_input,
                used_in_app,
                chat_input_common,
                use_in_other
            ]
            try:
                worksheet_common.append_row(row_data_common)
                st.success("Successfully logged the feature to the 'Common' tab!")
            except Exception as e:
                st.error(f"An error occurred while saving: {e}")
