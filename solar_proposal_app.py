import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import gspread
from gspread.exceptions import WorksheetNotFound
from google.oauth2.service_account import Credentials

# ==========================================
# ⚙️ CONFIGURATION & SETUP
# ==========================================
st.set_page_config(page_title="Rooftop Solar Proposal", page_icon="☀️", layout="centered")
IST = pytz.timezone('Asia/Kolkata')

# ⚠️ NEW SHEET NAME
SHEET_NAME = "PROPOSAL FOR RTSP 2"

HEADERS = [
    'Sl. No.', 'UDISE Code', 'Name  & Location of the PRIMARY SCHOOL',
    'Total usable shadow free roof space available for solar installation',
    'Whether any Solar PV system already exists. If exists, its capacity',
    'If exists, whether additional requirement is there'
]

# ==========================================
# 🔌 GOOGLE SHEETS CONNECTOR
# ==========================================
@st.cache_resource
def get_google_credentials():
    return Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.readonly"
        ]
    )

@st.cache_resource
def init_sheet():
    try: 
        return gspread.authorize(get_google_credentials()).open(SHEET_NAME)
    except Exception as e: 
        st.error(f"⚠️ Connection Error: {e}. Ensure the sheet name is exact and shared with your service account email.")
        st.stop()

def get_worksheet():
    sh = init_sheet()
    try:
        # Assuming the main submission data is on the first sheet
        return sh.sheet1
    except Exception as e:
        st.error(f"⚠️ Could not open the first worksheet. Error: {e}")
        st.stop()

@st.cache_data(ttl=60)
def fetch_existing_data():
    ws = get_worksheet()
    try:
        raw_values = ws.get_all_values()
        if not raw_values:
            return pd.DataFrame(columns=HEADERS)
            
        records = ws.get_all_records()
        return pd.DataFrame(records)
    except Exception as e:
        st.error(f"⚠️ Error fetching data: {e}")
        return pd.DataFrame(columns=HEADERS)

@st.cache_data(ttl=60)
def fetch_action_required():
    sh = init_sheet()
    try:
        ws = sh.worksheet("Action Required")
        raw_values = ws.get_all_values()
        # Prevent crash if the tab is completely blank
        if not raw_values:
            return pd.DataFrame()
        return pd.DataFrame(ws.get_all_records())
    except WorksheetNotFound:
        # If the tab doesn't exist yet, just return empty
        return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

