import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, date, timedelta
import os

# --- Helper Function for Indian Standard Time (IST) ---
def get_ist_now():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# --- Page Configuration ---
st.set_page_config(page_title="Election Duty 2026 - Party 116", page_icon="🗳️", layout="centered")

# --- Setup Your Sheet URL Here ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/YOUR_ACTUAL_SHEET_ID_HERE/edit"

# --- Google Sheets Authentication ---
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource
def get_gsheets_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], 
        scopes=SCOPES
    )
    return gspread.authorize(creds)

try:
    client = get_gsheets_client()
    spreadsheet = client.open("Election_Duty_Log")
    sheet_log = spreadsheet.worksheet("Election_Duty_Log")
    sheet_team = spreadsheet.worksheet("Team_Data")
    sheet_calls = spreadsheet.worksheet("Call_Logs")
    
    # Existing Booth Data Sheet
    try:
        sheet_booth = spreadsheet.worksheet("Booth_Data")
    except:
        sheet_booth = spreadsheet.add_worksheet(title="Booth_Data", rows="10", cols="15")
        sheet_booth.append_row(["AC_Name", "PS_No", "PS_Name", "Total", "Male", "Female", "TG", "EDC", "ASD", "Proxy", "PB"])
    
    # New Sheet for Form 17C Data
    try:
        sheet_17c = spreadsheet.worksheet("Form_17C")
    except:
        sheet_17c = spreadsheet.add_worksheet(title="Form_17C", rows="10", cols="10")
        sheet_17c.append_row(["Total_Assigned", "Form_17A", "Rule_49O", "Rule_49M", "Test_Votes", "EVM_Total", "Tendered"])
        
    # Updated Sheet for Continuous Live Turnout Data
    try:
        sheet_turnout = spreadsheet.worksheet("Turnout_Data")
    except:
        sheet_turnout = spreadsheet.add_worksheet(title="Turnout_Data", rows="100", cols="10")
        sheet_turnout.append_row(["Time_Block", "Timestamp", "Male", "Female", "TG", "Total_Cast", "EDC", "ASD", "Proxy", "PB"])
        
    try:
        sheet_memory = spreadsheet.worksheet("Memory_Log")
    except:
        sheet_memory = spreadsheet.add_worksheet(title="Memory_Log", rows="100", cols="4")
        sheet_memory.append_row(["Timestamp", "Test Type", "Your Answer", "Result"])
        
except Exception as e:
    st.error(f"Failed to connect to Google Sheets. Error: {e}")
    st.stop()

# --- Data Fetching Logic ---
@st.cache_data(ttl=60) 
def fetch_logs():
    try: return sheet_log.get_all_records()
    except: return []

@st.cache_data(ttl=60)
def fetch_team():
    try: return sheet_team.get_all_records()
    except: return []

@st.cache_data(ttl=60)
def fetch_booth_data():
    try: 
        records = sheet_booth.get_all_records()
        if records: return records[0]
        return {}
    except: return {}

@st.cache_data(ttl=60)
def fetch_17c_data():
    try: 
        records = sheet_17c.get_all_records()
        if records: return records[0]
        return {}
    except: return {}

@st.cache_data(ttl=60)
def fetch_turnout_records():
    try: return sheet_turnout.get_all_records()
    except: return []

records = fetch_logs()
team_records = fetch_team()
booth_data = fetch_booth_data()
data_17c = fetch_17c_data()
turnout_records = fetch_turnout_records()

pending_sessions = [{"sheet_row": i + 2, "data": r} for i, r in enumerate(records) if r.get("Start Time") == "Pending"]
team_list = [{"sheet_row": i + 2, "data": r} for i, r in enumerate(team_records)]

# Get the most recent turnout data for the form defaults
latest_turnout = {}
if turnout_records:
    latest_turnout = turnout_records[-1] # Get the last row

# --- Session States for Edit Modes ---
if "edit_booth" not in st.session_state: st.session_state.edit_booth = False
if "edit_17c" not in st.session_state: st.session_state.edit_17c = False
if "edit_turnout" not in st.session_state: st.session_state.edit_turnout = False

# --- DYNAMIC APP HEADER ---
header_col1, header_col2 = st.columns([1, 4], vertical_alignment="center")

with header_col1:
    if os.path.exists("election_logo.png"):
        st.image("election_logo.png", width=80)

with header_col2:
    st.title("🗳️ Election Duty 2026")
    st.markdown("### Party No. 116")
    if booth_data and booth_data.get("Total", "") != "":
        st.caption(f"**{booth_data.get('AC_Name', 'AC')} | Booth {booth_data.get('PS_No', '')} - {booth_data.get('PS_Name', 'Polling Station')}**")
    else:
        st.caption("⚠️ **Please enter your Booth Data in the Dashboard tab below.**")

st.divider()

