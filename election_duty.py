import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, date, timedelta

# --- Page Configuration ---
st.set_page_config(page_title="Election Duty Prep Tracker", page_icon="🗳️", layout="centered")

st.title("🗳️ Election Duty Tracker")
st.markdown("Schedule, log, and manage your polling team.")

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

pending_sessions = []
for index, rec in enumerate(records):
    if rec.get("Start Time") == "Pending":
        pending_sessions.append({"sheet_row": index + 2, "data": rec})

team_list = []
for index, rec in enumerate(team_records):
    team_list.append({"sheet_row": index + 2, "data": rec})

# --- App Layout: Tabs ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📝 Log & Complete", 
    "📅 Schedule Future", 
    "👥 Team Dashboard", 
    "📊 View Logs",
    "📖 Quick Reference"
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
        def clean_old_durations(val):
            if isinstance(val, str) and 'mins' in val:
                try:
                    total_mins = int(val.replace(' mins', '').strip())
                    return f"{total_mins // 60:02d}h {total_mins % 60:02d}m"
                except: return val
            return val
        if 'Duration' in df.columns: df['Duration'] = df['Duration'].apply(clean_old_durations)
        def highlight_pending(row):
            if row.get('Start Time') == 'Pending': return ['background-color: #ffcccc; color: black'] * len(row)
            return [''] * len(row)
        styled_df = df.style.apply(highlight_pending, axis=1)
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        st.caption(f"Total entries logged: {len(df)}")
    else:
        st.info("No logs found yet.")

# === TAB 5: QUICK REFERENCE (BENGALI / ENGLISH) ===
with tab5:
    st.header("📖 1st Polling Officer Guide")
    st.markdown("Polling Day-তে আপনার statutory duty-র quick reference.")
    
    with st.expander("📝 1. Electoral Roll Marking (ভোটার তালিকা দাগানো)"):
        st.markdown("""
        ভোটারের পরিচয় verify করার পর, **Marked Copy of the Electoral Roll**-এ ঠিক এইভাবে দাগ দেবেন:
        * **Male Voter (পুরুষ ভোটার):** ভোটারের নামের বাক্সের ওপর আড়াআড়ি লাল দাগ (Diagonal red line) টানুন।
        * **Female Voter (মহিলা ভোটার):** আড়াআড়ি লাল দাগ (Diagonal red line) টানুন **এবং** Serial Number-টি গোল (Circle) করে দিন।
        * **Third Gender Voter (তৃতীয় লিঙ্গ):** আড়াআড়ি লাল দাগ (Diagonal red line) টানুন **এবং** Serial Number-এর পাশে একটি স্টার (*) বা টিক (✓) চিহ্ন দিন।
        """)
        st.info("💡 **Pro Tip:** Serial Number এবং নাম জোরে, স্পষ্ট গলায় বলবেন যাতে Polling Agent-রা শুনতে পায়।")

    with st.expander("🪪 2. Approved Alternate ID (বিকল্প সচিত্র পরিচয়পত্র)"):
        st.markdown("""
        যদি ভোটারের কাছে EPIC না থাকে, তবে ECI অনুমোদিত নিচের যেকোনো একটি পরিচয়পত্র দেখাতে হবে:
        1. Aadhaar Card
        2. PAN Card
        3. Driving License
        4. Indian Passport
        5. Passbooks with photograph (Bank/Post Office ইস্যু করা)
        6. Smart Card (RGI/NPR ইস্যু করা)
        7. MNREGA Job Card
        8. Health Insurance Smart Card (Ministry of Labour)
        9. Pension document with photograph
        10. Official ID cards (MPs/MLAs/MLCs-দের জন্য)
        11. Service Identity Cards (Central/State Govt./PSUs)
        12. Unique Disability ID (UDID) Card
        """)

    with st.expander("⚠️ 3. Special Cases (ASD, Challenge & EDC)"):
        st.markdown("""
        * **ASD (Absent, Shifted, Dead) Voters:** যদি কোনো ভোটারের নাম ASD লিস্টে থাকে, খুব সতর্কভাবে পরিচয় verify করুন। সাথে সাথে Presiding Officer-কে জানান। এদের থেকে একটি আলাদা Declaration নেওয়া হবে।
        * **Challenged Votes:** কোনো Polling Agent ভোটারের পরিচয় নিয়ে আপত্তি (challenge) জানালে, তা আপনার টেবিলেই হবে। 
            * Agent-কে ₹2 challenge fee দিয়ে Presiding Officer-এর কাছে যেতে বলুন।
            * Presiding Officer summary inquiry করবেন। 
            * Presiding Officer চূড়ান্ত সিদ্ধান্ত না নেওয়া পর্যন্ত Electoral Roll-এ দাগ (strike off) দেবেন না।
        * **Blind & Infirm Voters:** দৃষ্টিহীন বা শারীরিকভাবে অক্ষম ভোটারদের সাথে একজন Companion (বয়স 18+ হতে হবে) থাকতে পারেন। খেয়াল রাখবেন, একজন companion যেন একাধিক ভোটারের হয়ে কাজ না করে।
        * **EDC (Election Duty Certificate):** Marked copy-তে EDC ভোটারের নাম strike off করা থাকলেও, যদি তারা আপনার specific booth-এ EDC নিয়ে ভোট দিতে আসে, তবে তাদের ভোট দিতে হবে।
        """)
