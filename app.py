import streamlit as st
import pandas as pd
import os
from datetime import datetime, time
import qrcode
from fpdf import FPDF
from streamlit_qrcode_scanner import qrcode_scanner

# --- 1. CONFIGURATION & STYLING ---
st.set_page_config(page_title="BPS Digital", page_icon="🏫", layout="centered")

st.markdown("""
    <style>
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
        [data-testid="stSidebar"] {display: none;}
        .block-container { padding-top: 1rem; max-width: 650px; }
        .school-title { font-size: 26px !important; font-weight: 900 !important; color: #1a1a1a; margin: 0; line-height: 1.1; }
        .bps-subtext { font-size: 14px; font-weight: 800; color: #007bff; margin-top: -5px; letter-spacing: 1px; }
        .summary-card { background-color: #ffffff; border: 2px solid #007bff; border-radius: 15px; padding: 20px; margin-bottom: 20px; box-shadow: 0px 4px 10px rgba(0,0,0,0.05); }
        .summary-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f0f2f6; font-size: 18px; }
        .summary-val { color: #007bff; font-weight: 900; font-size: 22px; }
        .stButton>button { width: 100%; border-radius: 12px; height: 3.5em; background-color: #007bff; color: white; font-weight: bold; border: none; }
        .warning-box { background-color: #fff3cd; color: #856404; padding: 12px; border-radius: 10px; border: 1px solid #ffeeba; margin-bottom: 15px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATA INITIALIZATION & LOADING ---
def init_files():
    files = {
        'mdm_log.csv': ['Date', 'Teacher', 'Class', 'Roll', 'Name', 'Time'],
        'student_attendance_master.csv': ['Date', 'Class', 'Roll', 'Name', 'Status'],
        'shoe_log.csv': ['Roll', 'Name', 'Class', 'Received', 'Date', 'Remark'],
        'teacher_leave.csv': ['Date', 'Teacher', 'Type', 'Substitute'], # Ensure this exists
        'notice.txt': 'Welcome to BPS Digital'
    }
    for f, cols in files.items():
        if not os.path.exists(f):
            if f.endswith('.csv'): pd.DataFrame(columns=cols).to_csv(f, index=False)
            else: 
                with open(f, 'w') as txt: txt.write(cols)

init_files()

# Time & Date Logic
now = datetime.now()
curr_date_str = now.strftime("%d-%m-%Y")
curr_time = now.time()
MDM_START, MDM_END = time(11, 15), time(12, 30)

TEACHER_CREDS = {
    "TAPASI RANA": "tr26", "SUJATA BISWAS ROTHA": "sbr26", "ROHINI SINGH": "rs26",
    "UDAY NARAYAN JANA": "unj26", "BIMAL KUMAR PATRA": "bkp26", "SUSMITA PAUL": "sp26",
    "TAPAN KUMAR MANDAL": "tkm26", "MANJUMA KHATUN": "mk26"
}

def get_csv(file):
    if os.path.exists(file): 
        try: return pd.read_csv(file)
        except: return pd.DataFrame()
    return pd.DataFrame()

# --- 3. BRANDED HEADER ---
hcol1, hcol2 = st.columns([1, 4])
with hcol1:
    if os.path.exists("logo.png"): st.image("logo.png", width=80)
    st.markdown('<p class="bps-subtext">BPS Digital</p>', unsafe_allow_html=True)
with hcol2:
    st.markdown('<p class="school-title">Bhagyabantapur<br>Primary School</p>', unsafe_allow_html=True)
st.divider()

# --- 4. NAVIGATION ---
page = st.selectbox("CHOOSE ACTION", ["Select Action...", "Assistant Teacher MDM Entry", "Admin (Attendance & HT Tools)", "📅 View Holiday List"])

# ==========================================
# MODULE: HOLIDAY LIST
# ==========================================
if page == "📅 View Holiday List":
    st.subheader("🗓️ School Holiday Calendar")
    h_df = get_csv('holidays.csv')
    if not h_df.empty: st.table(h_df)
    else: st.info("No holiday records uploaded.")

# ==========================================
# MODULE: ASSISTANT TEACHER (MDM ENTRY)
# ==========================================
elif page == "Assistant Teacher MDM Entry":
    teacher_options = ["Select Your Name..."] + list(TEACHER_CREDS.keys())
    t_name_select = st.selectbox("Teacher Name", teacher_options)
    
    if t_name_select != "Select Your Name...":
        t_pw = st.text_input("Password", type="password")
        
        if t_pw == TEACHER_CREDS.get(t_name_select):
            h_df = get_csv('holidays.csv')
            is_h = not h_df[h_df['Date'] == curr_date_str].empty if not h_df.empty else False
            
            if is_h or now.strftime('%A') == 'Sunday':
                st.warning("🏖️ School is closed today. Data entry is disabled.")
            else:
                if os.path.exists('notice.txt'):
                    with open('notice.txt', 'r') as f: st.info(f"📢 NOTICE: {f.read()}")
                
                at_tabs = st.tabs(["🍱 MDM Entry", "⏳ Routine", "📃 Leave Status"])

                # --- MDM ENTRY ---
                with at_tabs[0]:
                    mdm_log = get_csv('mdm_log.csv')
                    already_sub = not mdm_log[(mdm_log['Date'] == curr_date_str) & (mdm_log['Teacher'] == t_name_select)].empty
                    
                    if already_sub:
                        st.success("✅ You have already submitted MDM for today.")
                    elif not (MDM_START <= curr_time <= MDM_END):
                        st.error("⏰ MDM Entry Closed. Allowed: 11:15 AM - 12:30 PM.")
                    else:
                        st.subheader("Student MDM Entry")
                        class_opts = ["Select Class...", "CLASS PP", "CLASS I", "CLASS II", "CLASS III", "CLASS IV", "CLASS V"]
                        sel_class = st.selectbox("Class", class_opts)
                        
                        if sel_class != "Select Class...":
                            students = get_csv('students.csv')
                            if not students.empty:
                                roster = students[students['Class'] == sel_class].copy()
                                if roster.empty:
                                    st.warning("No students found for this class.")
                                else:
                                    roster['Ate_MDM'] = False
                                    st.write("Scan ID or Check List:")
                                    qr_val = qrcode_scanner(key='at_qr')
                                    
                                    edited = st.data_editor(roster[['Roll', 'Name', 'Ate_MDM']], hide_index=True, use_container_width=True)
                                    
                                    if st.button("Submit MDM Entry"):
                                        ate = edited[edited['Ate_MDM'] == True]
                                        new_rows = []
                                        for _, r in ate.iterrows():
                                            new_rows.append({
                                                'Date': curr_date_str, 'Teacher': t_name_select, 
                                                'Class': sel_class, 'Roll': r['Roll'], 
                                                'Name': r['Name'], 'Time': now.strftime("%H:%M")
                                            })
                                        if new_rows:
                                            pd.DataFrame(new_rows).to_csv('mdm_log.csv', mode='a', index=False, header=False)
                                            st.balloons()
                                            st.success("MDM Submitted Successfully!")
                                        else: st.warning("No students selected.")

                # --- ROUTINE ---
                with at_tabs[1]:
                    st.subheader("Your Routine")
                    routine = get_csv('routine.csv')
                    if not routine.empty:
                        my_r = routine[routine['Teacher'] == t_name_select]
                        st.dataframe(my_r, hide_index=True, use_container_width=True)
                    else: st.info("Routine file not found.")

                # --- LEAVE STATUS (UPDATED WITH SL) ---
                with at_tabs[2]:
                    st.subheader("My Leave Record")
                    leave_log = get_csv('teacher_leave.csv')
                    
                    if not leave_log.empty:
                        my_leaves = leave_log[leave_log['Teacher'] == t_name_select]
                        
                        # Separate CL and SL counts
                        cl_count = len(my_leaves[my_leaves['Type'] == 'CL'])
                        sl_count = len(my_leaves[my_leaves['Type'] == 'SL'])
                        
                        # Display Dual Metrics
                        col1, col2 = st.columns(2)
                        col1.metric("CL Remaining", f"{14 - cl_count} / 14")
                        col2.metric("SL (Duty) Taken", f"{sl_count}")
                        
                        st.write("History:")
                        st.dataframe(my_leaves, hide_index=True)
                    else:
                        st.metric("CL Remaining", "14 / 14")
                        st.info("No leave records found.")

# ==========================================
# MODULE: HEAD TEACHER (ADMIN)
# ==========================================
elif page == "Admin (Attendance & HT Tools)":
    admin_pw = st.text_input("Master Password", type="password")
    if admin_pw == "bpsAPP@2026":
        tabs = st.tabs(["📊 Summary", "📝 Attendance", "👨‍🏫 Leaves & Sub", "👟 Shoes", "🆔 Cards", "📢 Notice"])
        
        # --- SUMMARY ---
        with tabs[0]: 
            st.subheader(f"Status: {curr_date_str}")
            
            mdm_log = get_csv('mdm_log.csv')
            today_mdm = mdm_log[mdm_log['Date'] == curr_date_str]
            sub_teachers = today_mdm['Teacher'].unique() if not today_mdm.empty else []
            
            missing = [t for t in TEACHER_CREDS.keys() if t not in sub_teachers]
            h_df = get_csv('holidays.csv')
            is_h = not h_df[h_df['Date'] == curr_date_str].empty if not h_df.empty else False

            if missing and not is_h and now.strftime('%A') != 'Sunday':
                st.markdown(f"<div class='warning-box'>⚠️ Pending MDM Entry: {', '.join(missing)}</div>", unsafe_allow_html=True)

            att_master = get_csv('student_attendance_master.csv')
            if not att_master.empty:
                today = att_master[att_master['Date'] == curr_date_str]
                today_p = today[today['Status'] == True]
                
                pp_t = today_p[today_p['Class'] == 'CLASS PP'].shape[0]
                i_iv_t = today_p[today_p['Class'].isin(['CLASS I', 'CLASS II', 'CLASS III', 'CLASS IV'])].shape[0]
                v_t = today_p[today_p['Class'] == 'CLASS V'].shape[0]
                
                st.markdown(f"""
                <div class="summary-card">
                    <div class="summary-row"><span>Class PP</span><span class="summary-val">{pp_t}</span></div>
                    <div class="summary-row"><span>Class I - IV</span><span class="summary-val">{i_iv_t}</span></div>
                    <div class="summary-row"><span>Class V</span><span class="summary-val">{v_t}</span></div>
                    <div class="summary-row" style="border:none; margin-top:15px; background-color:#d4edda; padding:10px; border-radius:10px;">
                        <span style="font-weight:900;">GRAND TOTAL</span><span style="font-size:30px; font-weight:900;">{pp_t + i_iv_t + v_t}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else: st.info("No attendance marked today.")

        # --- STUDENT ATTENDANCE ---
        with tabs[1]:
            st.subheader("Mark Student Attendance")
            c_opts = ["Select Class...", "CLASS PP", "CLASS I", "CLASS II", "CLASS III", "CLASS IV", "CLASS V"]
            sel_c = st.selectbox("Class", c_opts, key='ht_att_c')
            
            if sel_c != "Select Class...":
                students = get_csv('students.csv')
                if not students.empty:
                    roster = students[students['Class'] == sel_c].copy()
                    if not roster.empty:
                        roster['Present'] = True
                        ed_att = st.data_editor(roster[['Roll', 'Name', 'Present']], hide_index=True, use_container_width=True)
                        if st.button(f"Save {sel_c} Attendance"):
                            recs = ed_att.copy()
                            save_df = pd.DataFrame({
                                'Date': curr_date_str, 'Class': sel_c,
                                'Roll': recs['Roll'], 'Name': recs['Name'], 'Status': recs['Present']
                            })
                            save_df.to_csv('student_attendance_master.csv', mode='a', index=False, header=False)
                            st.success("Saved!")

        # --- TEACHER LEAVES & SUBSTITUTION (UPDATED) ---
        with tabs[2]:
            st.subheader("Teacher Leave Overview")
            leave_log = get_csv('teacher_leave.csv')
            
            if not leave_log.empty:
                # Build Summary Table
                summary_data = []
                for t in TEACHER_CREDS.keys():
                    t_recs = leave_log[leave_log['Teacher'] == t]
                    cl_used = len(t_recs[t_recs['Type'] == 'CL'])
                    sl_used = len(t_recs[t_recs['Type'] == 'SL'])
                    summary_data.append({
                        "Teacher": t,
                        "CL Used": cl_used,
                        "CL Rem.": 14 - cl_used,
                        "SL (Duty)": sl_used
                    })
                st.dataframe(pd.DataFrame(summary_data), hide_index=True)
            
            st.divider()
            st.write("Mark New Absence / Duty")
            
            abs_t = st.selectbox("Teacher Name", ["Select..."] + list(TEACHER_CREDS.keys()))
            if abs_t != "Select...":
                # UPDATED: Select Type (CL or SL)
                l_type_raw = st.selectbox("Leave Type", ["CL (Casual Leave)", "SL (School Leave / Duty)", "Medical", "Other"])
                
                # Convert friendly name to code
                if "Casual" in l_type_raw: type_code = "CL"
                elif "School" in l_type_raw: type_code = "SL"
                else: type_code = l_type_raw
                
                sub_t = st.selectbox("Substitute", ["Internal/Staff"] + list(TEACHER_CREDS.keys()))
                
                if st.button("Confirm Record"):
                    new_l = pd.DataFrame([{
                        "Date": curr_date_str, 
                        "Teacher": abs_t, 
                        "Type": type_code, 
                        "Substitute": sub_t
                    }])
                    new_l.to_csv('teacher_leave.csv', mode='a', index=False, header=False)
                    st.success(f"{type_code} recorded for {abs_t}")

        # --- SHOES ---
        with tabs[3]:
            st.subheader("Shoe Distribution")
            s_class = st.selectbox("Class", ["Select Class...", "CLASS PP", "CLASS I", "CLASS II", "CLASS III", "CLASS IV", "CLASS V"], key='shoe_c')
            
            if s_class != "Select Class...":
                students = get_csv('students.csv')
                shoe_log = get_csv('shoe_log.csv')
                if not students.empty:
                    roster = students[students['Class'] == s_class].copy()
                    rec_rolls = shoe_log[shoe_log['Class'] == s_class]['Roll'].tolist() if not shoe_log.empty else []
                    
                    roster['Received_Before'] = roster['Roll'].isin(rec_rolls)
                    roster['Mark_Received'] = False
                    roster['Remark'] = ""
                    
                    ed_shoe = st.data_editor(roster[['Roll', 'Name', 'Received_Before', 'Mark_Received', 'Remark']], disabled=['Roll', 'Name', 'Received_Before'], hide_index=True, use_container_width=True)
                    
                    if st.button("Update Shoe Records"):
                        new_rec = ed_shoe[ed_shoe['Mark_Received'] == True]
                        if not new_rec.empty:
                            save_s = pd.DataFrame({
                                'Roll': new_rec['Roll'], 'Name': new_rec['Name'], 'Class': s_class,
                                'Received': True, 'Date': curr_date_str, 'Remark': new_rec['Remark']
                            })
                            save_s.to_csv('shoe_log.csv', mode='a', index=False, header=False)
                            st.success("Updated successfully.")

        # --- ID CARDS ---
        with tabs[4]:
            st.subheader("Generate ID Cards")
            id_c = st.selectbox("Class", ["Select Class...", "CLASS PP", "CLASS I", "CLASS II", "CLASS III", "CLASS IV", "CLASS V"], key='id_c')
            if id_c != "Select Class...":
                students = get_csv('students.csv')
                if not students.empty:
                    roster = students[students['Class'] == id_c]
                    sel_stds = st.multiselect("Select Students", roster['Name'].tolist())
                    
                    if st.button("Download PDF"):
                        if sel_stds:
                            pdf = FPDF()
                            for name in sel_stds:
                                row = roster[roster['Name'] == name].iloc[0]
                                pdf.add_page()
                                pdf.set_font("Arial", 'B', 16)
                                pdf.cell(0, 10, "Bhagyabantapur Primary School", 0, 1, 'C')
                                pdf.set_font("Arial", '', 12)
                                pdf.ln(10)
                                pdf.cell(0, 10, f"Name: {row['Name']}", 0, 1)
                                pdf.cell(0, 10, f"Class: {row['Class']} | Roll: {row['Roll']}", 0, 1)
                                
                                qr_data = f"{row['Roll']}-{row['Name']}-{row['Class']}"
                                qr = qrcode.make(qr_data)
                                qr.save("temp_qr.png")
                                pdf.image("temp_qr.png", x=150, y=30, w=40)
                            pdf_out = pdf.output(dest='S').encode('latin-1')
                            st.download_button("Download PDF", pdf_out, "ID_Cards.pdf", "application/pdf")

        # --- NOTICE ---
        with tabs[5]:
            st.subheader("Notice Board")
            if os.path.exists('notice.txt'):
                with open('notice.txt', 'r') as f: cur_n = f.read()
            else: cur_n = ""
            new_n = st.text_area("Message to Teachers", cur_n)
            if st.button("Update Notice"):
                with open('notice.txt', 'w') as f: f.write(new_n)
                st.success("Notice Published!")