# --- App Layout: Tabs ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11 = st.tabs([
    "🏠 Dashboard", 
    "📝 Log", 
    "📅 Sched", 
    "👥 Team", 
    "📊 Logs",
    "📖 1st PO Guide",
    "⏳ Timeline",
    "🧮 17C Calc",
    "🛠️ EVM Solver",
    "📑 PDF Index",
    "🧠 Memory Test"
])

# === TAB 1: DASHBOARD & SETUP ===
with tab1:
    st.header("🏢 Booth Details")
    if booth_data and booth_data.get("Total", "") != "" and not st.session_state.edit_booth:
        st.subheader("General Electors")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total", booth_data.get("Total", 0))
        c2.metric("Male", booth_data.get("Male", 0))
        c3.metric("Female", booth_data.get("Female", 0))
        c4.metric("Third Gender", booth_data.get("TG", 0))
        
        st.subheader("Special Voters")
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("EDC", booth_data.get("EDC", 0))
        c6.metric("ASD", booth_data.get("ASD", 0))
        c7.metric("Proxy (CSV)", booth_data.get("Proxy", 0))
        c8.metric("Postal Ballot", booth_data.get("PB", 0))
        
        st.divider()
        if st.button("✏️ Edit Booth Details"):
            st.session_state.edit_booth = True
            st.rerun()
    else:
        st.info("Please enter or update your exact booth details from the Electoral Roll.")
        with st.form("update_booth"):
            ac = st.text_input("AC Name & No.", value=str(booth_data.get("AC_Name", "")))
            ps_no = st.text_input("PS No.", value=str(booth_data.get("PS_No", "")))
            ps_name = st.text_input("PS Name", value=str(booth_data.get("PS_Name", "")))
            
            st.markdown("#### General Electors")
            col1, col2, col3, col4 = st.columns(4)
            with col1: total = st.number_input("Total", min_value=0, value=int(booth_data.get("Total", 0) if booth_data.get("Total") else 0))
            with col2: male = st.number_input("Male", min_value=0, value=int(booth_data.get("Male", 0) if booth_data.get("Male") else 0))
            with col3: female = st.number_input("Female", min_value=0, value=int(booth_data.get("Female", 0) if booth_data.get("Female") else 0))
            with col4: tg = st.number_input("TG", min_value=0, value=int(booth_data.get("TG", 0) if booth_data.get("TG") else 0))
            
            st.markdown("#### Special Voters (From Marked Copy)")
            col5, col6, col7, col8 = st.columns(4)
            with col5: edc = st.number_input("EDC Voters", min_value=0, value=int(booth_data.get("EDC", 0) if booth_data.get("EDC") else 0))
            with col6: asd = st.number_input("ASD Voters", min_value=0, value=int(booth_data.get("ASD", 0) if booth_data.get("ASD") else 0))
            with col7: proxy = st.number_input("Proxy (CSV)", min_value=0, value=int(booth_data.get("Proxy", 0) if booth_data.get("Proxy") else 0))
            with col8: pb = st.number_input("Postal Ballot", min_value=0, value=int(booth_data.get("PB", 0) if booth_data.get("PB") else 0))
            
            st.divider()
            c_btn1, c_btn2 = st.columns([1, 4])
            with c_btn1: submitted = st.form_submit_button("💾 Save Data", type="primary")
            with c_btn2:
                if booth_data and booth_data.get("Total", "") != "":
                    if st.form_submit_button("❌ Cancel"):
                        st.session_state.edit_booth = False
                        st.rerun()
            
            if submitted:
                with st.spinner("Saving Booth Data..."):
                    try:
                        sheet_booth.clear()
                        sheet_booth.append_row(["AC_Name", "PS_No", "PS_Name", "Total", "Male", "Female", "TG", "EDC", "ASD", "Proxy", "PB"])
                        sheet_booth.append_row([ac, ps_no, ps_name, total, male, female, tg, edc, asd, proxy, pb])
                        st.session_state.edit_booth = False
                        st.success("Booth Data Saved Successfully!")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e: st.error(f"Error saving data: {e}")

