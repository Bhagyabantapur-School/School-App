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

# ⚠️ VERY IMPORTANT: The exact name of your Google Sheet
SHEET_NAME = "PROPOSAL FOR ROOF TOP  SOLAR PANEL FOR GOVT. PRIMARY SCHOOLS UNDER HALDIA CIRCLE"

# ==========================================
# 🔌 GOOGLE SHEETS CONNECTOR (WITH DRIVE SCOPE FIXED)
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
        # Assuming the data is on the first sheet
        return sh.sheet1
    except Exception as e:
        st.error(f"⚠️ Could not open the first worksheet. Error: {e}")
        st.stop()

@st.cache_data(ttl=60)
def fetch_existing_data():
    ws = get_worksheet()
    try:
        records = ws.get_all_records()
        if records:
            return pd.DataFrame(records)
        else:
            return pd.DataFrame(columns=[
                'Sl. No.', 'UDISE Code', 'Name  & Location of the PRIMARY SCHOOL',
                'Total usable shadow free roof space available for solar installation',
                'Whether any Solar PV system already exists. If exists, its capacity',
                'If exists, whether additional requirement is there'
            ])
    except Exception as e:
        st.error(f"⚠️ Error fetching data: {e}")
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
    div[data-testid="stForm"] { border: 1px solid #ced4da; border-radius: 8px; padding: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="gov-header">
    <h2 class="gov-title">GOVERNMENT OF WEST BENGAL</h2>
    <h4 style="margin: 0; color: #444;">Office of the District Inspector of Schools (PE), Purba Medinipur</h4>
    <p class="gov-sub">Proposal for Installation of Roof Top Solar (RTS) Panels at Govt. Primary Schools (Haldia Circle)</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="info-box">
    <strong>📌 Context:</strong> As per Memo No:-78774/XXV dated 31/08/2026, the Dept. of Non-Conventional & Renewable Energy Sources (NRES) is implementing grid-connected Roof Top Solar PV systems across government buildings. All Primary Schools under Haldia Circle must submit their roof space details.
</div>
""", unsafe_allow_html=True)

# ==========================================
# 📝 SUBMISSION FORM
# ==========================================
existing_data = fetch_existing_data()

with st.form("solar_proposal_form"):
    st.markdown("### 🏫 School Information")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        udise_code = st.text_input("UDISE Code*", max_chars=11, help="Enter 11-digit UDISE code")
    with col2:
        school_name_loc = st.text_input("Name & Location of the Primary School*", help="E.g., Bhagyabantapur Primary School, Vill+PO - Haldia...")

    st.markdown("### ☀️ Solar & Roof Details")
    roof_space = st.text_input("Total usable shadow free roof space available for solar installation*", help="E.g., 1500 square feet")
    
    st.markdown("---")
    
    has_solar = st.radio("Does the school already have a Solar PV system installed?", ["No", "Yes"])
    
    solar_capacity = ""
    add_req = ""
    
    if has_solar == "Yes":
        col3, col4 = st.columns(2)
        with col3:
            solar_capacity = st.text_input("If Yes, what is its capacity?", help="E.g., 2 kW")
        with col4:
            add_req = st.radio("If exists, is there an additional requirement?", ["No", "Yes"])

    st.markdown("<small style='color: gray;'>* Mandatory fields</small>", unsafe_allow_html=True)
    
    submit_btn = st.form_submit_button("📤 Submit Proposal", type="primary", use_container_width=True)
    
    if submit_btn:
        if not udise_code or not school_name_loc or not roof_space:
            st.error("🚨 Please fill in all mandatory fields (UDISE Code, Name/Location, and Roof Space).")
        elif len(udise_code) != 11 or not udise_code.isdigit():
            st.error("🚨 UDISE Code must be exactly 11 digits.")
        else:
            with st.spinner("Verifying and submitting to secure database..."):
                try:
                    ws = get_worksheet()
                    
                    # 1. FETCH LIVE DATA (Bypasses the 60-second cache to prevent simultaneous overlap)
                    live_records = ws.get_all_records()
                    live_df = pd.DataFrame(live_records) if live_records else pd.DataFrame()
                    
                    # 2. LIVE DUPLICATE CHECK
                    if not live_df.empty and 'UDISE Code' in live_df.columns:
                        if int(udise_code) in live_df['UDISE Code'].astype(int).values:
                            st.warning(f"⚠️ A proposal for UDISE {udise_code} has already been submitted.")
                            st.stop()
                    
                    # 3. LIVE SERIAL NUMBER CALCULATION
                    next_sl_no = len(live_df) + 1 if not live_df.empty else 1
                        
                    # Prepare row data (Must exactly match CSV headers)
                    row_data = [
                        next_sl_no,
                        udise_code,
                        school_name_loc,
                        roof_space,
                        solar_capacity if has_solar == "Yes" else "No",
                        add_req if has_solar == "Yes" else "N/A"
                    ]
                    
                    # If sheet is totally empty, write headers first
                    if len(ws.get_all_values()) == 0:
                        headers = [
                            'Sl. No.', 'UDISE Code', 'Name  & Location of the PRIMARY SCHOOL',
                            'Total usable shadow free roof space available for solar installation',
                            'Whether any Solar PV system already exists. If exists, its capacity',
                            'If exists, whether additional requirement is there'
                        ]
                        ws.append_row(headers)
                    
                    # 4. APPEND ROW TO SHEET
                    ws.append_row(row_data)
                    fetch_existing_data.clear() # Clear dashboard cache to show new data
                    st.success(f"🎉 Proposal for {school_name_loc} submitted successfully!")
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
    # Display total count
    st.write(f"**Total Submissions:** {len(refreshed_data)}")
    
    # Show dataframe (hide index for cleaner look)
    st.dataframe(
        refreshed_data, 
        hide_index=True, 
        use_container_width=True,
        column_config={
            "Sl. No.": st.column_config.NumberColumn("Sl. No.", format="%d"),
            "UDISE Code": st.column_config.NumberColumn("UDISE Code", format="%d")
        }
    )
