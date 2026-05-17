import streamlit as st

# --- BACK BUTTON ---
if st.button("⬅️ Back to Hub", type="secondary"):
    st.switch_page("routine_app.py") 
st.write("---") 
# -------------------

import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import time

st.set_page_config(page_title="Smart Routine Editor", page_icon="⚙️", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 4rem; padding-bottom: 2rem;}
    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
        border-radius: 8px !important;
        border: 1px solid #cccccc !important;
        background-color: #ffffff !important;
    }
    .edit-header {
        color: #0068c9;
        font-size: 24px;
        font-weight: bold;
        margin-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("<div class='edit-header'>⚙️ Smart Schedule Manager</div>", unsafe_allow_html=True)

# ==========================================
# Database Connection & Caching
# ==========================================
@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

def get_main_spreadsheet(): return init_connection().open("MY ROUTINE 2026")
def get_sheet(tab_name): return get_main_spreadsheet().worksheet(tab_name)

def auto_adjust_schedule(df):
    """
    AI Auto-Fixer: Scans every day for time overlaps.
    If multiple tasks start at the same time, the shorter one wins and shifts the longer one forward.
    If a task overlaps into the next, it perfectly shrinks the first task.
    """
    def time_to_mins(t_str):
        try:
            t = datetime.strptime(str(t_str).strip(), '%H:%M')
            return t.hour * 60 + t.minute
        except: return 0

    def mins_to_time(mins):
        h = (int(mins) // 60) % 24
        m = int(mins) % 60
        return f"{h}:{m:02d}"

    final_rows = []
    for day in df['Day'].unique():
        day_df = df[df['Day'] == day].copy()
        day_df['Start_Mins'] = day_df['Start_Time'].apply(time_to_mins)
        day_df['End_Mins'] = day_df['End_Time'].apply(time_to_mins)
        # Handle midnight rollover
        day_df['End_Mins'] = day_df.apply(lambda r: r['End_Mins'] + 1440 if r['End_Mins'] <= r['Start_Mins'] and r['End_Mins'] < 120 else r['End_Mins'], axis=1)
        day_df['Dur_Mins'] = day_df['End_Mins'] - day_df['Start_Mins']
        
        # Sort so overlaps are naturally arranged (Earliest Start -> Shortest Duration)
        day_df = day_df.sort_values(['Start_Mins', 'Dur_Mins']).reset_index(drop=True)
        
        for i in range(len(day_df) - 1):
            for j in range(i+1, len(day_df)):
                start_A = day_df.loc[i, 'Start_Mins']
                end_A = day_df.loc[i, 'End_Mins']
                start_B = day_df.loc[j, 'Start_Mins']
                
                if start_B < end_A: # Overlap Detected!
                    if start_A == start_B:
                        # Same start time: Task B (longer) gets pushed forward
                        day_df.loc[j, 'Start_Mins'] = end_A
                        if day_df.loc[j, 'Start_Mins'] > day_df.loc[j, 'End_Mins']:
                            day_df.loc[j, 'End_Mins'] = day_df.loc[j, 'Start_Mins']
                    else:
                        # Task A bleeds into Task B: Task A gets shrunk backwards
                        day_df.loc[i, 'End_Mins'] = start_B
                        end_A = start_B
                        
        # Final Format and Recalculation
        day_df['Start_Time'] = day_df['Start_Mins'].apply(mins_to_time)
        day_df['End_Time'] = day_df['End_Mins'].apply(mins_to_time)
        day_df['Dur_Mins'] = day_df['End_Mins'] - day_df['Start_Mins']
        
        # Keep only tasks with a valid duration (removes swallowed tasks)
        day_df = day_df[day_df['Dur_Mins'] > 0].copy()
        day_df['Duration'] = day_df['Dur_Mins'].apply(lambda x: f"{int(x)//60:02d}:{int(x)%60:02d}")
        
        final_rows.append(day_df)
        
    if final_rows:
        fixed_df = pd.concat(final_rows, ignore_index=True)
        return fixed_df[["Day", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "App"]]
    return df

@st.cache_data(ttl=300) 
def get_routine_data():
    data = get_sheet("routine_master").get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    
    # Ensure exactly 8 columns (Day, Start, End, Dur, Act, Sub, Chk, App)
    while df.shape[1] < 8: df[df.shape[1]] = ""
    df = df.iloc[:, :8]
    df.columns = ["Day", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "App"]
    
    df = df[df["Day"].astype(str).str.strip() != ""]
    df["Activity"] = df["Activity"].astype(str).str.strip().str.upper()
    
    # Automatically heal any overlaps upon loading
    df = auto_adjust_schedule(df)
    return df

# ==========================================
# Main Logic
# ==========================================
try:
    df = get_routine_data()

    # --- 1. SMART DAY GROUPING LOGIC ---
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    has_all_weekdays = all(d in df['Day'].str.title().unique() for d in weekdays)

    mon_fri_grouped = False
    if has_all_weekdays:
        mon_df = df[df['Day'].str.title() == "Monday"].reset_index(drop=True)
        is_identical = True
        for d in weekdays[1:]:
            d_df = df[df['Day'].str.title() == d].reset_index(drop=True)
            if len(mon_df) != len(d_df):
                is_identical = False
                break
            if not mon_df['Activity'].equals(d_df['Activity']) or not mon_df['Start_Time'].equals(d_df['Start_Time']):
                is_identical = False
                break
        mon_fri_grouped = is_identical

    # Generate Dropdown Options
    day_options = []
    if mon_fri_grouped:
        day_options.append("Monday to Friday")
        for d in df['Day'].str.title().unique():
            if d not in weekdays:
                day_options.append(d)
    else:
        day_options = list(df['Day'].str.title().unique())

    # --- 2. DAY SELECTION ---
    st.markdown("#### 📅 1. Select Day to Manage")
    sel_day_opt = st.selectbox("Select Schedule Day", day_options, label_visibility="collapsed")
    
    if sel_day_opt == "Monday to Friday":
        target_days = weekdays
        display_day = "Monday" # We show Monday's schedule as the template
        st.info("💡 **Batch Mode Active:** Changes made here will instantly apply to Monday, Tuesday, Wednesday, Thursday, and Friday.")
    else:
        target_days = [sel_day_opt]
        display_day = sel_day_opt

    target_df = df[df['Day'].str.title() == display_day].copy()

    # --- 3. TIME SLOT SELECTION ---
    st.markdown("#### ⏱️ 2. Select Time Slot")
    slot_opts = [f"{row['Start_Time']} to {row['End_Time']}  |  {row['Activity']}" for _, row in target_df.iterrows()]
    selected_slot = st.selectbox("Choose the specific slot you want to update:", slot_opts)
    
    sel_start = selected_slot.split(" to ")[0].strip()

    # --- 4. HIGHLIGHTED SCHEDULE DISPLAY ---
    st.markdown(f"**Full Schedule for {display_day}** *(Editing row highlighted in yellow)*")
    
    def highlight_target_row(s):
        # Applies a bright yellow background to the selected row for easy viewing
        is_target = s['Start_Time'] == sel_start
        return ['background-color: #fff59d; color: black; font-weight: bold;' if is_target else '' for _ in s]

    st.dataframe(target_df.style.apply(highlight_target_row, axis=1), use_container_width=True, hide_index=True)

    st.markdown("---")

    # --- 5. SMART EDITOR FORM ---
    sel_row = target_df[target_df['Start_Time'] == sel_start].iloc[0]

    # Harvest all historical data for dropdowns
    all_acts = sorted(list(set(df['Activity'].dropna().str.upper())))
    all_subs = sorted(list(set([x.strip() for items in df['Sub_Activities'].dropna() for x in str(items).split(',') if x.strip()])))
    all_chks = sorted(list(set([x.strip() for items in df['check_list'].dropna() for x in str(items).split(',') if x.strip()])))
    all_apps_db = sorted(list(set([x.strip() for items in df['App'].dropna() for x in str(items).split(',') if x.strip()])))

    # APP GROUPING LOGIC
    app_groups = {
        "MONEY": ["Money & Location", "Money Utilities", "Money Tracker"],
        "ROUTINE": ["Live Routine Hub", "Routine Audit", "Routine Editor", "Project App"],
        "HEALTH": ["Health Hub", "Sleep & Water"],
        "SCH WORK": ["MDM Returns", "Video Manager"],
        "HOME": ["Trace Inventory", "Monthly Tracker"],
        "HARDWARE": ["Backup Tracker"],
        "BALANCE": ["Strong Tracker"],
        "ONES": ["Election Duty"]
    }
    app_to_group = {app: grp for grp, apps in app_groups.items() for app in apps}
    
    # Current cell values
    curr_act = str(sel_row['Activity']).strip()
    curr_sub_list = [x.strip() for x in str(sel_row['Sub_Activities']).split(',') if x.strip()]
    curr_chk_list = [x.strip() for x in str(sel_row['check_list']).split(',') if x.strip()]
    curr_app_list = [x.strip() for x in str(sel_row['App']).split(',') if x.strip()]

    # Ensure current items exist in the dropdown options
    opts_sub = sorted(list(set(all_subs + curr_sub_list)))
    opts_chk = sorted(list(set(all_chks + curr_chk_list)))
    
    # Merge grouped apps with historical apps
    standard_apps = [app for grp in app_groups.values() for app in grp]
    opts_app = standard_apps.copy()
    for a in all_apps_db + curr_app_list:
        if a not in opts_app and a.strip():
            opts_app.append(a)

    def format_app_display(app_name):
        grp = app_to_group.get(app_name, "CUSTOM")
        return f"[{grp}]  {app_name}"

    st.markdown(f"#### ✏️ 3. Update `{sel_row['Start_Time']}` Slot Details")
    
    with st.form("smart_edit_form"):
        st.markdown("<div style='background-color: #f8f9fa; padding: 15px; border-radius: 8px;'>", unsafe_allow_html=True)
        
        # TIME SLOT EDITING (Triggers Auto-Fix Overlaps)
        st.markdown("**⏰ Edit Time Slot (Overlaps will Auto-Fix upon saving!)**")
        col_t1, col_t2 = st.columns(2)
        with col_t1: new_start_txt = st.text_input("Start Time (H:MM)", value=sel_row['Start_Time'])
        with col_t2: new_end_txt = st.text_input("End Time (H:MM)", value=sel_row['End_Time'])
        
        st.markdown("<hr style='margin: 10px 0px;'>", unsafe_allow_html=True)

        # ACTIVITY
        st.markdown("**1️⃣ Activity Category**")
        col_a1, col_a2 = st.columns(2)
        with col_a1: new_act_sel = st.selectbox("Select Existing", all_acts, index=all_acts.index(curr_act) if curr_act in all_acts else 0)
        with col_a2: new_act_txt = st.text_input("Or Create New Activity (Overrides selection)", placeholder="Type new activity...")

        st.markdown("<hr style='margin: 10px 0px;'>", unsafe_allow_html=True)

        # SUB-ACTIVITIES
        st.markdown("**2️⃣ Sub-Activities**")
        new_subs_sel = st.multiselect("Select Existing (Multiple allowed)", opts_sub, default=curr_sub_list)
        new_subs_txt = st.text_input("Add New (Comma separated)", placeholder="e.g., Check emails, Plan week", key="new_sub")

        st.markdown("<hr style='margin: 10px 0px;'>", unsafe_allow_html=True)

        # CHECKLIST
        st.markdown("**3️⃣ Tasks & Reminders (Checklist)**")
        new_chks_sel = st.multiselect("Select Existing", opts_chk, default=curr_chk_list)
        new_chks_txt = st.text_input("Add New (Comma separated)", placeholder="e.g., Pay bills, Buy milk", key="new_chk")

        st.markdown("<hr style='margin: 10px 0px;'>", unsafe_allow_html=True)

        # APPS (With Visual Grouping)
        st.markdown("**4️⃣ Applications Launchpad**")
        new_apps_sel = st.multiselect("Select Apps (Grouped by category)", opts_app, default=curr_app_list, format_func=format_app_display)
        new_apps_txt = st.text_input("Add Custom App (Comma separated)", placeholder="e.g., Extra Tool 1", key="new_app")

        st.markdown("</div><br>", unsafe_allow_html=True)

        if st.form_submit_button("💾 Save Changes to Routine", type="primary", use_container_width=True):
            # Resolve final strings
            final_act = new_act_txt.strip().upper() if new_act_txt.strip() else new_act_sel
            
            # Combine multiselect and new typed text, then format perfectly
            final_subs = ",".join(filter(None, [x for x in new_subs_sel] + [x.strip() for x in new_subs_txt.split(',')]))
            final_chks = ",".join(filter(None, [x for x in new_chks_sel] + [x.strip() for x in new_chks_txt.split(',')]))
            final_apps = ",".join(filter(None, [x for x in new_apps_sel] + [x.strip() for x in new_apps_txt.split(',')]))

            # Apply changes to the main dataframe
            target_mask = (df['Day'].str.title().isin(target_days)) & (df['Start_Time'] == sel_start)
            
            df.loc[target_mask, 'Start_Time'] = new_start_txt.strip()
            df.loc[target_mask, 'End_Time'] = new_end_txt.strip()
            df.loc[target_mask, 'Activity'] = final_act
            df.loc[target_mask, 'Sub_Activities'] = final_subs
            df.loc[target_mask, 'check_list'] = final_chks
            df.loc[target_mask, 'App'] = final_apps

            # ✨ MAGIC OVERLAP FIXER ✨
            df = auto_adjust_schedule(df)

            # Push to Google Sheets
            with st.spinner("Healing Overlaps and Saving to Google Sheets..."):
                routine_sheet = get_sheet("routine_master")
                routine_sheet.clear()
                routine_sheet.update(values=[df.columns.values.tolist()] + df.values.tolist(), range_name="A1")
                
                # Clear Cache to show new data immediately
                get_routine_data.clear()
                
            st.success(f"✅ Successfully updated and healed schedule for {sel_day_opt}!")
            time.sleep(1.5)
            st.rerun()

except Exception as e:
    st.error(f"System Error: {e}")