# === TAB 2: LOG & COMPLETE ===
with tab2:
    action_type = st.radio("What would you like to do?", ["Complete a Scheduled Session", "Log a Brand New Session"], horizontal=True)
    st.divider()

    if action_type == "Complete a Scheduled Session":
        if not pending_sessions: st.info("No pending scheduled sessions found.")
        else:
            options = {f"{s['data']['Date']} - {s['data']['Activity Type']}": s for s in pending_sessions}
            selected_str = st.selectbox("📌 Select Pending Session", list(options.keys()))
            selected_session = options[selected_str]
            
            col1, col2 = st.columns(2)
            with col1: start_time = st.time_input("Start Time", step=60)
            with col2: end_time = st.time_input("End Time", step=60)
                
            updated_notes = st.text_area("Update Notes", value=selected_session['data']['Notes / Key Learnings'])
            
            if st.button("✅ Complete Session", type="primary"):
                log_date = datetime.strptime(selected_session['data']['Date'], "%d-%m-%Y").date()
                start_dt = datetime.combine(log_date, start_time)
                end_dt = datetime.combine(log_date, end_time)
                if end_dt < start_dt: end_dt += timedelta(days=1)
                total_minutes = int((end_dt - start_dt).total_seconds() / 60)
                duration_formatted = f"{total_minutes // 60:02d}h {total_minutes % 60:02d}m"
                
                with st.spinner("Updating Google Sheet..."):
                    try:
                        sheet_log.update_cell(selected_session['sheet_row'], 2, start_time.strftime("%I:%M %p"))
                        sheet_log.update_cell(selected_session['sheet_row'], 3, end_time.strftime("%I:%M %p"))
                        sheet_log.update_cell(selected_session['sheet_row'], 5, duration_formatted)
                        sheet_log.update_cell(selected_session['sheet_row'], 6, updated_notes)
                        st.success("Logged successfully!")
                        st.cache_data.clear()
                        st.rerun() 
                    except Exception as e: st.error(f"Error: {e}")

    elif action_type == "Log a Brand New Session":
        col1, col2, col3 = st.columns(3)
        with col1: log_date = st.date_input("Date", get_ist_now().date())
        with col2: start_time = st.time_input("Start Time", step=60)
        with col3: end_time = st.time_input("End Time", step=60)
            
        activity_selection = st.selectbox("Activity Type", ["PPT Study", "Form 12/12A Practice", "Hands-on Training Review", "EVM Mock Practice", "Other / Custom (Type below)"])
        custom_activity = st.text_input("Custom Activity Type") if activity_selection == "Other / Custom (Type below)" else ""
        notes = st.text_area("Notes", placeholder="What did you focus on today?")
        
        if st.button("Log New Activity", type="primary"):
            final_activity = custom_activity.strip() if custom_activity else activity_selection
            start_dt = datetime.combine(log_date, start_time)
            end_dt = datetime.combine(log_date, end_time)
            if end_dt < start_dt: end_dt += timedelta(days=1)
            total_minutes = int((end_dt - start_dt).total_seconds() / 60)
            duration_formatted = f"{total_minutes // 60:02d}h {total_minutes % 60:02d}m"
            
            with st.spinner("Saving..."):
                try:
                    sheet_log.append_row([log_date.strftime("%d-%m-%Y"), start_time.strftime("%I:%M %p"), end_time.strftime("%I:%M %p"), final_activity, duration_formatted, notes])
                    st.success("✅ Logged successfully!")
                    st.cache_data.clear() 
                except Exception as e: st.error(f"Error: {e}")

# === TAB 3: SCHEDULE FUTURE ===
with tab3:
    st.subheader("📅 Schedule an Upcoming Training")
    future_date = st.date_input("Scheduled Date", get_ist_now().date() + timedelta(days=1))
    sched_activity_selection = st.selectbox("Scheduled Activity Type", ["Hands-on Training", "EVM/VVPAT Collection", "Other / Custom"])
    sched_custom_activity = st.text_input("Custom Activity Type", key="s_cust") if sched_activity_selection == "Other / Custom" else ""
    sched_notes = st.text_area("Prep Required")
    
    if st.button("Save Schedule", type="primary"):
        final_sched_activity = sched_custom_activity.strip() if sched_custom_activity else sched_activity_selection
        with st.spinner("Scheduling..."):
            try:
                sheet_log.append_row([future_date.strftime("%d-%m-%Y"), "Pending", "Pending", final_sched_activity, "Pending", sched_notes])
                st.success("✅ Scheduled!")
                st.cache_data.clear() 
            except Exception as e: st.error(f"Error: {e}")

