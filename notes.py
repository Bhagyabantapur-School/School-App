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
    # Connecting to the new "NOTE APP" sheet and the "Notes" tab
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
    # Ensure every row has exactly 5 columns to prevent index errors
    padded_data = [row + [""] * (5 - len(row)) for row in raw_data]
    return padded_data

if "note_data" not in st.session_state:
    try:
        st.session_state.note_data = fetch_notes()
    except Exception as e:
        st.error(f"Failed to fetch Notes data: {e}")
        st.session_state.note_data = []

# Helper to get unique categories for the dropdown
def get_categories():
    if len(st.session_state.note_data) <= 1:
        return ["General", "Work", "Ideas", "Personal"]
    
    categories = [str(row[3]).strip() for row in st.session_state.note_data[1:] if str(row[3]).strip()]
    default_cats = ["General", "Work", "Ideas", "Personal"]
    # Combine and remove duplicates
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
    </style>
""", unsafe_allow_html=True)

# --- 3. USER INTERFACE ---
st.title("📝 My Quick Notes")

tab1, tab2 = st.tabs(["📚 View Notes", "➕ Add New Note"])

# ==========================================
# TAB 1: VIEW & SEARCH NOTES
# ==========================================
with tab1:
    search_query = st.text_input("🔍 Search notes by title, category, or content...")
    st.divider()
    
    if len(st.session_state.note_data) > 1:
        # Get all notes except header, reverse so newest are first
        all_notes = list(reversed(st.session_state.note_data[1:]))
        
        # Filter logic
        if search_query:
            query = search_query.lower()
            filtered_notes = [
                n for n in all_notes 
                if query in str(n[2]).lower() or query in str(n[3]).lower() or query in str(n[4]).lower()
            ]
        else:
            filtered_notes = all_notes
            
        if not filtered_notes:
            st.info("No notes found matching your search.")
        else:
            for note in filtered_notes:
                date_val = note[0]
                time_val = note[1]
                title_val = note[2]
                category_val = note[3]
                content_val = note[4]
                
                with st.expander(f"📌 {title_val}  —  🏷️ {category_val}"):
                    st.markdown(f"<div class='note-meta'>🕒 {date_val} at {time_val}</div>", unsafe_allow_html=True)
                    st.write(content_val)
    else:
        st.info("No notes saved yet. Go to the 'Add New Note' tab to create your first one!")

# ==========================================
# TAB 2: ADD NEW NOTE
# ==========================================
with tab2:
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
                
                new_row = [
                    str(current_ist.date()), 
                    str(current_ist.strftime("%H:%M:%S")), 
                    note_title.strip(), 
                    final_category.strip(), 
                    note_content.strip()
                ]
                
                try:
                    ws_notes.append_row(new_row)
                    st.session_state.note_data.append(new_row)
                    st.success("Note saved successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to save note: {e}")
