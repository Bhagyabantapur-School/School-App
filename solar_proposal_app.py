import streamlit as st
import pandas as pd
import re
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

# ⚠️ DUAL SHEET CONFIGURATION
MAIN_SHEET_NAME = "PROPOSAL FOR ROOF TOP  SOLAR PANEL FOR GOVT. PRIMARY SCHOOLS UNDER HALDIA CIRCLE"
NOTICE_SHEET_NAME = "PROPOSAL FOR RTSP 2"

# ⏱️ DEADLINE SETTING
DEADLINE = IST.localize(datetime(2026, 9, 23, 23, 59, 0))

# ==========================================
# 🧠 SESSION STATE INITIALIZATION
# ==========================================
if 'checked_udise' not in st.session_state:
    st.session_state.checked_udise = None
if 'is_editing' not in st.session_state:
    st.session_state.is_editing = False
if 'matched_row' not in st.session_state:
    st.session_state.matched_row = {}
if 'success_msg' not in st.session_state:
    st.session_state.success_msg = ""

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
def init_main_sheet():
    try: 
        return gspread.authorize(get_google_credentials()).open(MAIN_SHEET_NAME)
    except Exception as e: 
        st.error(f"⚠️ Main DB Connection Error: {e}")
        st.stop()

@st.cache_resource
def init_notice_sheet():
    try: 
        return gspread.authorize(get_google_credentials()).open(NOTICE_SHEET_NAME)
    except Exception as e: 
        st.error(f"⚠️ Notice DB Connection Error: {e}")
        st.stop()

def get_worksheet():
    sh = init_main_sheet()
    try:
        return sh.worksheet("Sheet1")
    except Exception as e:
        st.error(f"⚠️ Could not open 'Sheet1' in Main DB. Error: {e}")
        st.stop()

