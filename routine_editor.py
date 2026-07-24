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
    if not data or len(data) <= 1:
        return pd.DataFrame(columns=["Day", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "App", "Locked"])
        
    df = pd.DataFrame(data[1:], columns=data[0])
    
    required_cols = ["Day", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "App", "Locked"]
    for col in required_cols:
        if col not in df.columns:
            df[col] = ""
            
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

@st.cache_data(ttl=300)
def get_default_routine_data():
    try:
        sheet = get_main_spreadsheet().worksheet("Default Routine")
    except gspread.exceptions.WorksheetNotFound:
        spreadsheet = get_main_spreadsheet()
        sheet = spreadsheet.add_worksheet(title="Default Routine", rows="100", cols="7")
        sheet.update(values=[["Day_Type", "Start_Time", "End_Time", "Duration", "Dur_Mins", "Activity", "Sub_Activities"]], range_name="A1")
        return pd.DataFrame(columns=["Day_Type", "Start_Time", "End_Time", "Duration", "Dur_Mins", "Activity", "Sub_Activities"])
        
    data = sheet.get_all_values()
    if not data:
        return pd.DataFrame(columns=["Day_Type", "Start_Time", "End_Time", "Duration", "Dur_Mins", "Activity", "Sub_Activities"])
        
    if "Day_Type" not in data[0]:
        df = pd.DataFrame(data[1:], columns=data[0]) if len(data) > 1 else pd.DataFrame(columns=data[0])
        df.insert(0, "Day_Type", "WEEK DAYS")
        sheet.clear()
        sheet.update(values=[df.columns.values.tolist()] + df.values.tolist(), range_name="A1")
        data = sheet.get_all_values()

    if len(data) <= 1:
        return pd.DataFrame(columns=["Day_Type", "Start_Time", "End_Time", "Duration", "Dur_Mins", "Activity", "Sub_Activities"])
        
    df = pd.DataFrame(data[1:], columns=data[0])
    df['Dur_Mins'] = pd.to_numeric(df['Dur_Mins'], errors='coerce').fillna(0)
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

