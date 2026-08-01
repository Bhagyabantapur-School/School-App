import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pytz
from datetime import datetime

# --- 1. CACHED AUTHENTICATION & CONNECTION SETUP ---
@st.cache_resource(show_spinner="Connecting to Google Sheets...")
def init_connection():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=scopes,
    )
    client = gspread.authorize(credentials)
    sheet = client.open("APP UPDATE")
    ws_update = sheet.worksheet("Update") 
    ws_common = sheet.worksheet("Common")
    return ws_update, ws_common

try:
    worksheet_update, worksheet_common = init_connection()
except Exception as e:
    st.error(f"Authentication or connection failed. Details: {e}")
    st.stop()


# --- 2. SMART DATA CACHING & HELPER FUNCTIONS ---
def pad_row(row, length=16):
    return row + [""] * (length - len(row))

if "update_data" not in st.session_state:
    try:
        raw_data = worksheet_update.get_all_values()
        st.session_state.update_data = [pad_row(r) for r in raw_data]
    except Exception as e:
        st.error(f"Failed to fetch Update data: {e}")
        st.session_state.update_data = []

if "common_data" not in st.session_state:
    try:
        st.session_state.common_data = worksheet_common.get_all_values()
    except Exception as e:
        st.error(f"Failed to fetch Common data: {e}")
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

def get_last_app_data(app_name):
    if not app_name or app_name == "➕ Add New..." or not st.session_state.update_data:
        return {"lines": 0, "ai": "", "chat": "", "sheet": ""}
    
    for row in reversed(st.session_state.update_data):
        if len(row) > 11 and str(row[2]).strip() == app_name and str(row[0]).strip() != "":
            try:
                lines = int(row[7]) if str(row[7]).strip() else 0
            except:
                lines = 0
            return {
                "lines": lines,
                "ai": str(row[4]).strip(),
                "chat": str(row[10]).strip(),
                "sheet": str(row[11]).strip()
            }
    return {"lines": 0, "ai": "", "chat": "", "sheet": ""}