# === TAB 4: TEAM DASHBOARD ===
with tab4:
    st.subheader("👥 Polling Team Directory")
    if not team_list: st.info("No team members added yet.")
    else:
        for idx, officer_info in enumerate(team_list):
            officer = officer_info['data']
            row_num = officer_info['sheet_row']
            status = officer.get('Status', 'Active') or 'Active'
            status_icon, status_text = ("🟢", "") if status == "Active" else ("🔴", "(INACTIVE)")
            
            with st.expander(f"{status_icon} {idx + 1}. {officer.get('Name', 'Unknown')} - {officer.get('Polling Office Rank', 'Rank N/A')} {status_text}"):
                st.write(f"**Designation:** {officer.get('Designation', 'N/A')}")
                st.write(f"**Mobile:** {officer.get('Mobile Number', 'N/A')}")
                if status == "Active":
                    st.markdown(f"<a href='tel:{officer.get('Mobile Number', '')}' style='display: block; text-align: center; padding: 8px; background-color: #4CAF50; color: white; border-radius: 5px; text-decoration: none;'>📞 Tap to Dial</a>", unsafe_allow_html=True)
                    call_dir = st.radio("Direction", ["Outgoing", "Incoming"], key=f"dir_{idx}", horizontal=True)
                    call_notes = st.text_input("Call Notes", key=f"note_{idx}")
                    if st.button("Save Call Record", key=f"btn_{idx}"):
                        ist_time = get_ist_now()
                        sheet_calls.append_row([ist_time.strftime("%d-%m-%Y"), ist_time.strftime("%I:%M %p"), officer.get('Name'), call_dir, call_notes])
                        st.success("✅ Call logged!")
                if st.button("Toggle Status", key=f"tog_{idx}"):
                    sheet_team.update_cell(row_num, 6, "Inactive" if status == "Active" else "Active")
                    st.cache_data.clear()
                    st.rerun()
    st.divider()
    with st.expander("➕ Add New Team Member"):
        with st.form("add_officer_form"):
            t_name = st.text_input("Name")
            t_desig = st.text_input("Designation")
            t_rank = st.selectbox("Rank", ["Presiding Officer", "1st Polling Officer", "2nd Polling Officer", "3rd Polling Officer", "Sector Officer", "Micro Observer"])
            t_address = st.text_area("Office Address")
            t_mobile = st.text_input("Mobile Number")
            if st.form_submit_button("Save Officer Data"):
                if t_name and t_mobile:
                    sheet_team.append_row([t_name, t_desig, t_rank, t_address, t_mobile, "Active"])
                    st.success("Added!")
                    st.cache_data.clear()
                    st.rerun()

# === TAB 5: VIEW LOGS ===
with tab5:
    st.subheader("Your Study History")
    if st.button("🔄 Refresh Data"): st.cache_data.clear()
    df = pd.DataFrame(records)
    if not df.empty:
        def highlight_pending(row): return ['background-color: #ffcccc; color: black'] * len(row) if row.get('Start Time') == 'Pending' else [''] * len(row)
        st.dataframe(df.style.apply(highlight_pending, axis=1), use_container_width=True, hide_index=True)
    else: st.info("No logs found yet.")

# === TAB 6: 1st PO GUIDE ===
with tab6:
    st.header("📖 1st Polling Officer Guide")
    st.markdown("আপনার Polling Day-এর মূল দায়িত্ব ও নিয়মাবলি (Rules & Regulations).")
    
    with st.expander("📝 1. Marking the Electoral Roll"):
        st.markdown("* **Male Voter (পুরুষ):** ভোটারের বক্সের উপর আড়াআড়ি লাল দাগ (Diagonal red line) টানুন।\n* **Female Voter (মহিলা):** আড়াআড়ি লাল দাগ দিন **এবং** Serial Number-টি গোল (Circle) করুন।\n* **Third Gender (তৃতীয় লিঙ্গ):** আড়াআড়ি লাল দাগ দিন **এবং** Serial Number-এর পাশে একটি স্টার (*) বা টিক চিহ্ন (✓) দিন।")
    with st.expander("🕵️ 2. Test Vote (Rule 49MA)"):
        st.markdown("প্রথমে ভোটারের কাছ থেকে একটি লিখিত **Declaration** নিতে হবে। **Form 17A**-তে এই Test Vote-এর জন্য নতুন একটি Entry করতে হবে এবং 'Remarks' কলামে **'Rule 49MA'** লিখতে হবে।")
    with st.expander("📜 3. Tendered Vote"):
        st.markdown("তাকে **EVM**-এ ভোট দিতে দেওয়া যাবে না। Presiding Officer তাকে একটি **Tendered Ballot Paper** দেবেন। এই ভোটারের সই/টিপসই **Form 17B**-তে নিতে হবে, Form 17A-তে নয়।")
    with st.expander("👤 4. Proxy Voter (CSV)"):
        st.markdown("**Classified Service Voter (CSV)**-দের ক্ষেত্রে Proxy ভোটার ভোট দিতে পারেন। 2nd Polling Officer Proxy ভোটারের ডান হাতের মধ্যমায় (Middle Finger of Right Hand) কালির দাগ লাগাবেন।")
    with st.expander("⚠️ 5. ASD, Challenge & EDC"):
        st.markdown("* **ASD:** পরিচয় খুব সতর্কভাবে verify করুন।\n* **Challenged Votes:** Agent-কে ₹2 challenge fee দিয়ে Presiding Officer-এর কাছে যেতে বলুন।\n* **EDC:** Marked copy-তে নাম strike off করা থাকলেও, EDC নিয়ে ভোট দিতে এলে তাদের ভোট দিতে হবে এবং 17A তে Entry হবে।")

