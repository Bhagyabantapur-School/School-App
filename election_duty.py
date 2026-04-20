import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, date, timedelta

# --- Page Configuration ---
st.set_page_config(page_title="Election Duty App - Party 116", page_icon="🗳️", layout="centered")

# --- Setup Your Sheet URL Here ---
# Paste your actual Google Sheet link inside the quotes below!
SHEET_URL = "https://docs.google.com/spreadsheets/d/1ennsNFWIWfEwqKukv0OPIKF8r7T-oK7yD6kobCRmquc/edit"

st.title("🗳️ Election Duty: Party 116")
st.markdown("Schedule, log, manage your team, and track Polling Day.")

# --- Sidebar ---
with st.sidebar:
    st.header("🔗 Quick Links")
    st.link_button("📊 Open Google Sheet", SHEET_URL, use_container_width=True)
    st.info("Click the button above to view your raw database directly in Google Sheets.")

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

records = fetch_logs()
team_records = fetch_team()

# Process Duty Logs
pending_sessions = []
for index, rec in enumerate(records):
    if rec.get("Start Time") == "Pending":
        pending_sessions.append({"sheet_row": index + 2, "data": rec})

# Process Team Records
team_list = []
for index, rec in enumerate(team_records):
    team_list.append({"sheet_row": index + 2, "data": rec})

# --- App Layout: Tabs ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📝 Log", 
    "📅 Sched", 
    "👥 Team", 
    "📊 Logs",
    "📖 1st PO Guide",
    "⏳ Timeline",
    "🧮 17C Calc",
    "🛠️ EVM Solver"
])

# === TAB 1: LOG & COMPLETE ===
with tab1:
    action_type = st.radio("What would you like to do?", ["Complete a Scheduled Session", "Log a Brand New Session"], horizontal=True)
    st.divider()

    if action_type == "Complete a Scheduled Session":
        if not pending_sessions:
            st.info("No pending scheduled sessions found.")
        else:
            options = {f"{s['data']['Date']} - {s['data']['Activity Type']}": s for s in pending_sessions}
            selected_str = st.selectbox("📌 Select Pending Session", list(options.keys()))
            selected_session = options[selected_str]
            
            st.write(f"**Original Notes:** {selected_session['data']['Notes / Key Learnings']}")
            
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
                        st.success(f"Successfully completed: logged {duration_formatted}!")
                        st.cache_data.clear()
                        st.rerun() 
                    except Exception as e: st.error(f"Error updating sheet: {e}")

    elif action_type == "Log a Brand New Session":
        col1, col2, col3 = st.columns(3)
        with col1: log_date = st.date_input("Date", date.today())
        with col2: start_time = st.time_input("Start Time", step=60)
        with col3: end_time = st.time_input("End Time", step=60)
            
        activity_selection = st.selectbox("Activity Type", ["PPT Study", "Form 12/12A Practice", "Hands-on Training Review", "EVM Mock Practice", "Other / Custom (Type below)"])
        custom_activity = ""
        if activity_selection == "Other / Custom (Type below)":
            custom_activity = st.text_input("Custom Activity Type")
        
        notes = st.text_area("Notes", placeholder="What did you focus on today?")
        
        if st.button("Log New Activity", type="primary"):
            final_activity = custom_activity.strip() if activity_selection == "Other / Custom (Type below)" else activity_selection
            start_dt = datetime.combine(log_date, start_time)
            end_dt = datetime.combine(log_date, end_time)
            if end_dt < start_dt: end_dt += timedelta(days=1)
            total_minutes = int((end_dt - start_dt).total_seconds() / 60)
            duration_formatted = f"{total_minutes // 60:02d}h {total_minutes % 60:02d}m"
            
            row_data = [log_date.strftime("%d-%m-%Y"), start_time.strftime("%I:%M %p"), end_time.strftime("%I:%M %p"), final_activity, duration_formatted, notes]
            
            with st.spinner("Saving..."):
                try:
                    sheet_log.append_row(row_data)
                    st.success("✅ Logged successfully!")
                    st.cache_data.clear() 
                except Exception as e: st.error(f"Error: {e}")