@st.cache_data(ttl=60)
def fetch_existing_data():
    ws = get_worksheet()
    try:
        vals = ws.get_all_values()
        if not vals:
            return pd.DataFrame(columns=[
                'Sl. No.', 'UDISE Code', 'Name  & Location of the PRIMARY SCHOOL',
                'Total usable shadow free roof space available for solar installation',
                'Whether any Solar PV system already exists. If exists, its capacity',
                'If exists, whether additional requirement is there'
            ])
        else:
            return pd.DataFrame(ws.get_all_records())
    except Exception as e:
        st.error(f"⚠️ Error fetching data: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=60)
def fetch_action_required():
    sh = init_notice_sheet()
    try:
        ws = sh.worksheet("Action Required")
        raw_values = ws.get_all_values()
        
        if len(raw_values) <= 1:
            return pd.DataFrame()
            
        df = pd.DataFrame(raw_values)
        df.columns = df.iloc[0].astype(str).str.strip() 
        df = df[1:].copy()
        
        # Keep rows that have at least some data in UDISE or School Name
        df = df.dropna(subset=[col for col in ['UDISE Code', 'School Name'] if col in df.columns], how='all')
            
        return df
    except WorksheetNotFound:
        return pd.DataFrame()
    except Exception as e:
        st.error(f"⚠️ Action Tab Error: {e}") 
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
    .action-box { background-color: #fff3cd; border-left: 5px solid #ffc107; padding: 20px; border-radius: 4px; margin-bottom: 25px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);}
    .timer-box { background-color: #e9ecef; color: #495057; padding: 12px; border-radius: 5px; text-align: center; font-weight: bold; margin-bottom: 25px; border: 1px solid #ced4da; }
    .closed-box { background-color: #f8d7da; color: #721c24; padding: 20px; border-radius: 8px; border: 1px solid #f5c6cb; margin-bottom: 25px; text-align: center; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="gov-header">
    <h2 class="gov-title">GOVERNMENT OF WEST BENGAL</h2>
    <h4 style="margin: 0; color: #444;">Office of the District Inspector of Schools (PE), Purba Medinipur</h4>
    <p class="gov-sub">Proposal for Installation of Roof Top Solar (RTS) Panels at Govt. Primary Schools (Haldia Circle)</p>
</div>
""", unsafe_allow_html=True)

existing_data = fetch_existing_data()
current_time = datetime.now(IST)
is_active = current_time <= DEADLINE

# ==========================================
# ⏳ CONDITIONAL RENDERING (ACTIVE vs CLOSED)
# ==========================================
if is_active:
    time_left = DEADLINE - current_time
    days = time_left.days
    hours = time_left.seconds // 3600
    minutes = (time_left.seconds % 3600) // 60
    
    st.markdown(f"""
    <div class="timer-box">
        ⏳ <strong>Deadline:</strong> 23.09.2026 (11:59 PM) &nbsp;|&nbsp; 
        <strong>Time Left:</strong> <span style='color: #d9534f;'>{days} Days, {hours} Hours, {minutes} Minutes</span>
    </div>
    """, unsafe_allow_html=True)

    # --- 🚨 ACTION REQUIRED NOTICE BOARD ---
    if st.button("🔄 Refresh Notice Board", help="শিটে আপডেট করার পর এখানে ক্লিক করে নতুন নোটিশ লোড করুন"):
        fetch_action_required.clear()
        fetch_existing_data.clear()

    action_df = fetch_action_required()

    if not action_df.empty:
        disp_action = action_df.copy()
        
        # Format UDISE for display only
        if 'UDISE Code' in disp_action.columns:
            disp_action['UDISE Code'] = pd.to_numeric(disp_action['UDISE Code'], errors='coerce').fillna(0).astype(int).astype(str)
            disp_action['UDISE Code'] = disp_action['UDISE Code'].replace('0', '').str.strip()
            
        # 🧠 SMART NAME-BASED AUTO DISAPPEAR LOGIC
        if not existing_data.empty and 'Name  & Location of the PRIMARY SCHOOL' in existing_data.columns and 'School Name' in disp_action.columns:
            # 1. Get all submitted names and normalize them (lowercase, replace multiple spaces with one, strip edge spaces)
            main_names = existing_data['Name  & Location of the PRIMARY SCHOOL'].astype(str).str.lower().str.replace(r'\s+', ' ', regex=True).str.strip().tolist()
            
            def is_already_submitted_by_name(notice_name):
                n_name = str(notice_name).lower().strip()
                n_name = re.sub(r'\s+', ' ', n_name)
                
                if not n_name or n_name == 'nan': 
                    return False
                
                # 2. Check if the notice board name is a substring inside any submitted name
                for m_name in main_names:
                    if n_name in m_name:
                        return True
                return False
                
            # Filter out schools whose names match
            disp_action = disp_action[~disp_action['School Name'].apply(is_already_submitted_by_name)]
                
        if not disp_action.empty:
            def get_bengali_instruction(reason):
                r_lower = str(reason).lower()
                if "0" in r_lower or "sq ft" in r_lower or "zero" in r_lower or "space" in r_lower:
                    return "আপনি ছাঁদে ০ স্কয়ার ফিট জায়গা আছে বলেছেন। যদি এটি সত্যি হয়, তবে আপনার আর কিছু করার প্রয়োজন নেই। যদি এটি টাইপিং ভুল হয়, তবে সঠিক আয়তন দিয়ে পুনরায় আপডেট করুন।"
                elif "invalid" in r_lower or "incorrect" in r_lower or "wrong" in r_lower or "error" in r_lower:
                    return "আপনার দেওয়া তথ্যটি অসম্পূর্ণ বা ভুল। দয়া করে সঠিক তথ্য দিয়ে পুনরায় ফর্মটি আপডেট করুন।"
                else:
                    return "দয়া করে সঠিক তথ্য দিয়ে পুনরায় ফর্মটি আপডেট করুন।"
                    
            if 'Reason' in disp_action.columns:
                disp_action['Instruction'] = disp_action['Reason'].apply(get_bengali_instruction)
            else:
                disp_action['Instruction'] = "দয়া করে সঠিক তথ্য দিয়ে পুনরায় ফর্মটি আপডেট করুন।"
                
            html_content = """
            <div class="action-box">
                <h4 style='margin-top:0; color: #856404;'>🚨 ACTION REQUIRED: Attention HOI</h4>
                <p style='color: #856404; font-size: 14px;'>নিচের স্কুলগুলোর তথ্যে ভুল থাকায় তালিকা থেকে মুছে দেওয়া হয়েছে। দয়া করে UDISE কোড দিয়ে পুনরায় সঠিক তথ্য আপডেট করুন।</p>
                <hr style='border-color: #ffeeba; margin: 15px 0;'>
            """
            
            grouped_action = disp_action.groupby('Instruction')
            
            for instruction, group in grouped_action:
                html_content += f"<p style='color: #856404; font-weight: bold; margin-bottom: 5px;'>📌 {instruction}</p>"
                html_content += "<ul style='color: #856404; margin-top: 0; margin-bottom: 20px; font-size: 14px;'>"
                for _, row in group.iterrows():
                    school_name = row.get('School Name', 'Unknown School')
                    udise = row.get('UDISE Code', 'N/A')
                    html_content += f"<li><strong>{school_name}</strong> (UDISE: {udise})</li>"
                html_content += "</ul>"
                
            html_content += "</div>"
            st.markdown(html_content, unsafe_allow_html=True)

    # --- 📝 SUBMISSION FORM ---
    if st.session_state.success_msg:
        st.success(st.session_state.success_msg)
        st.balloons()
        st.session_state.success_msg = "" 

    st.markdown("### 🏫 School Information (স্কুলের তথ্য)")
    st.info("💡 **Instruction:** প্রথমে আপনার স্কুলের ১১ ডিজিটের UDISE Code দিন এবং **'Check UDISE'** বাটনে ক্লিক করুন।")

    col1, col2 = st.columns([2, 1])
    with col1:
        udise_input = st.text_input("1. UDISE Code*", max_chars=11, help="আপনার স্কুলের ১১ ডিজিটের সঠিক UDISE কোড লিখুন")
    with col2:
        st.write("") 
        st.write("")
        if st.button("🔍 Check UDISE (চেক করুন)", use_container_width=True):
            if udise_input and len(udise_input) == 11 and udise_input.isdigit():
                st.session_state.checked_udise = udise_input
                if not existing_data.empty and 'UDISE Code' in existing_data.columns:
                    mask = existing_data['UDISE Code'].astype(str).str.strip() == udise_input.strip()
                    if mask.any():
                        st.session_state.is_editing = True
                        st.session_state.matched_row = existing_data[mask].iloc[-1].to_dict()
                    else:
                        st.session_state.is_editing = False
                        st.session_state.matched_row = {}
                else:
                    st.session_state.is_editing = False
                    st.session_state.matched_row = {}
            else:
                st.error("🚨 অনুগ্রহ করে সঠিক ১১ ডিজিটের UDISE কোড দিন।")
                st.session_state.checked_udise = None

    if st.session_state.checked_udise:
        st.markdown("---")
        
        if st.session_state.is_editing:
            st.success(f"✅ **Old Entry Found:** UDISE {st.session_state.checked_udise}-এর পুরনো এন্ট্রি পাওয়া গেছে। আপনার আগের দেওয়া তথ্য নিচে লোড হয়েছে, আপনি চাইলে তা সংশোধন (Edit) করতে পারেন।")
        else:
            st.info(f"✨ **New Entry:** UDISE {st.session_state.checked_udise}-এর কোনো তথ্য আগে দেওয়া হয়নি। এটি একটি নতুন এন্ট্রি, অনুগ্রহ করে নিচের তথ্যগুলো পূরণ করুন।")

        matched_row = st.session_state.matched_row
        udise_code = st.session_state.checked_udise
        
        default_school = matched_row.get('Name  & Location of the PRIMARY SCHOOL', '')
        raw_roof = str(matched_row.get('Total usable shadow free roof space available for solar installation', '0'))
        nums = re.findall(r'\d+', raw_roof)
        default_roof = int(nums[0]) if nums else 0

        raw_solar = str(matched_row.get('Whether any Solar PV system already exists. If exists, its capacity', 'No'))
        default_has_solar = "Yes" if "Yes" in raw_solar else "No"
        default_capacity = raw_solar.split(", ")[1] if "Yes, " in raw_solar else ""

        raw_req = str(matched_row.get('If exists, whether additional requirement is there', 'N/A'))

        school_name_loc = st.text_input("2. Name & Location of the Primary School*", value=default_school, help="স্কুলের নাম ও ঠিকানা লিখুন, যেমন: Bhagyabantapur Primary School, Vill+PO - Haldia...")

        st.markdown("### ☀️ Solar & Roof Details (সোলার এবং ছাদের বিবরণ)")
        roof_space = st.number_input(
            "3. Total usable shadow free roof space available (in square feet)* - ছাদের ব্যবহারযোগ্য ফাঁকা জায়গা (বর্গফুটে)", 
            min_value=0, 
            value=default_roof,
            step=100,
            help="শুধুমাত্র সংখ্যা লিখুন (যেমন: 1500)। যদি একেবারেই জায়গা না থাকে তবে 0 রাখুন।"
        )

        st.markdown("---")
        col3, col4 = st.columns(2)

        with col3:
            has_solar_idx = 1 if default_has_solar == "Yes" else 0
            has_solar = st.radio("4. Whether any Solar PV system already exists?* (আগে থেকে সোলার আছে কি?)", ["No", "Yes"], index=has_solar_idx)
            
            solar_capacity = ""
            if has_solar == "Yes":
                solar_capacity = st.text_input("5. If exists, its capacity (থাকলে তার ধারণক্ষমতা):", value=default_capacity, help="যেমন: 2 kW")
                
        with col4:
            if has_solar == "No":
                add_req = st.radio("6. If exists, whether additional requirement is there?* (আরও সোলার প্রয়োজন কি?)", options=["N/A"], disabled=True)
            else:
                req_idx = 0 if raw_req == "Yes" else (1 if raw_req == "No" else 0)
                add_req = st.radio("6. If exists, whether additional requirement is there?* (আরও সোলার প্রয়োজন কি?)", options=["Yes", "No"], index=req_idx)

        st.markdown("<small style='color: gray;'>* Mandatory fields (আবশ্যক ঘরগুলি পূরণ করতে হবে)</small>", unsafe_allow_html=True)
        st.write("") 

        btn_label = "🔄 Update Existing Proposal (আপডেট করুন)" if st.session_state.is_editing else "📤 Submit Proposal (সাবমিট করুন)"
        submit_btn = st.button(btn_label, type="primary", use_container_width=True)

        if submit_btn:
            if not school_name_loc:
                st.error("🚨 অনুগ্রহ করে স্কুলের নাম ও ঠিকানা (Name/Location) পূরণ করুন।")
            elif has_solar == "Yes" and not solar_capacity:
                st.error("🚨 অনুগ্রহ করে বর্তমান সোলার সিস্টেমের ক্যাপাসিটি (capacity) উল্লেখ করুন।")
            else:
                with st.spinner("Verifying and saving to secure database... (তথ্য সেভ করা হচ্ছে)"):
                    try:
                        ws = get_worksheet()
                        live_values = ws.get_all_values()
                        
                        if not live_values:
                            headers = [
                                'Sl. No.', 'UDISE Code', 'Name  & Location of the PRIMARY SCHOOL',
                                'Total usable shadow free roof space available for solar installation',
                                'Whether any Solar PV system already exists. If exists, its capacity',
                                'If exists, whether additional requirement is there'
                            ]
                            ws.append_row(headers)
                            live_values = [headers]
                        
                        row_to_update = None
                        for i, row in enumerate(live_values):
                            if i > 0 and len(row) > 1 and str(row[1]).strip() == str(udise_code).strip():
                                row_to_update = i + 1 
                                break
                                
                        system_status = f"Yes, {solar_capacity}" if has_solar == "Yes" else "No"
                        formatted_roof_space = "0 sq ft (No space)" if roof_space == 0 else f"{roof_space} sq ft"
                        
                        if row_to_update:
                            existing_sl = live_values[row_to_update - 1][0]
                            row_data = [existing_sl, str(udise_code).strip(), school_name_loc.strip(), formatted_roof_space, system_status, add_req]
                            
                            try:
                                ws.update(values=[row_data], range_name=f"A{row_to_update}:F{row_to_update}")
                            except TypeError:
                                ws.update(f"A{row_to_update}:F{row_to_update}", [row_data]) 
                                
                            fetch_existing_data.clear()
                            fetch_action_required.clear() 
                            
                            st.session_state.success_msg = f"✏️ {school_name_loc}-এর তথ্য সফলভাবে আপডেট হয়েছে!"
                            st.session_state.checked_udise = None
                            st.session_state.is_editing = False
                            st.session_state.matched_row = {}
                            st.rerun()
                            
                        else:
                            live_df = pd.DataFrame(live_values[1:], columns=live_values[0])
                            if not live_df.empty and 'Sl. No.' in live_df.columns:
                                max_sl = pd.to_numeric(live_df['Sl. No.'], errors='coerce').max()
                                next_sl_no = int(max_sl) + 1 if pd.notna(max_sl) else 1
                            else:
                                next_sl_no = 1
                                
                            row_data = [next_sl_no, str(udise_code).strip(), school_name_loc.strip(), formatted_roof_space, system_status, add_req]
                            ws.append_row(row_data)
                            fetch_existing_data.clear()
                            fetch_action_required.clear() 
                            
                            st.session_state.success_msg = f"🎉 {school_name_loc}-এর তথ্য সফলভাবে সাবমিট হয়েছে!"
                            st.session_state.checked_udise = None
                            st.session_state.is_editing = False
                            st.session_state.matched_row = {}
                            st.rerun()
                        
                    except Exception as e:
                        st.error(f"⚠️ Google Sheets-এ সেভ করতে সমস্যা হয়েছে। Error: {e}")

else:
    # --- 🚫 PORTAL CLOSED MESSAGE ---
    st.markdown("""
    <div class="closed-box">
        <h3 style='margin-top: 0;'>🚫 Submission Portal Closed (সময়সীমা শেষ)</h3>
        <p style='font-size: 16px; margin-bottom: 0;'>The deadline for submitting the Rooftop Solar Proposal (23.09.2026, 23:59) has passed. No further submissions or edits can be made.</p>
    </div>
    """, unsafe_allow_html=True)


# ==========================================
# 📊 SUBMISSION DASHBOARD & ERROR TRACKING (Always Visible)
# ==========================================
st.markdown("---")
st.markdown("### 📋 Submitted Proposals (সাবমিট করা স্কুলের তালিকা)")

if existing_data.empty:
    st.info("এখনও কোনো তথ্য সাবমিট করা হয়নি।")
else:
    def is_mistake(val):
        val_str = str(val).strip()
        if not val_str or val_str.lower() == "nan":
            return True
        nums = re.findall(r'\d+', val_str)
        if not nums:
            return True 
        return False
        
    roof_col = 'Total usable shadow free roof space available for solar installation'
    if roof_col in existing_data.columns:
        mistakes_df = existing_data[existing_data[roof_col].apply(is_mistake)]
        
        if is_active and not mistakes_df.empty:
            st.error(f"⚠️ **Action Required (পদক্ষেপ প্রয়োজন):** {len(mistakes_df)} টি স্কুল **Question 3** (ছাদের জায়গা)-এ ভুল তথ্য দিয়েছে। তথ্য ঠিক করতে উপরে UDISE কোড দিয়ে চেক করুন এবং **Question 3** আপডেট করুন।")
            with st.expander("🚨 View Schools Requiring Correction (যে স্কুলগুলোর তথ্য ঠিক করা প্রয়োজন)", expanded=True):
                for _, row in mistakes_df.iterrows():
                    st.markdown(f"🔴 **{row.get('Name  & Location of the PRIMARY SCHOOL', 'Unknown')}** (UDISE: `{row.get('UDISE Code', 'N/A')}`)  \n*Question 3 ভুল এন্ট্রি:* `{row.get(roof_col, 'N/A')}`")
            st.markdown("---")

    st.write(f"**Total Valid Submissions (মোট সঠিক সাবমিশন):** {len(existing_data) - len(mistakes_df) if roof_col in existing_data.columns else len(existing_data)}")
    
    for index, row in existing_data.iterrows():
        sl_no = row.get('Sl. No.', '?')
        school_name = row.get('Name  & Location of the PRIMARY SCHOOL', 'Unknown School')
        udise = row.get('UDISE Code', 'N/A')
        
        is_bad_row = is_mistake(row.get(roof_col, '')) if roof_col in existing_data.columns else False
        status_icon = "🔴" if is_bad_row else "✅"
        
        with st.expander(f"{sl_no}. {status_icon} {school_name} (UDISE: {udise})"):
            st.markdown(f"**☀️ Roof Space:** {row.get('Total usable shadow free roof space available for solar installation', 'N/A')}")
            st.markdown(f"**🔋 Existing System:** {row.get('Whether any Solar PV system already exists. If exists, its capacity', 'N/A')}")
            st.markdown(f"**➕ Additional Requirement:** {row.get('If exists, whether additional requirement is there', 'N/A')}")