# === TAB 7: TIMELINE & LIVE VOTING RECORD ===
with tab7:
    st.header("⏳ Election Day Live Timeline")
    
    ist_now = get_ist_now()
    current_time_str = ist_now.strftime("%I:%M %p")
    current_hour_fraction = ist_now.hour + (ist_now.minute / 60.0)
    
    st.info(f"🕒 **Live Current Time (IST):** {current_time_str}")
    
    # ---------------- CONTINUOUS LIVE TURNOUT LOGGING ----------------
    st.divider()
    st.subheader("📊 Record Live Voting Data (Turnout)")
    st.markdown("Log the current vote count for SMS reporting. Every entry is saved as a history log.")
    
    if not st.session_state.edit_turnout:
        with st.form("new_turnout_entry"):
            time_block = st.selectbox("Select Time Block for SMS", ["09:00 AM", "11:00 AM", "01:00 PM", "03:00 PM", "05:00 PM", "06:00 PM", "End of Poll (Final)"])
            
            st.markdown("Enter total cumulative votes cast **up to this time block**:")
            col1, col2, col3 = st.columns(3)
            with col1: t_male = st.number_input("Male Votes", min_value=0, value=int(latest_turnout.get("Male", 0) if latest_turnout else 0))
            with col2: t_female = st.number_input("Female Votes", min_value=0, value=int(latest_turnout.get("Female", 0) if latest_turnout else 0))
            with col3: t_tg = st.number_input("TG Votes", min_value=0, value=int(latest_turnout.get("TG", 0) if latest_turnout else 0))
            
            st.markdown("Special Categories (If any):")
            col4, col5, col6, col7 = st.columns(4)
            with col4: t_edc = st.number_input("EDC Cast", min_value=0, value=int(latest_turnout.get("EDC", 0) if latest_turnout else 0))
            with col5: t_asd = st.number_input("ASD Cast", min_value=0, value=int(latest_turnout.get("ASD", 0) if latest_turnout else 0))
            with col6: t_proxy = st.number_input("Proxy Cast", min_value=0, value=int(latest_turnout.get("Proxy", 0) if latest_turnout else 0))
            with col7: t_pb = st.number_input("PB Recv.", min_value=0, value=int(latest_turnout.get("PB", 0) if latest_turnout else 0))
            
            submit_turnout = st.form_submit_button("💾 Save Turnout Log", type="primary")
            
            if submit_turnout:
                with st.spinner("Recording Data..."):
                    try:
                        total_cast = t_male + t_female + t_tg
                        exact_timestamp = get_ist_now().strftime("%I:%M %p")
                        sheet_turnout.append_row([time_block, exact_timestamp, t_male, t_female, t_tg, total_cast, t_edc, t_asd, t_proxy, t_pb])
                        st.success(f"Turnout for {time_block} Recorded Successfully!")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e: st.error(f"Error saving: {e}")
                    
        # Display the Historical Log
        if turnout_records:
            st.markdown("#### 📜 Turnout History Log")
            df_turnout = pd.DataFrame(turnout_records)
            st.dataframe(df_turnout[["Time_Block", "Timestamp", "Total_Cast", "Male", "Female", "TG"]], use_container_width=True, hide_index=True)
            
            if st.button("🗑️ Delete Last Entry"):
                try:
                    last_row_index = len(turnout_records) + 1 # +1 because row 1 is header
                    sheet_turnout.delete_rows(last_row_index)
                    st.success("Last entry deleted.")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e: st.error("Failed to delete.")

    # -------------------------------------------------------------------

    st.divider()
    timeline_events = [
        {"hour": 0, "time": "Pre 05:00 AM", "title": "Rest/Setup", "desc": "Sleep well or get ready for the day."},
        {"hour": 5.0, "time": "05:00 AM", "title": "Wake Up & Team Prep", "desc": "Ensure team is awake. PRO links EVM (BU -> VVPAT -> CU). Do NOT switch on CU yet."},
        {"hour": 5.5, "time": "05:30 AM", "title": "Mock Poll Preparation", "desc": "Agents arrive. Demonstrate empty EVM."},
        {"hour": 5.75, "time": "05:45 AM", "title": "Conduct Mock Poll", "desc": "Cast at least 50 votes across all candidates."},
        {"hour": 6.25, "time": "06:15 AM", "title": "Clear Mock Poll & Seal EVM", "desc": "CRITICAL: Press CLOSE, RESULT, then CLEAR. Seal EVM."},
        {"hour": 7, "time": "07:00 AM", "title": "🟢 ACTUAL POLL COMMENCES", "desc": "Start allowing voters."},
        {"hour": 9, "time": "09:00 AM", "title": "1st 2-Hourly Report", "desc": "Press 'Total', PRO sends SMS."},
        {"hour": 11, "time": "11:00 AM", "title": "2nd 2-Hourly Report", "desc": "Press 'Total', PRO sends SMS."},
        {"hour": 13, "time": "01:00 PM", "title": "3rd 2-Hourly Report", "desc": "Press 'Total', PRO sends SMS."},
        {"hour": 15, "time": "03:00 PM", "title": "4th 2-Hourly Report", "desc": "Press 'Total', PRO sends SMS."},
        {"hour": 17, "time": "05:00 PM", "title": "5th 2-Hourly Report", "desc": "Press 'Total', PRO sends SMS."},
        {"hour": 18, "time": "06:00 PM", "title": "Distribute Queue Slips", "desc": "Starting from the LAST person in line."},
        {"hour": 18.5, "time": "06:30 PM", "title": "🔴 CLOSE THE POLL", "desc": "Press CLOSE button on CU. Switch off."},
        {"hour": 19, "time": "07:00 PM", "title": "Final Sealing & Forms", "desc": "Pack CU, BU, VVPAT. Complete Form 17C."}
    ]
    
    for i, event in enumerate(timeline_events):
        is_active = False
        if i < len(timeline_events) - 1:
            next_hour = timeline_events[i+1]["hour"]
            if event["hour"] <= current_hour_fraction < next_hour:
                is_active = True
        else:
            if current_hour_fraction >= event["hour"]:
                is_active = True

        if is_active:
            st.success(f"### 👉 CURRENT TASK: {event['time']} - {event['title']}\n**Action Required:** {event['desc']}")
        else:
            with st.expander(f"{event['time']} - {event['title']}"): st.write(event['desc'])
            
    if st.button("🔄 Refresh Live Time"): st.rerun()

