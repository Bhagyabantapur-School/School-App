import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import time

# MUST be the first Streamlit command
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
    .local-warning {
        background-color: #fff3cd;
        border-left: 5px solid #ffc107;
        padding: 15px;
        border-radius: 5px;
        margin-bottom: 15px;
    }
    </style>
""", unsafe_allow_html=True)

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
        
        day_df['Locked_Sort'] = day_df.get('Locked', '').apply(lambda x: 0 if str(x).title() == 'Yes' else 1)
        day_df = day_df.sort_values(['Start_Mins', 'Locked_Sort', 'Dur_Mins']).reset_index(drop=True)
        
        for i in range(len(day_df) - 1):
            for j in range(i+1, len(day_df)):
                start_A = day_df.loc[i, 'Start_Mins']
                end_A = day_df.loc[i, 'End_Mins']
                start_B = day_df.loc[j, 'Start_Mins']
                locked_B = str(day_df.loc[j].get('Locked', '')).title() == 'Yes'
                
                if start_B < end_A:
                    if start_A == start_B:
                        if not locked_B:
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
        return fixed_df[["Day", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "App", "Locked"]]
    return df

@st.cache_data(ttl=300) 
def get_routine_data():
    data = get_sheet("routine_master").get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 13: df[df.shape[1]] = ""
    df = df.iloc[:, :13]
    df.columns = ["Day", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "App", "Role", "Urgent", "Important", "Energy_Level", "Locked"]
    df["Locked"] = df["Locked"].astype(str).str.strip().str.title()
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
    
    if "Day_Type" not in data[0]:
        df = pd.DataFrame(data[1:], columns=data[0]) if len(data) > 1 else pd.DataFrame(columns=data[0])
        df.insert(0, "Day_Type", "WEEK DAYS")
        sheet.clear()
        sheet.update(values=[df.columns.values.tolist()] + df.values.tolist(), range_name="A1")
        data = sheet.get_all_values()

    if len(data) <= 1:
        return pd.DataFrame(columns=["Day_Type", "Activity", "Sub_Activity", "Duration_Mins", "Sheet_Row"])
    
    df = pd.DataFrame(data[1:], columns=data[0])
    df['Sheet_Row'] = df.index + 2 
    df['Duration_Mins'] = pd.to_numeric(df['Duration_Mins'], errors='coerce').fillna(0)
    return df

def format_mins(total_mins):
    h = int(total_mins) // 60
    m = int(total_mins) % 60
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"

def format_matrix_mins(total_mins):
    if pd.isna(total_mins) or total_mins == 0:
        return "-"
    return format_mins(total_mins)

def parse_dur_to_mins(d_str):
    try:
        parts = str(d_str).split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except: return 0

def shift_routine_slot(df, target_days, curr_i, direction):
    df['Start_Mins'] = df['Start_Time'].apply(time_to_mins)
    df['End_Mins'] = df['End_Time'].apply(time_to_mins)
    df['End_Mins'] = df.apply(lambda r: r['End_Mins'] + 1440 if r['End_Mins'] <= r['Start_Mins'] and r['End_Mins'] < 120 else r['End_Mins'], axis=1)
    df['Dur_Mins'] = df['End_Mins'] - df['Start_Mins']
    
    new_start_time = None
    
    for day in target_days:
        day_mask = df['Day'].str.title() == day
        day_idx = df[day_mask].sort_values('Start_Mins').index
        
        target_i = None
        if direction == 'up':
            for k in range(curr_i - 1, -1, -1):
                if str(df.loc[day_idx[k], 'Locked']).title() != 'Yes':
                    target_i = k
                    break
        elif direction == 'down':
            for k in range(curr_i + 1, len(day_idx)):
                if str(df.loc[day_idx[k], 'Locked']).title() != 'Yes':
                    target_i = k
                    break
        
        if target_i is not None:
            idx_curr = day_idx[curr_i]
            idx_target = day_idx[target_i]
            
            start_curr = df.loc[idx_curr, 'Start_Mins']
            start_target = df.loc[idx_target, 'Start_Mins']
            
            df.loc[idx_curr, 'Start_Mins'] = start_target
            df.loc[idx_target, 'Start_Mins'] = start_curr
            
            df.loc[idx_curr, 'End_Mins'] = start_target + df.loc[idx_curr, 'Dur_Mins']
            df.loc[idx_target, 'End_Mins'] = start_curr + df.loc[idx_target, 'Dur_Mins']
            
            df.loc[idx_curr, 'Start_Time'] = mins_to_time(df.loc[idx_curr, 'Start_Mins'])
            df.loc[idx_curr, 'End_Time'] = mins_to_time(df.loc[idx_curr, 'End_Mins'])
            df.loc[idx_target, 'Start_Time'] = mins_to_time(df.loc[idx_target, 'Start_Mins'])
            df.loc[idx_target, 'End_Time'] = mins_to_time(df.loc[idx_target, 'End_Mins'])
            
            if day == target_days[0]:
                new_start_time = df.loc[idx_curr, 'Start_Time']
            
    df = df[df['Dur_Mins'] > 0].copy()
    df['Duration'] = df['Dur_Mins'].apply(lambda x: f"{int(x)//60:02d}:{int(x)%60:02d}")
    df = sort_routine_df(df)
    df = auto_adjust_schedule(df)
    df = df[["Day", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "App", "Locked"]]
    
    st.session_state.routine_df = df
    st.session_state.unsaved_sort = True
    return new_start_time

# ==========================================
# Top Action Bar
# ==========================================
col_nav1, col_nav2, col_nav3 = st.columns([2, 2, 8])
with col_nav1:
    if st.button("⬅️ Back to Hub", type="secondary", use_container_width=True):
        st.switch_page("routine_app.py") 
with col_nav2:
    if st.button("🔄 Sync Data", type="primary", use_container_width=True):
        get_routine_data.clear()
        get_activity_master.clear()
        if 'routine_df' in st.session_state:
            del st.session_state.routine_df
        if 'unsaved_sort' in st.session_state:
            st.session_state.unsaved_sort = False
        if 'active_slot_start' in st.session_state:
            del st.session_state.active_slot_start
        st.toast("✅ Cache cleared! Fetching latest data from Google Sheets...")
        time.sleep(1)
        st.rerun()
st.write("---") 

st.markdown("<div class='edit-header'>⚙️ Smart Schedule Manager</div>", unsafe_allow_html=True)

# ==========================================
# Main Logic
# ==========================================
try:
    if 'routine_df' not in st.session_state:
        st.session_state.routine_df = get_routine_data()
        
    df = st.session_state.routine_df
    act_master_df = get_activity_master()

    all_acts_db = df['Activity'].dropna().tolist()
    all_acts_builder = act_master_df['Activity'].dropna().tolist()
    all_acts = sorted(list(set([str(x).strip().upper() for x in all_acts_db + all_acts_builder if str(x).strip()])))
    
    all_subs_db = [x.strip() for items in df['Sub_Activities'].dropna() for x in str(items).split(',') if x.strip()]
    all_subs_builder = act_master_df['Sub_Activity'].dropna().tolist()
    all_subs = sorted(list(set([str(x).strip() for x in all_subs_db + all_subs_builder if str(x).strip()])))

    tab_editor, tab_summary, tab_builder = st.tabs(["⚙️ Routine Editor", "📊 Routine Summary", "🏗️ Activity Builder"])

    # ==========================================
    # TAB 3: ACTIVITY BUILDER
    # ==========================================
    with tab_builder:
        st.markdown("### 🏗️ Activity Database & Time Pool")
        
        st.markdown("<div class='profile-header'>📅 Select Schedule Profile</div>", unsafe_allow_html=True)
        profile_options = ["WEEK DAYS", "SATURDAY/HALF WORKING DAY", "SUNDAY", "HOLIDAY"]
        selected_day_type = st.radio("Profile Config", profile_options, horizontal=True, label_visibility="collapsed")
        
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
                sub_dur = st.number_input("Duration (Minutes)", min_value=0, max_value=1440, value=30, step=5)
                
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
            unique_acts_ordered = profile_df['Activity'].dropna().unique()
            
            for act in unique_acts_ordered:
                if not act: continue
                act_mins = profile_df[profile_df['Activity'] == act]['Duration_Mins'].sum()
                
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
                                new_dur = st.number_input("Mins", value=curr_dur, min_value=0, step=5, key=f"edit_dur_{sheet_row}", label_visibility="collapsed")
                            with col_btn:
                                if st.button("💾 Save", key=f"save_btn_{sheet_row}", use_container_width=True):
                                    diff = new_dur - curr_dur
                                    if diff > 0 and (total_used + diff > 1440):
                                        st.error(f"❌ Cannot increase by {diff} mins. Only {format_mins(max(0, remaining))} left!")
                                    elif diff != 0:
                                        with st.spinner("Updating..."):
                                            sheet = get_main_spreadsheet().worksheet("activity_master")
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
                
        summary_df['Dur_Mins'] = summary_df['Duration'].apply(parse_dur_to_mins)
        summary_df['Day'] = summary_df['Day'].str.title()

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
            st.markdown("### 🗓️ Weekly Activity Matrix")
            
            pivot_df = summary_df.pivot_table(
                index='Activity', 
                columns='Day', 
                values='Dur_Mins', 
                aggfunc='sum', 
                fill_value=0
            )
            
            day_mapping = {
                "Monday": "MON", "Tuesday": "TUE", "Wednesday": "WED", 
                "Thursday": "THU", "Friday": "FRI", "Saturday": "SAT", "Sunday": "SUN"
            }
            ordered_days = [d for d in day_mapping.keys() if d in pivot_df.columns]
            
            pivot_df = pivot_df[ordered_days]
            pivot_df.rename(columns=day_mapping, inplace=True)
            
            for col in pivot_df.columns:
                pivot_df[col] = pivot_df[col].apply(format_matrix_mins)
                
            st.dataframe(pivot_df, use_container_width=True)
            
            st.markdown("---")
            st.markdown("### 📊 Expandable Breakdown")
            st.info("💡 **Note:** If a single time slot has multiple sub-activities, the full duration of that slot is attributed to each sub-activity listed.")
        
        activity_grouped = filtered_summary_df.groupby("Activity")['Dur_Mins'].sum().sort_values(ascending=False)
        
        for act, act_mins in activity_grouped.items():
            act_name = str(act).strip() if str(act).strip() else "UNNAMED ACTIVITY"
            
            with st.expander(f"📁 **{act_name}** |  Total Time: **{format_mins(act_mins)}**"):
                act_df = filtered_summary_df[filtered_summary_df["Activity"] == act].copy()
                act_df['Sub_List'] = act_df['Sub_Activities'].apply(
                    lambda x: [i.strip() for i in str(x).split(',') if i.strip()] if str(x).strip() else ["No Sub-Activity"]
                )
                exploded_df = act_df.explode('Sub_List')
                sub_grouped = exploded_df.groupby("Sub_List")['Dur_Mins'].sum().sort_values(ascending=False)
                
                for sub_act, sub_mins in sub_grouped.items():
                    with st.expander(f"📄 {sub_act}  |  Time: {format_mins(sub_mins)}"):
                        slots_df = exploded_df[exploded_df["Sub_List"] == sub_act].copy()
                        day_order = {d: i for i, d in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])}
                        slots_df['Day_Idx'] = slots_df['Day'].str.title().map(day_order).fillna(99)
                        slots_df['Start_Sort'] = slots_df['Start_Time'].apply(time_to_mins)
                        slots_df = slots_df.sort_values(['Day_Idx', 'Start_Sort'])
                        
                        display_df = slots_df[["Day", "Start_Time", "End_Time", "Duration"]]
                        st.dataframe(display_df, hide_index=True, use_container_width=True)

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
        # --- 0. SCHEDULE HEALTH AUDIT ---
        st.markdown("#### 🏥 Schedule Health Audit")
        
        mismatches = []
        mismatched_combinations_per_day = {}
        
        exp_dicts = {}
        for dtype in ["WEEK DAYS", "SATURDAY/HALF WORKING DAY", "SUNDAY", "HOLIDAY"]:
            expected_df = act_master_df[(act_master_df['Day_Type'] == dtype) & (act_master_df['Sub_Activity'] != "")]
            exp_dicts[dtype] = expected_df.groupby(expected_df['Sub_Activity'].str.strip())['Duration_Mins'].sum().to_dict()
        
        audit_df = df.copy()
        audit_df['Dur_Mins'] = audit_df['Duration'].apply(parse_dur_to_mins)
        
        aggregated_live = audit_df.groupby(['Day', 'Sub_Activities'])['Dur_Mins'].sum().reset_index()
        
        for _, row in aggregated_live.iterrows():
            day_str = str(row['Day']).title()
            subs_str = str(row['Sub_Activities']).strip()
            live_mins = row['Dur_Mins']
            
            if not subs_str:
                continue
                
            day_type = "WEEK DAYS"
            if day_str == "Saturday": day_type = "SATURDAY/HALF WORKING DAY"
            elif day_str == "Sunday": day_type = "SUNDAY"
            elif day_str == "Holiday": day_type = "HOLIDAY"
            
            exp_dict = exp_dicts.get(day_type, {})
            
            subs_list = [x.strip() for x in subs_str.split(',') if x.strip()]
            expected_mins = sum(exp_dict.get(sub, 0) for sub in subs_list)
            
            if live_mins != expected_mins:
                if day_str not in mismatched_combinations_per_day:
                    mismatched_combinations_per_day[day_str] = []
                mismatched_combinations_per_day[day_str].append(subs_str)
                
                task_names = []
                for sub in subs_list:
                    builder_match = act_master_df[(act_master_df['Day_Type'] == day_type) & (act_master_df['Sub_Activity'].str.strip() == sub)]
                    if not builder_match.empty:
                        task_names.append(builder_match['Activity'].iloc[0])
                task_str = ", ".join(list(set(task_names))) if task_names else "Unknown"
                
                mismatches.append({
                    "Day": day_str,
                    "Task": task_str,
                    "Sub-Task(s)": subs_str,
                    "Live Mins": live_mins,
                    "Expected Mins": expected_mins,
                    "Difference": live_mins - expected_mins
                })
                    
        if not mismatches:
            st.success("✅ **Everything is OK!** All scheduled time slots perfectly match your configured Activity Builder durations.")
        else:
            st.warning(f"⚠️ **Mismatch Warning!** Found {len(mismatches)} sub-activity combinations where the total daily live schedule duration does not match your builder configuration.")
            with st.expander("🔍 Click to view mismatch details"):
                st.dataframe(pd.DataFrame(mismatches), use_container_width=True, hide_index=True)
        
        st.markdown("---")

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
        target_df['Start_Mins'] = target_df['Start_Time'].apply(time_to_mins)
        target_df['End_Mins'] = target_df['End_Time'].apply(time_to_mins)
        target_df['End_Mins'] = target_df.apply(lambda r: r['End_Mins'] + 1440 if r['End_Mins'] <= r['Start_Mins'] and r['End_Mins'] < 120 else r['End_Mins'], axis=1)
        target_df = target_df.sort_values('Start_Mins').reset_index(drop=True)

        # --- 3. TIME SLOT SELECTION WITH LOCAL SORT ENGINE ---
        st.markdown("#### ⏱️ 2. Select Time Slot to Manage or Move")
        
        day_mismatches = mismatched_combinations_per_day.get(display_day, [])
        slot_opts = []
        for _, row in target_df.iterrows():
            base_str = f"{row['Start_Time']} to {row['End_Time']}  |  {row['Activity']}"
            row_subs_str = str(row['Sub_Activities']).strip()
            
            if row_subs_str:
                base_str += f"  |  {row_subs_str}"
            if str(row.get('Locked', '')).title() == 'Yes':
                base_str += " 🔒 [FIXED]"
            if row_subs_str in day_mismatches:
                base_str += " ⚠️ [MISMATCH]"
                
            slot_opts.append(base_str)
        
        if 'active_slot_start' not in st.session_state:
            st.session_state.active_slot_start = None
            
        selected_index = 0
        if st.session_state.active_slot_start:
            for i, opt in enumerate(slot_opts):
                if opt.startswith(st.session_state.active_slot_start + " to"):
                    selected_index = i
                    break
        
        col_sel, col_up, col_dn = st.columns([8, 1, 1])
        with col_sel:
            selected_slot = st.selectbox("Choose the specific slot you want to update:", slot_opts, index=selected_index, label_visibility="collapsed")
        
        sel_start = selected_slot.split(" to ")[0].strip()
        st.session_state.active_slot_start = sel_start
        
        curr_i = target_df.index[target_df['Start_Time'] == sel_start].tolist()[0]
        is_curr_locked = str(target_df.loc[curr_i, 'Locked']).title() == 'Yes'
        
        can_move_up = False
        for k in range(curr_i - 1, -1, -1):
            if str(target_df.loc[k, 'Locked']).title() != 'Yes':
                can_move_up = True
                break
                
        can_move_dn = False
        for k in range(curr_i + 1, len(target_df)):
            if str(target_df.loc[k, 'Locked']).title() != 'Yes':
                can_move_dn = True
                break
        
        with col_up:
            if st.button("⬆️", key="move_up", disabled=(is_curr_locked or not can_move_up), use_container_width=True, help="Move Task Up (Skips Fixed Slots)"):
                new_start = shift_routine_slot(df.copy(), target_days, curr_i, 'up')
                if new_start: st.session_state.active_slot_start = new_start
                st.rerun()
        with col_dn:
            if st.button("⬇️", key="move_dn", disabled=(is_curr_locked or not can_move_dn), use_container_width=True, help="Move Task Down (Skips Fixed Slots)"):
                new_start = shift_routine_slot(df.copy(), target_days, curr_i, 'down')
                if new_start: st.session_state.active_slot_start = new_start
                st.rerun()

        if st.session_state.get('unsaved_sort', False):
            st.markdown("<div class='local-warning'>⚠️ <b>Sequence modified locally!</b> Click save to update Google Sheets to avoid losing changes.</div>", unsafe_allow_html=True)
            if st.button("💾 Push Reordered Schedule to Cloud", type="primary", use_container_width=True):
                with st.spinner("Pushing new sequence to the cloud..."):
                    routine_sheet = get_sheet("routine_master")
                    routine_sheet.clear()
                    routine_sheet.update(values=[df.columns.values.tolist()] + df.values.tolist(), range_name="A1")
                    get_routine_data.clear()
                    st.session_state.unsaved_sort = False
                st.success("✅ Sequence successfully saved to Google Sheets!")
                time.sleep(1.5)
                st.rerun()

        # --- 4. HIGHLIGHTED SCHEDULE DISPLAY ---
        st.markdown(f"**Full Schedule for {display_day}** *(Editing row highlighted in yellow, gaps in red)*")
        
        display_rows = []
        for i in range(len(target_df)):
            row_dict = target_df.iloc[i].to_dict()
            row_dict['Is_Gap'] = False
            display_rows.append(row_dict)
            if i < len(target_df) - 1:
                curr_end = target_df.iloc[i]['End_Mins']
                next_start = target_df.iloc[i+1]['Start_Mins']
                if curr_end < next_start:
                    gap_dur = next_start - curr_end
                    gap_row = {col: "" for col in target_df.columns}
                    gap_row.update({
                        "Day": row_dict['Day'],
                        "Start_Time": mins_to_time(curr_end),
                        "End_Time": mins_to_time(next_start),
                        "Duration": f"{int(gap_dur)//60:02d}:{int(gap_dur)%60:02d}",
                        "Activity": "⚠️ TIME GAP",
                        "Sub_Activities": "-",
                        "check_list": "-",
                        "App": "-",
                        "Locked": "-",
                        "Is_Gap": True
                    })
                    display_rows.append(gap_row)
        display_df = pd.DataFrame(display_rows)
        
        def highlight_target_row(s):
            if s.get('Is_Gap', False):
                return ['background-color: #ffcccc; color: #b30000; font-weight: bold;' for _ in s]
            is_target = s['Start_Time'] == sel_start and not s.get('Is_Gap', False)
            return ['background-color: #fff59d; color: black; font-weight: bold;' if is_target else '' for _ in s]

        st.dataframe(display_df.drop(columns=['Start_Mins', 'End_Mins', 'Is_Gap'], errors='ignore').style.apply(highlight_target_row, axis=1), use_container_width=True, hide_index=True)

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
        curr_locked = str(sel_row.get('Locked', '')).title() == 'Yes'

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
            
            new_locked = st.checkbox("🔒 Lock this Time Slot (Fixed time, cannot be moved)", value=curr_locked)
            
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

            col_sub1, col_sub2 = st.columns([7, 3])
            with col_sub1:
                save_btn = st.form_submit_button("💾 Save Changes to Routine", type="primary", use_container_width=True)
            with col_sub2:
                del_btn = st.form_submit_button("🗑️ Delete Slot", type="secondary", use_container_width=True)

            if save_btn:
                final_act = new_act_txt.strip().upper() if new_act_txt.strip() else new_act_sel
                final_subs = ",".join(filter(None, [x for x in new_subs_sel] + [x.strip() for x in new_subs_txt.split(',')]))
                final_chks = ",".join(filter(None, [x for x in new_chks_sel] + [x.strip() for x in new_chks_txt.split(',')]))
                final_apps = ",".join(filter(None, [x for x in new_apps_sel] + [x.strip() for x in new_apps_txt.split(',')]))
                final_locked_str = "Yes" if new_locked else ""

                df['Start_Mins'] = df['Start_Time'].apply(time_to_mins)
                df['End_Mins'] = df['End_Time'].apply(time_to_mins)
                df['End_Mins'] = df.apply(lambda r: r['End_Mins'] + 1440 if r['End_Mins'] <= r['Start_Mins'] and r['End_Mins'] < 120 else r['End_Mins'], axis=1)
                
                L_start_new = time_to_mins(new_start_txt.strip())
                L_end_new = time_to_mins(new_end_txt.strip())
                if L_end_new <= L_start_new and L_end_new < 120: L_end_new += 1440
                
                new_remainder_rows = []
                
                for day in target_days:
                    row_mask = (df['Day'].str.title() == day) & (df['Start_Time'] == sel_start)
                    if not row_mask.any(): continue
                    idx_to_edit = df[row_mask].index[0]
                    
                    old_start_mins = df.loc[idx_to_edit, 'Start_Mins']
                    old_end_mins = df.loc[idx_to_edit, 'End_Mins']
                    old_act = df.loc[idx_to_edit, 'Activity']
                    old_subs = df.loc[idx_to_edit, 'Sub_Activities']
                    old_chks = df.loc[idx_to_edit, 'check_list']
                    old_app = df.loc[idx_to_edit, 'App']
                    old_locked = df.loc[idx_to_edit, 'Locked']
                    
                    vacated_intervals = []
                    if L_start_new >= old_end_mins or L_end_new <= old_start_mins:
                        vacated_intervals.append((old_start_mins, old_end_mins))
                    else:
                        if L_start_new > old_start_mins:
                            vacated_intervals.append((old_start_mins, L_start_new))
                        if L_end_new < old_end_mins:
                            vacated_intervals.append((L_end_new, old_end_mins))
                            
                    for v_start, v_end in vacated_intervals:
                        new_remainder_rows.append({
                            "Day": day,
                            "Start_Time": mins_to_time(v_start),
                            "End_Time": mins_to_time(v_end),
                            "Start_Mins": v_start,
                            "End_Mins": v_end,
                            "Activity": old_act,
                            "Sub_Activities": old_subs,
                            "check_list": old_chks,
                            "App": old_app,
                            "Locked": old_locked
                        })
                    
                    df.loc[idx_to_edit, 'Start_Time'] = new_start_txt.strip()
                    df.loc[idx_to_edit, 'End_Time'] = new_end_txt.strip()
                    df.loc[idx_to_edit, 'Activity'] = final_act
                    df.loc[idx_to_edit, 'Sub_Activities'] = final_subs
                    df.loc[idx_to_edit, 'check_list'] = final_chks
                    df.loc[idx_to_edit, 'App'] = final_apps
                    df.loc[idx_to_edit, 'Start_Mins'] = L_start_new
                    df.loc[idx_to_edit, 'End_Mins'] = L_end_new
                    df.loc[idx_to_edit, 'Locked'] = final_locked_str
                    
                    day_idx = df[df['Day'].str.title() == day].index
                    for idx in day_idx:
                        if idx == idx_to_edit: continue
                        
                        T_start = df.loc[idx, 'Start_Mins']
                        T_end = df.loc[idx, 'End_Mins']
                        is_locked = str(df.loc[idx].get('Locked', '')).title() == 'Yes'
                        
                        if T_start < L_start_new and T_end > L_end_new:
                            df.loc[idx, 'End_Mins'] = L_start_new
                            df.loc[idx, 'End_Time'] = mins_to_time(L_start_new)
                            new_remainder_rows.append({
                                "Day": day,
                                "Start_Time": mins_to_time(L_end_new),
                                "End_Time": mins_to_time(T_end),
                                "Start_Mins": L_end_new,
                                "End_Mins": T_end,
                                "Activity": df.loc[idx, 'Activity'],
                                "Sub_Activities": df.loc[idx, 'Sub_Activities'],
                                "check_list": df.loc[idx, 'check_list'],
                                "App": df.loc[idx, 'App'],
                                "Locked": df.loc[idx].get('Locked', '')
                            })
                        elif T_start >= L_start_new and T_start < L_end_new and T_end > L_end_new:
                            if not is_locked:
                                df.loc[idx, 'Start_Mins'] = L_end_new
                                df.loc[idx, 'Start_Time'] = mins_to_time(L_end_new)
                        elif T_start < L_start_new and T_end > L_start_new and T_end <= L_end_new:
                            df.loc[idx, 'End_Mins'] = L_start_new
                            df.loc[idx, 'End_Time'] = mins_to_time(L_start_new)
                        elif T_start >= L_start_new and T_end <= L_end_new:
                            if not is_locked:
                                df.loc[idx, 'Start_Mins'] = 0
                                df.loc[idx, 'End_Mins'] = 0
                                
                if new_remainder_rows:
                    df = pd.concat([df, pd.DataFrame(new_remainder_rows)], ignore_index=True)
                    
                df['Dur_Mins'] = df['End_Mins'] - df['Start_Mins']
                df = df[df['Dur_Mins'] > 0].copy()
                df['Duration'] = df['Dur_Mins'].apply(lambda x: f"{int(x)//60:02d}:{int(x)%60:02d}")
                df = sort_routine_df(df)
                df = df[["Day", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "App", "Locked"]]
                
                with st.spinner("Healing Overlaps and Saving to Google Sheets..."):
                    routine_sheet = get_sheet("routine_master")
                    routine_sheet.clear()
                    routine_sheet.update(values=[df.columns.values.tolist()] + df.values.tolist(), range_name="A1")
                    get_routine_data.clear()
                    st.session_state.routine_df = df
                    st.session_state.unsaved_sort = False
                    st.session_state.active_slot_start = new_start_txt.strip()
                st.success(f"✅ Successfully updated and seamlessly aligned schedule for {sel_day_opt}!")
                time.sleep(1.5)
                st.rerun()

            elif del_btn:
                indices_to_drop = []
                for day in target_days:
                    row_mask = (df['Day'].str.title() == day) & (df['Start_Time'] == sel_start)
                    if row_mask.any():
                        indices_to_drop.extend(df[row_mask].index.tolist())
                
                if indices_to_drop:
                    df = df.drop(index=indices_to_drop)
                    
                    df['Start_Mins'] = df['Start_Time'].apply(time_to_mins)
                    df['End_Mins'] = df['End_Time'].apply(time_to_mins)
                    df['End_Mins'] = df.apply(lambda r: r['End_Mins'] + 1440 if r['End_Mins'] <= r['Start_Mins'] and r['End_Mins'] < 120 else r['End_Mins'], axis=1)
                    
                    df['Dur_Mins'] = df['End_Mins'] - df['Start_Mins']
                    df = df[df['Dur_Mins'] > 0].copy()
                    df['Duration'] = df['Dur_Mins'].apply(lambda x: f"{int(x)//60:02d}:{int(x)%60:02d}")
                    df = sort_routine_df(df)
                    df = df[["Day", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "App", "Locked"]]
                    
                    with st.spinner("Deleting time block and updating Google Sheets..."):
                        routine_sheet = get_sheet("routine_master")
                        routine_sheet.clear()
                        routine_sheet.update(values=[df.columns.values.tolist()] + df.values.tolist(), range_name="A1")
                        get_routine_data.clear()
                        st.session_state.routine_df = df
                        st.session_state.unsaved_sort = False
                        st.session_state.active_slot_start = None
                        
                    st.success(f"✅ Successfully deleted the time slot for {sel_day_opt}!")
                    time.sleep(1.5)
                    st.rerun()

        # --- 6. ADD NEW SLOT FORM ---
        st.markdown("---")
        st.markdown("#### ➕ 4. Add a Single Time Slot")
        with st.expander("Click to Create a New Block in the Schedule manually"):
            with st.form("add_new_slot_form"):
                st.markdown("<div style='background-color: #e3f2fd; padding: 15px; border-radius: 8px;'>", unsafe_allow_html=True)
                
                st.markdown("**📅 Target Day(s)**")
                add_day_opt = st.selectbox("Add to Day", day_options, key="add_day")
                
                st.markdown("**⏰ Define Time Block**")
                col_at1, col_at2 = st.columns(2)
                with col_at1: add_start = st.text_input("Start Time (H:MM)", value="12:00", key="add_start")
                with col_at2: add_end = st.text_input("End Time (H:MM)", value="", placeholder="Leave blank to auto-calc duration", key="add_end")
                
                add_locked = st.checkbox("🔒 Lock this Time Slot (Fixed time)")

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
                    final_add_locked = "Yes" if add_locked else ""
                    
                    df['Start_Mins'] = df['Start_Time'].apply(time_to_mins)
                    df['End_Mins'] = df['End_Time'].apply(time_to_mins)
                    df['End_Mins'] = df.apply(lambda r: r['End_Mins'] + 1440 if r['End_Mins'] <= r['Start_Mins'] and r['End_Mins'] < 120 else r['End_Mins'], axis=1)
                    
                    L_start_new = time_to_mins(add_start.strip())
                    
                    if add_end.strip():
                        L_end_new = time_to_mins(add_end.strip())
                    else:
                        selected_dur = 0
                        for sub in add_subs:
                            match = act_master_df[act_master_df['Sub_Activity'] == sub]
                            if not match.empty:
                                selected_dur += int(match['Duration_Mins'].iloc[0])
                        if selected_dur == 0: selected_dur = 30
                        L_end_new = L_start_new + selected_dur

                    if L_end_new <= L_start_new and L_end_new < 120: L_end_new += 1440
                    
                    new_remainder_rows = []
                    
                    for day in target_add_days:
                        day_idx = df[df['Day'].str.title() == day].index
                        for idx in day_idx:
                            T_start = df.loc[idx, 'Start_Mins']
                            T_end = df.loc[idx, 'End_Mins']
                            is_locked = str(df.loc[idx].get('Locked', '')).title() == 'Yes'
                            
                            if T_start < L_start_new and T_end > L_end_new:
                                df.loc[idx, 'End_Mins'] = L_start_new
                                df.loc[idx, 'End_Time'] = mins_to_time(L_start_new)
                                new_remainder_rows.append({
                                    "Day": day,
                                    "Start_Time": mins_to_time(L_end_new),
                                    "End_Time": mins_to_time(T_end),
                                    "Start_Mins": L_end_new,
                                    "End_Mins": T_end,
                                    "Activity": df.loc[idx, 'Activity'],
                                    "Sub_Activities": df.loc[idx, 'Sub_Activities'],
                                    "check_list": df.loc[idx, 'check_list'],
                                    "App": df.loc[idx, 'App'],
                                    "Locked": df.loc[idx].get('Locked', '')
                                })
                            elif T_start >= L_start_new and T_start < L_end_new and T_end > L_end_new:
                                if not is_locked:
                                    df.loc[idx, 'Start_Mins'] = L_end_new
                                    df.loc[idx, 'Start_Time'] = mins_to_time(L_end_new)
                            elif T_start < L_start_new and T_end > L_start_new and T_end <= L_end_new:
                                df.loc[idx, 'End_Mins'] = L_start_new
                                df.loc[idx, 'End_Time'] = mins_to_time(L_start_new)
                            elif T_start >= L_start_new and T_end <= L_end_new:
                                if not is_locked:
                                    df.loc[idx, 'Start_Mins'] = 0
                                    df.loc[idx, 'End_Mins'] = 0
                                
                        new_remainder_rows.append({
                            "Day": day,
                            "Start_Time": mins_to_time(L_start_new),
                            "End_Time": mins_to_time(L_end_new),
                            "Start_Mins": L_start_new,
                            "End_Mins": L_end_new,
                            "Activity": final_add_act,
                            "Sub_Activities": final_add_subs,
                            "check_list": final_add_chks,
                            "App": final_add_apps,
                            "Locked": final_add_locked
                        })
                    
                    if new_remainder_rows:
                        df = pd.concat([df, pd.DataFrame(new_remainder_rows)], ignore_index=True)
                    
                    df['Dur_Mins'] = df['End_Mins'] - df['Start_Mins']
                    df = df[df['Dur_Mins'] > 0].copy()
                    df['Duration'] = df['Dur_Mins'].apply(lambda x: f"{int(x)//60:02d}:{int(x)%60:02d}")
                    df = sort_routine_df(df)
                    df = df[["Day", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "App", "Locked"]]
                    
                    with st.spinner("Inserting Time Block and Healing Sequence..."):
                        routine_sheet = get_sheet("routine_master")
                        routine_sheet.clear()
                        routine_sheet.update(values=[df.columns.values.tolist()] + df.values.tolist(), range_name="A1")
                        get_routine_data.clear()
                        st.session_state.routine_df = df
                        st.session_state.unsaved_sort = False
                        st.session_state.active_slot_start = mins_to_time(L_start_new)
                    st.success(f"✅ Successfully inserted new block and adjusted schedule for {add_day_opt}!")
                    time.sleep(1.5)
                    st.rerun()

        # --- 7. AUTO-GENERATE DAY SCHEDULE ---
        st.markdown("---")
        st.markdown("#### ⚡ 5. Auto-Generate Day Schedule")
        with st.expander("Click to Auto-Build from Activity Profile"):
            st.info("💡 Pulls all sub-activities for a selected profile in order. Enter an anchor **Start Time** for the first task (e.g. 6:00). Leave subsequent times blank to auto-chain them based on your Builder durations!")
            
            col_gen1, col_gen2 = st.columns(2)
            with col_gen1:
                gen_day_opt = st.selectbox("Select Schedule Day to Build", day_options, key="gen_day")
            
            if gen_day_opt == "Monday to Friday":
                default_type = "WEEK DAYS"
            elif gen_day_opt == "Saturday":
                default_type = "SATURDAY/HALF WORKING DAY"
            elif gen_day_opt == "Sunday":
                default_type = "SUNDAY"
            else:
                default_type = "WEEK DAYS"
                
            with col_gen2:
                override_type = st.selectbox("Profile to Apply", ["WEEK DAYS", "SATURDAY/HALF WORKING DAY", "SUNDAY", "HOLIDAY"], index=["WEEK DAYS", "SATURDAY/HALF WORKING DAY", "SUNDAY", "HOLIDAY"].index(default_type))
            
            profile_df_gen = act_master_df[(act_master_df['Day_Type'] == override_type) & (act_master_df['Sub_Activity'] != "")].copy()
            
            if profile_df_gen.empty:
                st.warning(f"No sub-activities found for {override_type} in the Builder.")
            else:
                gen_df = profile_df_gen[['Activity', 'Sub_Activity', 'Duration_Mins']].copy()
                gen_df['Start_Time (H:MM)'] = ""
                gen_df['End_Time (H:MM)'] = ""
                
                apply_mode = st.radio("Apply Mode", ["Overwrite Day (Replace completely)", "Append (Add to existing schedule)"], horizontal=True)
                
                st.markdown("**Adjust Times & Generate:**")
                edited_gen_df = st.data_editor(
                    gen_df,
                    column_config={
                        "Activity": st.column_config.TextColumn("Activity", disabled=True),
                        "Sub_Activity": st.column_config.TextColumn("Sub-Activity", disabled=True),
                        "Duration_Mins": st.column_config.NumberColumn("Duration (Mins)", disabled=True),
                        "Start_Time (H:MM)": st.column_config.TextColumn("Start Time (Optional)"),
                        "End_Time (H:MM)": st.column_config.TextColumn("End Time (Optional)")
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                if st.button("🚀 Generate & Save Schedule", type="primary", use_container_width=True):
                    new_rows = []
                    current_mins = 0
                    
                    for _, row in edited_gen_df.iterrows():
                        act = row['Activity']
                        sub_act = row['Sub_Activity']
                        dur = int(row['Duration_Mins'])
                        st_str = str(row['Start_Time (H:MM)']).strip()
                        et_str = str(row['End_Time (H:MM)']).strip()
                        
                        if st_str:
                            start_mins = time_to_mins(st_str)
                        else:
                            start_mins = current_mins
                            
                        if et_str:
                            end_mins = time_to_mins(et_str)
                        else:
                            end_mins = start_mins + dur
                            
                        if end_mins <= start_mins and end_mins < 120:
                            end_mins += 1440
                            
                        current_mins = end_mins
                        
                        if start_mins == end_mins:
                            continue
                            
                        target_gen_days = weekdays if gen_day_opt == "Monday to Friday" else [gen_day_opt]
                        for d in target_gen_days:
                            new_rows.append({
                                "Day": d,
                                "Start_Time": mins_to_time(start_mins),
                                "End_Time": mins_to_time(end_mins),
                                "Start_Mins": start_mins,
                                "End_Mins": end_mins,
                                "Activity": act,
                                "Sub_Activities": sub_act,
                                "check_list": "",
                                "App": "",
                                "Locked": ""
                            })
                    
                    if new_rows:
                        target_gen_days = weekdays if gen_day_opt == "Monday to Friday" else [gen_day_opt]
                        
                        if apply_mode.startswith("Overwrite"):
                            df_clean = df[~df['Day'].str.title().isin([d.title() for d in target_gen_days])].copy()
                        else:
                            df_clean = df.copy()
                            
                        new_df = pd.DataFrame(new_rows)
                        df_final = pd.concat([df_clean, new_df], ignore_index=True)
                        
                        df_final['Start_Mins'] = df_final['Start_Time'].apply(time_to_mins)
                        df_final['End_Mins'] = df_final['End_Time'].apply(time_to_mins)
                        df_final['End_Mins'] = df_final.apply(lambda r: r['End_Mins'] + 1440 if r['End_Mins'] <= r['Start_Mins'] and r['End_Mins'] < 120 else r['End_Mins'], axis=1)
                        
                        df_final['Dur_Mins'] = df_final['End_Mins'] - df_final['Start_Mins']
                        df_final = df_final[df_final['Dur_Mins'] > 0].copy()
                        df_final['Duration'] = df_final['Dur_Mins'].apply(lambda x: f"{int(x)//60:02d}:{int(x)%60:02d}")
                        df_final = sort_routine_df(df_final)
                        df_final = df_final[["Day", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "App", "Locked"]]
                        
                        with st.spinner("Generating Schedule and Saving to Google Sheets..."):
                            routine_sheet = get_sheet("routine_master")
                            routine_sheet.clear()
                            routine_sheet.update(values=[df_final.columns.values.tolist()] + df_final.values.tolist(), range_name="A1")
                            get_routine_data.clear()
                            st.session_state.routine_df = df_final
                            st.session_state.unsaved_sort = False
                        st.success(f"✅ Auto-Generated schedule for {gen_day_opt}!")
                        time.sleep(1.5)
                        st.rerun()

except Exception as e:
    st.error(f"System Error: {e}")
