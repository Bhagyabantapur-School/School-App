import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, date, timedelta
import os

# --- Page Configuration ---
st.set_page_config(page_title="Election Duty App", page_icon="🗳️", layout="centered")

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
    
    try:
        sheet_booth = spreadsheet.worksheet("Booth_Data")
    except:
        sheet_booth = spreadsheet.add_worksheet(title="Booth_Data", rows="10", cols="10")
        sheet_booth.append_row(["AC_Name", "PS_No", "PS_Name", "Total", "Male", "Female", "TG"])
        
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

records = fetch_logs()
team_records = fetch_team()
booth_data = fetch_booth_data()

pending_sessions = [{"sheet_row": i + 2, "data": r} for i, r in enumerate(records) if r.get("Start Time") == "Pending"]
team_list = [{"sheet_row": i + 2, "data": r} for i, r in enumerate(team_records)]

if "edit_booth" not in st.session_state:
    st.session_state.edit_booth = False

# --- NO SIDEBAR: Dynamic App Header & Top Buttons ---
header_col1, header_col2 = st.columns([3, 1])

with header_col1:
    if booth_data and booth_data.get("Total", "") != "":
        st.title(f"🗳️ {booth_data.get('AC_Name', 'AC')} | Booth {booth_data.get('PS_No', '')}")
        st.markdown(f"**{booth_data.get('PS_Name', 'Polling Station')}**")
    else:
        st.title("🗳️ Election Duty App")
        st.markdown("⚠️ **Please enter your Booth Data in the Dashboard tab below.**")

with header_col2:
    if os.path.exists("election_logo.png"):
        st.image("election_logo.png", use_container_width=True)
    st.link_button("📊 Google Sheet", SHEET_URL, use_container_width=True)

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
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Electors", booth_data.get("Total", 0))
        c2.metric("Male", booth_data.get("Male", 0))
        c3.metric("Female", booth_data.get("Female", 0))
        c4.metric("Third Gender", booth_data.get("TG", 0))
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
            
            col1, col2, col3, col4 = st.columns(4)
            val_total = int(booth_data.get("Total", 0)) if booth_data.get("Total") else 0
            val_male = int(booth_data.get("Male", 0)) if booth_data.get("Male") else 0
            val_female = int(booth_data.get("Female", 0)) if booth_data.get("Female") else 0
            val_tg = int(booth_data.get("TG", 0)) if booth_data.get("TG") else 0
            
            with col1: total = st.number_input("Total Electors", min_value=0, value=val_total)
            with col2: male = st.number_input("Male", min_value=0, value=val_male)
            with col3: female = st.number_input("Female", min_value=0, value=val_female)
            with col4: tg = st.number_input("Third Gender", min_value=0, value=val_tg)
            
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
                        sheet_booth.append_row(["AC_Name", "PS_No", "PS_Name", "Total", "Male", "Female", "TG"])
                        sheet_booth.append_row([ac, ps_no, ps_name, total, male, female, tg])
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
        with col1: log_date = st.date_input("Date", date.today())
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
    future_date = st.date_input("Scheduled Date", date.today() + timedelta(days=1))
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
                        sheet_calls.append_row([datetime.now().strftime("%d-%m-%Y"), datetime.now().strftime("%I:%M %p"), officer.get('Name'), call_dir, call_notes])
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
    with st.expander("📝 1. Marking the Electoral Roll"):
        st.write("* **Male:** Diagonal red line.\n* **Female:** Diagonal red line AND circle the serial number.\n* **Third Gender:** Diagonal red line AND star/checkmark.")
    with st.expander("🕵️ 2. Test Vote (Rule 49MA)"):
        st.write("Take written Declaration. Enter in 17A with Remarks 'Rule 49MA'.")
    with st.expander("📜 3. Tendered Vote"):
        st.write("Voter gets Tendered Ballot Paper, signs in Form 17B, NOT 17A.")
    with st.expander("👤 4. Proxy Voter (CSV)"):
        st.write("Proxy gets ink on Middle Finger of Right Hand.")
    with st.expander("⚠️ 5. ASD, Challenge & EDC"):
        st.write("Thorough identity check for ASD. Challenges happen at your desk. EDC voters allowed if for your booth.")