# === TAB 2: SCHEDULE FUTURE ===
with tab2:
    st.subheader("📅 Schedule an Upcoming Training")
    future_date = st.date_input("Scheduled Date", date.today() + timedelta(days=1))
    sched_activity_selection = st.selectbox("Scheduled Activity Type", ["Hands-on Training", "EVM/VVPAT Collection", "Other / Custom (Type below)"])
    sched_custom_activity = ""
    if sched_activity_selection == "Other / Custom (Type below)":
        sched_custom_activity = st.text_input("Custom Activity Type", key="s_cust")
    sched_notes = st.text_area("Prep Required")
    
    if st.button("Save Schedule", type="primary"):
        final_sched_activity = sched_custom_activity.strip() if sched_activity_selection == "Other / Custom (Type below)" else sched_activity_selection
        row_data = [future_date.strftime("%d-%m-%Y"), "Pending", "Pending", final_sched_activity, "Pending", sched_notes]
        with st.spinner("Scheduling..."):
            try:
                sheet_log.append_row(row_data)
                st.success("✅ Scheduled!")
                st.cache_data.clear() 
            except Exception as e: st.error(f"Error: {e}")

# === TAB 3: TEAM DASHBOARD ===
with tab3:
    st.subheader("👥 Polling Team Directory")
    
    if not team_list:
        st.info("No team members added yet. Add them below!")
    else:
        for idx, officer_info in enumerate(team_list):
            officer = officer_info['data']
            row_num = officer_info['sheet_row']
            
            status = officer.get('Status', 'Active')
            if not status: status = 'Active'
                
            status_icon = "🟢" if status == "Active" else "🔴"
            status_text = "" if status == "Active" else "(INACTIVE)"
            
            with st.expander(f"{status_icon} {idx + 1}. {officer.get('Name', 'Unknown')} - {officer.get('Polling Office Rank', 'Rank N/A')} {status_text}"):
                st.write(f"**Designation:** {officer.get('Designation', 'N/A')}")
                st.write(f"**Office Address:** {officer.get('Office Address', 'N/A')}")
                mobile = officer.get('Mobile Number', 'N/A')
                st.write(f"**Mobile:** {mobile}")
                
                if status == "Active":
                    st.markdown(f"<a href='tel:{mobile}' style='display: block; text-align: center; padding: 8px; background-color: #4CAF50; color: white; border-radius: 5px; text-decoration: none; margin-bottom: 15px;'>📞 Tap to Dial</a>", unsafe_allow_html=True)
                    
                    st.caption("📝 **Log a Conversation**")
                    call_direction = st.radio("Direction", ["Outgoing (I called them)", "Incoming (They called me)"], key=f"dir_{idx}", horizontal=True)
                    call_notes = st.text_input("Call Notes", placeholder="What was discussed?", key=f"note_{idx}")
                    
                    if st.button("Save Call Record", key=f"btn_{idx}", use_container_width=True):
                        now = datetime.now()
                        direction_val = "Incoming" if "Incoming" in call_direction else "Outgoing"
                        call_data = [now.strftime("%d-%m-%Y"), now.strftime("%I:%M %p"), officer.get('Name'), direction_val, call_notes]
                        try:
                            sheet_calls.append_row(call_data)
                            st.success(f"✅ {direction_val} call logged successfully!")
                        except Exception as e:
                            st.error("Failed to log call.")
                else:
                    st.error("⚠️ This officer is currently marked as INACTIVE. Call logging is disabled.")
                
                st.divider()
                
                toggle_text = "🔴 Mark as Inactive (Disable)" if status == "Active" else "🟢 Mark as Active (Enable)"
                new_status_val = "Inactive" if status == "Active" else "Active"
                
                if st.button(toggle_text, key=f"tog_{idx}"):
                    with st.spinner("Updating status..."):
                        try:
                            sheet_team.update_cell(row_num, 6, new_status_val)
                            st.success(f"Officer status updated to {new_status_val}!")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to update status: {e}")

    st.divider()
    
    # This is the collapsible form that was accidentally removed!
    with st.expander("➕ Add New Team Member"):
        with st.form("add_officer_form"):
            t_name = st.text_input("Name")
            t_desig = st.text_input("Designation (e.g., Assistant Teacher)")
            t_rank = st.selectbox("Polling Office Rank", ["Presiding Officer", "1st Polling Officer", "2nd Polling Officer", "3rd Polling Officer", "Sector Officer", "Micro Observer"])
            t_address = st.text_area("Office Address")
            t_mobile = st.text_input("Mobile Number")
            
            if st.form_submit_button("Save Officer Data"):
                if t_name and t_mobile:
                    try:
                        sheet_team.append_row([t_name, t_desig, t_rank, t_address, t_mobile, "Active"])
                        st.success(f"{t_name} added to the team!")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to add officer. Error: {e}")
                else:
                    st.warning("Name and Mobile Number are required!")

