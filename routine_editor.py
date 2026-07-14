import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import time

# --- BACK BUTTON ---
if st.button("⬅️ Back to Hub", type="secondary"):
    st.switch_page("routine_app.py") 
st.write("---") 
# -------------------

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
    .total-time-footer {
        font-size: 20px;
        font-weight: bold;
        color: #0068c9;
        background-color: #e3f2fd;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
        margin-top: 20px;
    }
    .sub-act-row {
        background-color: #f8f9fa;
        padding: 10px;
        border-radius: 6px;
        margin-bottom: 8px;
        border: 1px solid #e0e0e0;
    }
    .profile-header {
        font-size: 18px;
        font-weight: 600;
        margin-bottom: -10px;
        color: #495057;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("<div class='edit-header'>⚙️ Smart Schedule Manager</div>", unsafe_allow_html=True)

# ==========================================
# Database Connection & Helper Functions
# ==========================================
@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

def get_main_spreadsheet(): return init_connection().open("MY ROUTINE 2026")
def get_sheet(tab_name): return get_main_spreadsheet().worksheet(tab_name)

def time_to_mins(t_str):
    try:
        t = datetime.strptime(str(t_str).strip(), '%H:%M')
        return t.hour * 60 + t.minute
    except: return 0

def mins_to_time(mins):
    h = (int(mins) // 60) % 24
    m = int(mins) % 60
    return f"{h}:{m:02d}"

def sort_routine_df(df):
    day_order = {d: i for i, d in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])}
    df['Day_Idx'] = df['Day'].str.title().map(day_order).fillna(99)
    df = df.sort_values(by=['Day_Idx', 'Start_Mins']).drop(columns=['Day_Idx']).reset_index(drop=True)
    return df

def auto_adjust_schedule(df):
    final_rows = []
    for day in df['Day'].unique():
        day_df = df[df['Day'] == day].copy()
        day_df['Start_Mins'] = day_df['Start_Time'].apply(time_to_mins)
        day_df['End_Mins'] = day_df['End_Time'].apply(time_to_mins)
        day_df['End_Mins'] = day_df.apply(lambda r: r['End_Mins'] + 1440 if r['End_Mins'] <= r['Start_Mins'] and r['End_Mins'] < 120 else r['End_Mins'], axis=1)
        day_df['Dur_Mins'] = day_df['End_Mins'] - day_df['Start_Mins']
        day_df = day_df.sort_values(['Start_Mins', 'Dur_Mins']).reset_index(drop=True)
        
        for i in range(len(day_df) - 1):
            for j in range(i+1, len(day_df)):
                start_A = day_df.loc[i, 'Start_Mins']
                end_A = day_df.loc[i, 'End_Mins']
                start_B = day_df.loc[j, 'Start_Mins']
                
                if start_B < end_A:
                    if start_A == start_B:
                        day_df.loc[j, 'Start_Mins'] = end_A
                        if day_df.loc[j, 'Start_Mins'] > day_df.loc[j, 'End_Mins']:
                            day_df.loc[j, 'End_Mins'] = day_df.loc[j, 'Start_Mins']
                    else:
                        day_df.loc[i, 'End_Mins'] = start_B
                        
        day_df['Start_Time'] = day_df['Start_Mins'].apply(mins_to_time)
        day_df['End_Time'] = day_df['End_Mins'].apply(mins_to_time)
        day_df['Dur_Mins'] = day_df['End_Mins'] - day_df['Start_Mins']
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
    while df.shape[1] < 12: df[df.shape[1]] = ""
    df = df.iloc[:, :12]
    df.columns = ["Day", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "App", "Role", "Urgent", "Important", "Energy_Level"]
    df = df[df["Day"].astype(str).str.strip() != ""]
    df["Activity"] = df["Activity"].astype(str).str.strip().str.upper()
    df = auto_adjust_schedule(df)
    return df

