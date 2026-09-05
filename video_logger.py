import streamlit as st
import pandas as pd
import time
from datetime import datetime
import pytz
import gspread
from gspread.exceptions import WorksheetNotFound, APIError
from google.oauth2.service_account import Credentials

# --- Configuration & Setup ---
st.set_page_config(page_title="BPS Video Logger", page_icon="🎥", layout="centered")
IST = pytz.timezone('Asia/Kolkata')

# --- Custom Button CSS ---
st.markdown("""
<style>
/* Make ALL Primary buttons Solid Blue (Start Recording) */
button[kind="primary"] {
    background: #007bff !important;
    background-color: #007bff !important;
    border: 2px solid #007bff !important;
    color: white !important;
    border-radius: 8px !important;
}
button[kind="primary"]:hover, 
button[kind="primary"]:focus, 
button[kind="primary"]:active {
    background: #0056b3 !important;
    background-color: #0056b3 !important;
    border-color: #0056b3 !important;
    color: white !important;
}
button[kind="primary"] * {
    color: white !important;
}

/* Make Primary buttons inside the 2nd column Solid Red (Stop Recording) */
div[data-testid="column"]:nth-of-type(2) button[kind="primary"] {
    background: #dc3545 !important;
    background-color: #dc3545 !important;
    border: 2px solid #dc3545 !important;
}
div[data-testid="column"]:nth-of-type(2) button[kind="primary"]:hover,
div[data-testid="column"]:nth-of-type(2) button[kind="primary"]:focus,
div[data-testid="column"]:nth-of-type(2) button[kind="primary"]:active {
    background: #c82333 !important;
    background-color: #c82333 !important;
    border-color: #c82333 !important;
}

/* Style Secondary buttons (Need Edit Marker) */
button[kind="secondary"] {
    font-weight: bold !important;
    border-radius: 8px !important;
}
</style>
""", unsafe_allow_html=True)

# --- State Management ---
if 'is_recording' not in st.session_state:
    st.session_state.is_recording = False
if 'current_row' not in st.session_state:
    st.session_state.current_row = None
if 'start_dt' not in st.session_state:
    st.session_state.start_dt = None
if 'edit_markers' not in st.session_state:
    st.session_state.edit_markers = []
if 'perf_name' not in st.session_state:
    st.session_state.perf_name = ""

# --- Google Sheets Connectors ---
@st.cache_resource
def get_google_credentials():
    return Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )

@st.cache_resource
def init_sheet():
    try: 
        return gspread.authorize(get_google_credentials()).open_by_key("1TXs2o0OnpPz1nr_AnhzrwR_OA3FsAss9gwGvbB6LHQo")
    except Exception as e: 
        st.error(f"⚠️ Connection Error: {e}")
        st.stop()

def get_video_worksheet(sh):
    try: 
        ws = sh.worksheet("Video Clips")
    except WorksheetNotFound:
        ws = sh.add_worksheet(title="Video Clips", rows=1000, cols=10)
        ws.append_row(["Date", "Start", "End", "Duration", "Perf_Name", "Edit_Timestamps"])
    return ws

@st.cache_data(ttl=60)
def fetch_performances():
    sh = init_sheet()
    try:
        ws = sh.worksheet("event_performances")
        data = ws.get_all_values()
        if not data or len(data) <= 1:
            return []
        df = pd.DataFrame(data[1:], columns=data[0])
        if not df.empty and 'Order_No' in df.columns:
            df['Order_No'] = pd.to_numeric(df['Order_No'], errors='coerce').fillna(99).astype(int)
            df = df.sort_values('Order_No')
            return df['Perf_Name'].tolist()
        return []
    except WorksheetNotFound:
        return []

@st.cache_data(ttl=5)
def fetch_video_logs():
    sh = init_sheet()
    ws = get_video_worksheet(sh)
    data = ws.get_all_values()
    
    expected_headers = ["Date", "Start", "End", "Duration", "Perf_Name", "Edit_Timestamps"]
    
    if not data or len(data) <= 1:
        return pd.DataFrame(columns=expected_headers)
    
    # Check if we need to silently fix the header row in Google Sheets
    try:
        if len(data[0]) < 6 or str(data[0][5]).strip() == "":
            ws.update_acell("F1", "Edit_Timestamps")
    except:
        pass

    # Process rows safely enforcing exactly our 6 headers
    rows = []
    for row in data[1:]:
        current_row = list(row)
        while len(current_row) < 6:
            current_row.append("")
        rows.append(current_row[:6])

    return pd.DataFrame(rows, columns=expected_headers)

# --- Main UI ---
st.markdown("<h2 style='text-align: center; color: #e83e8c;'>🎥 BPS Live Video Logger</h2>", unsafe_allow_html=True)
st.write("---")

sh = init_sheet()
video_ws = get_video_worksheet(sh)

