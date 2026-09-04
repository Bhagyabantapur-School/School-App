import streamlit as st
import pandas as pd
import uuid
from datetime import datetime, time
import pytz
import gspread
from gspread.exceptions import WorksheetNotFound, APIError
from google.oauth2.service_account import Credentials

IST = pytz.timezone('Asia/Kolkata')

TEACHER_LIST = [
    "SUKHAMAY KISKU", "TAPASI RANA", "SUJATA BISWAS ROTHA", 
    "ROHINI SINGH", "UDAY NARAYAN JANA", "BIMAL KUMAR PATRA", 
    "SUSMITA PAUL", "TAPAN KUMAR MANDAL", "MANJUMA KHATUN"
]

CLASS_OPTIONS = ["CLASS PP", "CLASS I", "CLASS II", "CLASS III", "CLASS IV", "CLASS V", "MIXED (Multiple Classes)"]
SECTIONS = ["A", "B", "C", "All Sections"]
PERFORMANCE_TYPES = ["Dance 💃", "Drama / Play 🎭", "Recitation 🎙️", "Chorus Song 🎵", "Solo Song 🎤", "Speech 🗣️", "Yoga / Drill 🧘‍♂️", "Other"]

# Safely inherit user details from app.py
current_user_name = st.session_state.get('user_name', 'Teacher')
current_user_role = st.session_state.get('user_role', 'teacher')

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
        ".song-card { background: white; padding: 15px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 15px; transition: transform 0.2s; }"
        ".song-card:hover { transform: translateY(-3px); box-shadow: 0 6px 12px rgba(0,0,0,0.15); }"
        ".yt-btn { display: inline-block; background-color: #ff0000; color: white !important; padding: 8px 15px; border-radius: 5px; text-decoration: none; font-weight: bold; margin-top: 10px; font-size: 14px; }"
        ".yt-btn:hover { background-color: #cc0000; }"
        "</style><div class=\"watermark\"></div>"
    )
    st.markdown(css, unsafe_allow_html=True)

inject_security_css(current_user_name)

# ==========================================
# GOOGLE SHEETS CONNECTORS (BYPASSING NAME SEARCH)
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
        # Using the exact unique ID extracted from your uploaded file!
        return gspread.authorize(get_google_credentials()).open_by_key("1TXs2o0OnpPz1nr_AnhzrwR_OA3FsAss9gwGvbB6LHQo")
    except APIError:
        st.error("⚠️ The Service Account does not have permission! Please ensure your Service Account email is added as an 'Editor' to the BPS_CELEBRATION sheet.")
        st.stop()
    except Exception as e: 
        st.error(f"⚠️ Connection Error: {e}")
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
# DATA FETCHING & SAVING
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
# MAIN UI
# ==========================================
st.markdown("<h2>🎊 BPS Celebration & Event Manager</h2>", unsafe_allow_html=True)
st.sidebar.button("🔄 Sync Event Data", on_click=refresh_event_data, use_container_width=True)

tabs = st.tabs(["🎵 Explore Songs", "🎭 Claim Performance", "📋 Event Playlist Manager", "📅 Manage Events (Admin)"])