@st.cache_data(ttl=300)
def get_activity_master():
    try:
        sheet = get_main_spreadsheet().worksheet("activity_master")
    except gspread.exceptions.WorksheetNotFound:
        spreadsheet = get_main_spreadsheet()
        sheet = spreadsheet.add_worksheet(title="activity_master", rows="100", cols="4")
        sheet.update(values=[["Day_Type", "Activity", "Sub_Activity", "Duration_Mins"]], range_name="A1")
        return pd.DataFrame(columns=["Day_Type", "Activity", "Sub_Activity", "Duration_Mins", "Sheet_Row"])
        
    data = sheet.get_all_values()
    if not data:
        return pd.DataFrame(columns=["Day_Type", "Activity", "Sub_Activity", "Duration_Mins", "Sheet_Row"])
    
    # Check for old schema and migrate gracefully without breaking user data
    if "Day_Type" not in data[0]:
        df = pd.DataFrame(data[1:], columns=data[0]) if len(data) > 1 else pd.DataFrame(columns=data[0])
        df.insert(0, "Day_Type", "WEEK DAYS")
        sheet.clear()
        sheet.update(values=[df.columns.values.tolist()] + df.values.tolist(), range_name="A1")
        data = sheet.get_all_values()

    if len(data) <= 1:
        return pd.DataFrame(columns=["Day_Type", "Activity", "Sub_Activity", "Duration_Mins", "Sheet_Row"])
    
    df = pd.DataFrame(data[1:], columns=data[0])
    # Track the exact row number in Google Sheets (header is row 1, data starts at row 2)
    df['Sheet_Row'] = df.index + 2 
    df['Duration_Mins'] = pd.to_numeric(df['Duration_Mins'], errors='coerce').fillna(0)
    return df

# Helper formatting function for summary duration
def format_mins(total_mins):
    h = int(total_mins) // 60
    m = int(total_mins) % 60
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"

# Formatting function for matrix to hide zeros cleanly
def format_matrix_mins(total_mins):
    if pd.isna(total_mins) or total_mins == 0:
        return "-"
    return format_mins(total_mins)

