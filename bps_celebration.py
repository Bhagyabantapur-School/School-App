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

PERF_HEADERS = ["Perf_ID", "Prog_ID", "Order_No", "Perf_Type", "Perf_Name", "Class", "Section", "Choreographer", "Duration_Mins", "YouTube_Link", "Live_Status", "Completed_At", "Cancel_Reason", "Canceled_By"]
AUDIT_HEADERS = ["Timestamp", "User", "Action", "Details"]

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
        ".local-warning { background-color: #fff3cd; border-left: 5px solid #ffc107; padding: 10px; border-radius: 5px; margin-bottom: 15px; }"
        "</style><div class=\"watermark\"></div>"
    )
    st.markdown(css, unsafe_allow_html=True)

inject_security_css(current_user_name)

# ==========================================
# GOOGLE SHEETS CONNECTORS
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
    fetch_audit_log.clear()

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
    ws = ensure_worksheet(sh, "event_performances", PERF_HEADERS)
    records = ws.get_all_records()
    if not records:
        return pd.DataFrame(columns=PERF_HEADERS)
    
    df = pd.DataFrame(records)
    for col in PERF_HEADERS:
        if col not in df.columns:
            if col == "Live_Status": df[col] = "Pending"
            elif col == "Order_No": df[col] = 99
            else: df[col] = ""
            
    df['Order_No'] = pd.to_numeric(df['Order_No'], errors='coerce').fillna(99).astype(int)
    df.fillna("", inplace=True)
    return df

@st.cache_data(ttl=300)
def fetch_audit_log():
    sh = init_celeb_sheet()
    ws = ensure_worksheet(sh, "event_audit_log", AUDIT_HEADERS)
    records = ws.get_all_records()
    if not records:
        return pd.DataFrame(columns=AUDIT_HEADERS)
    return pd.DataFrame(records)

def log_audit(action, details):
    try:
        sh = init_celeb_sheet()
        ws = ensure_worksheet(sh, "event_audit_log", AUDIT_HEADERS)
        timestamp = datetime.now(IST).strftime("%d-%m-%Y %I:%M:%S %p")
        ws.append_row([timestamp, current_user_name, action, details])
        fetch_audit_log.clear()
    except Exception:
        pass 

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
# MAIN UI & DYNAMIC TABS
# ==========================================
st.markdown("<h2>🎊 BPS Celebration & Event Manager</h2>", unsafe_allow_html=True)
st.sidebar.button("🔄 Sync Event Data", on_click=refresh_event_data, use_container_width=True)

if current_user_role == "admin":
    tab_titles = ["🎵 Explore Songs", "🔴 Live Controller", "🎭 Claim Performance", "📋 Playlist Manager", "📅 Manage Events", "📝 Audit Log"]
else:
    tab_titles = ["🎵 Explore Songs", "🔴 Live Controller", "🎭 Claim Performance", "📋 Playlist Manager"]

tabs = st.tabs(tab_titles)

