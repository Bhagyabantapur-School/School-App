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
# Helper function to ensure rows always have 14 columns to prevent indexing errors
def pad_row(row, length=14):
    return row + [""] * (length - len(row))

if "update_data" not in st.session_state:
    try:
        raw_data = worksheet_update.get_all_values()
        st.session_state.update_data = [pad_row(r) for r in raw_data]
    except:
        st.session_state.update_data = []

if "common_data" not in st.session_state:
    try:
        st.session_state.common_data = worksheet_common.get_all_values()
    except:
        st.session_state.common_data = []

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
st.write("Manage app updates, record ideas, and track reusable common features.")

# Expanded to 5 Tabs!
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🚀 Log App Update", 
    "💡 Brainstorming Hub",
    "🧩 Log Common Feature", 
    "📊 View Updates", 
    "🛠️ Manage Common Features"
])

# ==========================================
# TAB 1: THE APP UPDATE LOGGER (Handles Direct & Pending Ideas)
# ==========================================
with tab1:
    update_mode = st.radio(
        "Choose Update Mode:", 
        ["🚀 Direct Update", "✅ Complete Pending Idea"], 
        horizontal=True
    )
    st.divider()

    # Variables to hold pre-filled data if completing an idea
    target_sheet_row = None
    prefill_app = "➕ Add New..."
    prefill_details = ""
    prefill_idea_date = ""
    prefill_idea_time = ""

    if update_mode == "✅ Complete Pending Idea":
        # Find all rows where 'Date' (index 0) is empty, but 'App' (index 2) has text
        pending_ideas = []
        for i, row in enumerate(st.session_state.update_data):
            if i > 0 and str(row[0]).strip() == "" and str(row[2]).strip() != "":
                pending_ideas.append((i, row))
        
        if not pending_ideas:
            st.info("🎉 No pending ideas found in the database!")
        else:
            opt_dict = {f"{r[2]} ({r[12]}) - {r[3][:40]}...": (i, r) for i, r in pending_ideas}
            selected_opt = st.selectbox("Select Pending Idea to Complete:", list(opt_dict.keys()))
            
            # Extract the specific row data
            sheet_row_index, idea_row_data = opt_dict[selected_opt]
            target_sheet_row = sheet_row_index + 1 # +1 for 1-indexed Google Sheets
            
            prefill_app = idea_row_data[2]
            prefill_details = idea_row_data[3]
            prefill_idea_date = idea_row_data[12]
            prefill_idea_time = idea_row_data[13]
            
            st.info(f"Editing Idea from **{prefill_idea_date}**. Fill out the rest of the details below.")

    # Only show form if it's direct update OR (completing idea AND pending ideas exist)
    if update_mode == "🚀 Direct Update" or (update_mode == "✅ Complete Pending Idea" and target_sheet_row is not None):
        col1, col2 = st.columns(2)
        
        with col1:
            date_input = st.date_input("Date", value=current_ist.date(), key="d_up")
            time_input = st.time_input("Time", value=current_ist.time(), step=60, key="t_up")
            
            if update_mode == "✅ Complete Pending Idea":
                app_input = st.text_input("App Name", value=prefill_app, disabled=True)
            else:
                app_sel = st.selectbox("App Name", ["➕ Add New..."] + get_dropdown_options(2))
                app_input = st.text_input("Type New App Name") if app_sel == "➕ Add New..." else app_sel
            
            details_input = st.text_area("Details of Update", value=prefill_details)
            
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

        btn_text = "Update Pending Idea in Google Sheet" if update_mode == "✅ Complete Pending Idea" else "Save Update to Google Sheet"
        
        if st.button(btn_text, type="primary"):
            row_data_update = [
                str(date_input), str(time_input.strftime("%H:%M:%S")), app_input, details_input,
                ai_input, ai_answer, short_input, lines_input, features_input, selected_ai, chat_input, gs_input,
                prefill_idea_date, prefill_idea_time # Columns 13 & 14 (will remain blank for Direct Updates)
            ]
            
            try:
                if update_mode == "✅ Complete Pending Idea":
                    # Overwrite the exact row instead of appending
                    worksheet_update.update(values=[row_data_update], range_name=f"A{target_sheet_row}:N{target_sheet_row}")
                    st.session_state.update_data[target_sheet_row - 1] = row_data_update
                    st.success("Successfully completed and updated the pending idea!")
                else:
                    worksheet_update.append_row(row_data_update)
                    st.session_state.update_data.append(row_data_update) 
                    st.success("Successfully logged the new update!")
                
            except Exception as e:
                st.error(f"An error occurred while saving: {e}")

