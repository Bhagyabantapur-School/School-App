import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import pytz
import time

st.set_page_config(page_title="Speech Mastery", page_icon="🎙️", layout="centered")

GS_FORMULA = '=IF(INDIRECT("C"&ROW())="RUNNING", "RUNNING", IFERROR(TEXT(MOD(INDIRECT("C"&ROW())-INDIRECT("B"&ROW()), 1), "h:mm"), ""))'

st.markdown("""
    <style>
    div[data-testid="stCheckbox"] label { font-size: 16px !important; }
    .stProgress > div > div > div > div { background-color: #ff4b4b; }
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

def log_session_to_sheet(notes="Completed 1-Hour Training Framework"):
    try:
        conn = init_connection()
        sheet = conn.open("MY ROUTINE 2026").worksheet("activity_log")
        
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        start_time = (now - timedelta(hours=1)).strftime('%H:%M')
        end_time = now.strftime('%H:%M')
        today_str = now.strftime('%Y-%m-%d')
        
        row_data = [
            today_str, 
            start_time, 
            end_time, 
            GS_FORMULA, 
            "WORK", 
            "1-Min Independence Day Speech Prep", 
            "Phases 1-4 Completed", 
            notes, 
            "Head Teacher (BPS)", 
            "TRUE", 
            "TRUE", 
            "8" 
        ]
        
        sheet.append_row(row_data, value_input_option="USER_ENTERED")
        return True
    except Exception as e:
        st.error(f"Failed to log: {e}")
        return False

# ==========================================
# UI Layout
# ==========================================
st.title("🎙️ Aug 15 Speech Mastery")
st.markdown("**Bhagyabantapur Primary School - 1-Minute Delivery Protocol**")

tab_train, tab_event, tab_stage = st.tabs(["⏳ Daily 1-Hr Training", "🌅 Event Day (Aug 15)", "🧠 Stage Coping"])

with tab_train:
    st.markdown("### Daily 1-Hour Routine (Leading up to Aug 14)")
    st.progress(100)
    
    with st.expander("🧘‍♂️ 0-15 Mins: Mental Preparation & Visualization", expanded=True):
        st.markdown("""
        * **Breathing:** Channel your daily yoga and meditation practice into a focused 4-7-8 rhythm (Inhale 4s, Hold 7s, Exhale 8s).
        * **Visualization:** Mentally rehearse standing confidently on stage, projecting your voice, and ignoring the camera entirely to command the students' attention.
        """)
        c1 = st.checkbox("Mental Prep Completed", key="c1")

    with st.expander("🧩 15-30 Mins: Chunking & Keyword Memorization", expanded=True):
        st.markdown("""
        * **No Rote Memorization.** Focus purely on the three core thematic chunks:
            1. **Greetings & Context:** Welcoming everyone.
            2. **Honoring Martyrs:** The gravity of the historical sacrifices.
            3. **Pedagogical Message:** Holistic development and the students' oath.
        """)
        c2 = st.checkbox("Chunking Completed", key="c2")

    with st.expander("🗣️ 30-45 Mins: Delivery Mechanics", expanded=True):
        st.markdown("""
        * **Mirror Practice:** Focus on non-verbal communication.
        * **Voice Modulation:** Warmth for greetings, gravity for martyrs, enthusiasm for the oath.
        * **Eye Contact:** Maintain eye contact with an imaginary audience rather than staring at the camera lens.
        """)
        c3 = st.checkbox("Mechanics Completed", key="c3")

    with st.expander("🌪️ 45-60 Mins: Distraction-Proofing Simulation", expanded=True):
        st.markdown("""
        * **Setup:** Set up your Xiaomi 11X on a tripod to record yourself.
        * **Simulation:** Play audio of "noisy children" or "playground shouting" in the background. 
        * **Execution:** Deliver the 1-minute speech through the noise *without stopping*. Train the brain to maintain absolute focus during disruptions.
        """)
        c4 = st.checkbox("Simulation Completed", key="c4")
        
    st.markdown("---")
    training_notes = st.text_input("Session Notes (Optional)", placeholder="E.g., Nailed the transition to the student oath...")
    
    if st.button("💾 Log 1-Hour Session to Activity Log", type="primary", use_container_width=True, disabled=not (c1 and c2 and c3 and c4)):
        with st.spinner("Saving to Google Sheets..."):
            if log_session_to_sheet(training_notes if training_notes else "Completed full 4-phase daily training framework."):
                st.toast("✅ Training Logged Successfully!")
                time.sleep(1)
                st.rerun()

with tab_event:
    st.markdown("### Event Day Morning Routine (5:00 AM - 6:00 AM)")
    st.info("⚠️ **Rule:** Do not attempt any new memorization this morning.")
    
    st.markdown("""
    * **5:00 - 5:15 AM (Calm):** Hydration and 15 minutes of deep breathing. 
    * **5:15 - 5:30 AM (Warmup):** Read the speech aloud naturally in front of a mirror *only twice*. Do not force memory recall; just let the words flow.
    * **5:30 - 6:00 AM (Safety Net):** Create a small physical cue card.
    """)
    
    st.markdown("#### 📝 Your Cue Card Outline")
    st.markdown("""
    Write this in **LARGE TEXT** and keep it in your pocket. It is purely a psychological safety net to kill the fear of memory blanks.
    
    1. Welcome & Aug 15 Context
    2. Sacrifices of Martyrs
    3. True Independence = Holistic Growth
    4. The Students' Oath
    """)

with tab_stage:
    st.markdown("### Immediate Coping Strategies")
    
    st.error("🎥 **Camera Re-framing**")
    st.markdown("""
    Mentally re-categorize the camera as a **passive memory-recording tool** rather than an active evaluator. Shift your visual focus entirely to the familiar, welcoming faces of a few students in the front row.
    """)
    
    st.warning("⏸️ **The 2-Second Power Pause**")
    st.markdown("""
    If a memory blank strikes or the children become overwhelmingly loud:
    1. Deploy a deliberate **2 to 3-second silent pause**.
    2. Offer a **gentle smile**. 
    3. *Why it works:* The sudden silence naturally quiets the children out of curiosity. It buys you time to take a deep breath, access your mental keyword map, and seamlessly resume.
    """)
