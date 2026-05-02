import streamlit as st, streamlit.components.v1 as components, pandas as pd, os, calendar, base64, re, concurrent.futures
from datetime import datetime, time, timedelta, timezone
from streamlit_qrcode_scanner import qrcode_scanner
import gspread
from gspread.exceptions import WorksheetNotFound
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import AuthorizedSession

st.set_page_config(page_title="BPS Digital", page_icon="🏫", layout="centered")

# --- BACK BUTTON (MUST BE RIGHT AFTER PAGE CONFIG) ---
if st.button("⬅️ Back to BPS Home", type="secondary"):
    st.switch_page("bps_dashboard.py")
st.write("---") 
# -----------------------------------------------------

def inject_beep_script():
    components.html("""
# ... the rest of your app continues exactly as you wrote it ...

def inject_beep_script():
    components.html("""
        <script>
            const doc = window.parent.document;
            if (!doc.getElementById("beep-listener-setup")) {
                doc.body.insertAdjacentHTML('beforeend', '<div id="beep-listener-setup" style="display:none;"></div>');
                doc.body.addEventListener('change', function(e) {
                    if (e.target && e.target.type === 'checkbox') {
                        const AudioContext = window.parent.AudioContext || window.parent.webkitAudioContext;
                        if (AudioContext) {
                            const ctx = new AudioContext();
                            const osc = ctx.createOscillator(), gainNode = ctx.createGain();
                            osc.type = 'sine'; osc.frequency.setValueAtTime(880, ctx.currentTime); 
                            gainNode.gain.setValueAtTime(0.1, ctx.currentTime);
                            gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.1);
                            osc.connect(gainNode); gainNode.connect(ctx.destination);
                            osc.start(); osc.stop(ctx.currentTime + 0.1);
                        }
                    }
                });
            }
        </script>""", height=0, width=0)
inject_beep_script()

def inject_security_css(user_name):
    wm = f"{user_name} - CONFIDENTIAL"
    st.markdown(f"""<style>
        body {{ user-select: none; -webkit-user-select: none; }}
        .watermark {{ position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; pointer-events: none; z-index: 9999; background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" viewBox="0 0 300 300"><text x="50" y="150" fill="rgba(200, 200, 200, 0.25)" font-size="20" transform="rotate(-45 150 150)" font-family="Arial, sans-serif">{wm}</text></svg>'); background-repeat: repeat; }}
        #MainMenu, footer, header {{visibility: hidden;}}
        [data-testid="stSidebar"] {{display: none;}}
        .block-container {{ padding-top: 1rem; max-width: 650px; overflow-x: hidden; }}
        .summary-card {{ background-color: #fff; border: 2px solid #007bff; border-radius: 15px; padding: 20px; margin-bottom: 20px; box-shadow: 0px 4px 10px rgba(0,0,0,0.05); }}
        .stButton>button {{ width: 100%; border-radius: 12px; height: 3.5em; background-color: #007bff; color: white; font-weight: bold; border: none; }}
        .routine-card {{ background-color: #f8f9fa; padding: 15px; border-radius: 10px; border-left: 5px solid #007bff; margin-bottom: 15px; border-right: 1px solid #ddd; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; }}
        .login-box {{ padding: 20px; border-radius: 15px; background-color: #f0f2f6; border: 1px solid #d1d5db; margin-top: 20px; }}
        .report-table {{ width: 100%; border-collapse: collapse; }} .report-table td, .report-table th {{ border: 1px solid #ddd; padding: 8px; text-align: center; }} .report-table th {{ background-color: #007bff; color: white; }}
        .att-badge {{ padding: 8px 12px; border-radius: 8px; font-weight: bold; font-size: 15px; display: block; text-align: center; margin-top: 5px; margin-bottom: 5px;}}
        .att-wait {{ background-color: #fff3cd; color: #856404; border: 1px solid #ffeeba; }} .att-done {{ background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
        .sub-card {{ background-color: #e3f2fd; padding: 10px; border-radius: 8px; margin-bottom: 5px; border-left: 4px solid #2196f3; }}
        .floating-counter {{ position: fixed; top: 15px; right: 15px; background: linear-gradient(135deg, #007bff, #0056b3); color: white; padding: 10px 20px; border-radius: 30px; z-index: 999999; font-size: 16px; font-weight: 900; box-shadow: 0px 4px 12px rgba(0,0,0,0.3); border: 2px solid #ffffff; pointer-events: none; transition: all 0.3s ease; }}
        @media (max-width: 768px) {{
            .floating-counter {{ top: 10px; right: 10px; font-size: 14px; padding: 8px 16px; }}
            .roster-container [data-testid="stHorizontalBlock"] {{ display: flex !important; flex-direction: row !important; flex-wrap: nowrap !important; align-items: center !important; width: 100% !important; }}
            .roster-container [data-testid="column"] {{ display: block !important; min-width: 0 !important; margin-top: 0 !important; padding: 0 4px !important; }}
            .roster-container [data-testid="column"]:nth-child(1) {{ flex: 0 0 55px !important; max-width: 55px !important; width: 55px !important; }}
            .roster-container [data-testid="column"]:nth-child(2) {{ flex: 1 1 0% !important; max-width: calc(100% - 150px) !important; width: auto !important; }}
            .roster-container [data-testid="column"]:nth-child(3) {{ flex: 0 0 95px !important; max-width: 95px !important; width: 95px !important; }}
            .roster-container .stCheckbox p {{ font-size: 13px !important; padding-left: 1.2rem !important; margin-bottom: 0px !important; line-height: 1.2 !important; }}
            .roster-container .stCheckbox {{ min-height: 1.2rem; }}
            .header-school-name {{ font-size: 18px !important; }}
        }}
    </style><script>document.addEventListener('contextmenu', e => e.preventDefault());</script><div class="watermark"></div>""", unsafe_allow_html=True)

USERS = {"admin": {"name": "SUKHAMAY KISKU", "role": "admin", "password": "bpsAPP@2026"}, "tr": {"name": "TAPASI RANA", "role": "teacher", "password": "tr26"}, "sbr": {"name": "SUJATA BISWAS ROTHA", "role": "teacher", "password": "sbr26"}, "rs": {"name": "ROHINI SINGH", "role": "teacher", "password": "rs26"}, "unj": {"name": "UDAY NARAYAN JANA", "role": "teacher", "password": "unj26"}, "bkp": {"name": "BIMAL KUMAR PATRA", "role": "teacher", "password": "bkp26"}, "sp": {"name": "SUSMITA PAUL", "role": "teacher", "password": "sp26"}, "tkm": {"name": "TAPAN KUMAR MANDAL", "role": "teacher", "password": "tkm26"}, "mk": {"name": "MANJUMA KHATUN", "role": "teacher", "password": "mk26"}}
TEACHER_INITIALS = {"SUKHAMAY KISKU": "SK", "TAPASI RANA": "TR", "SUJATA BISWAS ROTHA": "SBR", "ROHINI SINGH": "RS", "UDAY NARAYAN JANA": "UNJ", "BIMAL KUMAR PATRA": "BKP", "SUSMITA PAUL": "SP", "TAPAN KUMAR MANDAL": "TKM", "MANJUMA KHATUN": "MK"}
INV_TEACHER_INITIALS = {v: k for k, v in TEACHER_INITIALS.items()}
TEACHER_LIST = [u["name"] for k, u in USERS.items()]
CLASS_OPTIONS = ["Select Class...", "CLASS PP", "CLASS I", "CLASS II", "CLASS III", "CLASS IV", "CLASS V"]
ATTENDANCE_OPTIONS = ["Select Class...", "CLASS PP A", "CLASS I A", "CLASS II A", "CLASS III A", "CLASS IV A", "CLASS IV B", "CLASS V A"]

if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'user_role' not in st.session_state: st.session_state.user_role = None
if 'user_name' not in st.session_state: st.session_state.user_name = None
if 'scan_msg' not in st.session_state: st.session_state.scan_msg = None
if 'admin_scanned_keys' not in st.session_state: st.session_state.admin_scanned_keys = []
if 'admin_scan_msg' not in st.session_state: st.session_state.admin_scan_msg = None

@st.cache_resource
def get_google_credentials(): return Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.readonly"])

@st.cache_resource
def init_gsheets():
    try: return gspread.authorize(get_google_credentials()).open("BPS_Database")
    except: st.error("⚠️ Google Sheets Connection Failed!"); st.stop()

@st.cache_resource
def get_drive_session(): return AuthorizedSession(get_google_credentials())

sh = init_gsheets()

@st.cache_data(ttl=600) 
def fetch_sheet_data(sheet_name):
    try: return pd.DataFrame(sh.worksheet(sheet_name).get_all_records()).replace({'TRUE': True, 'FALSE': False, 'True': True, 'False': False}).infer_objects(copy=False)
    except: return pd.DataFrame()

def clear_sheet_cache(): fetch_sheet_data.clear(); get_notice.clear()

def append_sheet_df(sheet_name, df):
    if df.empty: return
    try: ws = sh.worksheet(sheet_name)
    except WorksheetNotFound: ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=20); ws.append_row(list(df.columns))
    except: st.error("⚠️ API Busy."); return
    try: ws.append_rows(df.fillna("").astype(str).values.tolist()); clear_sheet_cache()
    except: st.error("⚠️ Submit Failed.")

def overwrite_sheet_df(sheet_name, df):
    try: ws = sh.worksheet(sheet_name)
    except WorksheetNotFound: ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=20)
    except: return
    try: ws.clear(); df = df.fillna("").astype(str); ws.update(values=[df.columns.values.tolist()] + df.values.tolist(), range_name='A1') if not df.empty else None; clear_sheet_cache()
    except: st.error("⚠️ Clear Failed.")

@st.cache_data(ttl=600)
def get_notice():
    try: return sh.worksheet("notice").acell("A1").value or ""
    except: return ""

def publish_notice(text):
    try: ws = sh.worksheet("notice")
    except: ws = sh.add_worksheet(title="notice", rows=10, cols=10)
    ws.update_acell("A1", text); clear_sheet_cache()

def get_local_csv(file): return pd.read_csv(file) if os.path.exists(file) else pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_secure_image_bytes(file_id):
    try:
        r = get_drive_session().get(f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media")
        return r.content if r.status_code == 200 else None
    except: return None

def get_secure_photo_uri(url):
    fb = "https://www.w3schools.com/howto/img_avatar.png"
    if pd.isna(url) or url == "" or not isinstance(url, str): return fb
    match = re.search(r"(?:id=|/d/)([\w-]+)", url)
    if match:
        b = fetch_secure_image_bytes(match.group(1))
        if b: return f"data:image/jpeg;base64,{base64.b64encode(b).decode()}"
    return url if url.startswith("http") else fb

utc_now = datetime.now(timezone.utc)
now = utc_now + timedelta(hours=5, minutes=30)
curr_date_str, curr_time = now.strftime("%d-%m-%Y"), now.time()

def parse_time_safe(t_str):
    for fmt in ('%H:%M', '%I:%M %p', '%H:%M:%S'):
        try: return datetime.strptime(str(t_str).strip(), fmt).time()
        except: continue
    return None

def render_header():
    if os.path.exists("logo.png"):
        with open("logo.png", "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        st.markdown(f"""
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #e0e0e0; padding-bottom: 15px; margin-bottom: 20px;">
            <img src="data:image/png;base64,{img_b64}" style="max-width: 80px; max-height: 80px; object-fit: contain;">
            <div style="text-align: right;">
                <h2 class="header-school-name" style="margin: 0; color: #007bff; font-weight: 900; font-size: 24px; line-height: 1.1;">BHAGYABANTAPUR</h2>
                <h2 class="header-school-name" style="margin: 0; color: #007bff; font-weight: 900; font-size: 20px; line-height: 1.1;">PRIMARY SCHOOL</h2>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="border-bottom: 2px solid #e0e0e0; padding-bottom: 15px; margin-bottom: 20px; text-align: center;">
            <h2 style="margin: 0; color: #007bff; font-weight: 900; font-size: 24px;">BHAGYABANTAPUR PRIMARY SCHOOL</h2>
        </div>
        """, unsafe_allow_html=True)

render_header()

if not st.session_state.authenticated:
    inject_security_css("BPS DIGITAL") 

    pn = get_notice()
    if pn.strip(): st.info(f"📢 NOTICE: {pn}")

    st.markdown("<div class='login-box'><h3>🔐 Staff Login</h3><p>Please enter your Username & Password.</p></div>", unsafe_allow_html=True)
    with st.form("login_form"):
        ui = st.text_input("Username", key="ui").lower().strip()
        pi = st.text_input("Password", type="password", key="pi")
        if st.form_submit_button("Login"):
            if ui in USERS and pi == USERS[ui]["password"]:
                st.session_state.update(authenticated=True, user_role=USERS[ui]["role"], user_name=USERS[ui]["name"])
                st.rerun()
            else: st.error("❌ Incorrect Credentials")
    
    with st.expander("📅 View Holiday List (Public)"):
        hd = get_local_csv('holidays.csv')
        if not hd.empty: st.table(hd)
        else: st.info("No data.")

    with st.expander("✨ What's New in BPS Digital?"):
        st.markdown("""
        **Recent Updates & Upgrades:**
        * **🏫 Admin MDM Portal:** Head Teacher can now scan late/missed students directly.
        * **📱 Enhanced Mobile View:** Horizontal side-by-side profile cards.
        * **🔊 Audio Feedback:** Instant "beep" when checking boxes.
        * **📸 Instant Scanning:** Checkboxes visibly tick the exact millisecond a QR code is read.
        * **📌 Live Floating Counter:** A sticky badge tracks your counts.
        * **⚡ Anti-Crash Engine:** Upgraded Cloud connectivity.
        """)
else:
    inject_security_css(st.session_state.user_name)
    st.success(f"👋 Welcome, {st.session_state.user_name}")
    if st.button("Log Out"): st.session_state.authenticated = False; st.rerun()

    if st.session_state.user_role == "teacher":
        t_name_select = st.session_state.user_name
        hd = get_local_csv('holidays.csv')
        is_h = not hd[hd['Date'] == curr_date_str].empty if not hd.empty else False
        
        if is_h or now.strftime('%A') == 'Sunday': st.warning("🏖️ School is closed today.")
        else:
            nt = get_notice()
            if nt.strip(): st.info(f"📢 NOTICE: {nt}")
            at_tabs = st.tabs(["🍱 MDM Entry", "⏳ Routine", "📃 Leave Status", "📅 Holidays"])

            with at_tabs[0]: 
                ml = fetch_sheet_data('mdm_log')
                already_sub = False
                if not ml.empty and 'Date' in ml.columns and 'Teacher' in ml.columns:
                    if not ml[(ml['Date'].astype(str).str.strip() == curr_date_str) & (ml['Teacher'].astype(str).str.strip() == t_name_select)].empty:
                        already_sub = True

                if already_sub: 
                    st.success("✅ MDM Submitted for today.")
                    st.info("💡 **Note:** If any student was missed during this submission, please send them to Head Sir to complete their MDM Entry.")
                else:
                    st.subheader("Student MDM Entry")
                    rout = get_local_csv('routine.csv')
                    mc = TEACHER_INITIALS.get(t_name_select, t_name_select)
                    tdy = now.strftime('%A')
                    tc, ts, is_sub, ab_t = None, None, False, ""

                    ll = fetch_sheet_data('teacher_leave')
                    if not ll.empty and 'Date' in ll.columns:
                        for _, r in ll[ll['Date'] == curr_date_str].iterrows():
                            lg = str(r.get('Detailed_Sub_Log', ''))
                            if f"11:15: {t_name_select}" in lg or f"11:15 AM: {t_name_select}" in lg:
                                is_sub = True; ab_t = r['Teacher']
                                ac = TEACHER_INITIALS.get(ab_t, "")
                                ar = rout[(rout['Teacher'] == ac) & (rout['Day'] == tdy)].copy()
                                ar['Start_Obj'] = ar['Start_Time'].apply(parse_time_safe)
                                match = ar[ar['Start_Obj'] == time(11, 15)]
                                if not match.empty: tc, ts = match.iloc[0]['Class'], match.iloc[0].get('Section', 'A')
                                break
                    if not tc:
                        ms = rout[(rout['Teacher'] == mc) & (rout['Day'] == tdy)].copy() if not rout.empty else pd.DataFrame()
                        if not ms.empty:
                            ms['Start_Obj'] = ms['Start_Time'].apply(parse_time_safe)
                            tr = ms[ms['Start_Obj'] == time(11, 15)]
                            if not tr.empty: tc, ts = tr.iloc[0]['Class'], tr.iloc[0].get('Section', 'A')

                    if tc:
                        if is_sub: st.info(f"🔄 **SUB:** Covering for **{ab_t}** ({tc} - {ts})")
                        else: st.info(f"📌 Assigned **11:15 AM** class: **{tc} - {ts}**")
                        sm = fetch_sheet_data('students_master')

                        if not sm.empty:
                            if 'Section' not in sm.columns: sm['Section'] = 'A'
                            if tc == 'CLASS PP': ros = sm[(sm['Class'].isin(['CLASS PP', 'CLASS LPP'])) & (sm['Section'] == ts)].copy()
                            else: ros = sm[(sm['Class'] == tc) & (sm['Section'] == ts)].copy()
                            
                            if not ros.empty:
                                if 'scanned_keys' not in st.session_state: st.session_state.scanned_keys = []
                                
                                st.write("📸 **Scan ID Cards (or tick manually below):**")
                                qv = qrcode_scanner(key='at_qr')
                                
                                if st.session_state.scan_msg:
                                    st.success(st.session_state.scan_msg)
                                    st.session_state.scan_msg = None

                                if qv:
                                    should_rerun = False
                                    try:
                                        qd = {p.split(':')[0].strip(): p.split(':')[1].strip() for p in qv.split('|') if ':' in p}
                                        sr, sn = str(qd.get('Roll', '')), str(qd.get('Name', ''))
                                        if sr and sn:
                                            match_df = ros[(ros['Roll'].astype(str).str.strip() == sr) & (ros['Name'].astype(str).str.strip() == sn)]
                                            if not match_df.empty:
                                                ar, an = match_df.iloc[0]['Roll'], match_df.iloc[0]['Name']
                                                sk = f"{ar}_{an}"
                                                if sk not in st.session_state.scanned_keys: 
                                                    st.session_state.scanned_keys.append(sk)
                                                    st.session_state[f"mdm_{ar}_{an}"] = True 
                                                    st.session_state.scan_msg = f"✅ Scanned Successfully: {an}"
                                                    should_rerun = True
                                            else: st.error(f"❌ MISMATCH: {sn} is NOT in {tc} {ts}!")
                                    except Exception: st.warning("⚠️ Invalid ID Card.")
                                    if should_rerun: st.rerun()

                                ros['Scan_Key'] = ros['Roll'].astype(str) + "_" + ros['Name'].astype(str)
                                if 'Thumb_URL' not in ros.columns: ros['Thumb_URL'] = ""
                                with st.spinner("Loading profiles..."):
                                    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as exe: ros['Photo'] = list(exe.map(get_secure_photo_uri, ros['Thumb_URL'].tolist()))

                                st.markdown("### Roster Selection")
                                cp = st.empty()
                                st.markdown('<div class="roster-container">', unsafe_allow_html=True)
                                sel_mdm = []
                                for _, r in ros.iterrows():
                                    c1, c2, c3 = st.columns([1, 4, 2])
                                    with c1: st.image(r['Photo'], width=85) 
                                    with c2: st.markdown(f"<div style='line-height:1.2; font-size:14px; margin-top:2px;'><b>{r['Name']}</b><br><span style='font-size:12px; color:gray;'>Roll: {r['Roll']} | {r['Class']}</span></div>", unsafe_allow_html=True)
                                    with c3:
                                        isc = r['Scan_Key'] in st.session_state.scanned_keys
                                        if st.checkbox("Ate MDM", value=isc, key=f"mdm_{r['Roll']}_{r['Name']}"): sel_mdm.append(r)
                                    st.divider()
                                
                                cp.markdown(f"<div class='floating-counter'>✅ Selected: {len(sel_mdm)}</div>", unsafe_allow_html=True)
                                st.markdown(f"<h3 style='text-align:center;'>✅ Total Selected: {len(sel_mdm)}</h3>", unsafe_allow_html=True)
                                if st.button("Submit MDM Data"):
                                    if sel_mdm:
                                        nr = [{'Date': curr_date_str, 'Teacher': t_name_select, 'Class': x['Class'], 'Section': ts, 'Roll': x['Roll'], 'Name': x['Name'], 'Time': now.strftime("%H:%M")} for x in sel_mdm]
                                        append_sheet_df('mdm_log', pd.DataFrame(nr))
                                        st.session_state.scanned_keys = []; st.success(f"Submitted {len(nr)} to Cloud DB!"); st.rerun()
                                    else: st.warning("No students selected.")
                                st.markdown('</div>', unsafe_allow_html=True)
                                
                                att = fetch_sheet_data('student_attendance_master')
                                if not att.empty and 'Date' in att.columns:
                                    ta = att[(att['Date'].astype(str) == curr_date_str) & (att['Class'].isin(['CLASS PP', 'CLASS LPP']) if tc == 'CLASS PP' else att['Class'] == tc) & (att['Section'] == ts) & (att['Status'] == True)]
                                    if not ta.empty: st.markdown(f"<div class='att-badge att-done'>✅ Attendance: {len(ta)}</div>", unsafe_allow_html=True)
                                    else: st.markdown("<div class='att-badge att-wait'>⏳ Attendance: Wait</div>", unsafe_allow_html=True)
                            else: st.warning("No students found.")
                    else: st.warning("⚠️ No class at 11:15 AM. MDM Entry disabled.")

            with at_tabs[1]:
                st.subheader("Live Class Status")
                ll = fetch_sheet_data('teacher_leave')
                rout = get_local_csv('routine.csv')
                ol, ld = False, None
                if not ll.empty and 'Date' in ll.columns:
                    mtl = ll[(ll['Date'] == curr_date_str) & (ll['Teacher'] == t_name_select)]
                    if not mtl.empty: ol, ld = True, mtl.iloc[0]
                
                if ol:
                    st.warning(f"🏖️ You are marked **{ld['Type']}** today.")
                    rs = str(ld.get('Detailed_Sub_Log', ''))
                    if rs and rs != "None":
                        st.markdown("### 🤝 Substitution Plan")
                        for a in rs.split(" | "):
                            p = a.split(": ")
                            if len(p) == 2: st.markdown(f"<div class='sub-card'><b>{p[0].strip()}</b> covered by <b>{p[1].strip()}</b></div>", unsafe_allow_html=True)
                    else: st.info("No specific substitutes assigned yet.")
                else:
                    mc = TEACHER_INITIALS.get(t_name_select, t_name_select)
                    tdy = now.strftime('%A')
                    ms = rout[(rout['Teacher'] == mc) & (rout['Day'] == tdy)].copy() if not rout.empty else pd.DataFrame()
                    if not ms.empty: ms['Is_Sub'] = False
                    sd = []
                    if not ll.empty:
                        for _, r in ll[ll['Date'] == curr_date_str].iterrows():
                            if t_name_select in str(r['Detailed_Sub_Log']):
                                ac = TEACHER_INITIALS.get(r['Teacher'], "")
                                for a in str(r['Detailed_Sub_Log']).split(" | "):
                                    if f": {t_name_select}" in a:
                                        slt = a.split(": ")[0].strip()
                                        oc = rout[(rout['Teacher'] == ac) & (rout['Day'] == tdy) & (rout['Start_Time'] == slt)]
                                        if not oc.empty:
                                            rx = oc.iloc[0]
                                            sd.append({'Start_Time': rx['Start_Time'], 'End_Time': rx['End_Time'], 'Class': rx['Class'], 'Section': rx.get('Section', 'A'), 'Subject': f"🔄 Sub for {r['Teacher']}", 'Teacher': mc, 'Day': tdy, 'Is_Sub': True})
                    
                    if sd: ms = pd.concat([ms, pd.DataFrame(sd)], ignore_index=True)
                    if not ms.empty:
                        ms['Start_Obj'] = ms['Start_Time'].apply(parse_time_safe)
                        ms = ms.dropna(subset=['Start_Obj']).sort_values('Start_Obj')
                        cc = None
                        for _, r in ms.iterrows():
                            st_time, et = r['Start_Obj'], parse_time_safe(r['End_Time'])
                            if st_time and et and st_time <= curr_time <= et: cc = r; break
                        if cc is not None:
                            sty = "border-left: 5px solid #ffc107; background-color:#fff3cd;" if cc['Is_Sub'] else "border-left: 5px solid #28a745;"
                            px = "🔄 SUB: " if cc['Is_Sub'] else "🔴 NOW: "
                            st.markdown(f"""<div class="routine-card" style="{sty}"><h3 style="margin:0; color:#333;">{px}{cc['Class']} - {cc.get('Section','')}</h3><p>{cc['Subject']}</p><p style="color:gray;">Ends {cc['End_Time']}</p></div>""", unsafe_allow_html=True)
                        else: st.info("☕ No class ongoing.")
                        st.divider()
                        def hls(row): return ['background-color: #fff3cd'] * len(row) if str(row['Subject']).startswith('🔄') else [''] * len(row)
                        st.dataframe(ms[['Start_Time', 'End_Time', 'Class', 'Section', 'Subject']].style.apply(hls, axis=1), hide_index=True)
                    else: st.info("No classes today.")

            with at_tabs[2]:
                st.subheader("My Leave Record")
                ll = fetch_sheet_data('teacher_leave')
                if not ll.empty and 'Teacher' in ll.columns:
                    ml = ll[ll['Teacher'] == t_name_select]
                    c1, c2, c3 = st.columns(3)
                    c1.metric("CL Remaining", f"{14 - len(ml[ml['Type'] == 'CL'])}")
                    c2.metric("SL Taken", f"{len(ml[ml['Type'] == 'SL'])}")
                    c3.metric("Commuted", f"{len(ml[ml['Type'] == 'Commuted Leave'])}")
                    st.dataframe(ml[~ml['Type'].isin(['Half Day', 'On Duty'])][['Date', 'Type', 'Substitute']], hide_index=True)

            with at_tabs[3]:
                st.subheader("🗓️ School Holiday List")
                hd = get_local_csv('holidays.csv')
                if not hd.empty: st.table(hd)
                else: st.info("No holiday data available.")

    elif st.session_state.user_role == "admin":
        tabs = st.tabs(["📊 Summary", "🍱 MDM Entry", "📝 Attend", "⏳ Live", "👨‍🏫 Leave", "📢 Staff Notice", "📅 Hols"])
        
        with tabs[0]: 
            st.subheader(f"MDM Status: {curr_date_str}")
            ml = fetch_sheet_data('mdm_log')
            al = fetch_sheet_data('student_attendance_master') 
            c1, c2 = st.columns([2, 1])
            vd = c1.date_input("Select Date", datetime.now()).strftime("%d-%m-%Y")
            sa = c2.checkbox("Show All")
            fm = ml if sa else ml[ml['Date'].astype(str) == vd].copy() if not ml.empty else pd.DataFrame()
            fa = al[al['Status'] == True] if sa else al[(al['Date'].astype(str) == vd) & (al['Status'] == True)].copy() if not al.empty else pd.DataFrame()
            cf = "All"
            if not fm.empty or not fa.empty:
                mc = fm.groupby(['Class', 'Section']).size().reset_index(name='MDM Entry') if not fm.empty else pd.DataFrame(columns=['Class', 'Section', 'MDM Entry'])
                ac = fa.groupby(['Class', 'Section']).size().reset_index(name='Attendance') if not fa.empty else pd.DataFrame(columns=['Class', 'Section', 'Attendance'])
                sd = pd.merge(ac, mc, on=['Class', 'Section'], how='outer').fillna(0).infer_objects(copy=False)
                sd['Attendance'], sd['MDM Entry'] = sd['Attendance'].astype(int), sd['MDM Entry'].astype(int)
                sd.sort_values(by=['Class', 'Section'], inplace=True)
                if not sd.empty: sd = pd.concat([sd, pd.DataFrame([{'Class': 'TOTAL', 'Section': '', 'Attendance': sd['Attendance'].sum(), 'MDM Entry': sd['MDM Entry'].sum()}])], ignore_index=True)
                st.markdown(f"##### 🏫 Breakdown for {vd if not sa else 'All Time'}")
                st.dataframe(sd, hide_index=True, use_container_width=True)
                st.markdown("##### 📄 Detailed List")
                if not fm.empty:
                    fm['Class_Sec'] = fm['Class'].astype(str) + " " + fm['Section'].astype(str)
                    cf = st.selectbox("Filter Class", ["All"] + sorted(fm['Class_Sec'].unique()))
                    ddf = fm[fm['Class_Sec'] == cf] if cf != "All" else fm
                    st.dataframe(ddf[['Date', 'Class', 'Section', 'Roll', 'Name']], hide_index=True)
            else: st.info("No data available for this date.")
            st.divider()
            if st.button(f"🗑️ Clear Data ({cf})"):
                tm = fetch_sheet_data('mdm_log')
                if not tm.empty:
                    if cf == "All": tm = tm[tm['Date'].astype(str) != curr_date_str]
                    else: tm = tm[~((tm['Date'].astype(str) == curr_date_str) & ((tm['Class'].astype(str) + " " + tm['Section'].astype(str)) == cf))]
                    overwrite_sheet_df('mdm_log', tm); st.success("Cleared!"); st.rerun()

        with tabs[1]:
            st.subheader("Admin MDM Entry (Late/Missed)")
            sc_mdm = st.selectbox("Mark MDM for Class", ATTENDANCE_OPTIONS, key='adm_mdm_sel')
            if sc_mdm != "Select Class...":
                tc, ts = sc_mdm.rsplit(' ', 1)
                sm = fetch_sheet_data('students_master')
                ml = fetch_sheet_data('mdm_log')
                if not sm.empty:
                    if 'Section' not in sm.columns: sm['Section'] = 'A'
                    if tc == 'CLASS PP': ros = sm[(sm['Class'].isin(['CLASS PP', 'CLASS LPP'])) & (sm['Section'] == ts)].copy()
                    else: ros = sm[(sm['Class'] == tc) & (sm['Section'] == ts)].copy()
                    
                    if not ros.empty:
                        me = ml[(ml['Date'].astype(str) == curr_date_str) & (ml['Class'].isin(['CLASS PP', 'CLASS LPP']) if tc == 'CLASS PP' else ml['Class'] == tc) & (ml['Section'] == ts)]['Roll'].astype(str).tolist() if not ml.empty else []
                        ros['MDM (Ate)'] = ros['Roll'].astype(str).isin(me)
                        
                        st.write("📸 **Scan Missed ID Cards (or tick manually below):**")
                        qv = qrcode_scanner(key='adm_mdm_qr')
                        
                        if st.session_state.admin_scan_msg:
                            st.success(st.session_state.admin_scan_msg)
                            st.session_state.admin_scan_msg = None
                            
                        if qv:
                            should_rerun = False
                            try:
                                qd = {p.split(':')[0].strip(): p.split(':')[1].strip() for p in qv.split('|') if ':' in p}
                                sr, sn = str(qd.get('Roll', '')), str(qd.get('Name', ''))
                                if sr and sn:
                                    match_df = ros[(ros['Roll'].astype(str).str.strip() == sr) & (ros['Name'].astype(str).str.strip() == sn)]
                                    if not match_df.empty:
                                        ar, an = match_df.iloc[0]['Roll'], match_df.iloc[0]['Name']
                                        if str(ar) in me:
                                            st.warning(f"⚠️ {an} is already marked for MDM today!")
                                        else:
                                            sk = f"{ar}_{an}"
                                            if sk not in st.session_state.admin_scanned_keys: 
                                                st.session_state.admin_scanned_keys.append(sk)
                                                st.session_state[f"adm_mdm_{ar}_{an}"] = True 
                                                st.session_state.admin_scan_msg = f"✅ Scanned Successfully: {an}"
                                                should_rerun = True
                                    else: st.error(f"❌ MISMATCH: {sn} is NOT in {tc} {ts}!")
                            except Exception: st.warning("⚠️ Invalid ID Card.")
                            if should_rerun: st.rerun()

                        ros['Scan_Key'] = ros['Roll'].astype(str) + "_" + ros['Name'].astype(str)
                        if 'Thumb_URL' not in ros.columns: ros['Thumb_URL'] = ""
                        with st.spinner("Loading profiles..."):
                            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as exe: ros['Photo'] = list(exe.map(get_secure_photo_uri, ros['Thumb_URL'].tolist()))

                        st.markdown("### Roster Selection")
                        cp = st.empty()
                        st.markdown('<div class="roster-container">', unsafe_allow_html=True)
                        sel_mdm, alc = [], 0
                        for _, r in ros.iterrows():
                            c1, c2, c3 = st.columns([1, 4, 2])
                            with c1: st.image(r['Photo'], width=85) 
                            with c2: st.markdown(f"<div style='line-height:1.2; font-size:14px; margin-top:2px;'><b>{r['Name']}</b><br><span style='font-size:12px; color:gray;'>Roll: {r['Roll']} | {r['Class']}</span></div>", unsafe_allow_html=True)
                            with c3:
                                if r['MDM (Ate)']:
                                    st.markdown("<span style='color:#28a745; font-weight:bold;'>✅ Done</span>", unsafe_allow_html=True)
                                    alc += 1
                                else:
                                    isc = r['Scan_Key'] in st.session_state.admin_scanned_keys
                                    if st.checkbox("Ate MDM", value=isc, key=f"adm_mdm_{r['Roll']}_{r['Name']}"): sel_mdm.append(r)
                            st.divider()
                        
                        cp.markdown(f"<div class='floating-counter'>✅ Selected: {len(sel_mdm)} | Done: {alc}</div>", unsafe_allow_html=True)
                        st.markdown(f"<h3 style='text-align:center;'>✅ New Selected: {len(sel_mdm)}</h3>", unsafe_allow_html=True)
                        if st.button("Submit Admin MDM Data"):
                            if sel_mdm:
                                nr = [{'Date': curr_date_str, 'Teacher': f"{st.session_state.user_name} (Admin)", 'Class': x['Class'], 'Section': ts, 'Roll': x['Roll'], 'Name': x['Name'], 'Time': now.strftime("%H:%M")} for x in sel_mdm]
                                append_sheet_df('mdm_log', pd.DataFrame(nr))
                                st.session_state.admin_scanned_keys = []; st.success(f"Added {len(nr)} late entries to Cloud DB!"); st.rerun()
                            else: st.warning("No new students selected.")
                        st.markdown('</div>', unsafe_allow_html=True)
                    else: st.warning("No students found.")

        with tabs[2]:
            st.subheader("Student Attendance")
            sc = st.selectbox("Mark Attendance", ATTENDANCE_OPTIONS, key='ht_att')
            if sc != "Select Class...":
                tc, ts = sc.rsplit(' ', 1)
                sm = fetch_sheet_data('students_master')
                ml = fetch_sheet_data('mdm_log')
                if not sm.empty:
                    if 'Section' not in sm.columns: sm['Section'] = 'A'
                    if tc == 'CLASS PP': ros = sm[(sm['Class'].isin(['CLASS PP', 'CLASS LPP'])) & (sm['Section'] == ts)].copy()
                    else: ros = sm[(sm['Class'] == tc) & (sm['Section'] == ts)].copy()
                    
                    if not ros.empty:
                        me = ml[(ml['Date'].astype(str) == curr_date_str) & (ml['Class'].isin(['CLASS PP', 'CLASS LPP']) if tc == 'CLASS PP' else ml['Class'] == tc) & (ml['Section'] == ts)]['Roll'].astype(str).tolist() if not ml.empty else []
                        ros['MDM (Ate)'] = ros['Roll'].astype(str).isin(me)
                        if 'Thumb_URL' not in ros.columns: ros['Thumb_URL'] = ""
                        with st.spinner("Loading profiles..."):
                            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as exe: ros['Photo'] = list(exe.map(get_secure_photo_uri, ros['Thumb_URL'].tolist()))
                        st.markdown("### Class Roster")
                        cp = st.empty()
                        st.markdown('<div class="roster-container">', unsafe_allow_html=True)
                        ad, pc = [], 0
                        for _, r in ros.iterrows():
                            c1, c2, c3 = st.columns([1, 4, 2.5])
                            with c1: st.image(r['Photo'], width=85) 
                            with c2: st.markdown(f"<div style='line-height:1.2; font-size:14px; margin-top:2px;'><b>{r['Name']}</b><br><span style='font-size:12px; color:gray;'>Roll: {r['Roll']} | {r['Class']}</span></div>", unsafe_allow_html=True)
                            with c3:
                                ip = st.checkbox("Present", value=True, key=f"att_{r['Roll']}_{r['Name']}")
                                if ip: pc += 1
                                st.checkbox("MDM Entry", value=bool(r['MDM (Ate)']), disabled=True, key=f"mdm_ro_{r['Roll']}_{r['Name']}")
                                ad.append({'Date': curr_date_str, 'Class': r['Class'], 'Section': ts, 'Roll': r['Roll'], 'Name': r['Name'], 'Status': ip})
                            st.divider()
                        cp.markdown(f"<div class='floating-counter'>✅ Present: {pc}</div>", unsafe_allow_html=True)
                        st.markdown(f"<h3 style='text-align:center;'>✅ Total Present: {pc}</h3>", unsafe_allow_html=True)
                        if st.button(f"Save Attendance"):
                            append_sheet_df('student_attendance_master', pd.DataFrame(ad)); st.success("Saved."); st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)

                        ac = fetch_sheet_data('student_attendance_master')
                        is_sub = not ac[(ac['Date'].astype(str) == curr_date_str) & (ac['Class'].isin(['CLASS PP', 'CLASS LPP']) if tc == 'CLASS PP' else ac['Class'] == tc) & (ac['Section'] == ts)].empty if not ac.empty else False
                        if is_sub:
                            st.info(f"🔒 Attendance is submitted.")
                            if st.button("🗑️ Clear Today's Attendance"):
                                ta = ac[~((ac['Date'].astype(str) == curr_date_str) & (ac['Class'].isin(['CLASS PP', 'CLASS LPP']) if tc == 'CLASS PP' else ac['Class'] == tc) & (ac['Section'] == ts))]
                                overwrite_sheet_df('student_attendance_master', ta); st.rerun()

            st.divider()
            st.subheader("📊 Daily Report")
            al = fetch_sheet_data('student_attendance_master')
            avd = st.date_input("Report Date", datetime.now(), key="att_d").strftime("%d-%m-%Y")
            if not al.empty:
                ta = al[(al['Date'].astype(str) == avd) & (al['Status'] == True)]
                if not ta.empty:
                    p = len(ta[ta['Class'].isin(['CLASS PP', 'CLASS LPP'])])
                    i4 = len(ta[ta['Class'].isin(['CLASS I', 'CLASS II', 'CLASS III', 'CLASS IV'])])
                    v = len(ta[ta['Class'] == 'CLASS V'])
                    st.markdown(f"<table class='report-table'><tr><th>Class PP</th><th>I-IV</th><th>Class V</th><th>TOTAL</th></tr><tr><td>{p}</td><td>{i4}</td><td>{v}</td><td><b>{p+i4+v}</b></td></tr></table>", unsafe_allow_html=True)
                else: st.info(f"No attendance for {avd}.")

        with tabs[3]: 
            st.subheader(f"🏫 Routine Status")
            rout = get_local_csv('routine.csv')
            tdy = now.strftime('%A')
            if not rout.empty:
                tr = rout[rout['Day'] == tdy].copy()
                ll = fetch_sheet_data('teacher_leave')
                if not ll.empty and 'Date' in ll.columns:
                    for _, r in ll[ll['Date'].astype(str) == curr_date_str].iterrows():
                        ac = TEACHER_INITIALS.get(r['Teacher'], r['Teacher'])
                        for a in str(r.get('Detailed_Sub_Log', '')).split(" | "):
                            if ": " in a:
                                slt, sub = a.split(": ")
                                tr.loc[(tr['Teacher'] == ac) & (tr['Start_Time'].str.strip() == slt.strip()), 'Teacher'] = f"{TEACHER_INITIALS.get(sub.strip(), sub.strip())} (Sub)"
                tr['Start_Obj'] = tr['Start_Time'].apply(parse_time_safe)
                tr['End_Obj'] = tr['End_Time'].apply(parse_time_safe)
                tr = tr.dropna(subset=['Start_Obj', 'End_Obj']).sort_values('Start_Obj')
                lc = [r for _, r in tr.iterrows() if r['Start_Obj'] <= curr_time <= r['End_Obj']]
                st.markdown("### 🔴 LIVE NOW")
                if lc:
                    cls = st.columns(2)
                    for i, r in enumerate(lc):
                        is_sub = "(Sub)" in r['Teacher']
                        tn = f"🔄 {INV_TEACHER_INITIALS.get(r['Teacher'].replace(' (Sub)', ''), r['Teacher'])} (Sub)" if is_sub else f"👨‍🏫 {INV_TEACHER_INITIALS.get(r['Teacher'], r['Teacher'])}"
                        cls[i%2].markdown(f"<div class='routine-card' style='border-left: 5px solid {'#ffc107' if is_sub else '#dc3545'};'><h4 style='margin:0;'>{r['Class']} {r.get('Section', '')}</h4><p style='margin:0; font-weight:bold;'>{tn}</p><p style='margin:0; font-size:12px; color:gray;'>{r['Subject']} | Ends: {r['End_Time']}</p></div>", unsafe_allow_html=True)
                else: st.info("☕ No classes ongoing.")
                st.dataframe(tr[['Start_Time', 'End_Time', 'Class', 'Subject', 'Teacher']], hide_index=True)

        with tabs[4]: 
            st.subheader("Substitution Manager")
            abt = st.selectbox("Absent Teacher", ["Select..."] + TEACHER_LIST)
            if abt != "Select...":
                lt = st.selectbox("Leave Type", ["CL", "SL", "Commuted Leave", "Half Day", "On Duty"])
                ism = st.checkbox("Mark for Multiple Days?", value=True) if lt == "Commuted Leave" else False
                if ism:
                    c1, c2 = st.columns(2)
                    sd = c1.date_input("Start Date", datetime.now())
                    ed = c2.date_input("End Date", sd)
                    if st.button(f"Save {lt} (Multi-Day)"):
                        if (ed - sd).days < 0: st.error("❌ End Date cannot be before Start Date!")
                        else:
                            ll = fetch_sheet_data('teacher_leave')
                            nl = []
                            for i in range((ed - sd).days + 1):
                                ds = (sd + timedelta(days=i)).strftime("%d-%m-%Y")
                                if ll.empty or ll[(ll['Date'].astype(str) == ds) & (ll['Teacher'] == abt)].empty:
                                    nl.append({"Date": ds, "Teacher": abt, "Type": lt, "Substitute": "None", "Detailed_Sub_Log": "None"})
                            if nl: append_sheet_df('teacher_leave', pd.DataFrame(nl)); st.success("✅ Saved!"); st.rerun()
                            else: st.warning("Already recorded.")
                else:
                    sds = st.date_input("Date", datetime.now()).strftime("%d-%m-%Y")
                    tdy = datetime.strptime(sds, "%d-%m-%Y").strftime('%A')
                    rout = get_local_csv('routine.csv')
                    tc = TEACHER_INITIALS.get(abt, abt)
                    ms = rout[(rout['Teacher'] == tc) & (rout['Day'] == tdy)].copy() if not rout.empty else pd.DataFrame()
                    ll = fetch_sheet_data('teacher_leave')
                    el = ll[(ll['Date'].astype(str) == sds) & (ll['Teacher'] == abt)] if not ll.empty else pd.DataFrame()
                    if not el.empty:
                        st.success(f"✅ Leave Submitted: **{abt}** on **{sds}**.")
                        if st.button("🗑️ Undo"): overwrite_sheet_df('teacher_leave', ll.drop(el.index)); st.rerun()
                    else:
                        bs = {}
                        if not ll.empty:
                            for _, r in ll[ll['Date'].astype(str) == sds].iterrows():
                                for a in str(r.get('Detailed_Sub_Log', '')).split(" | "):
                                    if ": " in a: slot, sub = a.split(": "); bs.setdefault(slot, []).append(sub.strip())
                        if not ms.empty:
                            assigns = []
                            for idx, r in ms.iterrows():
                                slot = str(r['Start_Time']).strip()
                                bc = rout[(rout['Day'] == tdy) & (rout['Start_Time'] == slot)]['Teacher'].tolist() if not rout.empty else []
                                fo, bo = [], []
                                for tn in TEACHER_LIST:
                                    if tn == abt: continue 
                                    tc2 = TEACHER_INITIALS.get(tn, "")
                                    if slot in bs and tn in bs[slot]: bo.append(f"⛔ {tn} (Already Subbing)")
                                    elif tc2 not in bc: fo.append(f"✅ {tn} (Free)")
                                    else: bo.append(f"⚠️ {tn} (Busy)")
                                st.markdown(f"<div class='routine-card'><b>{slot}</b> | {r['Class']}</div>", unsafe_allow_html=True)
                                ch = st.selectbox(f"Sub for {slot}", ["Select..."] + fo + bo, key=f"s_{idx}")
                                if ch != "Select...": assigns.append(f"{slot}: {ch.split(' (')[0][2:]}")
                            if st.button("Confirm"): append_sheet_df('teacher_leave', pd.DataFrame([{"Date": sds, "Teacher": abt, "Type": lt, "Substitute": "Multiple", "Detailed_Sub_Log": " | ".join(assigns)}])); st.rerun()
                        else:
                            st.info("No classes scheduled.")
                            if st.button("Mark Leave"): append_sheet_df('teacher_leave', pd.DataFrame([{"Date": sds, "Teacher": abt, "Type": lt, "Substitute": "None", "Detailed_Sub_Log": "None"}])); st.rerun()

        with tabs[5]: 
            st.subheader("📢 Staff Notice")
            n = st.text_area("Notice", get_notice())
            if st.button("Publish to Cloud"): publish_notice(n); st.success("Published!")

        with tabs[6]: 
            st.subheader("🗓️ School Holiday List")
            hd = get_local_csv('holidays.csv')
            if not hd.empty: st.data_editor(hd, num_rows="dynamic", key="h_edit")
            else: st.info("No data.")