# === TAB 8: FORM 17C CALCULATOR (NOW WITH SAVE & EDIT) ===
with tab8:
    st.header("🧮 Form 17C Calculator")
    
    if data_17c and "Form_17A" in data_17c and not st.session_state.edit_17c:
        # --- VIEW MODE ---
        st.success("✅ Form 17C Data is Safely Saved in Google Sheets.")
        
        st.write(f"**1. Total number of electors assigned:** {data_17c.get('Total_Assigned')}")
        st.write(f"**2. Total number of voters in Form 17A:** {data_17c.get('Form_17A')}")
        st.write(f"**3. Refused to vote (Rule 49-O):** {data_17c.get('Rule_49O')}")
        st.write(f"**4. Not allowed to vote (Rule 49M):** {data_17c.get('Rule_49M')}")
        st.write(f"**5. Test votes (Rule 49MA):** {data_17c.get('Test_Votes')}")
        st.write(f"**6. EVM Total:** {data_17c.get('EVM_Total')}")
        st.write(f"**8. Tendered Issued:** {data_17c.get('Tendered')}")
        
        expected = int(data_17c.get('Form_17A')) - int(data_17c.get('Rule_49O')) - int(data_17c.get('Rule_49M'))
        actual = int(data_17c.get('EVM_Total'))
        
        st.divider()
        st.markdown(f"### Expected EVM Total: **{expected}**")
        st.markdown(f"### Actual EVM Total: **{actual}**")
        if expected == actual: st.success("✅ TALLIES CORRECTLY.")
        else: st.error("🚨 DISCREPANCY NOTICED!")
        
        if st.button("✏️ Edit 17C Data"):
            st.session_state.edit_17c = True
            st.rerun()
            
    else:
        # --- EDIT / ENTRY MODE ---
        st.info("Fill out the Form 17C details to verify the tally. This data will be saved permanently.")
        
        calc_default_total = int(booth_data.get("Total", 0)) if booth_data.get("Total") else 0
        if data_17c and "Total_Assigned" in data_17c:
             calc_default_total = int(data_17c.get("Total_Assigned"))
             
        with st.form("form_17c_save"):
            total_assigned = st.number_input("1. Total number of electors assigned to the Polling Station", min_value=0, value=calc_default_total, step=1)
            form_17a_total = st.number_input("2. Total number of voters as entered in the Register for Voters (Form 17A)", min_value=0, value=int(data_17c.get("Form_17A", 0) if data_17c else 0), step=1)
            rule_49o = st.number_input("3. Number of voters deciding not to record votes/ refused to vote (Rule 49-O)", min_value=0, value=int(data_17c.get("Rule_49O", 0) if data_17c else 0), step=1)
            rule_49m = st.number_input("4. Number of voters not allowed to vote under Rule 49M", min_value=0, value=int(data_17c.get("Rule_49M", 0) if data_17c else 0), step=1)
            test_votes = st.number_input("5(a). Total number of test votes to be deducted (Rule 49MA)", min_value=0, value=int(data_17c.get("Test_Votes", 0) if data_17c else 0), step=1)
            actual_evm_total = st.number_input("6. Total number of votes recorded as per voting machine", min_value=0, value=int(data_17c.get("EVM_Total", 0) if data_17c else 0), step=1)
            tendered_issued = st.number_input("8. Number of voters to whom tendered ballot papers were issued", min_value=0, value=int(data_17c.get("Tendered", 0) if data_17c else 0), step=1)
            
            st.divider()
            c_btn1, c_btn2 = st.columns([1, 4])
            with c_btn1: submit_17c = st.form_submit_button("💾 Save 17C Data", type="primary")
            with c_btn2:
                if data_17c and "Form_17A" in data_17c:
                    if st.form_submit_button("❌ Cancel"):
                        st.session_state.edit_17c = False
                        st.rerun()
                        
            if submit_17c:
                with st.spinner("Saving Form 17C Data..."):
                    try:
                        sheet_17c.clear()
                        sheet_17c.append_row(["Total_Assigned", "Form_17A", "Rule_49O", "Rule_49M", "Test_Votes", "EVM_Total", "Tendered"])
                        sheet_17c.append_row([total_assigned, form_17a_total, rule_49o, rule_49m, test_votes, actual_evm_total, tendered_issued])
                        st.session_state.edit_17c = False
                        st.success("Form 17C Data Saved Successfully!")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e: st.error(f"Error saving data: {e}")