# === TAB 7: TIMELINE (LIVE) ===
with tab7:
    st.header("⏳ Election Day Live Timeline")
    st.markdown("Your app is automatically tracking the current time to show your exact statutory duty right now.")
    
    # Get current time in IST (Indian Standard Time) by adding 5 hours 30 mins to UTC
    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    current_time_str = ist_now.strftime("%I:%M %p")
    current_hour_fraction = ist_now.hour + (ist_now.minute / 60.0)
    
    st.info(f"🕒 **Live Current Time (IST):** {current_time_str}")
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
    
    # Determine which event is active right now
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
            
    if st.button("🔄 Refresh Live Time"):
        st.rerun()

# === TAB 8: FORM 17C CALCULATOR ===
with tab8:
    st.header("🧮 Form 17C Calculator")
    calc_default_total = int(booth_data.get("Total", 0)) if booth_data.get("Total") else 0
    c1, c2 = st.columns(2)
    with c1: total_assigned = st.number_input("Total Electors (1)", value=calc_default_total)
    with c2: form_17a_total = st.number_input("Form 17A Total (2)", value=0)
    c3, c4 = st.columns(2)
    with c3: rule_49o = st.number_input("Refused 49-O (3)", value=0)
    with c4: rule_49m = st.number_input("Not ALLOWED 49-M (4)", value=0)
    actual_evm_total = st.number_input("EVM Total (6)", value=0)
    
    st.divider()
    expected_evm_total = form_17a_total - rule_49o - rule_49m
    st.header("📝 Final Form 17C Verification")
    st.markdown(f"### Expected EVM Total: **{expected_evm_total}**")
    if form_17a_total > 0:
        if expected_evm_total == actual_evm_total: st.success("✅ MATCH! The 17A register perfectly matches the EVM.")
        else: st.error(f"🚨 MISMATCH! Difference of {abs(expected_evm_total - actual_evm_total)} votes.")

# === TAB 9: EVM TROUBLESHOOTER ===
with tab9:
    st.header("🛠️ EVM Troubleshooting")
    evm_error = st.selectbox("Select Error", ["Select...", "Link Error", "Pressed Error", "VVPAT Beeping", "Invalid Error", "Battery Low", "Close Button Not Working"])
    if "Link" in evm_error: st.error("Switch OFF CU. Check cables (BU -> VVPAT -> CU). Switch ON.")
    elif "Pressed" in evm_error: st.error("BU button is jammed. Clear it.")
    elif "Beeping" in evm_error: st.error("VVPAT paper jam/empty. Replace VVPAT only.")
    elif "Invalid" in evm_error: st.error("Wrong sequence. Remember: CLOSE -> RESULT -> CLEAR.")
    elif "Battery" in evm_error: st.error("Switch OFF CU. Replace Power Pack. Seal it.")
    elif "Close" in evm_error: st.error("Check 'Busy' light. Press any button on BU to clear pending ballot, then press Close.")

# === TAB 10: PDF INDEX ===
with tab10:
    st.header("📑 Training Manual Index")
    with st.expander("1. DCRC Activities [Pg 07-27]"): st.write("Collection, Checking Electoral Roll.")
    with st.expander("2. Pre-Poll Day [Pg 28-37]"): st.write("Voting compartment, notices.")
    with st.expander("4. Poll Day [Pg 46-86]"): st.write("Mock Poll, Sealing EVM.")
    with st.expander("5. Voting Process [Pg 87-109]"): st.write("Identification, Ink, CU Operation.")
    with st.expander("6. Exceptional Situations [Pg 110-132]"): st.write("Challenged/Tendered Votes, 49MA.")
    with st.expander("7. Close of Poll [Pg 133-166]"): st.write("Form 17C, Sealing cases.")

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
                    timestamp = datetime.now().strftime("%d-%m-%Y %I:%M %p")
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