# --- THE DUAL-ENGINE FOR ARROWS (SLIDE & JUMP) ---
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
            
            dur_curr = df.loc[idx_curr, 'Dur_Mins']
            dur_target = df.loc[idx_target, 'Dur_Mins']
            
            if abs(curr_i - target_i) == 1:
                # 1. Adjacent Slide
                if direction == 'up':
                    anchor_start = df.loc[idx_target, 'Start_Mins']
                    df.loc[idx_curr, 'Start_Mins'] = anchor_start
                    df.loc[idx_curr, 'End_Mins'] = anchor_start + dur_curr
                    df.loc[idx_target, 'Start_Mins'] = anchor_start + dur_curr
                    df.loc[idx_target, 'End_Mins'] = anchor_start + dur_curr + dur_target
                elif direction == 'down':
                    anchor_start = df.loc[idx_curr, 'Start_Mins']
                    df.loc[idx_target, 'Start_Mins'] = anchor_start
                    df.loc[idx_target, 'End_Mins'] = anchor_start + dur_target
                    df.loc[idx_curr, 'Start_Mins'] = anchor_start + dur_target
                    df.loc[idx_curr, 'End_Mins'] = anchor_start + dur_target + dur_curr
            else:
                # 2. Distant Jump across walls
                start_curr = df.loc[idx_curr, 'Start_Mins']
                start_target = df.loc[idx_target, 'Start_Mins']
                
                df.loc[idx_curr, 'Start_Mins'] = start_target
                df.loc[idx_curr, 'End_Mins'] = start_target + dur_curr
                
                df.loc[idx_target, 'Start_Mins'] = start_curr
                df.loc[idx_target, 'End_Mins'] = start_curr + dur_target
            
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
        get_default_routine_data.clear()
        if 'routine_df' in st.session_state:
            del st.session_state.routine_df
        if 'default_routine_df' in st.session_state:
            del st.session_state.default_routine_df
        if 'unsaved_sort' in st.session_state:
            st.session_state.unsaved_sort = False
        if 'active_slot_start' in st.session_state:
            del st.session_state.active_slot_start
        if 'unsaved_default' in st.session_state:
            st.session_state.unsaved_default = False
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

    tab_editor, tab_summary, tab_builder, tab_default = st.tabs(["⚙️ Routine Editor", "📊 Routine Summary", "🏗️ Activity Builder", "🔁 Default Routine"])

    # ==========================================
    # TAB 4: DEFAULT ROUTINE BUILDER
    # ==========================================
    with tab_default:
        st.markdown("### 🔁 Build Default Routine")
        st.info("💡 Check the box in the **Available Pool** to instantly append it to your **Default Routine**. Check a box in the Default Routine to remove it and send it back to the pool. Times are automatically calculated starting from 0:00.")

        if 'def_routine_refresh' not in st.session_state:
            st.session_state.def_routine_refresh = 0

        if 'default_routine_df' not in st.session_state:
            st.session_state.default_routine_df = get_default_routine_data()
            
        def_routine_df = st.session_state.default_routine_df.copy()

        st.markdown("<div class='profile-header'>📅 Select Base Profile to pull Activities from:</div>", unsafe_allow_html=True)
        profile_options = ["WEEK DAYS", "SATURDAY/HALF WORKING DAY", "SUNDAY", "HOLIDAY"]
        selected_def_profile = st.radio("Profile Config", profile_options, horizontal=True, label_visibility="collapsed", key="def_profile_radio")
        
        st.markdown("<hr style='margin: 15px 0px;'>", unsafe_allow_html=True)

        profile_df = act_master_df[(act_master_df['Day_Type'] == selected_def_profile) & (act_master_df['Sub_Activity'] != "")].copy()
        curr_def_routine_df = def_routine_df[def_routine_df['Day_Type'] == selected_def_profile]
        
        if not curr_def_routine_df.empty:
            def_routine_keys = curr_def_routine_df['Activity'] + "|" + curr_def_routine_df['Sub_Activities']
            def_routine_keys = def_routine_keys.tolist()
        else:
            def_routine_keys = []
            
        profile_df['Match_Key'] = profile_df['Activity'] + "|" + profile_df['Sub_Activity']
        available_pool_df = profile_df[~profile_df['Match_Key'].isin(def_routine_keys)].copy()
        
        available_pool_df['Duration'] = available_pool_df['Duration_Mins'].apply(lambda x: f"{int(x)//60:02d}:{int(x)%60:02d}")
        available_pool_df = available_pool_df[['Activity', 'Sub_Activity', 'Duration', 'Duration_Mins']].reset_index(drop=True)

        col_pool, col_routine = st.columns([1, 1])
        
        with col_pool:
            st.markdown("#### 📥 Window 1: Available Pool")
            if available_pool_df.empty:
                st.success(f"✅ All activities from {selected_def_profile} are currently in your Default Routine!")
            else:
                available_pool_df.insert(0, "Add", False)
                pool_event = st.data_editor(
                    available_pool_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Add": st.column_config.CheckboxColumn("➕ Add", default=False),
                        "Activity": st.column_config.TextColumn("Activity", disabled=True),
                        "Sub_Activity": st.column_config.TextColumn("Sub-Activity", disabled=True),
                        "Duration": st.column_config.TextColumn("Duration", disabled=True),
                        "Duration_Mins": None  
                    },
                    key=f"pool_grid_editor_{st.session_state.def_routine_refresh}"
                )
                
                selected_to_add = pool_event[pool_event["Add"] == True]
                if not selected_to_add.empty:
                    selected_item = selected_to_add.iloc[0]
                    new_row = {
                        "Day_Type": selected_def_profile,
                        "Start_Time": "", 
                        "End_Time": "", 
                        "Duration": selected_item['Duration'],
                        "Dur_Mins": selected_item['Duration_Mins'],
                        "Activity": selected_item['Activity'],
                        "Sub_Activities": selected_item['Sub_Activity']
                    }
                    def_routine_df = pd.concat([def_routine_df, pd.DataFrame([new_row])], ignore_index=True)
                    
                    mask = def_routine_df['Day_Type'] == selected_def_profile
                    profile_indices = def_routine_df[mask].index
                    current_mins = 0
                    for i in profile_indices:
                        dur = int(def_routine_df.loc[i, 'Dur_Mins'])
                        def_routine_df.loc[i, 'Start_Time'] = mins_to_time(current_mins)
                        current_mins += dur
                        def_routine_df.loc[i, 'End_Time'] = mins_to_time(current_mins)
                        
                    st.session_state.default_routine_df = def_routine_df
                    st.session_state.unsaved_default = True
                    st.session_state.def_routine_refresh += 1
                    st.rerun()

        with col_routine:
            st.markdown(f"#### 📤 Window 2: Default Routine Sequence")
            if curr_def_routine_df.empty:
                st.info(f"Your Default Routine for {selected_def_profile} is empty. Check tasks in Window 1 to add them.")
            else:
                def_routine_display = curr_def_routine_df.copy()
                def_routine_display.insert(0, "Remove", False)
                routine_event = st.data_editor(
                    def_routine_display,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Remove": st.column_config.CheckboxColumn("❌ Remove", default=False),
                        "Day_Type": None,
                        "Start_Time": st.column_config.TextColumn("Start Time", disabled=True),
                        "End_Time": st.column_config.TextColumn("End Time", disabled=True),
                        "Duration": st.column_config.TextColumn("Duration", disabled=True),
                        "Activity": st.column_config.TextColumn("Activity", disabled=True),
                        "Sub_Activities": st.column_config.TextColumn("Sub-Activity", disabled=True),
                        "Dur_Mins": None  
                    },
                    key=f"def_routine_grid_editor_{st.session_state.def_routine_refresh}"
                )
                
                selected_to_remove = routine_event[routine_event["Remove"] == True]
                if not selected_to_remove.empty:
                    act_to_remove = selected_to_remove.iloc[0]['Activity']
                    sub_to_remove = selected_to_remove.iloc[0]['Sub_Activities']
                    
                    idx_mask = (def_routine_df['Day_Type'] == selected_def_profile) & \
                               (def_routine_df['Activity'] == act_to_remove) & \
                               (def_routine_df['Sub_Activities'] == sub_to_remove)
                               
                    idx_to_remove = def_routine_df[idx_mask].index[0]
                    def_routine_df = def_routine_df.drop(index=idx_to_remove).reset_index(drop=True)
                    
                    mask = def_routine_df['Day_Type'] == selected_def_profile
                    profile_indices = def_routine_df[mask].index
                    current_mins = 0
                    for i in profile_indices:
                        dur = int(def_routine_df.loc[i, 'Dur_Mins'])
                        def_routine_df.loc[i, 'Start_Time'] = mins_to_time(current_mins)
                        current_mins += dur
                        def_routine_df.loc[i, 'End_Time'] = mins_to_time(current_mins)
                        
                    st.session_state.default_routine_df = def_routine_df
                    st.session_state.unsaved_default = True
                    st.session_state.def_routine_refresh += 1
                    st.rerun()
                    
        st.markdown("<hr style='margin: 15px 0px;'>", unsafe_allow_html=True)
        
        if st.session_state.get('unsaved_default', False):
            st.markdown("<div class='local-warning'>⚠️ <b>Default Routine modified locally!</b> Click save below to update Google Sheets.</div>", unsafe_allow_html=True)
            
        if st.button("💾 Save Default Routine to Google Sheets", type="primary", use_container_width=True):
            with st.spinner("Saving sequence to the cloud..."):
                sheet = get_sheet("Default Routine")
                sheet.clear()
                if not def_routine_df.empty:
                    sheet.update(values=[def_routine_df.columns.values.tolist()] + def_routine_df.values.tolist(), range_name="A1")
                else:
                    sheet.update(values=[["Day_Type", "Start_Time", "End_Time", "Duration", "Dur_Mins", "Activity", "Sub_Activities"]], range_name="A1")
                get_default_routine_data.clear()
                st.session_state.unsaved_default = False
            st.success("✅ Default Routine successfully saved to Google Sheets!")
            time.sleep(1.5)
            st.rerun()


    # ==========================================
    # TAB 3: ACTIVITY BUILDER
    # ==========================================
    with tab_builder:
        st.markdown("### 🏗️ Activity Database & Time Pool")
        
        st.markdown("<div class='profile-header'>📅 Select Schedule Profile</div>", unsafe_allow_html=True)
        profile_options = ["WEEK DAYS", "SATURDAY/HALF WORKING DAY", "SUNDAY", "HOLIDAY"]
        selected_day_type = st.radio("Profile Config", profile_options, horizontal=True, label_visibility="collapsed", key="builder_profile_radio")
        
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
            days_in_view = [selected_summary_day]
        else:
            filtered_summary_df = summary_df.copy()
            st.markdown("### 🗓️ Weekly Activity Matrix")
            
            pivot_df = summary_df.pivot_table(
                index='Activity', columns='Day', values='Dur_Mins', aggfunc='sum', fill_value=0
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
            st.markdown(f"### 📊 Weekly Breakdown")
            days_in_view = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        # --- SMART EDITOR VS BUILDER COMPARISON SYSTEM ---
        st.markdown("#### 🔍 Compare: Live Editor vs Activity Builder")
        st.info("💡 Missing tasks and duration mismatches are explicitly highlighted in **Red**. Extra Editor tasks are highlighted in **Gray**.")

        expected_act_sub = {}
        expected_act = {}
        for day in days_in_view:
            day_str = str(day).title()
            if day_str == 'Saturday': dtype = 'SATURDAY/HALF WORKING DAY'
            elif day_str == 'Sunday': dtype = 'SUNDAY'
            elif day_str == 'Holiday': dtype = 'HOLIDAY'
            else: dtype = 'WEEK DAYS'
            
            b_df = act_master_df[(act_master_df['Day_Type'] == dtype) & (act_master_df['Sub_Activity'] != "")]
            for _, r in b_df.iterrows():
                a = str(r['Activity']).strip().upper()
                s = str(r['Sub_Activity']).strip()
                m = int(r['Duration_Mins'])
                expected_act_sub[(a, s)] = expected_act_sub.get((a, s), 0) + m
                expected_act[a] = expected_act.get(a, 0) + m
                
        live_act_sub = {}
        live_act = {}
        temp_df = filtered_summary_df.copy()
        temp_df['Sub_List'] = temp_df['Sub_Activities'].apply(
            lambda x: [i.strip() for i in str(x).split(',') if i.strip()] if str(x).strip() else ["No Sub-Activity"]
        )
        exploded_df = temp_df.explode('Sub_List')
        
        for _, r in exploded_df.iterrows():
            a = str(r['Activity']).strip().upper() if str(r['Activity']).strip() else "UNNAMED ACTIVITY"
            s = str(r['Sub_List']).strip()
            m = int(r['Dur_Mins'])
            live_act_sub[(a, s)] = live_act_sub.get((a, s), 0) + m
            live_act[a] = live_act.get(a, 0) + m
            
        all_acts_view = set(live_act.keys()).union(set(expected_act.keys()))
        act_sort_list = []
        for a in all_acts_view:
            l = live_act.get(a, 0)
            e = expected_act.get(a, 0)
            act_sort_list.append({'act': a, 'live': l, 'exp': e, 'is_missing': l == 0})
        
        act_sort_list.sort(key=lambda x: (x['is_missing'], -x['live'], -x['exp']))
        
        for item in act_sort_list:
            a = item['act']
            l_act = item['live']
            e_act = item['exp']
            
            act_flag = ""
            if l_act == e_act: act_flag = "✅"
            elif l_act == 0: act_flag = "❌ Missing"
            elif e_act == 0: act_flag = "➕ Extra"
            else: act_flag = "🚨 Mismatch"
            
            expander_label = f"📁 {a} | Live: {format_mins(l_act)} | Builder: {format_mins(e_act)} | {act_flag}"
            with st.expander(expander_label):
                
                subs_for_act = set([s for act, s in live_act_sub.keys() if act == a]).union(
                               set([s for act, s in expected_act_sub.keys() if act == a]))
                
                sub_sort_list = []
                for s in subs_for_act:
                    l_s = live_act_sub.get((a, s), 0)
                    e_s = expected_act_sub.get((a, s), 0)
                    sub_sort_list.append({'sub': s, 'live': l_s, 'exp': e_s, 'is_missing': l_s == 0})
                
                sub_sort_list.sort(key=lambda x: (x['is_missing'], -x['live'], -x['exp']))
                
                for s_item in sub_sort_list:
                    s = s_item['sub']
                    l_s = s_item['live']
                    e_s = s_item['exp']
                    
                    bg_color = "transparent"
                    border_color = "#e0e0e0"
                    
                    if l_s == e_s:
                        s_flag = "✅ OK"
                    elif l_s == 0:
                        s_flag = "❌ Missing in Editor"
                        bg_color = "#f8d7da" # Light Red
                        border_color = "#f5c2c7"
                    elif e_s == 0:
                        s_flag = "➕ Extra (Not in Builder)"
                        bg_color = "#e2e3e5" # Gray
                        border_color = "#d3d6d8"
                    else:
                        s_flag = f"🚨 Mismatch ({l_s - e_s} mins)"
                        bg_color = "#f8d7da" # Light Red
                        border_color = "#f5c2c7"
                        
                    st.markdown(f"""
                    <div style='background-color: {bg_color}; border: 1px solid {border_color}; padding: 8px; border-radius: 6px; margin-bottom: 5px;'>
                        <b>📄 {s}</b> &nbsp;&nbsp;|&nbsp;&nbsp; Live: <b>{format_mins(l_s)}</b> &nbsp;&nbsp;|&nbsp;&nbsp; Builder: <b>{format_mins(e_s)}</b> &nbsp;&nbsp;|&nbsp;&nbsp; {s_flag}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if l_s > 0:
                        slots_df = exploded_df[(exploded_df["Activity"] == a) & (exploded_df["Sub_List"] == s)].copy()
                        day_order = {d: i for i, d in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])}
                        slots_df['Day_Idx'] = slots_df['Day'].str.title().map(day_order).fillna(99)
                        slots_df['Start_Sort'] = slots_df['Start_Time'].apply(time_to_mins)
                        slots_df = slots_df.sort_values(['Day_Idx', 'Start_Sort'])
                        
                        display_df = slots_df[["Day", "Start_Time", "End_Time", "Duration"]]
                        st.dataframe(display_df, hide_index=True, use_container_width=True)

        total_tracked_mins = filtered_summary_df['Dur_Mins'].sum()
        context_label = "Total Editor Live Time for " + (f"{selected_summary_day}" if view_mode == "Daily (24h) Breakdown" else "the Week")
        
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
        mismatched_act_subs_per_day = {}
        
        exp_dicts = {}
        for dtype in ["WEEK DAYS", "SATURDAY/HALF WORKING DAY", "SUNDAY", "HOLIDAY"]:
            expected_df = act_master_df[(act_master_df['Day_Type'] == dtype) & (act_master_df['Sub_Activity'] != "")]
            exp_dict = {}
            for _, r in expected_df.iterrows():
                k = (str(r['Activity']).strip().upper(), str(r['Sub_Activity']).strip())
                exp_dict[k] = exp_dict.get(k, 0) + int(r['Duration_Mins'])
            exp_dicts[dtype] = exp_dict
        
        audit_df = df.copy()
        audit_df['Dur_Mins'] = audit_df['Duration'].apply(parse_dur_to_mins)
        audit_df['Sub_List'] = audit_df['Sub_Activities'].apply(
            lambda x: [i.strip() for i in str(x).split(',') if i.strip()] if str(x).strip() else []
        )
        exploded_audit = audit_df.explode('Sub_List')
        exploded_audit = exploded_audit[exploded_audit['Sub_List'] != ""] 
        
        for day in df['Day'].unique():
            day_str = str(day).title()
            
            day_type = "WEEK DAYS"
            if day_str == "Saturday": day_type = "SATURDAY/HALF WORKING DAY"
            elif day_str == "Sunday": day_type = "SUNDAY"
            elif day_str == "Holiday": day_type = "HOLIDAY"
            
            exp_dict = exp_dicts.get(day_type, {})
            
            day_live = exploded_audit[exploded_audit['Day'].str.title() == day_str]
            live_dict = {}
            for _, r in day_live.iterrows():
                k = (str(r['Activity']).strip().upper(), str(r['Sub_List']).strip())
                live_dict[k] = live_dict.get(k, 0) + int(r['Dur_Mins'])
                
            all_keys = set(live_dict.keys()).union(set(exp_dict.keys()))
            
            for k in all_keys:
                act_name, sub_name = k
                l_mins = live_dict.get(k, 0)
                e_mins = exp_dict.get(k, 0)
                
                if l_mins != e_mins:
                    if day_str not in mismatched_act_subs_per_day:
                        mismatched_act_subs_per_day[day_str] = set()
                    mismatched_act_subs_per_day[day_str].add(k)
                    
                    mismatches.append({
                        "Day": day_str,
                        "Task": act_name,
                        "Sub-Task(s)": sub_name,
                        "Live Mins": l_mins,
                        "Expected Mins": e_mins,
                        "Difference": l_mins - e_mins
                    })
                    
        if not mismatches:
            st.success("✅ **Everything is OK!** All scheduled time slots perfectly match your configured Activity Builder durations.")
        else:
            st.warning(f"⚠️ **Mismatch Warning!** Found {len(mismatches)} sub-activity assignments where the total daily live schedule duration does not match your builder configuration.")
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

        if 'active_slot_start' not in st.session_state:
            st.session_state.active_slot_start = None
            
        if st.session_state.active_slot_start not in target_df['Start_Time'].values:
            if not target_df.empty:
                st.session_state.active_slot_start = target_df.iloc[0]['Start_Time']
                
        sel_start = st.session_state.active_slot_start
        day_mismatches = mismatched_act_subs_per_day.get(display_day, set())

        # --- 2. INTERACTIVE SCHEDULE TABLE ---
        col_sch_head1, col_sch_head2 = st.columns([7, 3])
        with col_sch_head1:
            st.markdown(f"#### 📋 2. Interactive Schedule ({display_day})")
            st.markdown("<div style='font-size: 0.9em; margin-bottom: 10px; color: #555;'>🖱️ <b>Click directly on any task row below</b> to select it for editing or moving!</div>", unsafe_allow_html=True)
            
        with col_sch_head2:
            if sel_day_opt == "Monday to Friday":
                reset_day_type = "WEEK DAYS"
            elif display_day.title() == "Saturday":
                reset_day_type = "SATURDAY/HALF WORKING DAY"
            elif display_day.title() == "Sunday":
                reset_day_type = "SUNDAY"
            elif display_day.title() == "Holiday":
                reset_day_type = "HOLIDAY"
            else:
                reset_day_type = "WEEK DAYS"
                
            if st.button(f"🔄 Reset to {reset_day_type} Default", help=f"Overwrite {sel_day_opt} with Default Routine", use_container_width=True):
                def_routine_df_live = get_default_routine_data()
                prof_def_df = def_routine_df_live[def_routine_df_live['Day_Type'] == reset_day_type].copy()
                
                if prof_def_df.empty:
                    st.error(f"❌ No Default Routine found for {reset_day_type}. Build it first in the Default Routine tab!")
                else:
                    df_clean = df[~df['Day'].str.title().isin([d.title() for d in target_days])].copy()
                    
                    new_rows = []
                    for d in target_days:
                        for _, r in prof_def_df.iterrows():
                            new_rows.append({
                                "Day": d.title(),
                                "Start_Time": r['Start_Time'],
                                "End_Time": r['End_Time'],
                                "Duration": r['Duration'],
                                "Activity": r['Activity'],
                                "Sub_Activities": r['Sub_Activities'],
                                "check_list": "",
                                "App": "",
                                "Locked": ""
                            })
                    
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
                    
                    with st.spinner(f"Resetting {sel_day_opt} to Default..."):
                        routine_sheet = get_sheet("routine_master")
                        routine_sheet.clear()
                        routine_sheet.update(values=[df_final.columns.values.tolist()] + df_final.values.tolist(), range_name="A1")
                        get_routine_data.clear()
                        st.session_state.routine_df = df_final
                        st.session_state.unsaved_sort = False
                        if not new_df.empty:
                            st.session_state.active_slot_start = new_df.iloc[0]['Start_Time']
                    st.success(f"✅ Successfully reset {sel_day_opt} to {reset_day_type} default!")
                    time.sleep(1.5)
                    st.rerun()

        display_rows = []
        for i in range(len(target_df)):
            row_dict = target_df.iloc[i].to_dict()
            row_dict['Is_Gap'] = False
            
            act = str(row_dict.get('Activity', '')).strip().upper()
            row_subs_str = str(row_dict.get('Sub_Activities', '')).strip()
            row_subs_list = [x.strip() for x in row_subs_str.split(',') if x.strip()]
            
            row_dict['Is_Mismatch'] = any((act, sub) in day_mismatches for sub in row_subs_list)
            
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
                        "Is_Gap": True,
                        "Is_Mismatch": False
                    })
                    display_rows.append(gap_row)
                    
        display_df = pd.DataFrame(display_rows)
        
        def highlight_target_row(s):
            is_gap = s.get('Is_Gap', False)
            is_mismatch = s.get('Is_Mismatch', False)
            is_target = s.get('Start_Time') == sel_start and not is_gap
            is_locked = str(s.get('Locked', '')).title() == 'Yes'
            
            if is_gap:
                return ['background-color: #ffcccc; color: #b30000; font-weight: bold;' for _ in s]
            elif is_target and is_mismatch:
                return ['background-color: #ffb74d; color: black; font-weight: bold;' for _ in s]
            elif is_target:
                return ['background-color: #fff59d; color: black; font-weight: bold;' for _ in s]
            elif is_mismatch:
                return ['background-color: #f8d7da; color: #842029; font-weight: bold;' for _ in s]
            elif is_locked:
                return ['background-color: #e2e3e5; color: #41464b;' for _ in s]
            else:
                return ['' for _ in s]

        styled_df = display_df.style.apply(highlight_target_row, axis=1)
        
        cols_to_hide = ['Start_Mins', 'End_Mins', 'Is_Gap', 'Is_Mismatch', 'Locked_Sort']
        hidden_columns_config = {col: None for col in cols_to_hide if col in display_df.columns}

        selection_event = st.dataframe(
            styled_df, 
            use_container_width=True, 
            hide_index=True,
            column_config=hidden_columns_config,
            on_select="rerun",
            selection_mode="single-row",
            key="schedule_grid"
        )
        
        if selection_event.selection.rows:
            clicked_idx = selection_event.selection.rows[0]
            clicked_row = display_df.iloc[clicked_idx]
            if not clicked_row['Is_Gap']:
                if clicked_row['Start_Time'] != st.session_state.active_slot_start:
                    st.session_state.active_slot_start = clicked_row['Start_Time']
                    st.rerun()

        st.markdown("""
        <div style='font-size: 0.9em; padding: 10px; background-color: #f8f9fa; border-radius: 6px; margin-top: 5px; margin-bottom: 15px; border: 1px solid #e0e0e0;'>
            <b>🎨 Color Legend:</b> &nbsp;
            🟨 <b>Yellow:</b> Currently selected editing row &nbsp;&nbsp;|&nbsp;&nbsp; 🟥 <b>Dark Red:</b> Missing time / Schedule Gaps &nbsp;&nbsp;|&nbsp;&nbsp;
            🚨 <b>Light Red:</b> Builder mismatch &nbsp;&nbsp;|&nbsp;&nbsp; 🔲 <b>Gray:</b> 🔒 Fixed slot
        </div>
        """, unsafe_allow_html=True)


        # --- 3. QUICK MOVE ARROWS ---
        st.markdown(f"#### ↕️ 3. Quick Move Slot: `{sel_start}`")
        
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
        
        col_up, col_dn, _ = st.columns([2, 2, 6])
        with col_up:
            if st.button("⬆️ Move Up", key="move_up", disabled=(is_curr_locked or not can_move_up), use_container_width=True, help="Swap position with the task above"):
                new_start = shift_routine_slot(df.copy(), target_days, curr_i, 'up')
                if new_start: st.session_state.active_slot_start = new_start
                st.rerun()
        with col_dn:
            if st.button("⬇️ Move Down", key="move_dn", disabled=(is_curr_locked or not can_move_dn), use_container_width=True, help="Swap position with the task below"):
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

        st.markdown("---")


        # --- 4. SMART EDITOR FORM ---
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

        st.markdown(f"#### ✏️ 4. Update `{sel_row['Start_Time']}` Slot Details")
        
        with st.form("smart_edit_form"):
            st.markdown("<div style='background-color: #f8f9fa; padding: 15px; border-radius: 8px;'>", unsafe_allow_html=True)
            
            st.markdown("**⏰ Edit Time Slot (Adjacent slots will auto-adjust!)**")
            col_t1, col_t2 = st.columns(2)
            with col_t1: new_start_txt = st.text_input("Start Time (H:MM)", value=sel_row['Start_Time'])
            with col_t2: new_end_txt = st.text_input("End Time (H:MM)", value=sel_row['End_Time'])
            
            col_chk1, col_chk2 = st.columns(2)
            with col_chk1: new_locked = st.checkbox("🔒 Lock this Time Slot (Fixed time)", value=curr_locked)
            with col_chk2: move_slide_chk = st.checkbox("🧲 Teleport & Slide (Pull tasks Up/Down to fill gaps left behind)")
            
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
                
                df['Dur_Mins'] = df['End_Mins'] - df['Start_Mins']
                
                L_start_new = time_to_mins(new_start_txt.strip())
                L_end_new = time_to_mins(new_end_txt.strip())
                if L_end_new <= L_start_new and L_end_new < 120: L_end_new += 1440
                
                # --- SMART AUTO-BALANCE RIPPLE ENGINE ---
                old_start_mins = time_to_mins(sel_row['Start_Time'])
                old_end_mins = time_to_mins(sel_row['End_Time'])
                if old_end_mins <= old_start_mins and old_end_mins < 120: old_end_mins += 1440
                old_dur = old_end_mins - old_start_mins
                
                delta_dur = (L_end_new - L_start_new) - old_dur
                auto_balance_success = False
                
                if delta_dur != 0 and L_start_new == old_start_mins:
                    for day in target_days:
                        day_mask = df['Day'].str.title() == day
                        day_indices = df[day_mask].sort_values('Start_Mins').index.tolist()
                        
                        idx_to_edit = None
                        for k in day_indices:
                            if df.loc[k, 'Start_Time'] == sel_start:
                                idx_to_edit = k
                                break
                                
                        if idx_to_edit is None: continue
                        
                        curr_pos = day_indices.index(idx_to_edit)
                        donor_idx = None
                        
                        for i in range(curr_pos + 1, len(day_indices)):
                            k = day_indices[i]
                            if str(df.loc[k, 'Locked']).title() == 'Yes':
                                break 
                                
                            k_subs = set([x.strip() for x in str(df.loc[k, 'Sub_Activities']).split(',') if x.strip()])
                            edit_subs = set([x.strip() for x in str(final_subs).split(',') if x.strip()])
                            
                            if k_subs & edit_subs:
                                if df.loc[k, 'Dur_Mins'] - delta_dur > 0:
                                    donor_idx = k
                                    break
                                    
                        if donor_idx is not None:
                            donor_pos = day_indices.index(donor_idx)
                            
                            for i in range(curr_pos + 1, donor_pos):
                                shift_k = day_indices[i]
                                df.loc[shift_k, 'Start_Mins'] += delta_dur
                                df.loc[shift_k, 'End_Mins'] += delta_dur
                                df.loc[shift_k, 'Start_Time'] = mins_to_time(df.loc[shift_k, 'Start_Mins'])
                                df.loc[shift_k, 'End_Time'] = mins_to_time(df.loc[shift_k, 'End_Mins'])
                                
                            df.loc[idx_to_edit, 'End_Mins'] = L_end_new
                            df.loc[idx_to_edit, 'End_Time'] = mins_to_time(L_end_new)
                            df.loc[idx_to_edit, 'Activity'] = final_act
                            df.loc[idx_to_edit, 'Sub_Activities'] = final_subs
                            df.loc[idx_to_edit, 'check_list'] = final_chks
                            df.loc[idx_to_edit, 'App'] = final_apps
                            df.loc[idx_to_edit, 'Locked'] = final_locked_str
                            df.loc[idx_to_edit, 'Dur_Mins'] = L_end_new - L_start_new
                            
                            df.loc[donor_idx, 'Start_Mins'] += delta_dur
                            df.loc[donor_idx, 'Start_Time'] = mins_to_time(df.loc[donor_idx, 'Start_Mins'])
                            df.loc[donor_idx, 'Dur_Mins'] = df.loc[donor_idx, 'End_Mins'] - df.loc[donor_idx, 'Start_Mins']
                            
                            auto_balance_success = True

                if not auto_balance_success:
                    if move_slide_chk and L_start_new != old_start_mins:
                        # --- MAGNETIC TELEPORT & SLIDE ENGINE ---
                        for day in target_days:
                            day_idx = df[df['Day'].str.title() == day].sort_values('Start_Mins').index.tolist()
                            idx_to_edit = None
                            for k in day_idx:
                                if df.loc[k, 'Start_Time'] == sel_start:
                                    idx_to_edit = k
                                    break
                            if idx_to_edit is None: continue

                            if L_start_new < old_start_mins:
                                # Moving UPWARD -> Pull intermediate tasks DOWN
                                shift_down_mins = L_end_new - L_start_new
                                for k in day_idx:
                                    if k == idx_to_edit: continue
                                    if str(df.loc[k, 'Locked']).title() == 'Yes': continue
                                    t_start = df.loc[k, 'Start_Mins']
                                    if t_start >= L_start_new and t_start < old_start_mins:
                                        df.loc[k, 'Start_Mins'] += shift_down_mins
                                        df.loc[k, 'End_Mins'] += shift_down_mins
                                        df.loc[k, 'Start_Time'] = mins_to_time(df.loc[k, 'Start_Mins'])
                                        df.loc[k, 'End_Time'] = mins_to_time(df.loc[k, 'End_Mins'])
                            else:
                                # Moving DOWNWARD -> Pull intermediate tasks UP
                                shift_up_mins = old_dur
                                for k in day_idx:
                                    if k == idx_to_edit: continue
                                    if str(df.loc[k, 'Locked']).title() == 'Yes': continue
                                    t_start = df.loc[k, 'Start_Mins']
                                    if t_start >= old_end_mins and t_start < L_end_new:
                                        df.loc[k, 'Start_Mins'] -= shift_up_mins
                                        df.loc[k, 'End_Mins'] -= shift_up_mins
                                        df.loc[k, 'Start_Time'] = mins_to_time(df.loc[k, 'Start_Mins'])
                                        df.loc[k, 'End_Time'] = mins_to_time(df.loc[k, 'End_Mins'])

                            # Update the edited task to its new Location
                            df.loc[idx_to_edit, 'Start_Time'] = new_start_txt.strip()
                            df.loc[idx_to_edit, 'End_Time'] = new_end_txt.strip()
                            df.loc[idx_to_edit, 'Activity'] = final_act
                            df.loc[idx_to_edit, 'Sub_Activities'] = final_subs
                            df.loc[idx_to_edit, 'check_list'] = final_chks
                            df.loc[idx_to_edit, 'App'] = final_apps
                            df.loc[idx_to_edit, 'Start_Mins'] = L_start_new
                            df.loc[idx_to_edit, 'End_Mins'] = L_end_new
                            df.loc[idx_to_edit, 'Locked'] = final_locked_str
                            
                            new_remainder_rows = []
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
                    else:
                        # --- SMART BUILDER GAP-FILL ENGINE (Replaces Standard Overwrite) ---
                        new_remainder_rows = []
                        
                        for day in target_days:
                            row_mask = (df['Day'].str.title() == day) & (df['Start_Time'] == sel_start)
                            if not row_mask.any(): continue
                            idx_to_edit = df[row_mask].index[0]
                            
                            old_start_mins = df.loc[idx_to_edit, 'Start_Mins']
                            old_end_mins = df.loc[idx_to_edit, 'End_Mins']
                            
                            # 1. Define Vacated Gap(s) Left Behind
                            vacated_intervals = []
                            if L_start_new >= old_end_mins or L_end_new <= old_start_mins:
                                vacated_intervals.append((old_start_mins, old_end_mins))
                            else:
                                if L_start_new > old_start_mins:
                                    vacated_intervals.append((old_start_mins, L_start_new))
                                if L_end_new < old_end_mins:
                                    vacated_intervals.append((L_end_new, old_end_mins))
                                    
                            # 2. Update the Target Block (Overwrite Destination)
                            df.loc[idx_to_edit, 'Start_Time'] = new_start_txt.strip()
                            df.loc[idx_to_edit, 'End_Time'] = new_end_txt.strip()
                            df.loc[idx_to_edit, 'Activity'] = final_act
                            df.loc[idx_to_edit, 'Sub_Activities'] = final_subs
                            df.loc[idx_to_edit, 'check_list'] = final_chks
                            df.loc[idx_to_edit, 'App'] = final_apps
                            df.loc[idx_to_edit, 'Start_Mins'] = L_start_new
                            df.loc[idx_to_edit, 'End_Mins'] = L_end_new
                            df.loc[idx_to_edit, 'Locked'] = final_locked_str
                            
                            # 3. Clip existing tasks around the new destination
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

                            # 4. Calculate Live vs Expected for the Day to find deficits
                            day_type = "WEEK DAYS"
                            if day.title() == "Saturday": day_type = "SATURDAY/HALF WORKING DAY"
                            elif day.title() == "Sunday": day_type = "SUNDAY"
                            elif day.title() == "Holiday": day_type = "HOLIDAY"
                            
                            exp_df = act_master_df[(act_master_df['Day_Type'] == day_type) & (act_master_df['Sub_Activity'] != "")]
                            expected = {}
                            for _, r in exp_df.iterrows():
                                k = (str(r['Activity']).strip().upper(), str(r['Sub_Activity']).strip())
                                expected[k] = expected.get(k, 0) + int(r['Duration_Mins'])
                                
                            live_dict = {}
                            temp_rows = []
                            for idx in day_idx:
                                if idx == idx_to_edit: continue
                                if df.loc[idx, 'End_Mins'] > df.loc[idx, 'Start_Mins']:
                                    temp_rows.append(df.loc[idx].to_dict())
                            temp_rows.append(df.loc[idx_to_edit].to_dict())
                            temp_rows.extend(new_remainder_rows)
                            
                            for r in temp_rows:
                                if r['Day'].title() != day.title(): continue
                                dur = r['End_Mins'] - r['Start_Mins']
                                if dur <= 0: continue
                                subs = [x.strip() for x in str(r['Sub_Activities']).split(',') if x.strip()]
                                act = str(r['Activity']).strip().upper()
                                for s in subs:
                                    k = (act, s)
                                    live_dict[k] = live_dict.get(k, 0) + dur

                            deficits = []
                            for k, exp_mins in expected.items():
                                l_mins = live_dict.get(k, 0)
                                if exp_mins > l_mins:
                                    deficits.append({'act': k[0], 'sub': k[1], 'deficit': exp_mins - l_mins})

                            # 5. Fill Vacated Intervals with Deficit Tasks
                            for v_start, v_end in vacated_intervals:
                                curr_start = v_start
                                for d_item in deficits:
                                    if curr_start >= v_end: break
                                    if d_item['deficit'] <= 0: continue
                                    
                                    fill_mins = min(d_item['deficit'], v_end - curr_start)
                                    chunk_end = curr_start + fill_mins
                                    
                                    new_remainder_rows.append({
                                        "Day": day,
                                        "Start_Time": mins_to_time(curr_start),
                                        "End_Time": mins_to_time(chunk_end),
                                        "Start_Mins": curr_start,
                                        "End_Mins": chunk_end,
                                        "Activity": d_item['act'],
                                        "Sub_Activities": d_item['sub'],
                                        "check_list": "",
                                        "App": "",
                                        "Locked": ""
                                    })
                                    d_item['deficit'] -= fill_mins
                                    curr_start = chunk_end
                                        
                        if new_remainder_rows:
                            df = pd.concat([df, pd.DataFrame(new_remainder_rows)], ignore_index=True)
                        
                # Final Save execution
                df['Dur_Mins'] = df['End_Mins'] - df['Start_Mins']
                df = df[df['Dur_Mins'] > 0].copy()
                df['Duration'] = df['Dur_Mins'].apply(lambda x: f"{int(x)//60:02d}:{int(x)%60:02d}")
                df = sort_routine_df(df)
                df = auto_adjust_schedule(df)
                df = df[["Day", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list", "App", "Locked"]]
                
                with st.spinner("Healing Overlaps and Saving to Google Sheets..."):
                    routine_sheet = get_sheet("routine_master")
                    routine_sheet.clear()
                    routine_sheet.update(values=[df.columns.values.tolist()] + df.values.tolist(), range_name="A1")
                    get_routine_data.clear()
                    st.session_state.routine_df = df
                    st.session_state.unsaved_sort = False
                    st.session_state.active_slot_start = mins_to_time(L_start_new)
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
        st.markdown("#### ➕ 5. Add a Single Time Slot")
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
        st.markdown("#### ⚡ 6. Auto-Generate Day Schedule")
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
