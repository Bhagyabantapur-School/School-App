import streamlit as st
import pandas as pd
import uuid
from datetime import datetime, time
import pytz
import gspread
from gspread.exceptions import WorksheetNotFound
from google.oauth2.service_account import Credentials

# ==========================================
# 1. AUTHENTICATION & SECURITY
# ==========================================
if 'authenticated' not in st.session_state or not st.session_state.authenticated:
    st.warning("🔒 Unauthorized Access. Please log in through the main portal.")
    st.stop()

IST = pytz.timezone('Asia/Kolkata')

TEACHER_LIST = [
    "SUKHAMAY KISKU", "TAPASI RANA", "SUJATA BISWAS ROTHA", 
    "ROHINI SINGH", "UDAY NARAYAN JANA", "BIMAL KUMAR PATRA", 
    "SUSMITA PAUL", "TAPAN KUMAR MANDAL", "MANJUMA KHATUN"
]

CLASS_OPTIONS = ["CLASS PP", "CLASS I", "CLASS II", "CLASS III", "CLASS IV", "CLASS V", "MIXED (Multiple Classes)"]
SECTIONS = ["A", "B", "C", "All Sections"]
PERFORMANCE_TYPES = ["Dance 💃", "Drama / Play 🎭", "Recitation 🎙️", "Chorus Song 🎵", "Solo Song 🎤", "Speech 🗣️", "Yoga / Drill 🧘‍♂️", "Other"]

def inject_security_css(user_name):
    wm = str(user_name) + " - CULTURAL EVENT"
    css = (
        "<style>"
        ".watermark { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; pointer-events: none; z-index: 9999; "
        "background-image: url('data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"300\" height=\"300\" viewBox=\"0 0 300 300\">"
        "<text x=\"50\" y=\"150\" fill=\"rgba(200, 200, 200, 0.15)\" font-size=\"20\" transform=\"rotate(-45 150 150)\" font-family=\"Arial, sans-serif\">" + wm + "</text></svg>'); "
        "background-repeat: repeat; }"
        ".stButton>button { border-radius: 8px; font-weight: bold; }"
        ".header-card { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border-left: 5px solid #ff4b4b; margin-bottom: 15px; }"
        ".kpi-card { background: linear-gradient(135deg, #ffebee, #ffcdd2); padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #ef9a9a; }"
        "</style><div class=\"watermark\"></div>"
    )
    st.markdown(css, unsafe_allow_html=True)

inject_security_css(st.session_state.user_name)

# ==========================================
# 2. GOOGLE SHEETS CONNECTORS
# ==========================================
@st.cache_resource
def get_google_credentials():
    return Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )

@st.cache_resource
def init_celeb_sheet():
    try: 
        return gspread.authorize(get_google_credentials()).open("BPS_CELEBRATION")
    except Exception: 
        st.error("⚠️ BPS_CELEBRATION Google Sheet not found! Please check the name and ensure it is shared with the service account.")
        st.stop()

def ensure_worksheet(sh, title, headers):
    try: 
        ws = sh.worksheet(title)
    except WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=1000, cols=20)
        ws.append_row(headers)
    return ws

def refresh_event_data():
    fetch_programs.clear()
    fetch_performances.clear()

# ==========================================
# 3. DATA FETCHING & SAVING
# ==========================================
@st.cache_data(ttl=300)
def fetch_programs():
    sh = init_celeb_sheet()
    ws = ensure_worksheet(sh, "event_programs", ["Prog_ID", "Event_Name", "Date", "Start_Time", "Status", "Created_By"])
    records = ws.get_all_records()
    if not records:
        return pd.DataFrame(columns=["Prog_ID", "Event_Name", "Date", "Start_Time", "Status", "Created_By"])
    return pd.DataFrame(records).astype(str)

