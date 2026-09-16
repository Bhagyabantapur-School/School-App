import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pytz
from datetime import datetime
import re
from spellchecker import SpellChecker

st.set_page_config(page_title="My Notes", page_icon="📝", layout="centered")

# --- 1. CACHED AUTHENTICATION & CONNECTION SETUP ---
@st.cache_resource(show_spinner="Connecting to NOTE APP Sheet...")
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
    sheet = client.open("NOTE APP")
    ws_notes = sheet.worksheet("Notes") 
    return ws_notes

try:
    ws_notes = init_connection()
except Exception as e:
    st.error(f"Connection failed. Please ensure the sheet is named exactly 'NOTE APP' and the service account is invited. Details: {e}")
    st.stop()

# --- 2. SPELLCHECKER ENGINE ---
@st.cache_resource(show_spinner="Loading dictionary...")
def init_spellchecker():
    spell = SpellChecker()
    spell.word_frequency.load_words([
        'nep', 'pedagogy', 'streamlit', 'pandas', 'jio', 'jiopc', 
        'bhagyabantapur', 'khanjanchak'
    ]) 
    return spell

spell = init_spellchecker()

def check_spelling(text):
    """Returns a dictionary of {typo: suggested_correction}"""
    if not text:
        return {}
    words = re.findall(r'\b[a-zA-Z]+\b', text)
    misspelled = spell.unknown(words)
    typo_details = {}
    for word in misspelled:
        typo_details[word] = spell.correction(word)
    return typo_details

def apply_fixes(text, typos_dict):
    """Automatically replaces typos with their suggestions in the text."""
    corrected_text = text
    for typo, suggestion in typos_dict.items():
        if suggestion:
            corrected_text = re.sub(rf'\b{typo}\b', suggestion, corrected_text, flags=re.IGNORECASE)
    return corrected_text

# --- 3. SMART DATA CACHING ---
def fetch_notes():
    raw_data = ws_notes.get_all_values()
    padded_data = [row + [""] * (6 - len(row)) for row in raw_data]
    return padded_data

if "note_data" not in st.session_state:
    try:
        st.session_state.note_data = fetch_notes()
    except Exception as e:
        st.error(f"Failed to fetch Notes data: {e}")
        st.session_state.note_data = []

st.session_state.note_data = [row + [""] * (6 - len(row)) for row in st.session_state.note_data]

def get_categories():
    if len(st.session_state.note_data) <= 1:
        return ["General", "Work", "Ideas", "Personal", "Training"]
    categories = [str(row[3]).strip() for row in st.session_state.note_data[1:] if str(row[3]).strip()]
    default_cats = ["General", "Work", "Ideas", "Personal", "Training"]
    return sorted(list(set(categories + default_cats)))

ist = pytz.timezone('Asia/Kolkata')
current_ist = datetime.now(ist)

# --- GLOBAL CSS ---
st.markdown("""
    <style>
    .note-meta { font-size: 0.85em; color: #666; margin-bottom: 8px; }
    .planned-context {
        background-color: #e3f2fd; padding: 15px; border-radius: 8px;
        border-left: 5px solid #2196f3; margin-bottom: 20px; font-size: 15px; line-height: 1.6;
    }
    </style>
""", unsafe_allow_html=True)

# --- 4. USER INTERFACE ---
st.title("📝 My Quick Notes")

tab_view, tab_add, tab_plan, tab_live = st.tabs(["📚 View Notes", "➕ Quick Note", "🗓️ Plan Training", "🎙️ Live Notes"])

