# ==========================================
# 8. LIVE ROUTINE TRACKER BANNER (CARD UI)
# ==========================================
def render_tracker():
    st.markdown("#### ⏱️ My Live Class")
    
    utc_now = datetime.now(timezone.utc)
    now = utc_now + timedelta(hours=5, minutes=30)
    curr_time = now.time()
    tdy = now.strftime('%A')
    curr_date_str = now.strftime('%d-%m-%Y')
    
    rout = fetch_routine_data()
    ll = fetch_leave_data()
    mc = TEACHER_INITIALS.get(st.session_state.user_name, st.session_state.user_name)
    
    is_fully_on_leave = False
    given_away_slots = []
    leave_type = ""
    
    if not ll.empty and 'Date' in ll.columns and 'Teacher' in ll.columns:
        user_leave = ll[(ll['Date'].astype(str).str.strip() == curr_date_str) & (ll['Teacher'].astype(str).str.strip() == st.session_state.user_name)]
        if not user_leave.empty:
            leave_type = str(user_leave.iloc[0].get('Type', 'Leave'))
            if leave_type in ['Class Shift / Internal Duty', 'Half Day']:
                given_away_slots = [a.split(": ")[0].strip() for a in str(user_leave.iloc[0].get('Detailed_Sub_Log', '')).split(" | ") if ": " in a and "None" not in a]
            else:
                is_fully_on_leave = True
            
    if is_fully_on_leave:
        st.warning(f"🏖️ You are marked on leave today ({leave_type}). Regular classes are hidden.")
        return

    ms = rout[(rout['Teacher'] == mc) & (rout['Day'] == tdy)].copy() if not rout.empty else pd.DataFrame()
    if not ms.empty:
        ms['Is_Sub'] = False
        if given_away_slots:
            ms = ms[~ms['Start_Time'].astype(str).str.strip().isin(given_away_slots)]
    
    sd = []
    if not ll.empty and 'Date' in ll.columns and not rout.empty:
        for _, r in ll[ll['Date'].astype(str).str.strip() == curr_date_str].iterrows():
            sub_log = str(r.get('Detailed_Sub_Log', ''))
            absent_teacher = str(r.get('Teacher', '')).strip()
            absent_initials = TEACHER_INITIALS.get(absent_teacher, absent_teacher)
            
            for item in sub_log.split(" | "):
                if ": " in item:
                    slot, sub_n = item.rsplit(": ", 1)
                    clean_sub_n = sub_n.replace('✅', '').replace('⚠️', '').replace('⛔', '').replace('🚫', '').strip()
                    if clean_sub_n == st.session_state.user_name:
                        oc = rout[(rout['Teacher'] == absent_initials) & (rout['Day'] == tdy) & (rout['Start_Time'].astype(str).str.strip() == slot.strip())]
                        if not oc.empty:
                            rx = oc.iloc[0]
                            sd.append({
                                'Start_Time': rx['Start_Time'],
                                'End_Time': rx['End_Time'],
                                'Class': rx['Class'],
                                'Section': rx.get('Section', 'A'),
                                'Subject': f"🔄 {rx['Subject']} (Sub for {absent_initials})",
                                'Teacher': mc,
                                'Day': tdy,
                                'Is_Sub': True
                            })
    
    if sd:
        ms = pd.concat([ms, pd.DataFrame(sd)], ignore_index=True)
    
    prev_rows, curr_rows, next_rows = [], [], []
    
    if not ms.empty:
        ms['Start_Obj'] = ms['Start_Time'].apply(parse_time_safe)
        ms['End_Obj'] = ms['End_Time'].apply(parse_time_safe)
        ms = ms.dropna(subset=['Start_Obj', 'End_Obj']).sort_values('Start_Obj')
        
        past_slots = ms[ms['End_Obj'] < curr_time]['Start_Obj']
        latest_past_slot = past_slots.max() if not past_slots.empty else None
        
        future_slots = ms[ms['Start_Obj'] > curr_time]['Start_Obj']
        earliest_future_slot = future_slots.min() if not future_slots.empty else None
        
        for _, r in ms.iterrows():
            st_obj = r['Start_Obj']
            et_obj = r['End_Obj']
            
            if st_obj <= curr_time <= et_obj:
                curr_rows.append(r)
            elif latest_past_slot and st_obj == latest_past_slot and et_obj < curr_time:
                prev_rows.append(r)
            elif earliest_future_slot and st_obj == earliest_future_slot:
                next_rows.append(r)
                
    # Function to generate the HTML for a single compact card (Compressed to prevent Markdown Code-Block rendering)
    def generate_card_html(label, rows_list, css_class):
        if not rows_list:
            return f"<div class='tracker-card {css_class}'><div class='tc-label'>{label}</div><div class='tc-time'>---</div><div class='tc-details' style='color: #adb5bd;'>No Class Scheduled</div></div>"
        
        r = rows_list[0]
        sub_text = "<br><span style='font-size:12px; font-weight:bold; color:#d9534f;'>(SUBSTITUTION)</span>" if r.get('Is_Sub', False) else ""
        time_str = f"{r.get('Start_Time', '')} - {r.get('End_Time', '')}" if 'End_Time' in r else str(r.get('Start_Time', ''))
        details = f"Class {r.get('Class', '')} '{r.get('Section', 'A')}'<br><strong>{r.get('Subject', '')}</strong>{sub_text}"
        
        return f"<div class='tracker-card {css_class}'><div class='tc-label'>{label}</div><div class='tc-time'>{time_str}</div><div class='tc-details'>{details}</div></div>"

    # Injecting the CSS and HTML for the 3-Card Layout (Compressed to prevent Markdown Code-Block rendering)
    html_content = f"""<style>
    .tracker-container {{ display: flex; gap: 15px; width: 100%; margin-bottom: 25px; flex-wrap: wrap; }}
    .tracker-card {{ flex: 1 1 250px; padding: 15px 20px; border-radius: 12px; text-align: center; display: flex; flex-direction: column; justify-content: center; transition: transform 0.2s ease-in-out; }}
    .tracker-card:hover {{ transform: translateY(-2px); }}
    .tc-label {{ font-size: 13px; font-weight: 800; text-transform: uppercase; margin-bottom: 10px; letter-spacing: 0.5px; }}
    .tc-time {{ font-size: 22px; font-weight: 900; margin-bottom: 8px; font-family: monospace; }}
    .tc-details {{ font-size: 15px; line-height: 1.5; }}
    .card-past {{ background-color: #e2e3e5; color: #6c757d; border-left: 6px solid #adb5bd; box-shadow: inset 0 0 10px rgba(0,0,0,0.02); opacity: 0.85; }}
    .card-current {{ background-color: #d4edda; color: #155724; border-left: 6px solid #28a745; border: 1px solid #c3e6cb; box-shadow: 0 4px 12px rgba(40, 167, 69, 0.15); }}
    .card-future {{ background-color: #f8f9fa; color: #495057; border-left: 6px solid #0d6efd; border: 1px solid #e9ecef; box-shadow: 0 2px 4px rgba(0,0,0,0.03); }}
    </style>
    <div class="tracker-container">
    {generate_card_html("⬅️ Finished", prev_rows, "card-past")}
    {generate_card_html("🟢 Ongoing Now", curr_rows, "card-current")}
    {generate_card_html("➡️ Coming Up", next_rows, "card-future")}
    </div>"""
    
    st.markdown(html_content, unsafe_allow_html=True)