@st.cache_data(ttl=300)
def fetch_performances():
    sh = init_celeb_sheet()
    ws = ensure_worksheet(sh, "event_performances", ["Perf_ID", "Prog_ID", "Order_No", "Perf_Type", "Perf_Name", "Class", "Section", "Choreographer", "Duration_Mins", "YouTube_Link"])
    records = ws.get_all_records()
    if not records:
        return pd.DataFrame(columns=["Perf_ID", "Prog_ID", "Order_No", "Perf_Type", "Perf_Name", "Class", "Section", "Choreographer", "Duration_Mins", "YouTube_Link"])
    
    df = pd.DataFrame(records)
    df['Order_No'] = pd.to_numeric(df['Order_No'], errors='coerce').fillna(99).astype(int)
    return df

def overwrite_sheet(sheet_name, df, headers):
    sh = init_celeb_sheet()
    ws = ensure_worksheet(sh, sheet_name, headers)
    ws.clear()
    if not df.empty:
        ws.update([df.columns.values.tolist()] + df.fillna("").values.tolist())
    else:
        ws.append_row(headers)
    refresh_event_data()

# ==========================================
# 4. MAIN UI
# ==========================================
st.markdown("<h2>🎊 BPS Celebration & Event Manager</h2>", unsafe_allow_html=True)
st.sidebar.button("🔄 Sync Event Data", on_click=refresh_event_data, use_container_width=True)

tabs = st.tabs(["🎭 Submit Performance", "📋 Event Playlist Manager", "📅 Manage Events (Admin)"])

# ---------------------------------------------------------
# TAB 1: TEACHER PERFORMANCE SUBMISSION
# ---------------------------------------------------------
with tabs[0]:
    st.markdown("<div class='header-card'><h4>🎭 Register Your Act</h4><p style='margin:0; font-size:14px;'>Fill out the details for your class performance below.</p></div>", unsafe_allow_html=True)
    
    programs = fetch_programs()
    active_progs = programs[programs['Status'] != 'Completed'] if not programs.empty else pd.DataFrame()
    
    if active_progs.empty:
        st.info("There are currently no upcoming celebrations scheduled. The Admin must create an event first.")
    else:
        prog_options = {f"{r['Event_Name']} ({r['Date']})": r['Prog_ID'] for _, r in active_progs.iterrows()}
        
        with st.form("perf_form"):
            sel_prog = st.selectbox("Select Celebration Event *", list(prog_options.keys()))
            
            c1, c2 = st.columns(2)
            perf_type = c1.selectbox("Performance Type *", PERFORMANCE_TYPES)
            perf_name = c2.text_input("Name of Song / Drama / Act *", placeholder="e.g., Alo Amar Alo")
            
            c3, c4 = st.columns(2)
            cls_sel = c3.selectbox("Participating Class *", CLASS_OPTIONS)
            sec_sel = c4.selectbox("Section", SECTIONS)
            
            c5, c6 = st.columns(2)
            # Default to logged-in user if they are a teacher
            def_idx = TEACHER_LIST.index(st.session_state.user_name) if st.session_state.user_name in TEACHER_LIST else 0
            choreo = c5.selectbox("Choreographer / Guiding Teacher *", TEACHER_LIST, index=def_idx)
            dur = c6.number_input("Estimated Duration (Minutes) *", min_value=1, max_value=45, value=5, step=1)
            
            yt_link = st.text_input("YouTube Track / Reference Link (Optional)", placeholder="Paste YouTube link here...")
            
            submit_act = st.form_submit_button("✅ Submit Performance to Playlist", use_container_width=True)
            
            if submit_act:
                if not perf_name.strip():
                    st.error("Please provide a name for the performance!")
                else:
                    prog_id = prog_options[sel_prog]
                    new_id = uuid.uuid4().hex[:8]
                    
                    new_act = {
                        "Perf_ID": new_id,
                        "Prog_ID": prog_id,
                        "Order_No": 99, # Default to bottom of list
                        "Perf_Type": perf_type,
                        "Perf_Name": perf_name.strip(),
                        "Class": cls_sel,
                        "Section": sec_sel,
                        "Choreographer": choreo,
                        "Duration_Mins": dur,
                        "YouTube_Link": yt_link.strip()
                    }
                    
                    curr_perfs = fetch_performances()
                    updated_perfs = pd.concat([curr_perfs, pd.DataFrame([new_act])], ignore_index=True)
                    overwrite_sheet("event_performances", updated_perfs, ["Perf_ID", "Prog_ID", "Order_No", "Perf_Type", "Perf_Name", "Class", "Section", "Choreographer", "Duration_Mins", "YouTube_Link"])
                    st.success(f"Performance '{perf_name}' successfully added to {sel_prog}!")
                    st.rerun()