# ==========================================
# TAB 2: BRAINSTORMING HUB (New Ideas)
# ==========================================
with tab2:
    st.subheader("💡 Log a New Idea")
    
    app_sel_idea = st.selectbox("App Name", ["➕ Add New..."] + get_dropdown_options(2), key="app_idea")
    app_input_idea = st.text_input("Type New App Name", key="app_idea_new") if app_sel_idea == "➕ Add New..." else app_sel_idea
    
    idea_details = st.text_area("Record your idea (Saved as 'Details of Update')")
    
    if st.button("Save Idea to Pending List", type="primary"):
        # Leaves columns 1-12 blank (except app and details), fills 13-14 with Idea Date/Time
        row_data_idea = [
            "", "", app_input_idea, idea_details, "", "", "", "", "", "", "", "", 
            str(current_ist.date()), str(current_ist.strftime("%H:%M:%S"))
        ]
        try:
            worksheet_update.append_row(row_data_idea)
            st.session_state.update_data.append(row_data_idea)
            st.success("Idea successfully added to the Pending List!")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to log idea: {e}")

    st.divider()
    st.subheader("📝 Pending Ideas")
    
    if len(st.session_state.update_data) > 1:
        has_pending = False
        for row in reversed(st.session_state.update_data[1:]):
            if str(row[0]).strip() == "" and str(row[2]).strip() != "":
                has_pending = True
                with st.expander(f"📱 {row[2]} | Added: {row[12]} at {row[13]}"):
                    st.markdown(f"**Idea:** {row[3]}")
        if not has_pending:
            st.info("No pending ideas at the moment. Great job!")

# ==========================================
# TAB 3: THE COMMON FEATURE LOGGER 
# ==========================================
with tab3:
    with st.form("common_form", clear_on_submit=True):
        col3, col4 = st.columns(2)
        
        with col3:
            date_input_common = st.date_input("Date", value=current_ist.date(), key="d_com")
            time_input_common = st.time_input("Time", value=current_ist.time(), step=60, key="t_com") 
            common_feature = st.text_input("Common Feature Name")
            ask_for_prompt = st.text_area("Ask for the Prompt (How you asked AI)")
            
        with col4:
            prompt_input = st.text_area("Prompt (The resulting AI instruction)")
            used_in_app = st.text_input("Used in App (Where it was first used)")
            chat_input_common = st.text_input("Chat Name")
            use_in_other = st.text_area("Use in other app (Add names as you use this in the future)")

        if st.form_submit_button("Save Feature to Google Sheet"):
            row_data_common = [
                str(date_input_common), str(time_input_common.strftime("%H:%M:%S")),
                common_feature, ask_for_prompt, prompt_input, used_in_app, chat_input_common, use_in_other
            ]
            try:
                worksheet_common.append_row(row_data_common)
                st.session_state.common_data.append(row_data_common)
                st.success("Successfully logged the feature to the 'Common' tab!")
            except Exception as e:
                st.error(f"An error occurred while saving: {e}")

# ==========================================
# TAB 4: VIEW UPDATES BY APP (Grouped Layout)
# ==========================================
with tab4:
    st.subheader("App Update History")
    
    if len(st.session_state.update_data) > 1:
        # Filter OUT pending ideas so they don't show up in completed updates
        completed_records = [r for r in st.session_state.update_data[1:] if str(r[0]).strip() != ""]
        
        app_groups = {}
        for row in completed_records:
            app_name = str(row[2]).strip()
            if app_name not in app_groups:
                app_groups[app_name] = []
            app_groups[app_name].append(row)
                
        for app_name, logs in sorted(app_groups.items()):
            with st.expander(f"📱 {app_name} ({len(logs)} updates)"):
                for log in reversed(logs): 
                    date_val = log[0]
                    features_added = log[8]
                    short_desc = log[6] if len(log) > 6 else ""
                    
                    st.markdown(f"**Date:** {date_val} | **Features:** {features_added}")
                    if short_desc:
                        st.caption(f"**Short:** {short_desc}")
                    st.divider()
    else:
        st.info("No app updates logged yet.")

# ==========================================
# TAB 5: MANAGE COMMON FEATURES (Editable Layout)
# ==========================================
with tab5:
    st.subheader("Manage Common Features")
    st.write("Click on a feature to update where it is being used.")
    
    if len(st.session_state.common_data) > 1:
        records = st.session_state.common_data[1:]
        
        for index, row in enumerate(records):
            if len(row) > 7:
                sheet_row = index + 2 
                feature_name = str(row[2]).strip()
                current_apps = str(row[7]).strip()
                
                with st.expander(f"🧩 {feature_name}"):
                    st.markdown(f"**Original Prompt:** {row[4]}")
                    st.markdown(f"**First used in:** `{row[5]}`")
                    
                    with st.form(key=f"edit_common_{sheet_row}"):
                        new_apps = st.text_area(
                            "Use in other app (Update list here)", 
                            value=current_apps, 
                            help="Add or edit the names of apps using this feature."
                        )
                        
                        if st.form_submit_button("Update App List"):
                            try:
                                worksheet_common.update_cell(sheet_row, 8, new_apps)
                                st.session_state.common_data[sheet_row - 1][7] = new_apps
                                st.success("Updated successfully!")
                                st.rerun() 
                            except Exception as e:
                                st.error(f"Failed to update Google Sheet: {e}")
    else:
        st.info("No common features logged yet.")