# ---------------------------------------------------------
# TAB 1: EXPLORE SONGS & ACTS (BEAUTIFUL GALLERY)
# ---------------------------------------------------------
with tabs[0]:
    st.markdown("<div class='header-card' style='border-left-color: #e83e8c;'><h4>🎵 Explore Songs & Acts</h4><p style='margin:0; font-size:14px;'>Listen to the songs curated by the Head Teacher and choose the perfect one for your class!</p></div>", unsafe_allow_html=True)
    
    programs = fetch_programs()
    active_progs = programs[programs['Status'] != 'Completed'] if not programs.empty else pd.DataFrame()
    
    if active_progs.empty:
        st.info("No upcoming celebrations found. Please wait for the Admin to schedule one.")
    else:
        prog_options = {f"{r['Event_Name']} ({r['Date']})": r['Prog_ID'] for _, r in active_progs.iterrows()}
        sel_prog = st.selectbox("Select Celebration Event to Explore", list(prog_options.keys()), key="explore_prog")
        prog_id = prog_options[sel_prog]
        
        event_name_clean = sel_prog.split(' (')[0]
        st.markdown(f"### 🎊 {event_name_clean} - Act Gallery")
        
        all_perfs = fetch_performances()
        event_perfs = all_perfs[all_perfs['Prog_ID'] == prog_id] if not all_perfs.empty else pd.DataFrame()
        
        if event_perfs.empty:
            st.warning("No songs or acts have been added to this event yet. Check back later!")
        else:
            cols = st.columns(2)
            for i, (_, row) in enumerate(event_perfs.iterrows()):
                with cols[i % 2]:
                    # Design the Card based on Availability
                    is_available = row['Choreographer'] == "TBD"
                    status_color = "#28a745" if is_available else "#dc3545"
                    status_text = "🟢 AVAILABLE TO CLAIM" if is_available else f"🔴 CLAIMED BY: {row['Choreographer']} ({row['Class']})"
                    
                    yt_link = str(row['YouTube_Link']).strip()
                    yt_html = ""
                    if yt_link.startswith("http"):
                        yt_html = f"<a href='{yt_link}' target='_blank' class='yt-btn'>▶️ Listen on YouTube</a>"
                    
                    card_html = f"""
                    <div class="song-card" style="border-left: 6px solid {status_color};">
                        <h4 style="margin: 0 0 5px 0; color: #333;">{row['Perf_Name']}</h4>
                        <p style="margin: 0; font-size: 13px; font-weight: bold; color: {status_color};">{status_text}</p>
                        {yt_html}
                    </div>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)

# ---------------------------------------------------------
# TAB 2: TEACHER PERFORMANCE SUBMISSION
# ---------------------------------------------------------
with tabs[1]:
    st.markdown("<div class='header-card'><h4>🎭 Claim & Register Your Act</h4><p style='margin:0; font-size:14px;'>Found a song you like in the Explore tab? Select it here to assign your class to it!</p></div>", unsafe_allow_html=True)
    
    programs = fetch_programs()
    active_progs = programs[programs['Status'] != 'Completed'] if not programs.empty else pd.DataFrame()
    
    if active_progs.empty:
        st.info("There are currently no upcoming celebrations scheduled.")
    else:
        prog_options = {f"{r['Event_Name']} ({r['Date']})": r['Prog_ID'] for _, r in active_progs.iterrows()}
        
        # Select Event outside the form so the available acts table updates dynamically
        sel_prog_claim = st.selectbox("1. Select Celebration Event *", list(prog_options.keys()), key="claim_prog")
        prog_id_claim = prog_options[sel_prog_claim]
        
        all_perfs = fetch_performances()
        available_acts = all_perfs[(all_perfs['Prog_ID'] == prog_id_claim) & (all_perfs['Choreographer'] == "TBD")] if not all_perfs.empty else pd.DataFrame()
        
        if available_acts.empty:
            st.warning("⚠️ No available acts for this event. All curated acts have already been claimed by other teachers!")
        else:
            with st.form("perf_form"):
                act_dict = {f"{r['Perf_Name']}": r['Perf_ID'] for _, r in available_acts.iterrows()}
                selected_act_name = st.selectbox("2. Select Act to Claim *", list(act_dict.keys()))
                
                c1, c2 = st.columns(2)
                perf_type = c1.selectbox("Performance Type *", PERFORMANCE_TYPES)
                cls_sel = c2.selectbox("Participating Class *", CLASS_OPTIONS)
                
                c3, c4 = st.columns(2)
                sec_sel = c3.selectbox("Section", SECTIONS)
                def_idx = TEACHER_LIST.index(current_user_name) if current_user_name in TEACHER_LIST else 0
                choreo = c4.selectbox("Choreographer / Guiding Teacher *", TEACHER_LIST, index=def_idx)
                
                dur = st.number_input("Estimated Duration (Minutes) *", min_value=1, max_value=45, value=5, step=1)
                
                submit_act = st.form_submit_button("✅ Claim & Submit Performance", use_container_width=True)
                
                if submit_act:
                    target_id = act_dict[selected_act_name]
                    
                    # Update the specific row in the master dataframe
                    all_perfs.loc[all_perfs['Perf_ID'] == target_id, ['Perf_Type', 'Class', 'Section', 'Choreographer', 'Duration_Mins']] = [perf_type, cls_sel, sec_sel, choreo, dur]
                    
                    overwrite_sheet("event_performances", all_perfs, ["Perf_ID", "Prog_ID", "Order_No", "Perf_Type", "Perf_Name", "Class", "Section", "Choreographer", "Duration_Mins", "YouTube_Link"])
                    st.success(f"Successfully claimed '{selected_act_name}' for {cls_sel}!")
                    st.rerun()

# ---------------------------------------------------------
# TAB 3: PLAYLIST & SEQUENCE MANAGER
# ---------------------------------------------------------
with tabs[2]:
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
            
            unclaimed_count = len(event_perfs[event_perfs['Choreographer'] == "TBD"])
            kpi_html = f"""
            <div class='kpi-card'>
                <h3>⏱️ Total Program Duration: {hrs} Hours {mins} Mins</h3>
                <p style='margin:0; color:#555;'>({len(event_perfs)} Acts Total | <b>{unclaimed_count} Unclaimed by Teachers</b>)</p>
            </div>
            """
            st.markdown(kpi_html, unsafe_allow_html=True)
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
# TAB 4: ADMIN EVENT CREATION
# ---------------------------------------------------------
with tabs[3]:
    if current_user_role == "admin":
        st.markdown("<div class='header-card' style='border-left: 5px solid #17a2b8;'><h4>📅 Create New Celebration</h4><p style='margin:0; font-size:14px;'>Schedule an upcoming school event first, then add specific songs/acts for teachers to claim.</p></div>", unsafe_allow_html=True)
        
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
                        "Created_By": current_user_name
                    }
                    programs = fetch_programs()
                    updated_progs = pd.concat([programs, pd.DataFrame([new_ev])], ignore_index=True)
                    overwrite_sheet("event_programs", updated_progs, ["Prog_ID", "Event_Name", "Date", "Start_Time", "Status", "Created_By"])
                    st.success(f"Event '{ev_name}' created successfully!")
                    st.rerun()
                    
        st.divider()
        
        st.markdown("##### 🎵 Curate Songs / Acts for an Event")
        st.caption("Add the specific songs or drama topics here. Teachers will then log in and 'claim' them for their classes.")
        
        programs = fetch_programs()
        active_progs_admin = programs[programs['Status'] != 'Completed'] if not programs.empty else pd.DataFrame()
        
        if not active_progs_admin.empty:
            prog_opts_admin = {f"{r['Event_Name']} ({r['Date']})": r['Prog_ID'] for _, r in active_progs_admin.iterrows()}
            with st.form("add_act_form"):
                sel_prog_admin = st.selectbox("Select Celebration Event *", list(prog_opts_admin.keys()))
                act_name = st.text_input("Name of Song / Drama / Act *", placeholder="e.g., Alo Amar Alo (Rabindra Sangeet)")
                yt_link = st.text_input("YouTube Track / Reference Link (Optional)", placeholder="Paste YouTube link here...")
                
                add_act_btn = st.form_submit_button("➕ Add Act to Event Pool")
                
                if add_act_btn:
                    if not act_name.strip():
                        st.error("Please enter the Act Name.")
                    else:
                        new_act = {
                            "Perf_ID": uuid.uuid4().hex[:8],
                            "Prog_ID": prog_opts_admin[sel_prog_admin],
                            "Order_No": 99, 
                            "Perf_Type": "TBD",
                            "Perf_Name": act_name.strip(),
                            "Class": "TBD",
                            "Section": "TBD",
                            "Choreographer": "TBD",
                            "Duration_Mins": 0,
                            "YouTube_Link": yt_link.strip()
                        }
                        curr_perfs = fetch_performances()
                        updated_perfs = pd.concat([curr_perfs, pd.DataFrame([new_act])], ignore_index=True)
                        overwrite_sheet("event_performances", updated_perfs, ["Perf_ID", "Prog_ID", "Order_No", "Perf_Type", "Perf_Name", "Class", "Section", "Choreographer", "Duration_Mins", "YouTube_Link"])
                        st.success(f"Act '{act_name}' added to the pool!")
                        st.rerun()
        else:
            st.info("Create an event above before adding songs/acts.")

        st.divider()
        st.markdown("##### 📌 Event History Management")
        if not programs.empty:
            st.dataframe(programs[['Event_Name', 'Date', 'Start_Time', 'Status']], hide_index=True, use_container_width=True)
            
            mk_comp = st.selectbox("Mark Event as Completed", ["Select..."] + programs[programs['Status'] == 'Upcoming']['Event_Name'].tolist())
            if mk_comp != "Select..." and st.button("✔️ Mark Completed"):
                programs.loc[programs['Event_Name'] == mk_comp, 'Status'] = 'Completed'
                overwrite_sheet("event_programs", programs, ["Prog_ID", "Event_Name", "Date", "Start_Time", "Status", "Created_By"])
                st.success(f"{mk_comp} moved to Completed history.")
                st.rerun()
    else:
        st.warning("Only the Head Teacher (Admin) can schedule new celebration events.")