# === TAB 4: VIEW LOGS ===
with tab4:
    st.subheader("Your Study History")
    if st.button("🔄 Refresh Data"): st.cache_data.clear()
    
    df = pd.DataFrame(records)
    if not df.empty:
        # Re-added the cleanup and highlighting logic that was removed!
        def clean_old_durations(val):
            if isinstance(val, str) and 'mins' in val:
                try:
                    total_mins = int(val.replace(' mins', '').strip())
                    return f"{total_mins // 60:02d}h {total_mins % 60:02d}m"
                except: return val
            return val
            
        if 'Duration' in df.columns: 
            df['Duration'] = df['Duration'].apply(clean_old_durations)
            
        def highlight_pending(row):
            if row.get('Start Time') == 'Pending': 
                return ['background-color: #ffcccc; color: black'] * len(row)
            return [''] * len(row)
            
        styled_df = df.style.apply(highlight_pending, axis=1)
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        st.caption(f"Total entries logged: {len(df)}")
    else:
        st.info("No logs found yet.")

# === TAB 5: 1st PO GUIDE ===
with tab5:
    st.header("📖 1st Polling Officer Guide")
    st.markdown("আপনার Polling Day-এর মূল দায়িত্ব ও নিয়মাবলি (Rules & Regulations).")
    
    with st.expander("📝 1. Marking the Electoral Roll (ভোটার তালিকা চিহ্নিতকরণ)"):
        st.markdown("""
        ভোটারের পরিচয় (Identity) verify করার পর **Marked Copy of the Electoral Roll**-এ নিচের নিয়মে দাগ দিন:
        * **Male Voter (পুরুষ):** ভোটারের বক্সের উপর আড়াআড়ি লাল দাগ (Diagonal red line) টানুন।
        * **Female Voter (মহিলা):** আড়াআড়ি লাল দাগ দিন **এবং** Serial Number-টি গোল (Circle) করুন।
        * **Third Gender (তৃতীয় লিঙ্গ):** আড়াআড়ি লাল দাগ দিন **এবং** Serial Number-এর পাশে একটি স্টার (*) বা টিক চিহ্ন (✓) দিন।
        """)
        st.info("💡 **Pro Tip:** Polling Agent-দের সুবিধার্থে ভোটারের Serial Number এবং নাম স্পষ্ট ও জোরে উচ্চারণ করবেন।")

    with st.expander("🕵️ 2. Test Vote (টেস্ট ভোট) - Rule 49MA"):
        st.markdown("""
        যদি কোনো ভোটার দাবি করেন যে তিনি যাকে ভোট দিয়েছেন, **VVPAT**-এ সেই প্রার্থীর Slip প্রিন্ট হয়নি, তবে **Rule 49MA** প্রযোজ্য হবে:
        * প্রথমে ভোটারের কাছ থেকে একটি লিখিত **Declaration** (Annexure/Form-এর মাধ্যমে) নিতে হবে।
        * তাকে সতর্ক করতে হবে যে তার দাবি মিথ্যে প্রমাণিত হলে তার বিরুদ্ধে আইনি ব্যবস্থা নেওয়া হতে পারে।
        * এরপর Polling Agents এবং Presiding Officer-এর সামনে তাকে একটি **Test Vote** দিতে বলা হবে।
        * **Form 17A (Register of Voters)**-তে এই Test Vote-এর জন্য নতুন একটি Entry করতে হবে এবং 'Remarks' কলামে স্পষ্ট করে **"Rule 49MA"** লিখতে হবে।
        """)

    with st.expander("📜 3. Tendered Vote (টেন্ডার ভোট)"):
        st.markdown("""
        যদি কোনো প্রকৃত ভোটার বুথে এসে দেখেন যে তার নামে আগেই কেউ ভোট দিয়ে চলে গেছে:
        * ১নং পোলিং অফিসার হিসেবে তার পরিচয় নিখুঁতভাবে verify করুন।
        * তাকে **EVM**-এ ভোট দিতে দেওয়া যাবে না।
        * Presiding Officer তাকে একটি **Tendered Ballot Paper** (ব্যালট পেপার) দেবেন।
        * এই ভোটারের সই/টিপসই **Form 17B (Register of Tendered Votes)**-তে নিতে হবে, Form 17A-তে নয়।
        """)

    with st.expander("👤 4. Proxy Voter (প্রক্সি ভোটার) - CSV"):
        st.markdown("""
        * **Classified Service Voter (CSV)**-দের ক্ষেত্রে তাদের নিযুক্ত Proxy ভোটার ভোট দিতে পারেন।
        * Marked Copy-তে আসল ভোটারের নামের পাশে **'CSV'** লেখা থাকবে।
        * 2nd Polling Officer Proxy ভোটারের ডান হাতের মধ্যমায় (Middle Finger of Right Hand) কালির দাগ (Indelible Ink) লাগাবেন (বাঁ হাতের তর্জনীতে নয়)।
        """)

    with st.expander("⚠️ 5. ASD, Challenge & EDC"):
        st.markdown("""
        * **ASD (Absent, Shifted, Dead):** ভোটারের নাম ASD লিস্টে থাকলে, পরিচয় খুব সতর্কভাবে verify করুন। এদের থেকে একটি আলাদা Declaration নেওয়া হবে।
        * **Challenged Votes:** কোনো Polling Agent ভোটারের পরিচয় নিয়ে আপত্তি (challenge) জানালে, তা আপনার টেবিলেই হবে। Agent-কে ₹2 challenge fee দিয়ে Presiding Officer-এর কাছে যেতে বলুন। সিদ্ধান্ত না হওয়া পর্যন্ত Electoral Roll-এ দাগ দেবেন না।
        * **EDC (Election Duty Certificate):** Voter on election duty. Marked copy-তে নাম strike off করা থাকলেও, EDC নিয়ে ভোট দিতে এলে তাদের ভোট দিতে হবে এবং 17A তে Entry হবে।
        """)