# ---------------------------------------------------------
# TAB 1: EXPLORE SONGS & ACTS
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
                    is_available = row['Class'] == "TBD"
                    is_canceled = str(row.get('Cancel_Reason', '')) != ""
                    
                    if is_canceled:
                        status_color = "#6c757d"
                        status_text = f"🚫 CANCELED by {row['Canceled_By']}"
                    elif is_available:
                        status_color = "#28a745"
                        status_text = f"🟢 AVAILABLE TO CLAIM (Assigned: {row['Choreographer']})"
                    else:
                        status_color = "#dc3545"
                        status_text = f"🔴 CLAIMED BY: {row['Choreographer']} ({row['Class']})"
                    
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
# TAB 2: LIVE PROGRAM CONTROLLER
# ---------------------------------------------------------
with tabs[1]:
    programs = fetch_programs()
    active_progs = programs[programs['Status'] != 'Completed'] if not programs.empty else pd.DataFrame()
    
    if active_progs.empty:
        st.info("No upcoming celebrations found. Please wait for the Admin to schedule one.")
    else:
        prog_options = {f"{r['Event_Name']} ({r['Date']})": r['Prog_ID'] for _, r in active_progs.iterrows()}
        sel_prog = st.selectbox("Select Celebration to Monitor Live", list(prog_options.keys()), key="live_prog")
        prog_id = prog_options[sel_prog]
        
        event_name_clean = sel_prog.split(' (')[0]
        ev_info = active_progs[active_progs['Prog_ID'] == prog_id].iloc[0]
        
        current_dt = datetime.now(IST)
        try:
            ev_dt_str = f"{ev_info['Date']} {ev_info['Start_Time']}"
            ev_dt = datetime.strptime(ev_dt_str, "%d-%m-%Y %I:%M %p")
            ev_dt = IST.localize(ev_dt)
            is_event_started = current_dt >= ev_dt
        except Exception:
            is_event_started = True 
        
        st.markdown(f"<div style='background: linear-gradient(135deg, #1e3c72, #2a5298); padding: 15px; border-radius: 10px; text-align: center; color: white; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'><h2 style='margin:0; font-size: 26px;'>🎉 {event_name_clean}</h2><p style='margin:2px 0 0 0; font-size: 14px; opacity: 0.9;'>🔴 LIVE PROGRAM DASHBOARD</p></div>", unsafe_allow_html=True)
        
        all_perfs = fetch_performances()
        event_perfs = all_perfs[all_perfs['Prog_ID'] == prog_id] if not all_perfs.empty else pd.DataFrame()
        
        if event_perfs.empty:
            st.warning("No performances have been added to this event yet.")
        else:
            event_perfs = event_perfs.sort_values('Order_No')
            
            for _, row in event_perfs.iterrows():
                is_done = (row['Live_Status'] == 'Done')
                is_canceled = (str(row.get('Cancel_Reason', '')) != "")
                
                bg_color = "#ffffff"
                border_color = "#007bff"
                opacity = "1.0"
                
                if is_canceled:
                    bg_color = "#f8d7da"
                    border_color = "#dc3545"
                    opacity = "0.6"
                    title_html = f"<s style='color:{border_color};'>#{row['Order_No']} - {row['Perf_Name']}</s> <span style='font-size:14px; color:#dc3545;'>[CANCELED]</span>"
                elif is_done:
                    bg_color = "#eafaf1"
                    border_color = "#28a745"
                    opacity = "0.7"
                    title_html = f"<span style='color:{border_color};'>#{row['Order_No']}</span> - {row['Perf_Name']}"
                else:
                    title_html = f"<span style='color:{border_color};'>#{row['Order_No']}</span> - {row['Perf_Name']}"
                
                yt_link = str(row['YouTube_Link']).strip()
                yt_html = ""
                if yt_link.startswith("http") and not is_canceled:
                    yt_html = f"<a href='{yt_link}' target='_blank' style='display:inline-block; background-color:#ff0000; color:white !important; padding:4px 8px; border-radius:4px; text-decoration:none; font-weight:bold; font-size:12px; box-shadow: 0 1px 2px rgba(0,0,0,0.2);'>▶️ Track</a>"
                
                sec_str = f"({row.get('Section','')})" if row.get('Section') and row.get('Section') != "TBD" else ""
                comp_time_str = f" | 🕒 {row.get('Completed_At', '')}" if is_done and row.get('Completed_At') else ""
                
                c1, c2 = st.columns([5, 1.5])
                
                with c1:
                    card_html = f"""
                    <div style="background-color: {bg_color}; border-left: 5px solid {border_color}; padding: 10px 12px; border-radius: 6px; box-shadow: 0 1px 4px rgba(0,0,0,0.1); margin-bottom: 5px; opacity: {opacity}; transition: all 0.2s;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <h4 style="margin:0; color:#333; font-size: 16px;">{title_html}</h4>
                                <p style="margin:2px 0 0 0; color:#555; font-size:13px;">
                                    {row['Perf_Type']} | {row['Class']} {sec_str} | {row['Choreographer']} {comp_time_str}
                                </p>
                            </div>
                            <div>{yt_html}</div>
                        </div>
                    </div>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)
                
                with c2:
                    st.write("") 
                    if not is_canceled:
                        if is_event_started:
                            chk = st.checkbox("✅ Done", value=is_done, key=f"live_chk_{row['Perf_ID']}")
                            if chk != is_done:
                                new_status = 'Done' if chk else 'Pending'
                                comp_timestamp = current_dt.strftime("%I:%M %p") if chk else ""
                                
                                all_perfs.loc[all_perfs['Perf_ID'] == row['Perf_ID'], 'Live_Status'] = new_status
                                all_perfs.loc[all_perfs['Perf_ID'] == row['Perf_ID'], 'Completed_At'] = comp_timestamp
                                overwrite_sheet("event_performances", all_perfs, PERF_HEADERS)
                                
                                action_txt = "Marked Completed" if chk else "Marked Pending"
                                log_audit(action_txt, f"{row['Perf_Name']} in {event_name_clean}")
                                st.rerun()
                        else:
                            st.markdown(f"<div style='margin-top:10px; font-size:13px; color:#e67e22; font-weight:bold;'>⏳ Starts at {ev_info['Start_Time']}</div>", unsafe_allow_html=True)
            st.write("")

# ---------------------------------------------------------
# TAB 3: TEACHER PERFORMANCE SUBMISSION
# ---------------------------------------------------------
with tabs[2]:
    st.markdown("<div class='header-card'><h4>🎭 Claim & Register Your Act</h4><p style='margin:0; font-size:14px;'>Complete the registration for the song/act assigned to you by the Head Teacher.</p></div>", unsafe_allow_html=True)
    
    programs = fetch_programs()
    active_progs = programs[programs['Status'] != 'Completed'] if not programs.empty else pd.DataFrame()
    
    if active_progs.empty:
        st.info("There are currently no upcoming celebrations scheduled.")
    else:
        prog_options = {f"{r['Event_Name']} ({r['Date']})": r['Prog_ID'] for _, r in active_progs.iterrows()}
        
        sel_prog_claim = st.selectbox("1. Select Celebration Event *", list(prog_options.keys()), key="claim_prog")
        prog_id_claim = prog_options[sel_prog_claim]
        
        all_perfs = fetch_performances()
        available_acts = all_perfs[(all_perfs['Prog_ID'] == prog_id_claim) & 
                                   (all_perfs['Class'] == "TBD") & 
                                   (all_perfs['Cancel_Reason'] == "") &
                                   (all_perfs['Choreographer'].isin(["TBD", current_user_name]))] if not all_perfs.empty else pd.DataFrame()
        
        if available_acts.empty:
            st.warning("⚠️ You currently have no unassigned curated acts for this event. You can add a custom act below.")
            
            with st.form("custom_perf_form"):
                st.markdown("##### ✨ Submit a Custom Act")
                c1, c2 = st.columns(2)
                perf_type = c1.selectbox("Performance Type *", PERFORMANCE_TYPES)
                perf_name = c2.text_input("Name of Song / Drama / Act *", placeholder="e.g., Alo Amar Alo")
                
                c3, c4 = st.columns(2)
                cls_sel = c3.selectbox("Participating Class *", CLASS_OPTIONS)
                sec_sel = c4.selectbox("Section", SECTIONS)
                
                c5, c6 = st.columns(2)
                with c5:
                    st.text_input("Choreographer (Read Only)", value=current_user_name, disabled=True)
                with c6:
                    dur = st.number_input("Estimated Duration (Minutes) *", min_value=1, max_value=45, value=5, step=1)
                
                yt_link = st.text_input("YouTube Track / Reference Link (Optional)", placeholder="Paste YouTube link here...")
                
                submit_act = st.form_submit_button("✅ Submit Custom Performance", use_container_width=True)
                
                if submit_act:
                    if not perf_name.strip():
                        st.error("Please provide a name for the performance!")
                    else:
                        new_id = uuid.uuid4().hex[:8]
                        new_act = {
                            "Perf_ID": new_id, "Prog_ID": prog_id_claim, "Order_No": 99, 
                            "Perf_Type": perf_type, "Perf_Name": perf_name.strip(),
                            "Class": cls_sel, "Section": sec_sel, "Choreographer": current_user_name,
                            "Duration_Mins": dur, "YouTube_Link": yt_link.strip(), "Live_Status": "Pending", 
                            "Completed_At": "", "Cancel_Reason": "", "Canceled_By": ""
                        }
                        updated_perfs = pd.concat([all_perfs, pd.DataFrame([new_act])], ignore_index=True)
                        overwrite_sheet("event_performances", updated_perfs, PERF_HEADERS)
                        log_audit("Added Custom Act", f"{perf_name.strip()} for {cls_sel}")
                        st.success(f"Custom Performance '{perf_name}' successfully added!")
                        st.rerun()

        else:
            act_dict = {f"{r['Perf_Name']} (Assigned to: {r['Choreographer']})": r['Perf_ID'] for _, r in available_acts.iterrows()}
            selected_act_label = st.selectbox("2. Select Act to Claim *", list(act_dict.keys()))
            
            if selected_act_label:
                target_id = act_dict[selected_act_label]
                target_act = available_acts[available_acts['Perf_ID'] == target_id].iloc[0]
                
                c1, c2 = st.columns(2)
                perf_type = c1.selectbox("Performance Type *", PERFORMANCE_TYPES)
                cls_sel = c2.selectbox("Participating Class *", CLASS_OPTIONS)
                
                c3, c4 = st.columns(2)
                sec_sel = c3.selectbox("Section", SECTIONS)
                with c4:
                    st.text_input("Choreographer (Read Only)", value=target_act['Choreographer'], disabled=True)
                
                dur = st.number_input("Estimated Duration (Minutes) *", min_value=1, max_value=45, value=5, step=1)
                
                if st.button("✅ Claim & Submit Performance", use_container_width=True):
                    choreo_val = current_user_name if target_act['Choreographer'] == "TBD" else target_act['Choreographer']
                    
                    all_perfs.loc[all_perfs['Perf_ID'] == target_id, ['Perf_Type', 'Class', 'Section', 'Choreographer', 'Duration_Mins', 'Live_Status']] = [perf_type, cls_sel, sec_sel, choreo_val, dur, "Pending"]
                    overwrite_sheet("event_performances", all_perfs, PERF_HEADERS)
                    log_audit("Claimed Curated Act", f"{target_act['Perf_Name']} for {cls_sel}")
                    st.success(f"Successfully claimed '{target_act['Perf_Name']}' for {cls_sel}!")
                    st.rerun()

# ---------------------------------------------------------
# TAB 4: PLAYLIST & SEQUENCE MANAGER
# ---------------------------------------------------------
with tabs[3]:
    st.markdown("<div class='header-card'><h4>📋 Event Playlist Manager</h4><p style='margin:0; font-size:14px;'>Review all acts and manage the event playlist.</p></div>", unsafe_allow_html=True)
    
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
            # Active performances calculation
            active_event_perfs = event_perfs[event_perfs['Cancel_Reason'] == ""]
            total_mins = pd.to_numeric(active_event_perfs['Duration_Mins'], errors='coerce').sum()
            hrs = int(total_mins // 60)
            mins = int(total_mins % 60)
            
            unclaimed_count = len(active_event_perfs[active_event_perfs['Class'] == "TBD"])
            kpi_html = f"""
            <div class='kpi-card'>
                <h3>⏱️ Estimated Duration: {hrs} Hours {mins} Mins</h3>
                <p style='margin:0; color:#555;'>({len(active_event_perfs)} Active Acts | <b>{unclaimed_count} Unclaimed</b>)</p>
            </div>
            """
            st.markdown(kpi_html, unsafe_allow_html=True)
            st.write("")
            
            def highlight_pl_row(s):
                is_canceled = str(s.get('Cancel_Reason', '')) != ""
                is_done = str(s.get('Live_Status', '')) == 'Done'
                if is_canceled:
                    return ['background-color: #f8d7da; color: #dc3545;' for _ in s]
                elif is_done:
                    return ['background-color: #d4edda; color: #155724;' for _ in s]
                return ['' for _ in s]
                
            # ===============================================
            # ADMIN VIEW: Interactive Reorder & Delete
            # ===============================================
            if current_user_role == "admin":
                canceled_acts = event_perfs[event_perfs['Cancel_Reason'] != ""]
                if not canceled_acts.empty:
                    st.error("⚠️ **CANCELED PERFORMANCES AWAITING REMOVAL**")
                    for _, r in canceled_acts.iterrows():
                        st.markdown(f"**{r['Perf_Name']}** | Choreographer: {r['Choreographer']} | <span style='color:red;'>Canceled by: {r['Canceled_By']}</span> | Reason: {r['Cancel_Reason']}", unsafe_allow_html=True)
                    st.write("")
                
                st.markdown("##### ↕️ Arrange Performance Order")
                st.caption("🖱️ **Click directly on any performance row below** to select it, then use the Up/Down arrows to move it.")

                # State tracking for order manipulation
                if 'current_pl_prog' not in st.session_state or st.session_state.current_pl_prog != view_prog_id:
                    st.session_state.current_pl_prog = view_prog_id
                    event_perfs = event_perfs.sort_values('Order_No').reset_index(drop=True)
                    event_perfs['Order_No'] = range(1, len(event_perfs) + 1) # Force strict sequential integers
                    st.session_state.local_pl_df = event_perfs.copy()
                    st.session_state.unsaved_pl = False

                local_df = st.session_state.local_pl_df

                edit_cols = ["Order_No", "Perf_Type", "Perf_Name", "Class", "Choreographer", "Duration_Mins", "Live_Status", "Cancel_Reason"]
                disp_df = local_df[edit_cols].copy()
                
                selection_event = st.dataframe(
                    disp_df.style.apply(highlight_pl_row, axis=1),
                    hide_index=True,
                    use_container_width=True,
                    selection_mode="single-row",
                    on_select="rerun",
                    key="pl_grid_selection",
                    column_config={"Cancel_Reason": None} # Hide raw reason column from grid
                )
                
                sel_idx = None
                if selection_event.selection.rows:
                    sel_idx = selection_event.selection.rows[0]
                
                col_up, col_dn, _ = st.columns([2, 2, 6])
                with col_up:
                    if st.button("⬆️ Move Up", disabled=(sel_idx is None or sel_idx == 0), use_container_width=True):
                        idx1, idx2 = sel_idx, sel_idx - 1
                        local_df.loc[idx1, 'Order_No'], local_df.loc[idx2, 'Order_No'] = local_df.loc[idx2, 'Order_No'], local_df.loc[idx1, 'Order_No']
                        local_df = local_df.sort_values('Order_No').reset_index(drop=True)
                        st.session_state.local_pl_df = local_df
                        st.session_state.unsaved_pl = True
                        st.rerun()
                with col_dn:
                    if st.button("⬇️ Move Down", disabled=(sel_idx is None or sel_idx == len(local_df)-1), use_container_width=True):
                        idx1, idx2 = sel_idx, sel_idx + 1
                        local_df.loc[idx1, 'Order_No'], local_df.loc[idx2, 'Order_No'] = local_df.loc[idx2, 'Order_No'], local_df.loc[idx1, 'Order_No']
                        local_df = local_df.sort_values('Order_No').reset_index(drop=True)
                        st.session_state.local_pl_df = local_df
                        st.session_state.unsaved_pl = True
                        st.rerun()

                if st.session_state.get('unsaved_pl', False):
                    st.markdown("<div class='local-warning'>⚠️ <b>Sequence modified locally!</b> Click save below to update Google Sheets.</div>", unsafe_allow_html=True)

                col_s1, col_s2 = st.columns([1, 1])
                with col_s1:
                    if st.button("💾 Save New Playlist Order", type="primary", use_container_width=True):
                        for _, r in local_df.iterrows():
                            all_perfs.loc[all_perfs['Perf_ID'] == r['Perf_ID'], 'Order_No'] = r['Order_No']
                        overwrite_sheet("event_performances", all_perfs, PERF_HEADERS)
                        log_audit("Reordered Playlist", f"For event: {view_prog.split(' (')[0]}")
                        st.session_state.unsaved_pl = False
                        st.success("Playlist order successfully updated!")
                        st.rerun()
                
                with col_s2:
                    del_id = st.selectbox("Remove a Performance Forever", ["Select to remove..."] + local_df['Perf_Name'].tolist())
                    if del_id != "Select to remove..." and st.button("🗑️ Delete Selected from Database"):
                        target_pid = local_df[local_df['Perf_Name'] == del_id].iloc[0]['Perf_ID']
                        all_perfs = all_perfs[all_perfs['Perf_ID'] != target_pid]
                        overwrite_sheet("event_performances", all_perfs, PERF_HEADERS)
                        log_audit("Deleted Performance", f"{del_id} from {view_prog.split(' (')[0]}")
                        st.session_state.current_pl_prog = None # force reset of local dataframe
                        st.success("Performance removed.")
                        st.rerun()
                        
            # ===============================================
            # TEACHER VIEW: View Data + Cancel Action
            # ===============================================
            else:
                st.markdown("##### 📜 Official Playlist")
                event_perfs = event_perfs.sort_values('Order_No')
                disp_df = event_perfs[["Order_No", "Perf_Type", "Perf_Name", "Class", "Choreographer", "Duration_Mins", "Live_Status", "Cancel_Reason"]].copy()
                st.dataframe(
                    disp_df.style.apply(highlight_pl_row, axis=1), 
                    hide_index=True, 
                    use_container_width=True,
                    column_config={"Cancel_Reason": None}
                )
                
                st.divider()
                st.markdown("##### 🚫 Cancel Performance")
                
                if not active_event_perfs.empty:
                    cancel_name = st.selectbox("Select a Performance to Cancel", ["Select to cancel..."] + active_event_perfs['Perf_Name'].tolist())
                    cancel_reason = st.selectbox("Reason for Cancellation", ["Students Absent", "Not Prepared", "Time Constraints", "Technical Issue", "Other"])
                    
                    custom_reason = ""
                    if cancel_reason == "Other":
                        custom_reason = st.text_input("Please specify the exact reason *", placeholder="Type your reason here...")
                    
                    if st.button("Submit Cancellation"):
                        if cancel_name != "Select to cancel...":
                            final_reason = custom_reason.strip() if cancel_reason == "Other" else cancel_reason
                            
                            if cancel_reason == "Other" and not final_reason:
                                st.error("Please specify a reason for cancellation.")
                            else:
                                target_pid = active_event_perfs[active_event_perfs['Perf_Name'] == cancel_name].iloc[0]['Perf_ID']
                                all_perfs.loc[all_perfs['Perf_ID'] == target_pid, ['Cancel_Reason', 'Canceled_By']] = [final_reason, current_user_name]
                                overwrite_sheet("event_performances", all_perfs, PERF_HEADERS)
                                log_audit("Canceled Performance", f"{cancel_name} canceled by {current_user_name}")
                                st.success("Performance cancellation submitted to Head Teacher.")
                                st.rerun()
                        else:
                            st.warning("Please select a valid performance.")

# ---------------------------------------------------------
# TAB 5 & 6: ADMIN TABS (HIDDEN FROM TEACHERS)
# ---------------------------------------------------------
if current_user_role == "admin":
    with tabs[4]:
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
                    log_audit("Scheduled Event", ev_name.strip())
                    st.success(f"Event '{ev_name}' created successfully!")
                    st.rerun()
                    
        st.divider()
        
        st.markdown("##### 🎵 Curate Songs / Acts for an Event")
        st.caption("Add specific songs or drama topics. Teachers will then log in and 'claim' them.")
        
        programs = fetch_programs()
        active_progs_admin = programs[programs['Status'] != 'Completed'] if not programs.empty else pd.DataFrame()
        
        if not active_progs_admin.empty:
            prog_opts_admin = {f"{r['Event_Name']} ({r['Date']})": r['Prog_ID'] for _, r in active_progs_admin.iterrows()}
            with st.form("add_act_form"):
                sel_prog_admin = st.selectbox("Select Celebration Event *", list(prog_opts_admin.keys()))
                act_name = st.text_input("Name of Song / Drama / Act *", placeholder="e.g., Alo Amar Alo")
                yt_link = st.text_input("YouTube Track / Reference Link (Optional)", placeholder="Paste YouTube link here...")
                choreo_assign = st.selectbox("Assign to Teacher *", ["TBD (Any Teacher)"] + TEACHER_LIST)
                
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
                            "Choreographer": choreo_assign if choreo_assign != "TBD (Any Teacher)" else "TBD",
                            "Duration_Mins": 0,
                            "YouTube_Link": yt_link.strip(),
                            "Live_Status": "Pending",
                            "Completed_At": "",
                            "Cancel_Reason": "",
                            "Canceled_By": ""
                        }
                        curr_perfs = fetch_performances()
                        updated_perfs = pd.concat([curr_perfs, pd.DataFrame([new_act])], ignore_index=True)
                        overwrite_sheet("event_performances", updated_perfs, PERF_HEADERS)
                        log_audit("Added Curated Act to Pool", f"{act_name.strip()} in {sel_prog_admin.split(' (')[0]}")
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
                log_audit("Completed Event", f"Closed out {mk_comp}")
                st.success(f"{mk_comp} moved to Completed history.")
                st.rerun()
                
    with tabs[5]:
        st.markdown("### 📝 System Audit Log")
        st.caption("See a live ledger of who modified what within the Celebration module.")
        
        audit_data = fetch_audit_log()
        
        if audit_data.empty:
            st.info("No modifications have been logged yet.")
        else:
            audit_data = audit_data.iloc[::-1]
            st.dataframe(audit_data, hide_index=True, use_container_width=True)
            if st.button("🗑️ Clear Audit Log"):
                overwrite_sheet("event_audit_log", pd.DataFrame(columns=AUDIT_HEADERS), AUDIT_HEADERS)
                st.rerun()