# ---------------------------------------------------------
# TAB 2: PLAYLIST & SEQUENCE MANAGER
# ---------------------------------------------------------
with tabs[1]:
    st.markdown("<div class='header-card'><h4>📋 Event Playlist Manager</h4><p style='margin:0; font-size:14px;'>Review all acts and edit the <b>Order No.</b> to arrange the sequence of performances.</p></div>", unsafe_allow_html=True)
    
    programs = fetch_programs()
    if programs.empty:
        st.info("No events found.")
    else:
        prog_opts = {f"{r['Event_Name']} ({r['Date']})": r['Prog_ID'] for _, r in programs.iterrows()}
        view_prog = st.selectbox("Select Event to View Playlist", list(prog_opts.keys()), key="view_pl")
        view_prog_id = prog_opts[view_prog]
        
        all_perfs = fetch_performances()
        event_perfs = all_perfs[all_perfs['Prog_ID'] == view_prog_id].copy() if not all_perfs.empty else pd.DataFrame()
        
        if event_perfs.empty:
            st.info("No performances have been registered for this event yet.")
        else:
            # Sort by Order_No
            event_perfs = event_perfs.sort_values('Order_No')
            
            # Calculate Total Time
            total_mins = pd.to_numeric(event_perfs['Duration_Mins'], errors='coerce').sum()
            hrs = int(total_mins // 60)
            mins = int(total_mins % 60)
            
            st.markdown(f"<div class='kpi-card'><h3>⏱️ Total Program Duration: {hrs} Hours {mins} Mins</h3><p style='margin:0; color:#555;'>({len(event_perfs)} Performances Registered)</p></div>", unsafe_allow_html=True)
            st.write("")
            
            st.markdown("##### ↕️ Arrange Performance Order")
            st.caption("Double-click a cell in the **Order No.** column to type a new number. Then click Save to reorder the list.")
            
            # Setup Editor
            edit_cols = ["Order_No", "Perf_Type", "Perf_Name", "Class", "Choreographer", "Duration_Mins", "YouTube_Link", "Perf_ID"]
            disp_df = event_perfs[edit_cols].copy()
            
            edited_pl = st.data_editor(
                disp_df,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Perf_ID": None, # Hide ID
                    "Order_No": st.column_config.NumberColumn("Order No.", min_value=1, step=1, required=True),
                    "Perf_Type": st.column_config.TextColumn("Type", disabled=True),
                    "Perf_Name": st.column_config.TextColumn("Act / Song", disabled=True),
                    "Class": st.column_config.TextColumn("Class", disabled=True),
                    "Choreographer": st.column_config.TextColumn("Guide", disabled=True),
                    "Duration_Mins": st.column_config.NumberColumn("Mins", disabled=True),
                    "YouTube_Link": st.column_config.LinkColumn("YT Link")
                }
            )
            
            col_s1, col_s2 = st.columns([1, 1])
            with col_s1:
                if st.button("💾 Save New Playlist Order", type="primary", use_container_width=True):
                    # Update master dataframe with new order numbers
                    for _, r in edited_pl.iterrows():
                        all_perfs.loc[all_perfs['Perf_ID'] == r['Perf_ID'], 'Order_No'] = r['Order_No']
                    
                    overwrite_sheet("event_performances", all_perfs, ["Perf_ID", "Prog_ID", "Order_No", "Perf_Type", "Perf_Name", "Class", "Section", "Choreographer", "Duration_Mins", "YouTube_Link"])
                    st.success("Playlist order successfully updated!")
                    st.rerun()
            
            with col_s2:
                del_id = st.selectbox("Remove a Performance", ["Select to remove..."] + event_perfs['Perf_Name'].tolist())
                if del_id != "Select to remove..." and st.button("🗑️ Delete Selected"):
                    target_pid = event_perfs[event_perfs['Perf_Name'] == del_id].iloc[0]['Perf_ID']
                    all_perfs = all_perfs[all_perfs['Perf_ID'] != target_pid]
                    overwrite_sheet("event_performances", all_perfs, ["Perf_ID", "Prog_ID", "Order_No", "Perf_Type", "Perf_Name", "Class", "Section", "Choreographer", "Duration_Mins", "YouTube_Link"])
                    st.success("Performance removed.")
                    st.rerun()