# ==========================================
# 1. RECORDING CONTROLS
# ==========================================
if not st.session_state.is_recording:
    st.markdown("### 🎬 Setup New Clip")
    perf_list = fetch_performances()
    
    options = ["-- Select Performance --"] + perf_list + ["✨ Custom / Out of List"]
    selected_perf = st.selectbox("Select Performance Being Recorded:", options)
    
    custom_perf = ""
    if selected_perf == "✨ Custom / Out of List":
        custom_perf = st.text_input("Enter Custom Performance Name:")
    
    if st.button("🔵 Start Recording", type="primary", use_container_width=True):
        final_name = custom_perf.strip() if selected_perf == "✨ Custom / Out of List" else selected_perf
        
        if selected_perf == "-- Select Performance --" or (selected_perf == "✨ Custom / Out of List" and not custom_perf.strip()):
            st.error("⚠️ Please select or enter a performance name before recording.")
        else:
            # 5-Second Start Countdown
            countdown_ph = st.empty()
            for i in range(5, 0, -1):
                countdown_ph.markdown(f"<h3 style='text-align:center; color:#007bff;'>Recording starts in {i}...</h3>", unsafe_allow_html=True)
                time.sleep(1)
            countdown_ph.empty()
            
            # Record Start
            now = datetime.now(IST)
            date_str = now.strftime("%d-%m-%Y")
            start_str = now.strftime("%I:%M:%S %p")
            
            # The exact formula you provided
            formula = '=IF(INDIRECT("C"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("C"&ROW())-INDIRECT("B"&ROW()), 1), "h:mm"), ""))'
            
            new_row = [date_str, start_str, "RUNNING", formula, final_name, ""]
            
            # Append to sheet and find row number
            video_ws.append_row(new_row, value_input_option='USER_ENTERED')
            all_vals = video_ws.get_all_values()
            target_row = len(all_vals)
            
            # Update State
            st.session_state.is_recording = True
            st.session_state.current_row = target_row
            st.session_state.start_dt = now
            st.session_state.perf_name = final_name
            st.session_state.edit_markers = []
            
            st.rerun()

else:
    # 🔴 ACTIVELY RECORDING VIEW
    st.markdown(f"""
    <div style='background-color: #ffebee; border: 2px solid #dc3545; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 20px;'>
        <h2 style='margin:0; color: #c62828;'>🔴 RECORDING LIVE</h2>
        <p style='margin:5px 0 0 0; font-size: 18px;'><b>{st.session_state.perf_name}</b></p>
        <p style='margin:0; color: #555;'>Started at: {st.session_state.start_dt.strftime("%I:%M:%S %p")}</p>
    </div>
    """, unsafe_allow_html=True)
    
    stop_ph = st.empty() # Placeholder for the ending countdown
    c1, c2 = st.columns(2)
    
    with c1:
        if st.button("✂️ Need Edit Marker", help="Marks the current timestamp for later editing", use_container_width=True):
            # Calculate elapsed time for the editor
            elapsed = datetime.now(IST) - st.session_state.start_dt
            total_sec = int(elapsed.total_seconds())
            m, s = divmod(total_sec, 60)
            h, m = divmod(m, 60)
            timestamp_str = f"[{h:02d}:{m:02d}:{s:02d}]" if h > 0 else f"[{m:02d}:{s:02d}]"
            
            st.session_state.edit_markers.append(timestamp_str)
            markers_joined = ", ".join(st.session_state.edit_markers)
            
            # Update the specific cell in column F (Column 6)
            video_ws.update_acell(f"F{st.session_state.current_row}", markers_joined)
            st.toast(f"✅ Edit marker logged at {timestamp_str}")
            
    with c2:
        if st.button("⏹️ Stop Recording", type="primary", use_container_width=True):
            
            # 5-Second Ending Buffer Countdown
            for i in range(5, 0, -1):
                stop_ph.markdown(f"""
                <div style='background-color: #fff3cd; border: 2px solid #ffc107; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 20px;'>
                    <h3 style='margin:0; color:#856404;'>⏳ Capturing final buffer... ({i}s)</h3>
                </div>
                """, unsafe_allow_html=True)
                time.sleep(1)
            stop_ph.empty()
            
            # Record End Time exactly after the 5 seconds is up
            end_dt = datetime.now(IST)
            end_str = end_dt.strftime("%I:%M:%S %p")
            
            # Update End Time in column C (Column 3)
            video_ws.update_acell(f"C{st.session_state.current_row}", end_str)
            
            # Clear State
            st.session_state.is_recording = False
            st.session_state.current_row = None
            st.session_state.start_dt = None
            st.session_state.perf_name = ""
            st.session_state.edit_markers = []
            
            fetch_video_logs.clear()
            st.success("✅ Clip successfully logged and saved!")
            time.sleep(1.5)
            st.rerun()
            
    if st.session_state.edit_markers:
        st.markdown("**Logged Edit Markers (Elapsed Time):**")
        st.code(", ".join(st.session_state.edit_markers))

st.write("---")

# ==========================================
# 2. VIDEO EDITING REFERENCE LOG
# ==========================================
st.markdown("### 🗂️ Video Editing Reference Log")
st.caption("Review your clips here to quickly jump to the exact timestamps during editing.")

if st.button("🔄 Refresh Video Logs"):
    fetch_video_logs.clear()

logs_df = fetch_video_logs()

if logs_df.empty:
    st.info("No video clips have been recorded yet.")
else:
    # Sort newest first
    logs_df = logs_df.iloc[::-1]
    
    st.dataframe(
        logs_df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Date": st.column_config.TextColumn("Date"),
            "Start": st.column_config.TextColumn("Start Time"),
            "End": st.column_config.TextColumn("End Time"),
            "Duration": st.column_config.TextColumn("Duration"),
            "Perf_Name": st.column_config.TextColumn("Performance"),
            "Edit_Timestamps": st.column_config.TextColumn("✂️ Edit Markers")
        }
    )