# ==========================================
# Main Logic
# ==========================================
try:
    df = get_routine_data()
    act_master_df = get_activity_master()

    # Consolidate standard options and Builder DB options to feed Tab 1 dropdowns dynamically
    all_acts_db = df['Activity'].dropna().tolist()
    all_acts_builder = act_master_df['Activity'].dropna().tolist()
    all_acts = sorted(list(set([str(x).strip().upper() for x in all_acts_db + all_acts_builder if str(x).strip()])))
    
    all_subs_db = [x.strip() for items in df['Sub_Activities'].dropna() for x in str(items).split(',') if x.strip()]
    all_subs_builder = act_master_df['Sub_Activity'].dropna().tolist()
    all_subs = sorted(list(set([str(x).strip() for x in all_subs_db + all_subs_builder if str(x).strip()])))

    # Create Tabs for the Interface
    tab_editor, tab_summary, tab_builder = st.tabs(["⚙️ Routine Editor", "📊 Routine Summary", "🏗️ Activity Builder"])

    # ==========================================
    # TAB 3: ACTIVITY BUILDER
    # ==========================================
    with tab_builder:
        st.markdown("### 🏗️ Activity Database & Time Pool")
        
        # Profile Configuration Selector
        st.markdown("<div class='profile-header'>📅 Select Schedule Profile</div>", unsafe_allow_html=True)
        profile_options = ["WEEK DAYS", "SATURDAY/HALF WORKING DAY", "SUNDAY", "HOLIDAY"]
        selected_day_type = st.radio("Profile Config", profile_options, horizontal=True, label_visibility="collapsed")
        
        # Filter dataframe for current profile
        profile_df = act_master_df[act_master_df['Day_Type'] == selected_day_type].copy()
        
        total_used = profile_df['Duration_Mins'].sum()
        remaining = 1440 - total_used
        
        st.markdown(f"**Managing time pool and activities for:** `{selected_day_type}`")
        
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Total Day Limit", "24h 0m")
        col_m2.metric("Allocated Time", format_mins(total_used))
        col_m3.metric("Remaining Time", format_mins(max(0, remaining)))
        
        st.markdown("---")
        col_add1, col_add2 = st.columns(2)
        
        with col_add1:
            st.markdown("#### 1️⃣ Create New Parent Activity")
            with st.form("create_act_form"):
                new_act_input = st.text_input("New Activity Name", placeholder="e.g. MORNING ROUTINE").strip().upper()
                if st.form_submit_button("➕ Add Activity", use_container_width=True):
                    if new_act_input:
                        if new_act_input not in profile_df['Activity'].values:
                            sheet = get_main_spreadsheet().worksheet("activity_master")
                            # Schema: Day_Type, Activity, Sub_Activity, Duration_Mins
                            sheet.append_row([selected_day_type, new_act_input, "", 0])
                            get_activity_master.clear()
                            st.success(f"✅ Created Activity: {new_act_input} for {selected_day_type}")
                            time.sleep(1.5)
                            st.rerun()
                        else:
                            st.warning("⚠️ Activity already exists in this profile.")
                            
        with col_add2:
            st.markdown("#### 2️⃣ Add Dependent Sub-Activity")
            with st.form("create_sub_form"):
                existing_acts = sorted(list(profile_df['Activity'].unique()))
                if "" in existing_acts: existing_acts.remove("")
                
                sel_act = st.selectbox("Select Parent Activity", existing_acts) if existing_acts else st.selectbox("No Parents Available", [""])
                new_sub_input = st.text_input("New Sub-Activity Name", placeholder="e.g. Meditation").strip()
                sub_dur = st.number_input("Duration (Minutes)", min_value=1, max_value=1440, value=30, step=5)
                
                if st.form_submit_button("➕ Add Sub-Activity", use_container_width=True):
                    if sel_act and new_sub_input:
                        if sub_dur <= remaining:
                            sheet = get_main_spreadsheet().worksheet("activity_master")
                            sheet.append_row([selected_day_type, sel_act, new_sub_input, sub_dur])
                            get_activity_master.clear()
                            st.success(f"✅ Added '{new_sub_input}' under '{sel_act}'")
                            time.sleep(1.5)
                            st.rerun()
                        else:
                            st.error(f"❌ Cannot allocate {sub_dur} mins. Only {format_mins(remaining)} left in the day!")
                            
        st.markdown("---")
        st.markdown(f"### 📋 Configured Activities for {selected_day_type}")
        st.info("💡 Adjust the minutes below and click **Save** to update the sub-activity duration.")
        
        if not profile_df.empty:
            grouped = profile_df.groupby("Activity")['Duration_Mins'].sum().sort_values(ascending=False)
            for act, act_mins in grouped.items():
                if not act: continue
                with st.expander(f"📁 **{act}** | Sub-Activities Total: **{format_mins(act_mins)}**"):
                    sub_df = profile_df[(profile_df['Activity'] == act) & (profile_df['Sub_Activity'] != "")]
                    
                    if not sub_df.empty:
                        for _, row in sub_df.iterrows():
                            sub_name = row['Sub_Activity']
                            curr_dur = int(row['Duration_Mins'])
                            sheet_row = row['Sheet_Row']
                            
                            st.markdown("<div class='sub-act-row'>", unsafe_allow_html=True)
                            col_sn, col_in, col_btn = st.columns([5, 3, 2])
                            
                            with col_sn:
                                st.markdown(f"<div style='padding-top: 8px;'>📄 <b>{sub_name}</b> <span style='color: #6c757d; font-size: 0.9em; margin-left: 8px;'>({format_mins(curr_dur)})</span></div>", unsafe_allow_html=True)
                            with col_in:
                                # Track unique keys for the inputs to prevent widget rendering conflicts
                                new_dur = st.number_input("Mins", value=curr_dur, min_value=1, step=5, key=f"edit_dur_{sheet_row}", label_visibility="collapsed")
                            with col_btn:
                                if st.button("💾 Save", key=f"save_btn_{sheet_row}", use_container_width=True):
                                    diff = new_dur - curr_dur
                                    if diff > 0 and (total_used + diff > 1440):
                                        st.error(f"❌ Cannot increase by {diff} mins. Only {format_mins(max(0, remaining))} left!")
                                    elif diff != 0:
                                        with st.spinner("Updating..."):
                                            sheet = get_main_spreadsheet().worksheet("activity_master")
                                            # Column D contains the durations in the new schema
                                            sheet.update_acell(f"D{sheet_row}", new_dur)
                                            get_activity_master.clear()
                                        st.success("✅ Saved!")
                                        time.sleep(1)
                                        st.rerun()
                                    else:
                                        st.warning("No changes made.")
                            st.markdown("</div>", unsafe_allow_html=True)
                    else:
                        st.markdown("*No sub-activities allocated yet.*")
        else:
            st.markdown(f"*No activities configured for {selected_day_type} yet.*")

    # ==========================================
    # TAB 2: ROUTINE SUMMARY
    # ==========================================
    with tab_summary:
        
        summary_df = df.copy()
        
        # Calculate raw minutes from the Duration column (HH:MM)
        def parse_dur_to_mins(d_str):
            try:
                parts = str(d_str).split(":")
                return int(parts[0]) * 60 + int(parts[1])
            except:
                return 0
                
        summary_df['Dur_Mins'] = summary_df['Duration'].apply(parse_dur_to_mins)
        
        # Clean 'Day' format just in case
        summary_df['Day'] = summary_df['Day'].str.title()

        # UI for selecting the Breakdown View
        col_view1, col_view2 = st.columns([1, 1])
        with col_view1:
            view_mode = st.radio("Select Summary View Mode", ["Weekly Routine Breakdown", "Daily (24h) Breakdown"], horizontal=True)

        if view_mode == "Daily (24h) Breakdown":
            available_days_summary = list(summary_df['Day'].unique())
            with col_view2:
                selected_summary_day = st.selectbox("Select Specific Day", available_days_summary)
            
            filtered_summary_df = summary_df[summary_df['Day'] == selected_summary_day].copy()
            st.markdown(f"### 📊 Daily Breakdown: {selected_summary_day}")
            st.info("💡 **Note:** If a single time slot has multiple sub-activities, the full duration of that slot is attributed to each sub-activity listed.")
            
        else:
            filtered_summary_df = summary_df.copy()
            
            # --- WEEKLY MATRIX TABLE ---
            st.markdown("### 🗓️ Weekly Activity Matrix")
            
            # Create a pivot table mapping Activity vs Day
            pivot_df = summary_df.pivot_table(
                index='Activity', 
                columns='Day', 
                values='Dur_Mins', 
                aggfunc='sum', 
                fill_value=0
            )
            
            # Reorder and rename columns to MON - SUN
            day_mapping = {
                "Monday": "MON", "Tuesday": "TUE", "Wednesday": "WED", 
                "Thursday": "THU", "Friday": "FRI", "Saturday": "SAT", "Sunday": "SUN"
            }
            ordered_days = [d for d in day_mapping.keys() if d in pivot_df.columns]
            
            pivot_df = pivot_df[ordered_days]
            pivot_df.rename(columns=day_mapping, inplace=True)
            
            # Format the cells
            for col in pivot_df.columns:
                pivot_df[col] = pivot_df[col].apply(format_matrix_mins)
                
            st.dataframe(pivot_df, use_container_width=True)
            
            st.markdown("---")
            st.markdown("### 📊 Expandable Breakdown")
            st.info("💡 **Note:** If a single time slot has multiple sub-activities, the full duration of that slot is attributed to each sub-activity listed.")
        
        # --- EXPANDABLE ACTIVITY LIST ---
        # Group by Top-Level Activity using the filtered dataframe
        activity_grouped = filtered_summary_df.groupby("Activity")['Dur_Mins'].sum().sort_values(ascending=False)
        
        for act, act_mins in activity_grouped.items():
            act_name = str(act).strip() if str(act).strip() else "UNNAMED ACTIVITY"
            
            with st.expander(f"📁 **{act_name}** |  Total Time: **{format_mins(act_mins)}**"):
                act_df = filtered_summary_df[filtered_summary_df["Activity"] == act].copy()
                
                # Explode Sub-Activities so each comma-separated item gets its own grouping
                act_df['Sub_List'] = act_df['Sub_Activities'].apply(
                    lambda x: [i.strip() for i in str(x).split(',') if i.strip()] if str(x).strip() else ["No Sub-Activity"]
                )
                exploded_df = act_df.explode('Sub_List')
                
                sub_grouped = exploded_df.groupby("Sub_List")['Dur_Mins'].sum().sort_values(ascending=False)
                
                for sub_act, sub_mins in sub_grouped.items():
                    with st.expander(f"📄 {sub_act}  |  Time: {format_mins(sub_mins)}"):
                        slots_df = exploded_df[exploded_df["Sub_List"] == sub_act].copy()
                        
                        # Sort slots logically by Day and Time
                        day_order = {d: i for i, d in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])}
                        slots_df['Day_Idx'] = slots_df['Day'].str.title().map(day_order).fillna(99)
                        slots_df['Start_Sort'] = slots_df['Start_Time'].apply(time_to_mins)
                        slots_df = slots_df.sort_values(['Day_Idx', 'Start_Sort'])
                        
                        display_df = slots_df[["Day", "Start_Time", "End_Time", "Duration"]]
                        st.dataframe(display_df, hide_index=True, use_container_width=True)

        # --- GRAND TOTAL FOOTER ---
        total_tracked_mins = filtered_summary_df['Dur_Mins'].sum()
        context_label = "Total Tracked Time for " + (f"{selected_summary_day}" if view_mode == "Daily (24h) Breakdown" else "the Week")
        
        st.markdown(
            f"<div class='total-time-footer'>⏱️ {context_label}: {format_mins(total_tracked_mins)}</div>", 
            unsafe_allow_html=True
        )

    # ==========================================
    # TAB 1: ROUTINE EDITOR
    # ==========================================
    with tab_editor:
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
            display_day = "Monday" 
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
            is_target = s['Start_Time'] == sel_start
            return ['background-color: #fff59d; color: black; font-weight: bold;' if is_target else '' for _ in s]

        st.dataframe(target_df.style.apply(highlight_target_row, axis=1), use_container_width=True, hide_index=True)

        st.markdown("---")

        # --- 5. SMART EDITOR FORM ---
        sel_row = target_df[target_df['Start_Time'] == sel_start].iloc[0]
        
        all_chks = sorted(list(set([x.strip() for items in df['check_list'].dropna() for x in str(items).split(',') if x.strip()])))
        all_apps_db = sorted(list(set([x.strip() for items in df['App'].dropna() for x in str(items).split(',') if x.strip()])))

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
        
        curr_act = str(sel_row['Activity']).strip()
        curr_sub_list = [x.strip() for x in str(sel_row['Sub_Activities']).split(',') if x.strip()]
        curr_chk_list = [x.strip() for x in str(sel_row['check_list']).split(',') if x.strip()]
        curr_app_list = [x.strip() for x in str(sel_row['App']).split(',') if x.strip()]

        opts_sub = sorted(list(set(all_subs + curr_sub_list)))
        opts_chk = sorted(list(set(all_chks + curr_chk_list)))
        
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
            
            st.markdown("**⏰ Edit Time Slot (Adjacent slots will auto-adjust!)**")
            col_t1, col_t2 = st.columns(2)
            with col_t1: new_start_txt = st.text_input("Start Time (H:MM)", value=sel_row['Start_Time'])
            with col_t2: new_end_txt = st.text_input("End Time (H:MM)", value=sel_row['End_Time'])
            
            st.markdown("<hr style='margin: 10px 0px;'>", unsafe_allow_html=True)

            st.markdown("**1️⃣ Activity Category**")
            col_a1, col_a2 = st.columns(2)
            with col_a1: new_act_sel = st.selectbox("Select Existing", all_acts, index=all_acts.index(curr_act) if curr_act in all_acts else 0)
            with col_a2: new_act_txt = st.text_input("Or Create New Activity (Overrides selection)", placeholder="Type new activity...")

            st.markdown("<hr style='margin: 10px 0px;'>", unsafe_allow_html=True)

            st.markdown("**2️⃣ Sub-Activities**")
            new_subs_sel = st.multiselect("Select Existing (Multiple allowed)", opts_sub, default=curr_sub_list)
            new_subs_txt = st.text_input("Add New (Comma separated)", placeholder="e.g., Check emails, Plan week", key="new_sub")

            st.markdown("<hr style='margin: 10px 0px;'>", unsafe_allow_html=True)

            st.markdown("**3️⃣ Tasks & Reminders (Checklist)**")
            new_chks_sel = st.multiselect("Select Existing", opts_chk, default=curr_chk_list)
            new_chks_txt = st.text_input("Add New (Comma separated)", placeholder="e.g., Pay bills, Buy milk", key="new_chk")

            st.markdown("<hr style='margin: 10px 0px;'>", unsafe_allow_html=True)

            st.markdown("**4️⃣ Applications Launchpad**")
            new_apps_sel = st.multiselect("Select Apps (Grouped by category)", opts_app, default=curr_app_list, format_func=format_app_display)
            new_apps_txt = st.text_input("Add Custom App (Comma separated)", placeholder="e.g., Extra Tool 1", key="new_app")

            st.markdown("</div><br>", unsafe_allow_html=True)

            if st.form_submit_button("💾 Save Changes to Routine", type="primary", use_container_width=True):
                final_act = new_act_txt.strip().upper() if new_act_txt.strip() else new_act_sel
                final_subs = ",".join(filter(None, [x for x in new_subs_sel] + [x.strip() for x in new_subs_txt.split(',')]))
                final_chks = ",".join(filter(None, [x for x in new_chks_sel] + [x.strip() for x in new_chks_txt.split(',')]))
                final_apps = ",".join(filter(None, [x for x in new_apps_sel] + [x.strip() for x in new_apps_txt.split(',')]))

                df['Start_Mins'] = df['Start_Time'].apply(time_to_mins)
                df['End_Mins'] = df['End_Time'].apply(time_to_mins)
                df['End_Mins'] = df.apply(lambda r: r['End_Mins'] + 1440 if r['End_Mins'] <= r['Start_Mins'] and r['End_Mins'] < 120 else r['End_Mins'], axis=1)
                
                L_start_new = time_to_mins(new_start_txt.strip())
                L_end_new = time_to_mins(new_end_txt.strip())
                if L_end_new <= L_start_new and L_end_new < 120: L_end_new += 1440
                
                for day in target_days:
                    row_mask = (df['Day'].str.title() == day) & (df['Start_Time'] == sel_start)
                    if not row_mask.any(): continue
                    idx_to_edit = df[row_mask].index[0]
                    
                    df.loc[idx_to_edit, 'Start_Time'] = new_start_txt.strip()
                    df.loc[idx_to_edit, 'End_Time'] = new_end_txt.strip()
                    df.loc[idx_to_edit, 'Activity'] = final_act
                    df.loc[idx_to_edit, 'Sub_Activities'] = final_subs
                    df.loc[idx_to_edit, 'check_list'] = final_chks
                    df.loc[idx_to_edit, 'App'] = final_apps
                    df.loc[idx_to_edit, 'Start_Mins'] = L_start_new
                    df.loc[idx_to_edit, 'End_Mins'] = L_end_new
                    
                    day_idx = df[df['Day'].str.title() == day].index
                    for idx in day_idx:
                        if idx == idx_to_edit: continue
                        
                        T_start = df.loc[idx, 'Start_Mins']
                        T_end = df.loc[idx, 'End_Mins']
                        
                        if T_start < L_start_new and T_end > L_start_new:
                            df.loc[idx, 'End_Mins'] = L_start_new
                            df.loc[idx, 'End_Time'] = mins_to_time(L_start_new)
                        elif T_start >= L_start_new and T_start < L_end_new:
                            df.loc[idx, 'Start_Mins'] = L_end_new
                            df.loc[idx, 'Start_Time'] = mins_to_time(L_end_new)
                            
                df['Dur_Mins'] = df['End_Mins'] - df['Start_Mins']
                df = df[df['Dur_Mins'] > 0].copy()
                df['Duration'] = df['Dur_Mins'].apply(lambda x: f"{int(x)//60:02d}:{int(x)%60:02d}")
                df = sort_routine_df(df)
                df = df[["Day", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "App"]]
                
                with st.spinner("Healing Overlaps and Saving to Google Sheets..."):
                    routine_sheet = get_sheet("routine_master")
                    routine_sheet.clear()
                    routine_sheet.update(values=[df.columns.values.tolist()] + df.values.tolist(), range_name="A1")
                    get_routine_data.clear()
                    
                st.success(f"✅ Successfully updated and seamlessly aligned schedule for {sel_day_opt}!")
                time.sleep(1.5)
                st.rerun()

        # --- 6. ADD NEW SLOT FORM ---
        st.markdown("---")
        st.markdown("#### ➕ 4. Add a New Time Slot")
        with st.expander("Click to Create a New Block in the Schedule"):
            with st.form("add_new_slot_form"):
                st.markdown("<div style='background-color: #e3f2fd; padding: 15px; border-radius: 8px;'>", unsafe_allow_html=True)
                
                st.markdown("**📅 Target Day(s)**")
                add_day_opt = st.selectbox("Add to Day", day_options, key="add_day")
                
                st.markdown("**⏰ Define Time Block**")
                col_at1, col_at2 = st.columns(2)
                with col_at1: add_start = st.text_input("Start Time (H:MM)", value="12:00", key="add_start")
                with col_at2: add_end = st.text_input("End Time (H:MM)", value="12:30", key="add_end")
                
                st.markdown("<hr style='margin: 10px 0px;'>", unsafe_allow_html=True)
                
                st.markdown("**1️⃣ Activity Category**")
                col_aa1, col_aa2 = st.columns(2)
                with col_aa1: add_act_sel = st.selectbox("Select Existing", all_acts, key="add_act_sel")
                with col_aa2: add_act_txt = st.text_input("Or New Activity", key="add_act_txt")
                
                st.markdown("<hr style='margin: 10px 0px;'>", unsafe_allow_html=True)
                
                st.markdown("**2️⃣ Sub-Activities & Checklists**")
                add_subs = st.multiselect("Sub-Activities", opts_sub, key="add_subs")
                add_chks = st.multiselect("Checklist", opts_chk, key="add_chks")
                
                st.markdown("<hr style='margin: 10px 0px;'>", unsafe_allow_html=True)
                
                st.markdown("**3️⃣ Connected Apps**")
                add_apps = st.multiselect("Apps", opts_app, format_func=format_app_display, key="add_apps")
                
                st.markdown("</div><br>", unsafe_allow_html=True)
                
                if st.form_submit_button("➕ Insert New Slot & Auto-Adjust", type="primary", use_container_width=True):
                    target_add_days = weekdays if add_day_opt == "Monday to Friday" else [add_day_opt]
                    
                    final_add_act = add_act_txt.strip().upper() if add_act_txt.strip() else add_act_sel
                    final_add_subs = ",".join(filter(None, [x for x in add_subs]))
                    final_add_chks = ",".join(filter(None, [x for x in add_chks]))
                    final_add_apps = ",".join(filter(None, [x for x in add_apps]))
                    
                    df['Start_Mins'] = df['Start_Time'].apply(time_to_mins)
                    df['End_Mins'] = df['End_Time'].apply(time_to_mins)
                    df['End_Mins'] = df.apply(lambda r: r['End_Mins'] + 1440 if r['End_Mins'] <= r['Start_Mins'] and r['End_Mins'] < 120 else r['End_Mins'], axis=1)
                    
                    L_start_new = time_to_mins(add_start.strip())
                    L_end_new = time_to_mins(add_end.strip())
                    if L_end_new <= L_start_new and L_end_new < 120: L_end_new += 1440
                    
                    new_rows = []
                    
                    for day in target_add_days:
                        day_idx = df[df['Day'].str.title() == day].index
                        for idx in day_idx:
                            T_start = df.loc[idx, 'Start_Mins']
                            T_end = df.loc[idx, 'End_Mins']
                            
                            if T_start < L_start_new and T_end > L_start_new:
                                df.loc[idx, 'End_Mins'] = L_start_new
                                df.loc[idx, 'End_Time'] = mins_to_time(L_start_new)
                            elif T_start >= L_start_new and T_start < L_end_new:
                                df.loc[idx, 'Start_Mins'] = L_end_new
                                df.loc[idx, 'Start_Time'] = mins_to_time(L_end_new)
                                
                        new_rows.append({
                            "Day": day,
                            "Start_Time": add_start.strip(),
                            "End_Time": add_end.strip(),
                            "Start_Mins": L_start_new,
                            "End_Mins": L_end_new,
                            "Activity": final_add_act,
                            "Sub_Activities": final_add_subs,
                            "check_list": final_add_chks,
                            "App": final_add_apps
                        })
                    
                    if new_rows:
                        new_df = pd.DataFrame(new_rows)
                        df = pd.concat([df, new_df], ignore_index=True)
                    
                    df['Dur_Mins'] = df['End_Mins'] - df['Start_Mins']
                    df = df[df['Dur_Mins'] > 0].copy()
                    df['Duration'] = df['Dur_Mins'].apply(lambda x: f"{int(x)//60:02d}:{int(x)%60:02d}")
                    df = sort_routine_df(df)
                    df = df[["Day", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "App"]]
                    
                    with st.spinner("Inserting Time Block and Healing Sequence..."):
                        routine_sheet = get_sheet("routine_master")
                        routine_sheet.clear()
                        routine_sheet.update(values=[df.columns.values.tolist()] + df.values.tolist(), range_name="A1")
                        get_routine_data.clear()
                    st.success(f"✅ Successfully inserted new block and adjusted schedule for {add_day_opt}!")
                    time.sleep(1.5)
                    st.rerun()

except Exception as e:
    st.error(f"System Error: {e}")