# ---------------------------------------------------------
# TAB 3: ADMIN EVENT CREATION
# ---------------------------------------------------------
with tabs[2]:
    if st.session_state.user_role == "admin":
        st.markdown("<div class='header-card' style='border-left: 5px solid #17a2b8;'><h4>📅 Create New Celebration</h4><p style='margin:0; font-size:14px;'>Schedule an upcoming school event to allow teachers to start submitting their acts.</p></div>", unsafe_allow_html=True)
        
        with st.form("create_event"):
            ev_name = st.text_input("Celebration Name *", placeholder="e.g., Independence Day 2026")
            e1, e2 = st.columns(2)
            ev_date = e1.date_input("Date of Event", datetime.now(IST).date()).strftime("%d-%m-%Y")
            ev_time = e2.time_input("Start Time", time(10, 0)).strftime("%I:%M %p")
            
            sub_ev = st.form_submit_button("➕ Schedule Celebration")
            
            if sub_ev:
                if not ev_name.strip():
                    st.error("Please enter a Celebration Name.")
                else:
                    new_ev = {
                        "Prog_ID": f"EV_{uuid.uuid4().hex[:6]}",
                        "Event_Name": ev_name.strip(),
                        "Date": ev_date,
                        "Start_Time": ev_time,
                        "Status": "Upcoming",
                        "Created_By": st.session_state.user_name
                    }
                    programs = fetch_programs()
                    updated_progs = pd.concat([programs, pd.DataFrame([new_ev])], ignore_index=True)
                    overwrite_sheet("event_programs", updated_progs, ["Prog_ID", "Event_Name", "Date", "Start_Time", "Status", "Created_By"])
                    st.success(f"Event '{ev_name}' created successfully!")
                    st.rerun()
                    
        st.divider()
        st.markdown("##### 📌 Existing Events")
        programs = fetch_programs()
        if not programs.empty:
            st.dataframe(programs[['Event_Name', 'Date', 'Start_Time', 'Status']], hide_index=True, use_container_width=True)
            
            mk_comp = st.selectbox("Mark Event as Completed", ["Select..."] + programs[programs['Status'] == 'Upcoming']['Event_Name'].tolist())
            if mk_comp != "Select..." and st.button("✔️ Mark Completed"):
                programs.loc[programs['Event_Name'] == mk_comp, 'Status'] = 'Completed'
                overwrite_sheet("event_programs", programs, ["Prog_ID", "Event_Name", "Date", "Start_Time", "Status", "Created_By"])
                st.success(f"{mk_comp} moved to Completed history.")
                st.rerun()
        else:
            st.info("No events scheduled.")
    else:
        st.warning("Only the Head Teacher (Admin) can schedule new celebration events.")