# === TAB 9: EVM TROUBLESHOOTER ===
with tab9:
    st.header("🛠️ EVM Troubleshooting (ইভিএম সমস্যা সমাধান)")
    
    evm_error = st.selectbox("Select EVM/VVPAT Error (সমস্যা নির্বাচন করুন)", [
        "Select an error...",
        "1. Link Error / Communication Error",
        "2. Pressed Error",
        "3. VVPAT Beeping / Error 2.6",
        "4. Invalid Error",
        "5. Low Battery / Replace Power Pack",
        "6. Close Button Not Working"
    ])
    st.divider()

    if "Link Error" in evm_error:
        st.error("🚨 CU Display: 'LINK ERROR'")
        st.write("**Solution (সমাধান):** প্রথমেই Control Unit (CU)-টি **Switch OFF** করুন। Cables ঠিকমত কানেক্ট করা আছে কিনা চেক করুন। **(BU এর কেবল VVPAT এ, এবং VVPAT এর কেবল CU তে লাগাতে হবে)**। সব ঠিক থাকলে আবার CU **Switch ON** করুন।")
    elif "Pressed Error" in evm_error:
        st.error("🚨 CU Display: 'PRESSED ERROR'")
        st.write("**Solution (সমাধান):** এর মানে হলো Ballot Unit (BU)-এর কোনো বোতাম (Button) আগে থেকেই আটকে (jam) আছে। BU-তে গিয়ে চেক করুন কোনো বোতাম আটকে আছে কিনা, থাকলে তা ধীরে ধীরে ছাড়িয়ে দিন।")
    elif "VVPAT Beeping" in evm_error:
        st.error("🚨 VVPAT একটানা Beep শব্দ করছে / Error 2.6")
        st.write("**Solution (সমাধান):** VVPAT-এর Paper Roll শেষ হয়ে গেলে বা কাগজ আটকে গেলে এই শব্দ হয়। **Actual Poll চলাকালীন VVPAT খারাপ হলে, শুধুমাত্র VVPAT পরিবর্তন করতে হবে (EVM বা BU নয়)।**")
    elif "Invalid Error" in evm_error:
        st.error("🚨 CU Display: 'INVALID'")
        st.write("**Solution (সমাধান):** আপনি ভুল Sequence-এ বোতাম টিপেছেন। সঠিক Sequence মনে রাখুন: **CLOSE ➡️ RESULT ➡️ CLEAR** (Mock poll-এর সময়)।")
    elif "Low Battery" in evm_error:
        st.error("🚨 CU Display: 'BATTERY LOW'")
        st.write("**Solution (সমাধান):** CU **Switch OFF** করুন। Presiding Officer-এর কাছে থাকা Extra Battery (Power Pack) দিয়ে CU-এর ব্যাটারি পরিবর্তন করুন।")
    elif "Close Button Not Working" in evm_error:
        st.error("🚨 Close Button কাজ করছে গান্ধ করছে না")
        st.write("**Solution (সমাধান):** ভোট গ্রহণ শেষে যদি Close বোতাম কাজ না করে, চেক করুন 'Busy' ইন্ডিকেটর জ্বলছে কিনা। BU-তে গিয়ে যেকোনো একটি বোতাম টিপে সেই ব্যালটটি বাতিল/সম্পূর্ণ করুন, এরপর CU-তে 'Close' বোতাম কাজ করবে।")

