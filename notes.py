import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pytz
from datetime import datetime

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

# --- 2. SMART DATA CACHING ---
def fetch_notes():
    raw_data = ws_notes.get_all_values()
    # Expanded to 6 columns to support the new "Status" column (Planned vs Completed)
    padded_data = [row + [""] * (6 - len(row)) for row in raw_data]
    return padded_data

if "note_data" not in st.session_state:
    try:
        st.session_state.note_data = fetch_notes()
    except Exception as e:
        st.error(f"Failed to fetch Notes data: {e}")
        st.session_state.note_data = []

# FIX: Self-healing data padder. Ensures any old cached session data gets pushed to 6 columns automatically.
st.session_state.note_data = [row + [""] * (6 - len(row)) for row in st.session_state.note_data]

# Helper to get unique categories for the dropdown
def get_categories():
    if len(st.session_state.note_data) <= 1:
        return ["General", "Work", "Ideas", "Personal", "Training"]
    
    categories = [str(row[3]).strip() for row in st.session_state.note_data[1:] if str(row[3]).strip()]
    default_cats = ["General", "Work", "Ideas", "Personal", "Training"]
    return sorted(list(set(categories + default_cats)))

# --- TIMEZONE CONFIGURATION ---
ist = pytz.timezone('Asia/Kolkata')
current_ist = datetime.now(ist)