# ==========================================
# TAB 1: VIEW, EDIT & SEARCH NOTES
# ==========================================
with tab_view:
    search_query = st.text_input("🔍 Search completed notes by title, category, or content...")
    st.divider()
    
    if len(st.session_state.note_data) > 1:
        all_notes = []
        for idx, row in enumerate(st.session_state.note_data):
            if idx == 0: continue 
            if len(row) <= 5 or str(row[5]).strip() != "Planned":
                all_notes.append((idx, row))
                
        all_notes = list(reversed(all_notes)) 
        
        if search_query:
            query = search_query.lower()
            filtered_notes = [
                (orig_idx, n) for (orig_idx, n) in all_notes 
                if query in str(n[2]).lower() or query in str(n[3]).lower() or query in str(n[4]).lower()
            ]
        else:
            filtered_notes = all_notes
            
        if not filtered_notes:
            st.info("No completed notes found matching your search.")
        else:
            for orig_idx, note in filtered_notes:
                sheet_row = orig_idx + 1 
                date_val, time_val, title_val, category_val, content_val = note[0], note[1], note[2], note[3], note[4]
                
                with st.expander(f"📌 {title_val}  —  🏷️ {category_val}"):
                    st.markdown(f"<div class='note-meta'>🕒 {date_val} at {time_val}</div>", unsafe_allow_html=True)
                    
                    read_tab, edit_tab = st.tabs(["📖 Read", "✏️ Edit / Delete"])
                    
                    with read_tab:
                        st.write(content_val)
                        
                    with edit_tab:
                        # Ensure state keys exist
                        if f"title_{orig_idx}" not in st.session_state:
                            st.session_state[f"title_{orig_idx}"] = title_val
                        if f"content_{orig_idx}" not in st.session_state:
                            st.session_state[f"content_{orig_idx}"] = content_val
                        if f"typos_{orig_idx}" not in st.session_state:
                            st.session_state[f"typos_{orig_idx}"] = {}

                        edit_title = st.text_input("Edit Title", key=f"title_{orig_idx}")
                        edit_content = st.text_area("Edit Content", key=f"content_{orig_idx}", height=150)
                        
                        col_save, col_del = st.columns(2)
                        with col_save:
                            if st.button("💾 Update Note", key=f"update_{orig_idx}", type="primary", use_container_width=True):
                                typos = check_spelling(st.session_state[f"content_{orig_idx}"])
                                if typos:
                                    st.session_state[f"typos_{orig_idx}"] = typos
                                    st.rerun()
                                else:
                                    # Execute Update
                                    update_vals = [[st.session_state[f"title_{orig_idx}"], category_val, st.session_state[f"content_{orig_idx}"]]]
                                    try:
                                        ws_notes.update(range_name=f"C{sheet_row}:E{sheet_row}", values=update_vals, value_input_option="USER_ENTERED")
                                    except TypeError:
                                        ws_notes.update(f"C{sheet_row}:E{sheet_row}", update_vals, value_input_option="USER_ENTERED")
                                    st.session_state.pop('note_data', None)
                                    st.rerun()
                                    
                        with col_del:
                            if st.button("🗑️ Delete Note", key=f"delete_{orig_idx}", use_container_width=True):
                                ws_notes.delete_row(sheet_row)
                                st.session_state.pop('note_data', None)
                                st.rerun()
                                
                        # Edit Warning Gate
                        if st.session_state[f"typos_{orig_idx}"]:
                            warning_msg = "**Hold on! Potential typos detected:**\n"
                            for typo, suggestion in st.session_state[f"typos_{orig_idx}"].items():
                                warning_msg += f"- `{typo}` *(Did you mean: **{suggestion}**?)*\n"
                            st.warning(warning_msg)
                            
                            c1, c2 = st.columns(2)
                            with c1:
                                if st.button("🪄 Fix Typos & Update", key=f"fix_{orig_idx}", type="primary", use_container_width=True):
                                    # Fix text, update sheets, clear warnings
                                    fixed = apply_fixes(st.session_state[f"content_{orig_idx}"], st.session_state[f"typos_{orig_idx}"])
                                    update_vals = [[st.session_state[f"title_{orig_idx}"], category_val, fixed]]
                                    try:
                                        ws_notes.update(range_name=f"C{sheet_row}:E{sheet_row}", values=update_vals, value_input_option="USER_ENTERED")
                                    except TypeError:
                                        ws_notes.update(f"C{sheet_row}:E{sheet_row}", update_vals, value_input_option="USER_ENTERED")
                                    st.session_state.pop('note_data', None)
                                    st.session_state[f"typos_{orig_idx}"] = {}
                                    st.rerun()
                            with c2:
                                if st.button("✅ Ignore & Update", key=f"ignore_{orig_idx}", use_container_width=True):
                                    update_vals = [[st.session_state[f"title_{orig_idx}"], category_val, st.session_state[f"content_{orig_idx}"]]]
                                    try:
                                        ws_notes.update(range_name=f"C{sheet_row}:E{sheet_row}", values=update_vals, value_input_option="USER_ENTERED")
                                    except TypeError:
                                        ws_notes.update(f"C{sheet_row}:E{sheet_row}", update_vals, value_input_option="USER_ENTERED")
                                    st.session_state.pop('note_data', None)
                                    st.session_state[f"typos_{orig_idx}"] = {}
                                    st.rerun()
    else:
        st.info("No notes saved yet. Create a Quick Note or complete a Training!")