# === TAB 6: TIMELINE ===
with tab6:
    st.header("⏳ Election Day Timeline")
    st.markdown("Your minute-by-minute statutory schedule.")
    
    st.caption("🔧 **Testing Mode:** Drag the slider to simulate the time of day.")
    simulated_hour = st.slider("Simulate Time (24H Format)", min_value=4, max_value=20, value=7, step=1)
    
    st.divider()

    timeline_events = [
        {"time": "05:00 AM", "hour": 5, "title": "Wake Up & Team Prep", "desc": "Ensure all team members are awake. Presiding Officer links EVM components (BU -> VVPAT -> CU). Do NOT switch on CU yet."},
        {"time": "05:30 AM", "hour": 5.5, "title": "Mock Poll Preparation", "desc": "Agents should arrive. Demonstrate empty EVM and empty VVPAT drop box. Switch on CU."},
        {"time": "05:45 AM", "hour": 5.75, "title": "Conduct Mock Poll", "desc": "Cast at least 50 votes across all candidates (including NOTA). Ensure agents participate."},
        {"time": "06:15 AM", "hour": 6.25, "title": "Clear Mock Poll & Seal EVM", "desc": "CRITICAL: Press CLOSE, RESULT, then CLEAR on CU. Remove Mock VVPAT slips, stamp them 'Mock Poll', and seal in black envelope. Seal the EVM with Green Paper Seal, Special Tag, and Address Tags."},
        {"time": "07:00 AM", "hour": 7, "title": "🟢 ACTUAL POLL COMMENCES", "desc": "Start allowing voters. 1st PO begins identifying voters and marking the Electoral Roll."},
        {"time": "09:00 AM", "hour": 9, "title": "1st 2-Hourly Report", "desc": "Press 'Total' on CU. Presiding Officer sends 9 AM SMS report."},
        {"time": "11:00 AM", "hour": 11, "title": "2nd 2-Hourly Report", "desc": "Press 'Total' on CU. Presiding Officer sends 11 AM SMS report."},
        {"time": "01:00 PM", "hour": 13, "title": "3rd 2-Hourly Report", "desc": "Press 'Total' on CU. Presiding Officer sends 1 PM SMS report. (Take lunch in shifts)."},
        {"time": "03:00 PM", "hour": 15, "title": "4th 2-Hourly Report", "desc": "Press 'Total' on CU. Presiding Officer sends 3 PM SMS report."},
        {"time": "05:00 PM", "hour": 17, "title": "5th 2-Hourly Report", "desc": "Press 'Total' on CU. Presiding Officer sends 5 PM SMS report. Check queue outside."},
        {"time": "06:00 PM", "hour": 18, "title": "Distribute Queue Slips", "desc": "Distribute signed slips to all voters standing in the queue at exactly 6 PM, starting from the LAST person."},
        {"time": "06:30 PM", "hour": 18.5, "title": "🔴 CLOSE THE POLL", "desc": "After last voter, remove cap and press CLOSE button on CU. Switch off CU. Disconnect cables."},
        {"time": "07:00 PM", "hour": 19, "title": "Final Sealing & Forms", "desc": "Pack CU, BU, and VVPAT in carrying cases and seal with Address Tags. Complete Form 17C (Part 1) and Presiding Officer's Diary."},
    ]

    for i, event in enumerate(timeline_events):
        is_active = False
        
        if i < len(timeline_events) - 1:
            next_hour = timeline_events[i+1]["hour"]
            if event["hour"] <= simulated_hour < next_hour:
                is_active = True
        else:
            if simulated_hour >= event["hour"]:
                is_active = True

        if is_active:
            st.success(f"### 👉 CURRENT TASK: {event['time']} - {event['title']}")
            st.write(f"**Action Required:** {event['desc']}")
        else:
            with st.expander(f"{event['time']} - {event['title']}"):
                st.write(event['desc'])

