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

st.set_page_config(page_title="Routine Editor", page_icon="⚙️", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 2rem; padding-bottom: 2rem;}
    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
        border-radius: 0px !important;
        border: 1px solid #cccccc !important;
        background-color: #ffffff !important;
        box-shadow: none !important;
    }
    div[data-testid="metric-container"] {
        text-align: center; 
        background-color: #f0f2f6; 
        padding: 10px; 
        border-radius: 10px; 
        margin-bottom: 15px;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# Database Connection
# ==========================================
@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

def get_sheet(tab_name):
    return init_connection().open("MY ROUTINE 2026").worksheet(tab_name)

@st.cache_data(ttl=300) 
def get_routine_data():
    data = get_sheet("routine_master").get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    while df.shape[1] < 7: df[df.shape[1]] = ""
    df = df.iloc[:, :7]
    df.columns = ["Day", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list"]
    df = df[df["Day"].astype(str).str.strip() != ""]
    return df

def parse_duration_to_minutes(dur_str):
    try:
        h, m = map(int, str(dur_str).strip().split(':'))
        return (h * 60) + m
    except: return 0

# ==========================================
# Main App UI
# ==========================================
try:
    df = get_routine_data()
    now = datetime.now()
    current_day = now.strftime('%A')
    days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "Holiday"]

    col_title, col_sync = st.columns([8, 2])
    with col_title: st.markdown("<h3 style='color: #555; margin-top: 0px;'>📅 Smart Schedule Manager</h3>", unsafe_allow_html=True)
    with col_sync:
        if st.button("🔄 Sync Editor", use_container_width=True):
            get_routine_data.clear()
            st.toast("Synced!")
            time.sleep(1.0)
            st.rerun()

    with st.expander("🛠️ Advanced Tools: Batch Add, Replace & Free Time", expanded=False):
        tool_mode = st.radio("Select Tool:", ["🔍 Find Free Time", "➕ Batch Add Task", "🔄 Find & Replace"], horizontal=True)
        
        if tool_mode == "🔍 Find Free Time":
            st.markdown("#### Find Gaps in Your Routine")
            free_day = st.selectbox("Select Day to Analyze", days_of_week, key="free_day")
            day_df_free = df[df['Day'].str.strip().str.title() == free_day.title()].copy()
            
            if not day_df_free.empty:
                time_blocks = []
                for _, r in day_df_free.iterrows():
                    try:
                        st_m = int(r['Start_Time'].split(':')[0])*60 + int(r['Start_Time'].split(':')[1])
                        et_m = 24 * 60 if r['End_Time'].strip() in ['0:00', '00:00'] else int(r['End_Time'].split(':')[0])*60 + int(r['End_Time'].split(':')[1])
                        time_blocks.append((st_m, et_m, r['Activity']))
                    except: pass
                
                time_blocks.sort(key=lambda x: x[0])
                free_slots = []
                current_min = 0
                for block in time_blocks:
                    if block[0] > current_min: free_slots.append((current_min, block[0]))
                    current_min = max(current_min, block[1])
                if current_min < 24 * 60: free_slots.append((current_min, 24 * 60))
                    
                if free_slots:
                    st.success(f"Found {len(free_slots)} free time slots on {free_day}:")
                    for start, end in free_slots:
                        s_str = datetime.strptime(f"{start//60:02d}:{start%60:02d}", '%H:%M').strftime('%I:%M %p')
                        e_str = "12:00 AM" if end == 24*60 else datetime.strptime(f"{end//60:02d}:{end%60:02d}", '%H:%M').strftime('%I:%M %p')
                        st.markdown(f"- **{s_str} to {e_str}** ({end - start} mins available)")
                else: st.info("This day is completely fully scheduled!")
            else: st.info("No routine set for this day. The whole day is free!")

        elif tool_mode == "➕ Batch Add Task":
            st.markdown("#### Add Task to Multiple Days")
            b_days = st.multiselect("Select Days", days_of_week, default=[current_day], key="b_days")
            col1, col2 = st.columns(2)
            with col1: b_start = st.time_input("Start Time", value=datetime.strptime('09:00', '%H:%M').time(), key="b_start")
            with col2: b_end = st.time_input("End Time", value=datetime.strptime('10:00', '%H:%M').time(), key="b_end")
            b_act = st.text_input("Activity Name (e.g. PYTHON CODING)").upper()
            b_sub = st.text_input("Sub-Activities (comma separated)")
            b_chk = st.text_input("Checklist (comma separated)")
            b_overwrite = st.checkbox("⚠️ Overwrite existing tasks in this time slot?", value=False)
            
            if st.button("Apply to Selected Days", type="primary"):
                if not b_days or not b_act: st.error("Please provide both Days and an Activity Name.")
                else:
                    ns_min, ne_min = b_start.hour * 60 + b_start.minute, b_end.hour * 60 + b_end.minute
                    if ne_min == 0: ne_min = 24 * 60
                    
                    if ne_min <= ns_min: st.error("End time must be after start time.")
                    else:
                        full_df = df.copy()
                        rows_to_keep = []
                        for _, r in full_df.iterrows():
                            if str(r['Day']).strip().title() in [d.title() for d in b_days] and b_overwrite:
                                try:
                                    rs_min = int(r['Start_Time'].split(':')[0])*60 + int(r['Start_Time'].split(':')[1])
                                    re_min = 24*60 if r['End_Time'].strip() in ['0:00', '00:00'] else int(r['End_Time'].split(':')[0])*60 + int(r['End_Time'].split(':')[1])
                                    if max(ns_min, rs_min) < min(ne_min, re_min): continue 
                                except: pass
                            rows_to_keep.append(r)
                        
                        filtered_df = pd.DataFrame(rows_to_keep, columns=full_df.columns)
                        new_rows = [{"Day": d, "Start_Time": b_start.strftime('%H:%M'), "End_Time": b_end.strftime('%H:%M'), "Duration": f"{(ne_min - ns_min)//60}:{(ne_min - ns_min)%60:02d}", "Activity": b_act, "Sub_Activities": b_sub, "check_list": b_chk} for d in b_days]
                        final_df = pd.concat([filtered_df, pd.DataFrame(new_rows)], ignore_index=True)
                        
                        day_map = {d: i for i, d in enumerate(days_of_week)}
                        final_df['Day_Idx'] = final_df['Day'].str.title().map(day_map)
                        final_df['ST_Min'] = final_df['Start_Time'].apply(lambda x: int(x.split(':')[0])*60 + int(x.split(':')[1]) if ':' in x else 0)
                        final_df = final_df.sort_values(['Day_Idx', 'ST_Min']).drop(columns=['Day_Idx', 'ST_Min'])
                        
                        routine_sheet = get_sheet("routine_master")
                        routine_sheet.clear()
                        routine_sheet.update(values=[final_df.columns.values.tolist()] + final_df.values.tolist(), range_name="A1")
                        
                        get_routine_data.clear()
                        st.success(f"Added '{b_act}' to {len(b_days)} days!")
                        time.sleep(1.5)
                        st.rerun()

        elif tool_mode == "🔄 Find & Replace":
            st.markdown("#### Replace Items Across Schedule")
            r_days = st.multiselect("Select Days to Search", days_of_week, default=days_of_week, key="r_days")
            target_col = st.radio("What do you want to replace?", ["Activity", "Sub-Activity", "Checklist"], horizontal=True)
            
            if target_col == "Activity": unique_vals = sorted(list(set([a.strip().upper() for a in df['Activity'] if a.strip()])))
            elif target_col == "Sub-Activity":
                all_items = []
                for val in df['Sub_Activities']: all_items.extend([s.strip() for s in str(val).split(',') if s.strip()])
                unique_vals = sorted(list(set(all_items)))
            else: 
                all_items = []
                for val in df['check_list']: all_items.extend([c.strip() for c in str(val).split(',') if c.strip()])
                unique_vals = sorted(list(set(all_items)))
            
            old_val = st.selectbox("Target Item to Replace", unique_vals) if unique_vals else None
            new_val = st.text_input("New Item Name")
            
            if st.button("Replace Item", type="primary"):
                if not r_days or not new_val or not old_val: st.error("Please fill all fields.")
                else:
                    full_df = df.copy()
                    count = 0
                    for idx, r in full_df.iterrows():
                        if str(r['Day']).strip().title() in [d.title() for d in r_days]:
                            if target_col == "Activity" and str(r['Activity']).strip().upper() == old_val.upper():
                                full_df.at[idx, 'Activity'] = new_val.upper()
                                count += 1
                            elif target_col in ["Sub-Activity", "Checklist"]:
                                col_name = "Sub_Activities" if target_col == "Sub-Activity" else "check_list"
                                items = [s.strip() for s in str(r[col_name]).split(',') if s.strip()]
                                if old_val in items:
                                    full_df.at[idx, col_name] = ", ".join([new_val if x == old_val else x for x in items])
                                    count += 1
                    
                    if count > 0:
                        routine_sheet = get_sheet("routine_master")
                        routine_sheet.clear()
                        routine_sheet.update(values=[full_df.columns.values.tolist()] + full_df.values.tolist(), range_name="A1")
                        get_routine_data.clear()
                        st.success(f"Replaced {count} instances of '{old_val}'!")
                        time.sleep(1.5)
                        st.rerun()
                    else: st.info(f"No instances found.")

    st.markdown("---")
    target_day = st.selectbox("Select Day to Edit Manually", days_of_week, index=days_of_week.index(current_day if current_day in days_of_week else "Monday"))
    
    target_full_df = df[df['Day'].str.strip().str.title() == target_day.title()].copy()
    
    if not target_full_df.empty:
        edit_df = target_full_df[['Start_Time', 'End_Time', 'Activity', 'Sub_Activities', 'check_list']].copy()
        def convert_to_time(t_str):
            try: return datetime.strptime('00:00', '%H:%M').time() if t_str.strip() == '0:00' else datetime.strptime(t_str.strip(), '%H:%M').time()
            except: return datetime.strptime('00:00', '%H:%M').time()
        edit_df['Start_Time'] = edit_df['Start_Time'].apply(convert_to_time)
        edit_df['End_Time'] = edit_df['End_Time'].apply(convert_to_time)
        
        edited_schedule = st.data_editor(
            edit_df,
            column_config={
                "Start_Time": st.column_config.TimeColumn("Start", format="HH:mm", step=60, required=True),
                "End_Time": st.column_config.TimeColumn("End", format="HH:mm", step=60, required=True),
                "Activity": st.column_config.TextColumn("Activity", required=True),
                "Sub_Activities": st.column_config.TextColumn("Sub List"),
                "check_list": st.column_config.TextColumn("Checklist")
            },
            hide_index=True, use_container_width=True, num_rows="dynamic", key="schedule_editor"
        )
        
        if st.button(f"💾 Save Changes for {target_day}", use_container_width=True):
            with st.spinner("Syncing to Google Sheets..."):
                new_rows = []
                for _, row in edited_schedule.iterrows():
                    if pd.isna(row['Activity']) or str(row['Activity']).strip() == "": continue
                    if pd.isna(row['Start_Time']) or pd.isna(row['End_Time']): continue
                    
                    s_dt = datetime.combine(now.date(), row['Start_Time'])
                    e_dt = datetime.combine(now.date(), row['End_Time'])
                    if row['End_Time'].strftime('%H:%M') in ['00:00', '0:00'] or e_dt < s_dt: e_dt = e_dt.replace(day=e_dt.day + 1)
                    h, m = divmod((e_dt - s_dt).seconds, 3600)
                    
                    sub_act = "" if str(row.get('Sub_Activities', '')).strip() == 'nan' else str(row.get('Sub_Activities', '')).strip()
                    chk_act = "" if str(row.get('check_list', '')).strip() == 'nan' else str(row.get('check_list', '')).strip()
                    new_rows.append([target_day, row['Start_Time'].strftime('%H:%M'), row['End_Time'].strftime('%H:%M'), f"{h}:{m//60:02d}", str(row['Activity']).strip().upper(), sub_act, chk_act])

                full_df = df.copy()
                other_days_df = full_df[full_df['Day'].str.strip().str.title() != target_day.title()]
                final_df = pd.concat([other_days_df, pd.DataFrame(new_rows, columns=["Day", "Start_Time", "End_Time", "Duration", "Activity", "Sub_Activities", "check_list"])], ignore_index=True)
                
                routine_sheet = get_sheet("routine_master")
                routine_sheet.clear() 
                routine_sheet.update(values=[final_df.columns.values.tolist()] + final_df.values.tolist(), range_name="A1")
                get_routine_data.clear() 
                st.success("Schedule successfully updated!")
                time.sleep(1.5)
                st.rerun()

        target_full_df['Total_Minutes'] = target_full_df['Duration'].apply(parse_duration_to_minutes)
        schedule_summary = target_full_df.groupby('Activity')['Total_Minutes'].sum().sort_values(ascending=False)
        st.markdown("<br><h5>📈 Scheduled Summary</h5>", unsafe_allow_html=True)
        cols_sched = st.columns(min(len(schedule_summary), 4))
        for idx, (act, total_mins) in enumerate(schedule_summary.items()):
            with cols_sched[idx % 4]: st.metric(label=act, value=f"{int(total_mins // 60)}:{int(total_mins % 60):02d}")
    else: st.info(f"No routine scheduled for {target_day}. Add one using the tools above.")

except Exception as e: st.error(f"System Error: {e}")