# ==========================================
# TAB 2: ADD QUICK NOTE
# ==========================================
with tab_add:
    if "quick_typos" not in st.session_state:
        st.session_state.quick_typos = {}

    note_title = st.text_input("Note Title*", placeholder="Enter a clear title...", key="quick_title")
    
    col1, col2 = st.columns(2)
    with col1:
        cat_opts = get_categories() + ["➕ Add New..."]
        cat_sel = st.selectbox("Category", cat_opts, key="quick_cat")
    with col2:
        cat_new = st.text_input("Type New Category", disabled=(cat_sel != "➕ Add New..."), key="quick_new_cat")
        
    note_content = st.text_area("Note Content*", height=200, placeholder="Write your note here...", key="quick_content")
    
    if st.button("💾 Save Note", type="primary"):
        if not note_title or not note_content:
            st.error("Title and Content are required fields!")
        else:
            typos = check_spelling(note_content)
            if typos:
                st.session_state.quick_typos = typos
                st.rerun()
            else:
                final_category = cat_new if cat_sel == "➕ Add New..." else cat_sel
                new_row = [str(current_ist.date()), str(current_ist.strftime("%H:%M:%S")), note_title.strip(), final_category.strip(), note_content.strip(), "Completed"]
                
                try:
                    ws_notes.append_row(new_row)
                    st.session_state.pop('note_data', None)
                    st.session_state.quick_title = ""
                    st.session_state.quick_content = ""
                    st.success("Note saved successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to save note: {e}")

    # Warning Gate
    if st.session_state.quick_typos:
        warning_msg = "**Hold on! Potential typos detected:**\n"
        for typo, suggestion in st.session_state.quick_typos.items():
            warning_msg += f"- `{typo}` *(Did you mean: **{suggestion}**?)*\n"
        st.warning(warning_msg)
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🪄 Auto-Fix Typos", type="primary", use_container_width=True):
                # 1-Click Fix applies to the text box instantly
                fixed = apply_fixes(st.session_state.quick_content, st.session_state.quick_typos)
                st.session_state.quick_content = fixed
                st.session_state.quick_typos = {}
                st.rerun()
        with c2:
            if st.button("✅ Ignore & Save Anyway", use_container_width=True):
                final_category = st.session_state.quick_new_cat if st.session_state.quick_cat == "➕ Add New..." else st.session_state.quick_cat
                new_row = [str(current_ist.date()), str(current_ist.strftime("%H:%M:%S")), st.session_state.quick_title.strip(), final_category.strip(), st.session_state.quick_content.strip(), "Completed"]
                ws_notes.append_row(new_row)
                st.session_state.pop('note_data', None)
                st.session_state.quick_typos = {}
                st.session_state.quick_title = ""
                st.session_state.quick_content = ""
                st.rerun()

# ==========================================
# TAB 3: PLAN TRAINING (PRE-EVENT)
# ==========================================
with tab_plan:
    st.markdown("### Pre-Plan a Training Session")
    st.info("Enter the context here so you don't have to type it while the speaker is talking.")
    
    with st.form("plan_training_form", clear_on_submit=True):
        train_title = st.text_input("Event/Training Title*", placeholder="e.g., NEP 2020 Implementation Workshop")
        
        col1, col2 = st.columns(2)
        with col1:
            trainer_name = st.text_input("Trainer/Speaker Name")
        with col2:
            planned_date = st.date_input("Scheduled Date", value=current_ist.date())
            
        topic = st.text_input("Core Topic / Subject")
        
        plan_submitted = st.form_submit_button("🗓️ Save to Planned Trainings", type="primary")
        
        if plan_submitted:
            if not train_title:
                st.error("Event Title is required!")
            else:
                context_block = f"**🗓️ Date:** {planned_date}\n**👤 Speaker:** {trainer_name}\n**🎯 Topic:** {topic}\n\n---\n**Live Notes:**\n"
                new_row = [str(current_ist.date()), str(current_ist.strftime("%H:%M:%S")), train_title.strip(), "Training", context_block, "Planned"]
                
                try:
                    ws_notes.append_row(new_row)
                    st.session_state.note_data.append(new_row)
                    st.success("Training Planned! It is now waiting for you in the 'Live Notes' tab.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to save planned training: {e}")