# --- GLOBAL CSS ---
st.markdown("""
    <style>
    .note-card {
        background-color: #f9f9fa;
        border-left: 4px solid #1890ff;
        padding: 15px;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .note-meta {
        font-size: 0.85em;
        color: #666;
        margin-bottom: 8px;
    }
    .planned-context {
        background-color: #e3f2fd;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #2196f3;
        margin-bottom: 20px;
        font-size: 15px;
        line-height: 1.6;
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. USER INTERFACE ---
st.title("📝 My Quick Notes")

tab_view, tab_add, tab_plan, tab_live = st.tabs(["📚 View Notes", "➕ Quick Note", "🗓️ Plan Training", "🎙️ Live Notes"])

# ==========================================
# TAB 1: VIEW & SEARCH NOTES
# ==========================================
with tab_view:
    search_query = st.text_input("🔍 Search completed notes by title, category, or content...")
    st.divider()
    
    if len(st.session_state.note_data) > 1:
        # Filter out "Planned" notes so they only show up in the Live Notes tab
        all_notes = [n for n in st.session_state.note_data[1:] if len(n) <= 5 or str(n[5]).strip() != "Planned"]
        all_notes = list(reversed(all_notes)) # Newest first
        
        if search_query:
            query = search_query.lower()
            filtered_notes = [
                n for n in all_notes 
                if query in str(n[2]).lower() or query in str(n[3]).lower() or query in str(n[4]).lower()
            ]
        else:
            filtered_notes = all_notes
            
        if not filtered_notes:
            st.info("No completed notes found matching your search.")
        else:
            for note in filtered_notes:
                date_val, time_val, title_val, category_val, content_val = note[0], note[1], note[2], note[3], note[4]
                
                with st.expander(f"📌 {title_val}  —  🏷️ {category_val}"):
                    st.markdown(f"<div class='note-meta'>🕒 {date_val} at {time_val}</div>", unsafe_allow_html=True)
                    st.write(content_val)
    else:
        st.info("No notes saved yet. Create a Quick Note or complete a Training!")

# ==========================================
# TAB 2: ADD QUICK NOTE
# ==========================================
with tab_add:
    with st.form("add_note_form", clear_on_submit=True):
        note_title = st.text_input("Note Title*", placeholder="Enter a clear title...")
        
        col1, col2 = st.columns(2)
        with col1:
            cat_opts = get_categories() + ["➕ Add New..."]
            cat_sel = st.selectbox("Category", cat_opts)
        with col2:
            cat_new = st.text_input("Type New Category", disabled=(cat_sel != "➕ Add New..."))
            
        note_content = st.text_area("Note Content*", height=200, placeholder="Write your note here...")
        submitted = st.form_submit_button("💾 Save Note", type="primary")
        
        if submitted:
            if not note_title or not note_content:
                st.error("Title and Content are required fields!")
            else:
                final_category = cat_new if cat_sel == "➕ Add New..." else cat_sel
                # Column 6 is marked as "Completed"
                new_row = [str(current_ist.date()), str(current_ist.strftime("%H:%M:%S")), note_title.strip(), final_category.strip(), note_content.strip(), "Completed"]
                
                try:
                    ws_notes.append_row(new_row)
                    st.session_state.note_data.append(new_row)
                    st.success("Note saved successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to save note: {e}")

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
                # Compile the context into the top of the content block
                context_block = f"**🗓️ Date:** {planned_date}\n**👤 Speaker:** {trainer_name}\n**🎯 Topic:** {topic}\n\n---\n**Live Notes:**\n"
                
                # Column 6 is marked as "Planned"
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
    # Bulletproof filtering for planned notes
    planned_notes = [(idx, note) for idx, note in enumerate(st.session_state.note_data) if len(note) > 5 and str(note[5]).strip() == "Planned"]
    
    if not planned_notes:
        st.success("🎉 You have no pending planned trainings! Plan one in the previous tab.")
    else:
        st.markdown("### Active Training Session")
        
        # Dropdown to select which planned training you are attending right now
        selected_idx = st.selectbox("Select Training:", options=[idx for idx, _ in planned_notes], format_func=lambda x: st.session_state.note_data[x][2])
        
        if selected_idx is not None:
            active_note = st.session_state.note_data[selected_idx]
            sheet_row = selected_idx + 1 # Exact row in Google Sheets (List Index + 1)
            
            # Show the pre-planned context and all notes saved so far
            st.markdown(f"<div class='planned-context'>{active_note[4]}</div>", unsafe_allow_html=True)
            
            st.markdown("---")
            st.markdown("#### Add New Note")
            
            # Form for continuous note addition
            with st.form("live_notes_append_form", clear_on_submit=True):
                sub_topic = st.text_input("Sub-Topic / Category (Optional)", placeholder="e.g., Pedagogy, Q&A, Speaker 2...")
                live_content = st.text_area("Note Content*", height=150, placeholder="Type your live notes here...")
                
                col_save, col_empty = st.columns([2, 1])
                with col_save:
                    append_submitted = st.form_submit_button("💾 Save Note & Continue", type="primary", use_container_width=True)
                
                if append_submitted:
                    if not live_content.strip():
                        st.warning("Note content cannot be empty!")
                    else:
                        # Format the new entry
                        timestamp = current_ist.strftime("%I:%M %p")
                        topic_header = f"**🔹 {sub_topic.strip()}**" if sub_topic.strip() else "**🔹 Note**"
                        new_entry = f"\n\n{topic_header} *({timestamp})*:\n{live_content.strip()}"
                        
                        # Merge old content with new entry
                        final_content = active_note[4] + new_entry
                        
                        try:
                            # Append to Content (Col E) directly
                            try:
                                ws_notes.update(range_name=f"E{sheet_row}", values=[[final_content]], value_input_option="USER_ENTERED")
                            except TypeError:
                                ws_notes.update(f"E{sheet_row}", [[final_content]], value_input_option="USER_ENTERED")
                            
                            st.session_state.pop('note_data', None)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to append note: {e}")
            
            # Button to finalize the training and move it out of the Live queue
            st.markdown("<br><br>", unsafe_allow_html=True)
            if st.button("✅ Finish & Archive Training", type="secondary", use_container_width=True):
                try:
                    # Update Status (Col F) to 'Completed'
                    try:
                        ws_notes.update(range_name=f"F{sheet_row}", values=[["Completed"]], value_input_option="USER_ENTERED")
                    except TypeError:
                        ws_notes.update(f"F{sheet_row}", [["Completed"]], value_input_option="USER_ENTERED")
                    
                    st.session_state.pop('note_data', None)
                    st.success("Training finalized and archived to 'View Notes'!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to archive training: {e}")