# === TAB 7: FORM 17C CALCULATOR ===
with tab7:
    st.header("🧮 Form 17C Calculator")
    st.markdown("Ensure your Form 17A register perfectly matches the EVM total before sealing.")
    
    st.info("💡 **Instructions:** At the close of poll, enter the final numbers from your booth. The app will verify the math required for Part I of Form 17C.")
    
    st.subheader("1. Base Numbers")
    col1, col2 = st.columns(2)
    with col1:
        total_assigned = st.number_input("Total Electors Assigned to Booth (1)", min_value=0, value=1000, step=1)
    with col2:
        form_17a_total = st.number_input("Total entries in Form 17A Register (2)", min_value=0, value=0, step=1)
        
    st.divider()
        
    st.subheader("2. Exceptions (Voters who didn't press the EVM)")
    col3, col4 = st.columns(2)
    with col3:
        rule_49o = st.number_input("Voters deciding NOT to vote (Rule 49-O) (3)", min_value=0, value=0, step=1, help="They signed the register but refused to press a button.")
    with col4:
        rule_49m = st.number_input("Voters NOT ALLOWED to vote (Rule 49-M) (4)", min_value=0, value=0, step=1, help="Presiding Officer stopped them for violating secrecy rules.")
        
    st.divider()
    
    st.subheader("3. Final EVM Reading")
    actual_evm_total = st.number_input("Total Votes Recorded on EVM Control Unit (6)", min_value=0, value=0, step=1)
    
    st.divider()

    st.subheader("4. Tendered Votes")
    tendered_votes = st.number_input("Number of Tendered Votes (Ballot Paper)", min_value=0, value=0, step=1)
    st.caption("*(Note: Tendered votes are cast on paper and do NOT affect the EVM total).*")
    
    st.divider()

    # --- THE CALCULATION LOGIC ---
    expected_evm_total = form_17a_total - rule_49o - rule_49m
    
    st.header("📝 Final Form 17C Verification")
    
    st.write(f"**Total from Register (17A):** {form_17a_total}")
    st.write(f"**Minus Exceptions (49-O + 49-M):** - {rule_49o + rule_49m}")
    st.markdown(f"### Expected EVM Total: **{expected_evm_total}**")
    st.markdown(f"### Actual EVM Total: **{actual_evm_total}**")
    
    if form_17a_total == 0 and actual_evm_total == 0:
        st.info("Awaiting final data entry.")
    elif expected_evm_total == actual_evm_total:
        st.success("✅ SUCCESS! The Form 17A register PERFECTLY MATCHES the EVM Control Unit.")
        st.markdown("""
        **What to write on Form 17C:**
        * Item 2 (Total in 17A): **{val1}**
        * Item 3 (Rule 49-O): **{val2}**
        * Item 4 (Rule 49-M): **{val3}**
        * Item 6 (Total in EVM): **{val4}**
        * Item 7 (Does Item 6 tally with Item 2 - Item 3 - Item 4?): **YES**
        """.format(val1=form_17a_total, val2=rule_49o, val3=rule_49m, val4=actual_evm_total))
    else:
        st.error("🚨 MISMATCH DETECTED! Do NOT seal the EVM yet.")
        diff = abs(expected_evm_total - actual_evm_total)
        st.write(f"There is a difference of **{diff}** vote(s) between the 17A Register and the EVM.")
        st.write("**Troubleshooting:**")
        st.write("1. Check if the 2nd Polling Officer miscounted the Serial Numbers in Form 17A.")
        st.write("2. Double-check if any Test Votes (Rule 49-MA) were cast, which requires additional adjustments.")
        st.write("3. Ensure Tendered Votes were NOT accidentally entered into the EVM.")