# === TAB 10: PDF INDEX ===
with tab10:
    st.header("📑 Training Manual Index")
    st.markdown("আপনার 191-পাতার PDF Training Manual-এর সূচিপত্র। সহজে Page Number খুঁজে বের করার জন্য।")
    
    with st.expander("1. বিতরণ কেন্দ্রে কার্যক্রম (DCRC Activities) ➡️ [পৃষ্ঠা 07-27]"):
        st.markdown("* Collection of EVM/VVPAT and checking serial numbers.\n* Checking the Electoral Roll & Marked Copy.\n* Collection of Statutory/Non-Statutory forms, tags, and seals.")
    with st.expander("2. পোলিং স্টেশনে ভোটের আগের দিনে ক্রিয়াকলাপ (Pre-Poll Day) ➡️ [পৃষ্ঠা 28-37]"):
        st.markdown("* Setting up the voting compartment.\n* Displaying notices outside the polling station.\n* Checking voting materials inside the booth.")
    with st.expander("3. ভোটকেন্দ্রগুলির চারপাশে আইনশৃঙ্খলা (Law & Order) ➡️ [পৃষ্ঠা 38-43]"):
        st.markdown("* 100-meter and 200-meter perimeter rules.\n* Regulating entry into the polling station.")
    with st.expander("4. পোলিং স্টেশনে ভোটের দিনে ক্রিয়াকলাপ (Poll Day) ➡️ [পৃষ্ঠা 46-86]"):
        st.markdown("* Mock Poll procedures and clearing data (CRITICAL).\n* Sealing the EVM with Green Paper Seal, Special Tag, etc.")
    with st.expander("5. ভোট গ্রহণ প্রক্রিয়া (Voting Process) ➡️ [পৃষ্ঠা 87-109]"):
        st.markdown("* Duties of 1st, 2nd, and 3rd Polling Officers.\n* Voter Identification and checking EPIC/Alternate IDs.\n* Application of Indelible Ink.\n* Operating the Control Unit (CU).")
    with st.expander("6. কিছু ব্যতিক্রমী / বিশেষ পরিস্থিতি (Exceptional Situations) ➡️ [পৃষ্ঠা 110-132]"):
        st.markdown("* Challenged Votes & Tendered Votes.\n* Voters deciding not to vote (Rule 49-O).\n* Test Votes (Rule 49MA).")
    with st.expander("7. ভোট গ্রহণ সমাপ্তিতে কার্যাদি (Close of Poll) ➡️ [পৃষ্ঠা 133-166]"):
        st.markdown("* Distribution of queue slips at 6:00 PM.\n* Pressing the CLOSE button on the CU.\n* Filling out Form 17C and the Presiding Officer's Diary.")
    with st.expander("8. রিসিভিং সেন্টারে ক্রিয়াকলাপ (RC Activities) ➡️ [পৃষ্ঠা 167-176]"):
        st.markdown("* Handing over sealed EVMs and VVPATs.\n* Submission of Statutory (Green) and Non-Statutory (Yellow) packets.")
    with st.expander("9. SMS Poll Reporting ও ECINET App ➡️ [পৃষ্ঠা 177-191]"):
        st.markdown("* Presiding Officer's SMS formatting and sending schedule.\n* 2-Hourly turnout reporting via SMS.\n* ECINET app installation and usage guidelines.\n* Helpline numbers and troubleshooting for reporting.")

# === TAB 11: MEMORY TEST ===
with tab11:
    st.header("🧠 Memorize Your Booth Details")
    if not booth_data or booth_data.get("AC_Name", "") == "":
        st.warning("⚠️ Please configure your exact Booth Details in the 'Dashboard' tab first before taking the test.")
    else:
        test_type = st.selectbox("What do you want to test?", ["Assembly Constituency (AC)", "Polling Station (PS)"])
        if test_type == "Assembly Constituency (AC)":
            st.info("Question: What is your AC Name & Number?")
            correct_answer = str(booth_data.get("AC_Name", ""))
        else:
            st.info(f"Question: What is the Name for Polling Station No. {booth_data.get('PS_No', '')}?")
            correct_answer = str(booth_data.get("PS_Name", ""))
            
        user_guess = st.text_input("Type your answer here:")
        
        if st.button("Submit Answer", type="primary"):
            if user_guess.strip().lower() == correct_answer.strip().lower():
                result = "Passed ✅"
                st.balloons()
                st.success(f"Excellent! The correct answer is **{correct_answer}**.")
            else:
                result = "Failed ❌"
                st.error(f"Incorrect. The correct answer was **{correct_answer}**. Try again!")
                
            with st.spinner("Logging test result..."):
                try:
                    timestamp = get_ist_now().strftime("%d-%m-%Y %I:%M %p")
                    sheet_memory.append_row([timestamp, test_type, user_guess.strip(), result])
                    st.cache_data.clear()
                except Exception as e: st.error("Could not save the result to Google Sheets.")
                    
        st.divider()
        st.subheader("Your Test History")
        try:
            mem_records = sheet_memory.get_all_records()
            if mem_records:
                recent_tests = pd.DataFrame(mem_records).iloc[::-1].head(5)
                st.dataframe(recent_tests, use_container_width=True, hide_index=True)
            else: st.caption("Take a test to see your results here.")
        except: st.caption("Unable to load history.")