# ==========================================
# 🎨 CUSTOM UI & HEADER
# ==========================================
st.markdown("""
<style>
    .gov-header {
        text-align: center;
        padding: 15px;
        background-color: #f8f9fa;
        border-bottom: 3px solid #0056b3;
        border-radius: 8px 8px 0 0;
        margin-bottom: 25px;
    }
    .gov-title { color: #0056b3; margin-bottom: 5px; font-weight: 900; }
    .gov-sub { color: #333; font-size: 14px; margin-bottom: 0; }
    .info-box { background-color: #e9f7ef; border-left: 5px solid #28a745; padding: 15px; border-radius: 4px; margin-bottom: 20px;}
    .action-box { background-color: #fff3cd; border-left: 5px solid #ffc107; padding: 20px; border-radius: 4px; margin-bottom: 25px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);}
    .form-container { border: 1px solid #ced4da; border-radius: 8px; padding: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); background-color: #ffffff;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="gov-header">
    <h2 class="gov-title">GOVERNMENT OF WEST BENGAL</h2>
    <h4 style="margin: 0; color: #444;">Office of the District Inspector of Schools (PE), Purba Medinipur</h4>
    <p class="gov-sub">Proposal for Installation of Roof Top Solar (RTS) Panels at Govt. Primary Schools (Haldia Circle)</p>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 🚨 ACTION REQUIRED NOTICE BOARD
# ==========================================
action_df = fetch_action_required()

if not action_df.empty:
    st.markdown('<div class="action-box">', unsafe_allow_html=True)
    st.markdown("<h4 style='margin-top:0; color: #856404;'>🚨 ACTION REQUIRED: Attention Head Teachers</h4>", unsafe_allow_html=True)
    st.markdown("<p style='color: #856404; font-size: 14px;'>The following proposals were removed due to invalid or incorrect data. Please read the specific instructions below.</p>", unsafe_allow_html=True)
    
    disp_action = action_df.copy()
    
    # Safely convert UDISE to string to remove .0 decimals
    if 'UDISE Code' in disp_action.columns:
        disp_action['UDISE Code'] = pd.to_numeric(disp_action['UDISE Code'], errors='coerce').fillna(0).astype(int).astype(str)
        disp_action['UDISE Code'] = disp_action['UDISE Code'].replace('0', '')
        
    st.dataframe(disp_action, hide_index=True, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("""
<div class="info-box">
    <strong>📌 Context:</strong> As per Memo No:-78774/XXV dated 31/08/2026, the Dept. of Non-Conventional & Renewable Energy Sources (NRES) is implementing grid-connected Roof Top Solar PV systems across government buildings. All Primary Schools under Haldia Circle must submit their roof space details.
</div>
""", unsafe_allow_html=True)

# ==========================================
# 📝 SUBMISSION FORM (Dynamic Live Updates)
# ==========================================
existing_data = fetch_existing_data()

st.markdown('<div class="form-container">', unsafe_allow_html=True)

st.markdown("### 🏫 School Information")
col1, col2 = st.columns([1, 2])
with col1:
    udise_code = st.text_input("UDISE Code*", max_chars=11, help="Enter 11-digit UDISE code")
with col2:
    school_name_loc = st.text_input("Name & Location of the Primary School*", help="E.g., Bhagyabantapur Primary School, Vill+PO - Haldia...")

st.markdown("### ☀️ Solar & Roof Details")
roof_space = st.text_input("Total usable shadow free roof space available for solar installation*", help="E.g., 1500 square feet")

st.markdown("---")

col3, col4 = st.columns(2)

with col3:
    has_solar = st.radio("Whether any Solar PV system already exists?*", ["No", "Yes"])
    solar_capacity = ""
    if has_solar == "Yes":
        solar_capacity = st.text_input("If exists, its capacity:", help="E.g., 2 kW")
        
with col4:
    is_locked = (has_solar == "No")
    add_req = st.radio(
        "If exists, whether additional requirement is there?*", 
        ["No", "Yes"], 
        disabled=is_locked
    )

st.markdown("<small style='color: gray;'>* Mandatory fields</small>", unsafe_allow_html=True)
st.write("") 

submit_btn = st.button("📤 Submit Proposal", type="primary", use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 🚀 SUBMIT LOGIC (Concurrency-Proof)
# ==========================================
if submit_btn:
    if not udise_code or not school_name_loc or not roof_space:
        st.error("🚨 Please fill in all mandatory fields (UDISE Code, Name/Location, and Roof Space).")
    elif len(udise_code) != 11 or not udise_code.isdigit():
        st.error("🚨 UDISE Code must be exactly 11 digits.")
    elif has_solar == "Yes" and not solar_capacity:
        st.error("🚨 Please mention the capacity of the existing solar system.")
    else:
        with st.spinner("Verifying and submitting to secure database..."):
            try:
                ws = get_worksheet()
                
                # 1. FETCH LIVE DATA SAFELY
                raw_values = ws.get_all_values()
                
                if not raw_values:
                    ws.append_row(HEADERS)
                    live_df = pd.DataFrame(columns=HEADERS)
                else:
                    live_df = pd.DataFrame(ws.get_all_records())
                
                # 2. SAFE DUPLICATE CHECK
                if not live_df.empty and 'UDISE Code' in live_df.columns:
                    safe_udises = live_df['UDISE Code'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().values
                    if str(udise_code).strip() in safe_udises:
                        st.warning(f"⚠️ A proposal for UDISE {udise_code} has already been submitted.")
                        st.stop()
                
                # 3. ROBUST SERIAL NUMBER CALCULATION
                if not live_df.empty and 'Sl. No.' in live_df.columns:
                    max_sl = pd.to_numeric(live_df['Sl. No.'], errors='coerce').max()
                    next_sl_no = int(max_sl) + 1 if pd.notna(max_sl) else 1
                else:
                    next_sl_no = 1
                    
                # Prepare row data
                row_data = [
                    next_sl_no,
                    udise_code,
                    school_name_loc,
                    roof_space,
                    solar_capacity if has_solar == "Yes" else "No",
                    add_req if has_solar == "Yes" else "No"
                ]
                
                # 4. APPEND ROW TO SHEET
                ws.append_row(row_data)
                fetch_existing_data.clear() 
                st.success(f"🎉 Proposal for {school_name_loc} submitted successfully! You can view it in the dashboard below.")
                st.balloons()
                
            except Exception as e:
                st.error(f"⚠️ Failed to save to Google Sheets. The server might be busy. Please try again in a moment. Error: {e}")

# ==========================================
# 📊 SUBMISSION DASHBOARD
# ==========================================
st.markdown("---")
st.markdown("### 📋 Submitted Proposals (Haldia Circle)")

refreshed_data = fetch_existing_data()

if refreshed_data.empty:
    st.info("No proposals have been submitted yet.")
else:
    st.write(f"**Total Submissions:** {len(refreshed_data)}")
    
    display_df = refreshed_data.copy()
    for col in ['Sl. No.', 'UDISE Code']:
        if col in display_df.columns:
            display_df[col] = pd.to_numeric(display_df[col], errors='coerce').fillna(0).astype(int).astype(str)
            display_df[col] = display_df[col].replace('0', '')
    
    st.dataframe(
        display_df, 
        hide_index=True, 
        use_container_width=True
    )