# === TAB 8: EVM TROUBLESHOOTER ===
with tab8:
    st.header("🛠️ EVM Troubleshooting (ইভিএম সমস্যা সমাধান)")
    st.markdown("EVM বা VVPAT-এ কোনো Error Message দেখালে এখান থেকে তার সমাধান (Solution) দেখে নিন।")
    
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
        st.write("**Solution (সমাধান):**")
        st.markdown("""
        1. প্রথমেই Control Unit (CU)-টি **Switch OFF** করুন।
        2. Cables ঠিকমত কানেক্ট করা আছে কিনা চেক করুন। **(BU এর কেবল VVPAT এ, এবং VVPAT এর কেবল CU তে লাগাতে হবে)**।
        3. Connector-এর পিনগুলো ঠিক আছে কিনা দেখুন, জোর করে ঢোকাবেন না।
        4. সব ঠিক থাকলে আবার CU **Switch ON** করুন। সমস্যা না মিটলে Sector Officer-কে জানান।
        """)
        
    elif "Pressed Error" in evm_error:
        st.error("🚨 CU Display: 'PRESSED ERROR'")
        st.write("**Solution (সমাধান):**")
        st.markdown("""
        1. এর মানে হলো Ballot Unit (BU)-এর কোনো বোতাম (Button) আগে থেকেই আটকে (jam) আছে।
        2. BU-তে গিয়ে চেক করুন কোনো বোতাম আটকে আছে কিনা, থাকলে তা ধীরে ধীরে ছাড়িয়ে দিন।
        3. ঠিক না হলে Sector Officer-কে জানিয়ে পুরো BU রিপ্লেস (Replace) করতে হবে।
        """)
        
    elif "VVPAT Beeping" in evm_error:
        st.error("🚨 VVPAT একটানা Beep শব্দ করছে / Error 2.6")
        st.write("**Solution (সমাধান):**")
        st.markdown("""
        1. VVPAT-এর Paper Roll শেষ হয়ে গেলে বা কাগজ আটকে (Paper Jam) গেলে এই শব্দ হয়।
        2. **Actual Poll চলাকালীন VVPAT খারাপ হলে, শুধুমাত্র VVPAT পরিবর্তন করতে হবে (EVM বা BU নয়)।**
        3. পরিবর্তনের সময় Mock Poll করার প্রয়োজন নেই, শুধু একটি Test Vote দিয়ে চেক করতে হবে। Sector Officer-কে অবিলম্বে খবর দিন।
        """)
        
    elif "Invalid Error" in evm_error:
        st.error("🚨 CU Display: 'INVALID'")
        st.write("**Solution (সমাধান):**")
        st.markdown("""
        1. আপনি ভুল Sequence-এ বোতাম টিপেছেন।
        2. যেমন: 'Close' বোতাম টেপার আগে যদি 'Result' বোতাম টেপেন, তাহলে এই Error দেখাবে।
        3. সঠিক Sequence মনে রাখুন: **CLOSE ➡️ RESULT ➡️ CLEAR** (Mock poll-এর সময়)।
        """)
        
    elif "Low Battery" in evm_error:
        st.error("🚨 CU Display: 'BATTERY LOW'")
        st.write("**Solution (সমাধান):**")
        st.markdown("""
        1. CU **Switch OFF** করুন।
        2. Presiding Officer-এর কাছে থাকা Extra Battery (Power Pack) দিয়ে CU-এর ব্যাটারি পরিবর্তন করুন।
        3. এটি করার আগে অবশ্যই Polling Agent-দের উপস্থিতিতে ব্যাটারি কম্পার্টমেন্টের সিল ভাঙতে হবে এবং নতুন সিল লাগাতে হবে (Part-II of PO Report)।
        """)
        
    elif "Close Button Not Working" in evm_error:
        st.error("🚨 Close Button কাজ করছে না")
        st.write("**Solution (সমাধান):**")
        st.markdown("""
        1. ভোট গ্রহণ শেষে (Close of Poll) যদি Close বোতাম কাজ না করে, চেক করুন 'Busy' ইন্ডিকেটর জ্বলছে কিনা।
        2. যদি 'Busy' ইন্ডিকেটর জ্বলে থাকে, তার মানে কোনো ভোটারের জন্য Ballot ইস্যু করা আছে কিন্তু সে ভোট দেয়নি।
        3. BU-তে গিয়ে যেকোনো একটি বোতাম টিপে সেই ব্যালটটি বাতিল/সম্পূর্ণ করুন, এরপর CU-তে 'Close' বোতাম কাজ করবে।
        """)
    elif evm_error == "Select an error...":
        st.info("👆 উপর থেকে আপনার EVM-এর সমস্যাটি নির্বাচন করুন।")