# --- GITHUB-STYLE RELATIVE TIME LOGIC ---
def get_time_ago(date_str, time_str):
    if not date_str:
        return ""
    try:
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        
        if not time_str:
            time_str = "00:00:00"
            
        dt_str = f"{date_str.strip()} {time_str.strip()}"
        past_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        past_dt = ist.localize(past_dt)
        
        diff = now - past_dt
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            mins = int(seconds // 60)
            return f"{mins} minute{'s' if mins != 1 else ''} ago"
        elif seconds < 86400:
            hrs = int(seconds // 3600)
            return f"{hrs} hour{'s' if hrs != 1 else ''} ago"
        elif seconds < 604800:
            days = int(seconds // 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
        elif seconds < 2592000:
            weeks = int(seconds // 604800)
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        elif seconds < 31536000:
            months = int(seconds // 2592000)
            if months <= 1:
                return "last month"
            return f"{months} months ago"
        else:
            years = int(seconds // 31536000)
            return f"{years} year{'s' if years != 1 else ''} ago"
    except Exception:
        return "" 

# --- FORM CLEARING LOGIC ---
if "form_reset_counter" not in st.session_state:
    st.session_state.form_reset_counter = 0

def clear_form_fields():
    st.session_state.form_reset_counter += 1

fk = st.session_state.form_reset_counter 

# --- 3. TIMEZONE CONFIGURATION ---
ist = pytz.timezone('Asia/Kolkata')
current_ist = datetime.now(ist)

# --- GLOBAL CSS ---
st.markdown("""
    <style>
    div[data-testid="stExpander"] details:has(summary:contains("👑")) {
        background-color: #fffbeb; 
        border: 1px solid #fde68a;
        border-radius: 8px;
    }
    div[data-testid="stExpander"] details:has(summary:contains("👑")) summary {
        background-color: #fef3c7; 
        border-radius: 8px;
    }
    div[data-testid="stExpander"] details:has(summary:contains("🚨")) {
        background-color: #fff0f0; 
        border: 1px solid #ffcccc;
        border-radius: 8px;
    }
    div[data-testid="stExpander"] details:has(summary:contains("🚨")) summary {
        background-color: #ffe6e6; 
        border-radius: 8px;
    }
    div[data-testid="stExpander"] details:has(summary:contains("[main.py]")) {
        background-color: #f0f7ff; 
        border: 1px solid #cce3ff;
        border-radius: 8px;
    }
    div[data-testid="stExpander"] details:has(summary:contains("[main.py]")) summary {
        background-color: #e0f0ff; 
        border-radius: 8px;
    }
    div[data-testid="stExpander"] details:has(summary:contains("[app.py]")) {
        background-color: #f4fcfa; 
        border: 1px solid #ccebe1;
        border-radius: 8px;
    }
    div[data-testid="stExpander"] details:has(summary:contains("[app.py]")) summary {
        background-color: #e0f5ee; 
        border-radius: 8px;
    }
    div[data-testid="stSelectbox"]:has(label:contains("✨")) div[data-baseweb="select"],
    div[data-testid="stNumberInput"]:has(label:contains("✨")) div[data-baseweb="input"],
    div[data-testid="stTextInput"]:has(label:contains("✨")) div[data-baseweb="input"] {
        background-color: #f0f8ff !important;
        border: 1px solid #1890ff !important;
        border-left: 4px solid #1890ff !important;
        border-radius: 4px;
    }
    label:has(span:contains("✨")) {
        color: #1890ff !important;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)

# --- 4. STREAMLIT USER INTERFACE ---
st.title("BPS Digital - App & Feature Logger")
st.write("Manage app updates, record ideas, and track reusable common features.")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🚀 Log App Update", 
    "💡 Brainstorming Hub",
    "🧩 Log Common Feature", 
    "📊 View Updates", 
    "🛠️ Manage Common Features"
])

# ==========================================
# TAB 1: THE APP UPDATE LOGGER 
# ==========================================
with tab1:
    update_mode = st.radio("Choose Update Mode:", ["🚀 Direct Update", "✅ Complete Pending Idea"], horizontal=True, key=f"mode_{fk}")
    st.divider()

    target_sheet_row = None
    prefill_app, prefill_details, prefill_idea_date, prefill_idea_time = "➕ Add New...", "", "", ""
    prefill_ai, prefill_ai_ans, prefill_short = "", "", ""
    prefill_lines = 0
    prefill_feat, prefill_sel_ai, prefill_chat, prefill_gs = "", "", "", ""
    prefill_code = False

    if update_mode == "✅ Complete Pending Idea":
        pending_ideas = []
        for i, row in enumerate(st.session_state.update_data):
            if i > 0 and str(row[0]).strip() == "" and str(row[2]).strip() != "":
                pending_ideas.append((i, row))
        
        if not pending_ideas:
            st.info("🎉 No pending ideas found in the database!")
        else:
            opt_dict = {f"{r[2]} ({r[12]}) - {r[3][:40]}...": (i, r) for i, r in pending_ideas}
            selected_opt = st.selectbox("Select Pending Idea to Complete:", list(opt_dict.keys()), key=f"pend_sel_{fk}")
            
            sheet_row_index, idea_row_data = opt_dict[selected_opt]
            target_sheet_row = sheet_row_index + 1 
            
            prefill_app = idea_row_data[2]
            prefill_details = idea_row_data[3]
            prefill_ai = idea_row_data[4]
            prefill_ai_ans = idea_row_data[5]
            prefill_short = idea_row_data[6]
            prefill_lines = int(idea_row_data[7]) if str(idea_row_data[7]).strip().isdigit() else 0
            prefill_feat = idea_row_data[8]
            prefill_sel_ai = idea_row_data[9]
            prefill_chat = idea_row_data[10]
            prefill_gs = idea_row_data[11]
            prefill_idea_date = idea_row_data[12]
            prefill_idea_time = idea_row_data[13]
            prefill_code = True if len(idea_row_data) > 15 and str(idea_row_data[15]).upper() == "TRUE" else False
            
            st.info(f"Editing Idea from **{prefill_idea_date}**. Fill out the details below.")

    if update_mode == "🚀 Direct Update" or (update_mode == "✅ Complete Pending Idea" and target_sheet_row is not None):
        col1, col2 = st.columns(2)
        is_completing = (update_mode == "✅ Complete Pending Idea")
        
        with col1:
            date_input = st.date_input("Date", value=current_ist.date(), key=f"d_up_{fk}")
            time_input = st.time_input("Time", value=current_ist.time(), step=60, key=f"t_up_{fk}")
            
            if is_completing:
                app_input = st.text_input("App Name", value=prefill_app, disabled=True, key=f"app_in_dis_{fk}_{target_sheet_row}")
                app_key = f"pend_{target_sheet_row}"
            else:
                app_sel = st.selectbox("App Name", ["➕ Add New..."] + get_dropdown_options(2), key=f"app_sel_{fk}")
                app_input = st.text_input("Type New App Name", key=f"app_in_new_{fk}_{app_sel}") if app_sel == "➕ Add New..." else app_sel
                app_key = f"dir_{app_input}"
            
            details_input = st.text_area("Details of Update", value=prefill_details, key=f"det_{fk}_{app_key}")
            
            last_data = get_last_app_data(app_input)
            
            ai_opts = ["➕ Add New..."] + get_dropdown_options(4)
            ai_def = prefill_ai if (is_completing and prefill_ai) else last_data["ai"]
            ai_sel_lbl = "AI Used ✨ (Pending Data)" if (is_completing and prefill_ai) else ("AI Used ✨ (Last updated)" if ai_def else "AI Used")
            
            ai_sel = st.selectbox(ai_sel_lbl, ai_opts, index=0, key=f"ai_sel_{fk}_{app_key}")
            if ai_sel == "➕ Add New...":
                t_lbl = "Type New AI ✨" if ai_def else "Type New AI"
                ai_input = st.text_input(t_lbl, value=ai_def, key=f"ai_in_new_{fk}_{app_key}")
            else:
                ai_input = ai_sel
            
            ai_answer = st.text_area("AI Answer", value=prefill_ai_ans if is_completing else "", key=f"ai_ans_{fk}_{app_key}")
            contain_code = st.checkbox("💻 Contain Code", value=prefill_code if is_completing else False, key=f"contain_code_{fk}_{app_key}")
            
        with col2:
            short_opts = ["➕ Add New..."] + get_dropdown_options(6)
            short_sel = st.selectbox("Short Description", short_opts, index=0, key=f"sh_sel_{fk}_{app_key}")
            if short_sel == "➕ Add New...":
                short_input = st.text_input("Type New Short Description", value=prefill_short if is_completing else "", key=f"sh_in_new_{fk}_{app_key}")
            else:
                short_input = short_sel
            
            lines_def = prefill_lines if (is_completing and prefill_lines > 0) else last_data["lines"]
            lines_lbl = "Lines of Code ✨ (Pending Data)" if (is_completing and prefill_lines > 0) else ("Lines of Code ✨ (Last updated)" if lines_def > 0 else "Lines of Code")
            lines_input = st.number_input(lines_lbl, min_value=0, step=1, value=lines_def, key=f"lines_{fk}_{app_key}")
            
            feat_opts = ["➕ Add New..."] + get_dropdown_options(8)
            feat_sel = st.selectbox("Features Added", feat_opts, index=0, key=f"feat_sel_{fk}_{app_key}")
            if feat_sel == "➕ Add New...":
                features_input = st.text_input("Type New Feature", value=prefill_feat if is_completing else "", key=f"feat_in_new_{fk}_{app_key}")
            else:
                features_input = feat_sel
            
            chat_opts = ["➕ Add New..."] + get_dropdown_options(10)
            chat_def = prefill_chat if (is_completing and prefill_chat) else last_data["chat"]
            chat_sel_lbl = "Chat Reference / Link ✨ (Pending Data)" if (is_completing and prefill_chat) else ("Chat Reference / Link ✨ (Last updated)" if chat_def else "Chat Reference / Link")
            
            chat_sel = st.selectbox(chat_sel_lbl, chat_opts, index=0, key=f"chat_sel_{fk}_{app_key}")
            if chat_sel == "➕ Add New...":
                t_lbl = "Type New Chat Reference ✨" if chat_def else "Type New Chat Reference"
                chat_input = st.text_input(t_lbl, value=chat_def, key=f"chat_in_new_{fk}_{app_key}")
            else:
                chat_input = chat_sel
            
            gs_opts = ["➕ Add New..."] + get_dropdown_options(11)
            gs_def = prefill_gs if (is_completing and prefill_gs) else last_data["sheet"]
            gs_sel_lbl = "Google Sheet (Linked) ✨ (Pending Data)" if (is_completing and prefill_gs) else ("Google Sheet (Linked) ✨ (Last updated)" if gs_def else "Google Sheet (Linked)")
            
            gs_sel = st.selectbox(gs_sel_lbl, gs_opts, index=0, key=f"gs_sel_{fk}_{app_key}")
            if gs_sel == "➕ Add New...":
                t_lbl = "Type New Google Sheet Name ✨" if gs_def else "Type New Google Sheet Name"
                gs_input = st.text_input(t_lbl, value=gs_def, key=f"gs_in_new_{fk}_{app_key}")
            else:
                gs_input = gs_sel
            
            selected_ai = st.text_area("Selected AI Content (Paste the line here)", value=prefill_sel_ai if is_completing else "", key=f"sel_ai_{fk}_{app_key}")

        st.divider()
        
        existing_category = ""
        if app_input and app_input != "➕ Add New...":
            for r in st.session_state.update_data:
                if str(r[2]).strip() == app_input and len(r) > 14 and str(r[14]).strip() != "":
                    existing_category = str(r[14]).strip()
                    break
        
        col15_value = ""
        
        if existing_category:
            disp_cat = "Main App (Legacy Data)" if existing_category.upper() == "TRUE" else existing_category
            
            file_assoc = ""
            if existing_category in ["Personal Hub", "BPS Digital System"] or existing_category.upper() == "TRUE":
                file_assoc = " ⚙️ [main.py]"
            elif existing_category == "App":
                file_assoc = " 📱 [app.py]"
                
            st.checkbox(f"✅ Added to: **{disp_cat}**{file_assoc}", value=True, disabled=True, key=f"main_chk_dis_{fk}_{app_key}")
            col15_value = existing_category  
        else:
            add_to_main = st.checkbox("➕ Mark as 'Added to Main App' for this update?", key=f"main_chk_{fk}_{app_key}")
            if add_to_main:
                selected_category = st.selectbox("App Category", ["Personal Hub", "BPS Digital System", "App"], key=f"cat_sel_{fk}_{app_key}")
                col15_value = selected_category

        st.write("") 
        btn_col1, btn_col2 = st.columns([1, 5])
        
        with btn_col1:
            btn_text = "Update Pending Idea" if update_mode == "✅ Complete Pending Idea" else "Save Update to Sheet"
            submit_clicked = st.button(btn_text, type="primary")
            
        with btn_col2:
            st.button("🔄 Clear Fields", on_click=clear_form_fields, help="Reset all fields on this tab")
        
        if submit_clicked:
            contain_code_str = "TRUE" if contain_code else ""
            
            row_data_update = [
                str(date_input), str(time_input.strftime("%H:%M:%S")), app_input, details_input,
                ai_input, ai_answer, short_input, lines_input, features_input, selected_ai, chat_input, gs_input,
                prefill_idea_date, prefill_idea_time, col15_value, contain_code_str 
            ]
            
            try:
                if update_mode == "✅ Complete Pending Idea":
                    worksheet_update.update(values=[row_data_update], range_name=f"A{target_sheet_row}:P{target_sheet_row}")
                    st.session_state.update_data[target_sheet_row - 1] = row_data_update
                    st.success("Successfully completed and updated the pending idea!")
                else:
                    worksheet_update.append_row(row_data_update)
                    st.session_state.update_data.append(row_data_update) 
                    st.success("Successfully logged the new update!")
            except Exception as e:
                st.error(f"An error occurred while saving: {e}")

# ==========================================
# TAB 2: BRAINSTORMING HUB
# ==========================================
with tab2:
    st.subheader("💡 Log a New Idea")
    
    app_sel_idea = st.selectbox("App Name", ["➕ Add New..."] + get_dropdown_options(2), key="app_idea")
    app_input_idea = st.text_input("Type New App Name", key="app_idea_new") if app_sel_idea == "➕ Add New..." else app_sel_idea
    idea_details = st.text_area("Record your idea (Saved as 'Details of Update')")
    
    # --- NEW: Fetch last chat default dynamically based on app selection ---
    last_idea_data = get_last_app_data(app_sel_idea)
    default_chat_val = last_idea_data["chat"]
    
    chat_opts_idea = ["No Chat Yet", "➕ Add New..."] + get_dropdown_options(10)
    
    # If app is selected and has a previous chat, figure out its position in the list
    default_chat_idx = 0 
    if app_sel_idea != "➕ Add New..." and default_chat_val and default_chat_val in chat_opts_idea:
        default_chat_idx = chat_opts_idea.index(default_chat_val)
        
    chat_sel_idea = st.selectbox(
        "Chat Reference / Link (Select to unlock advanced fields)", 
        chat_opts_idea, 
        index=default_chat_idx, 
        key="chat_sel_idea"
    )
    
    if chat_sel_idea == "➕ Add New...":
        chat_input_idea = st.text_input("Type New Chat Reference", key="chat_in_new_idea")
    elif chat_sel_idea == "No Chat Yet":
        chat_input_idea = ""
    else:
        chat_input_idea = chat_sel_idea
        
    ai_input_idea, ai_answer_idea, short_input_idea = "", "", ""
    lines_input_idea, features_input_idea, gs_input_idea = 0, "", ""
    selected_ai_idea, contain_code_idea = "", False
    
    if chat_input_idea:
        st.info("💡 Chat detected! You can optionally fill the remaining details below before saving to pending.")
        col1_i, col2_i = st.columns(2)
        
        last_data_idea = get_last_app_data(app_input_idea)
        
        with col1_i:
            ai_opts_i = ["➕ Add New..."] + get_dropdown_options(4)
            ai_def_i = last_data_idea["ai"]
            ai_sel_lbl_i = "AI Used ✨ (Last updated)" if ai_def_i else "AI Used"
            
            ai_sel_i = st.selectbox(ai_sel_lbl_i, ai_opts_i, index=0, key="ai_sel_idea_adv")
            if ai_sel_i == "➕ Add New...":
                t_lbl = "Type New AI ✨" if ai_def_i else "Type New AI"
                ai_input_idea = st.text_input(t_lbl, value=ai_def_i, key="ai_in_new_idea_adv")
            else:
                ai_input_idea = ai_sel_i
            
            ai_answer_idea = st.text_area("AI Answer", key="ai_ans_idea_adv")
            contain_code_idea = st.checkbox("💻 Contain Code", key="contain_code_idea_adv")
            
        with col2_i:
            short_sel_i = st.selectbox("Short Description", ["➕ Add New..."] + get_dropdown_options(6), key="sh_sel_idea_adv")
            short_input_idea = st.text_input("Type New Short Description", key="sh_in_new_idea_adv") if short_sel_i == "➕ Add New..." else short_sel_i
            
            lines_def_i = last_data_idea["lines"]
            lines_lbl_i = "Lines of Code ✨ (Last updated)" if lines_def_i > 0 else "Lines of Code"
            lines_input_idea = st.number_input(lines_lbl_i, min_value=0, step=1, value=lines_def_i, key="lines_idea_adv")
            
            feat_sel_i = st.selectbox("Features Added", ["➕ Add New..."] + get_dropdown_options(8), key="feat_sel_idea_adv")
            features_input_idea = st.text_input("Type New Feature", key="feat_in_new_idea_adv") if feat_sel_i == "➕ Add New..." else feat_sel_i
            
            gs_opts_i = ["➕ Add New..."] + get_dropdown_options(11)
            gs_def_i = last_data_idea["sheet"]
            gs_sel_lbl_i = "Google Sheet (Linked) ✨ (Last updated)" if gs_def_i else "Google Sheet (Linked)"
            
            gs_sel_i = st.selectbox(gs_sel_lbl_i, gs_opts_i, index=0, key="gs_sel_idea_adv")
            if gs_sel_i == "➕ Add New...":
                t_lbl = "Type New Google Sheet Name ✨" if gs_def_i else "Type New Google Sheet Name"
                gs_input_idea = st.text_input(t_lbl, value=gs_def_i, key="gs_in_new_idea_adv")
            else:
                gs_input_idea = gs_sel_i
            
            selected_ai_idea = st.text_area("Selected AI Content (Paste the line here)", key="sel_ai_idea_adv")

    if st.button("Save Idea to Pending List", type="primary"):
        contain_code_str_idea = "TRUE" if contain_code_idea else ""
        row_data_idea = [
            "", "", app_input_idea, idea_details, ai_input_idea, ai_answer_idea, short_input_idea, 
            lines_input_idea, features_input_idea, selected_ai_idea, chat_input_idea, gs_input_idea, 
            str(current_ist.date()), str(current_ist.strftime("%H:%M:%S")), "", contain_code_str_idea 
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
# TAB 4: VIEW UPDATES BY APP 
# ==========================================
with tab4:
    st.subheader("App Update History")
    
    if len(st.session_state.update_data) > 1:
        completed_records = [r for r in st.session_state.update_data[1:] if str(r[0]).strip() != ""]
        
        app_groups = {}
        for row in completed_records:
            app_name = str(row[2]).strip()
            if app_name not in app_groups:
                app_groups[app_name] = []
            app_groups[app_name].append(row)
            
        def custom_app_sort(item):
            name = item[0].lower()
            if name == "main.py":
                return (0, name)
            elif name == "app.py":
                return (1, name)
            return (2, name)
                
        for app_name, logs in sorted(app_groups.items(), key=custom_app_sort):
            
            is_base_file = app_name.lower() in ["main.py", "app.py"]
            
            app_category = ""
            for r in st.session_state.update_data:
                if str(r[2]).strip() == app_name and len(r) > 14 and str(r[14]).strip() != "":
                    app_category = str(r[14]).strip()
                    break
            
            if is_base_file:
                title = f"👑 🏗️ BASE SYSTEM: {app_name} ({len(logs)} updates)"
            elif app_category:
                disp_cat = "Main App" if app_category.upper() == "TRUE" else app_category
                
                file_badge = ""
                if app_category in ["Personal Hub", "BPS Digital System"] or app_category.upper() == "TRUE":
                    file_badge = " ⚙️ [main.py]"
                elif app_category == "App":
                    file_badge = " 📱 [app.py]"
                    
                title = f"✅ 📱 {app_name} ({len(logs)} updates)  —  🗂️ {disp_cat}{file_badge}"
            else:
                title = f"🚨 📱 {app_name} ({len(logs)} updates)"
            
            logs.sort(key=lambda x: f"{str(x[0]).strip()} {str(x[1]).strip()}" if len(x) > 1 else "", reverse=True)
            
            with st.expander(title):
                for log in logs: 
                    date_val = log[0] if len(log) > 0 else ""
                    time_val = log[1] if len(log) > 1 else ""
                    
                    time_ago_str = get_time_ago(date_val, time_val)
                    date_display = f"{date_val} *({time_ago_str})*" if time_ago_str else date_val
                    
                    details_val = log[3] if len(log) > 3 else ""
                    ai_val = log[4] if len(log) > 4 else ""
                    ai_answer_val = log[5] if len(log) > 5 else ""
                    short_desc = log[6] if len(log) > 6 else ""
                    lines_val = log[7] if len(log) > 7 else ""
                    features_added = log[8] if len(log) > 8 else ""
                    selected_ai_val = log[9] if len(log) > 9 else ""
                    chat_val = log[10] if len(log) > 10 else ""
                    gs_val = log[11] if len(log) > 11 else ""
                    contain_code_val = log[15] if len(log) > 15 else ""
                    
                    st.markdown(f"**Date:** {date_display} &nbsp;|&nbsp; **Lines:** {lines_val}")
                    
                    if features_added:
                        st.markdown(f"🚀 **Features:** {features_added}")
                        
                    if short_desc:
                        st.caption(f"**Short:** {short_desc}")
                    
                    meta_info = []
                    if contain_code_val.upper() == "TRUE":
                        meta_info.append("💻 **Contains Code**")
                        
                    if ai_val: meta_info.append(f"**AI:** {ai_val}") 
                    if chat_val: meta_info.append(f"**Chat:** {chat_val}")
                    if gs_val: meta_info.append(f"**Google Sheet:** {gs_val}")
                    
                    if meta_info:
                        st.markdown(" &nbsp;|&nbsp; ".join(meta_info))
                        
                    if details_val or ai_answer_val or selected_ai_val:
                        with st.expander("📝 View Full Details & AI Output"):
                            if details_val:
                                st.markdown("**Details of Update:**")
                                st.write(details_val)
                            
                            if ai_answer_val:
                                st.markdown("**AI Answer:**")
                                st.write(ai_answer_val)
                                
                            if selected_ai_val:
                                st.markdown("**Selected from AI:**")
                                st.write(selected_ai_val)

                    st.divider()
    else:
        st.info("No app updates logged yet.")

# ==========================================
# TAB 5: MANAGE COMMON FEATURES
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