# ==========================================
# TAB 4: LIVE NOTE-TAKING (EVENT DAY)
# ==========================================
with tab_live:
    planned_notes = [(idx, note) for idx, note in enumerate(st.session_state.note_data) if len(note) > 5 and str(note[5]).strip() == "Planned"]
    
    if not planned_notes:
        st.success("🎉 You have no pending planned trainings! Plan one in the previous tab.")
    else:
        st.markdown("### Active Training Session")
        selected_idx = st.selectbox("Select Training:", options=[idx for idx, _ in planned_notes], format_func=lambda x: st.session_state.note_data[x][2])
        
        if selected_idx is not None:
            active_note = st.session_state.note_data[selected_idx]
            sheet_row = selected_idx + 1
            
            st.markdown(f"<div class='planned-context'>{active_note[4]}</div>", unsafe_allow_html=True)
            st.markdown("---")
            st.markdown("#### Add New Note")
            
            if "live_typos" not in st.session_state:
                st.session_state.live_typos = {}
            
            sub_topic = st.text_input("Sub-Topic / Category (Optional)", placeholder="e.g., Pedagogy, Q&A, Speaker 2...", key="live_sub")
            live_content = st.text_area("Note Content*", height=150, placeholder="Type your live notes here...", key="live_content")
            
            if st.button("💾 Save Note & Continue", type="primary", use_container_width=True):
                if not live_content.strip():
                    st.warning("Note content cannot be empty!")
                else:
                    typos = check_spelling(live_content)
                    if typos:
                        st.session_state.live_typos = typos
                        st.rerun()
                    else:
                        timestamp = current_ist.strftime("%I:%M %p")
                        topic_header = f"**🔹 {sub_topic.strip()}**" if sub_topic.strip() else "**🔹 Note**"
                        new_entry = f"\n\n{topic_header} *({timestamp})*:\n{live_content.strip()}"
                        final_content = active_note[4] + new_entry
                        
                        try:
                            try:
                                ws_notes.update(range_name=f"E{sheet_row}", values=[[final_content]], value_input_option="USER_ENTERED")
                            except TypeError:
                                ws_notes.update(f"E{sheet_row}", [[final_content]], value_input_option="USER_ENTERED")
                            st.session_state.pop('note_data', None)
                            st.session_state.live_content = ""
                            st.session_state.live_sub = ""
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to append note: {e}")

            # Warning Gate
            if st.session_state.live_typos:
                warning_msg = "**Potential typos detected:**\n"
                for typo, suggestion in st.session_state.live_typos.items():
                    warning_msg += f"- `{typo}` *(Did you mean: **{suggestion}**?)*\n"
                st.warning(warning_msg)
                
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("🪄 Auto-Fix Typos", type="primary", use_container_width=True):
                        # 1-Click Fix applies to the text box instantly
                        fixed = apply_fixes(st.session_state.live_content, st.session_state.live_typos)
                        st.session_state.live_content = fixed
                        st.session_state.live_typos = {}
                        st.rerun()
                with c2:
                    if st.button("✅ Ignore & Save", use_container_width=True):
                        timestamp = current_ist.strftime("%I:%M %p")
                        topic_header = f"**🔹 {st.session_state.live_sub.strip()}**" if st.session_state.live_sub.strip() else "**🔹 Note**"
                        new_entry = f"\n\n{topic_header} *({timestamp})*:\n{st.session_state.live_content.strip()}"
                        final_content = active_note[4] + new_entry
                        
                        try:
                            ws_notes.update(range_name=f"E{sheet_row}", values=[[final_content]], value_input_option="USER_ENTERED")
                        except TypeError:
                            ws_notes.update(f"E{sheet_row}", [[final_content]], value_input_option="USER_ENTERED")
                            
                        st.session_state.pop('note_data', None)
                        st.session_state.live_content = ""
                        st.session_state.live_sub = ""
                        st.session_state.live_typos = {}
                        st.rerun()
            
            st.markdown("<br><br>", unsafe_allow_html=True)
            if st.button("✅ Finish & Archive Training", type="secondary", use_container_width=True):
                try:
                    try:
                        ws_notes.update(range_name=f"F{sheet_row}", values=[["Completed"]], value_input_option="USER_ENTERED")
                    except TypeError:
                        ws_notes.update(f"F{sheet_row}", [["Completed"]], value_input_option="USER_ENTERED")
                    
                    st.session_state.pop('note_data', None)
                    st.success("Training finalized and archived to 'View Notes'!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to archive training: {e}")
